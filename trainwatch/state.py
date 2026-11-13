"""Персистентное состояние в SQLite (один файл, переживает перезапуски).

watches      – отслеживаемые поезда (управляются из веб-интерфейса)
watch_state  – последний принятый снимок вагонов, известные номера, счётчики ошибок
checks       – история проверок (для графика свободных мест)
events       – лента событий: тревоги, отчёты, ошибки (для интерфейса)
outbox       – очередь сообщений в Telegram: при недоступности сети они не теряются
push_subs    – подписки браузеров на Web Push
settings     – настройки из интерфейса (JSON)

Все обращения — из одного потока asyncio-цикла.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import RuntimeSettings, WatchConfig
from .models import Car


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _dt(v: str | None) -> datetime | None:
    return datetime.fromisoformat(v) if v else None


@dataclass
class WatchState:
    watch_id: str
    cars: dict[str, Car] = field(default_factory=dict)
    # номер вагона -> когда впервые увиден; вагоны на момент старта отслеживания помечены baseline
    seen: dict[str, str] = field(default_factory=dict)
    baseline_numbers: set[str] = field(default_factory=set)
    baseline_done: bool = False
    finished: bool = False
    consecutive_failures: int = 0
    failure_alert_sent: bool = False
    pending_empty: int = 0
    started_at: datetime | None = None
    last_check_at: datetime | None = None
    last_ok_at: datetime | None = None
    last_error: str | None = None
    train_info: str | None = None
    departure: datetime | None = None

    @property
    def seen_numbers(self) -> set[str]:
        return set(self.seen)


@dataclass
class Event:
    kind: str                 # alert | report | error | recovered | finished | info
    title: str                # короткий заголовок (push / лента)
    body: str                 # простой текст (push / лента)
    html: str                 # текст для Telegram (HTML)
    watch_id: str | None = None
    url: str | None = None
    data: dict = field(default_factory=dict)
    at: datetime = field(default_factory=utcnow)
    id: int | None = None

    def to_api(self) -> dict:
        return {"id": self.id, "kind": self.kind, "title": self.title, "body": self.body,
                "watch_id": self.watch_id, "url": self.url, "data": self.data, "at": self.at.isoformat()}


@dataclass
class OutboxItem:
    id: int
    text: str
    created_at: datetime
    attempts: int
    silent: bool = False


SETTINGS_KEY = "runtime_settings"
HISTORY_DAYS = 30


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA busy_timeout=5000")
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS watches (
                id TEXT PRIMARY KEY, data TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS watch_state (
                watch_id TEXT PRIMARY KEY, data TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                watch_id TEXT NOT NULL, at TEXT NOT NULL, ok INTEGER NOT NULL,
                total_free INTEGER, cars INTEGER, cabins INTEGER, error TEXT
            );
            CREATE INDEX IF NOT EXISTS checks_watch_at ON checks(watch_id, at);
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                watch_id TEXT, at TEXT NOT NULL, kind TEXT NOT NULL,
                title TEXT NOT NULL, body TEXT NOT NULL, url TEXT, data TEXT
            );
            CREATE INDEX IF NOT EXISTS events_at ON events(at);
            CREATE TABLE IF NOT EXISTS outbox (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL, created_at TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0, next_attempt_at TEXT NOT NULL,
                silent INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS push_subs (
                endpoint TEXT PRIMARY KEY, data TEXT NOT NULL, created_at TEXT NOT NULL, user_agent TEXT
            );
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY, value TEXT NOT NULL
            );
            """
        )
        cols = {r["name"] for r in self._db.execute("PRAGMA table_info(outbox)")}
        if "silent" not in cols:  # миграция базы первой версии
            self._db.execute("ALTER TABLE outbox ADD COLUMN silent INTEGER NOT NULL DEFAULT 0")

    @contextmanager
    def tx(self):
        self._db.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            self._db.execute("ROLLBACK")
            raise
        self._db.execute("COMMIT")

    # ---------- settings ----------
    def get_setting(self, key: str) -> str | None:
        row = self._db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None

    def set_setting(self, key: str, value: str) -> None:
        self._db.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )

    def load_settings(self) -> RuntimeSettings | None:
        v = self.get_setting(SETTINGS_KEY)
        if v is None:
            return None
        data = json.loads(v)
        # невалидные/устаревшие значения не должны ронять запуск
        try:
            return RuntimeSettings.model_validate(data)
        except Exception:
            ok = {}
            for k, val in data.items():
                try:
                    RuntimeSettings.model_validate({k: val})
                    ok[k] = val
                except Exception:
                    pass
            return RuntimeSettings.model_validate(ok)

    def save_settings(self, s: RuntimeSettings) -> None:
        self.set_setting(SETTINGS_KEY, s.model_dump_json())

    # ---------- watches ----------
    def list_watches(self) -> list[WatchConfig]:
        rows = self._db.execute("SELECT data FROM watches ORDER BY created_at, id").fetchall()
        return [WatchConfig.model_validate_json(r["data"]) for r in rows]

    def get_watch(self, watch_id: str) -> WatchConfig | None:
        row = self._db.execute("SELECT data FROM watches WHERE id=?", (watch_id,)).fetchone()
        return WatchConfig.model_validate_json(row["data"]) if row else None

    def upsert_watch(self, w: WatchConfig) -> None:
        self._db.execute(
            "INSERT INTO watches(id, data, created_at) VALUES(?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET data=excluded.data",
            (w.id, w.model_dump_json(), utcnow().isoformat()),
        )

    def delete_watch(self, watch_id: str) -> None:
        with self.tx():
            for table, col in (("watches", "id"), ("watch_state", "watch_id"),
                               ("checks", "watch_id"), ("events", "watch_id")):
                self._db.execute(f"DELETE FROM {table} WHERE {col}=?", (watch_id,))

    # ---------- watch state ----------
    def load_watch(self, watch_id: str) -> WatchState:
        row = self._db.execute("SELECT data FROM watch_state WHERE watch_id=?", (watch_id,)).fetchone()
        if row is None:
            return WatchState(watch_id=watch_id)
        d = json.loads(row["data"])
        cars = {k: Car.from_dict(v) for k, v in d.get("cars", {}).items()}
        seen = d.get("seen")
        if seen is None:  # формат предыдущей версии: только список номеров
            seen = {n: d.get("last_ok_at") or "" for n in (d.get("seen_numbers") or [c.number for c in cars.values()])}
        return WatchState(
            watch_id=watch_id,
            cars=cars,
            seen=seen,
            baseline_numbers=set(d.get("baseline_numbers", seen.keys() if "seen" not in d else [])),
            baseline_done=d.get("baseline_done", False),
            finished=d.get("finished", False),
            consecutive_failures=d.get("consecutive_failures", 0),
            failure_alert_sent=d.get("failure_alert_sent", False),
            pending_empty=d.get("pending_empty", 0),
            started_at=_dt(d.get("started_at")),
            last_check_at=_dt(d.get("last_check_at")),
            last_ok_at=_dt(d.get("last_ok_at")),
            last_error=d.get("last_error"),
            train_info=d.get("train_info"),
            departure=_dt(d.get("departure")),
        )

    def save_watch(
        self,
        st: WatchState,
        events: list[Event] = (),
        outbox: list[tuple[str, bool]] = (),
        check: dict | None = None,
    ) -> None:
        """Состояние, события, сообщения в Telegram и запись истории пишутся одной транзакцией."""
        iso = lambda d: d.isoformat() if d else None
        data = {
            "cars": {k: c.to_dict() for k, c in st.cars.items()},
            "seen": st.seen,
            "baseline_numbers": sorted(st.baseline_numbers),
            "baseline_done": st.baseline_done,
            "finished": st.finished,
            "consecutive_failures": st.consecutive_failures,
            "failure_alert_sent": st.failure_alert_sent,
            "pending_empty": st.pending_empty,
            "started_at": iso(st.started_at),
            "last_check_at": iso(st.last_check_at),
            "last_ok_at": iso(st.last_ok_at),
            "last_error": st.last_error,
            "train_info": st.train_info,
            "departure": iso(st.departure),
        }
        now = utcnow().isoformat()
        with self.tx():
            self._db.execute(
                "INSERT INTO watch_state(watch_id, data) VALUES(?, ?) "
                "ON CONFLICT(watch_id) DO UPDATE SET data=excluded.data",
                (st.watch_id, json.dumps(data, ensure_ascii=False)),
            )
            for ev in events:
                cur = self._db.execute(
                    "INSERT INTO events(watch_id, at, kind, title, body, url, data) VALUES(?,?,?,?,?,?,?)",
                    (ev.watch_id, ev.at.isoformat(), ev.kind, ev.title, ev.body, ev.url,
                     json.dumps(ev.data, ensure_ascii=False)),
                )
                ev.id = cur.lastrowid
            for text, silent in outbox:
                self._insert_message(text, silent, now)
            if check is not None:
                self._db.execute(
                    "INSERT INTO checks(watch_id, at, ok, total_free, cars, cabins, error) VALUES(?,?,?,?,?,?,?)",
                    (st.watch_id, check["at"], int(check["ok"]), check.get("total_free"),
                     check.get("cars"), check.get("cabins"), check.get("error")),
                )

    def add_event(self, ev: Event, outbox: list[tuple[str, bool]] = ()) -> None:
        with self.tx():
            cur = self._db.execute(
                "INSERT INTO events(watch_id, at, kind, title, body, url, data) VALUES(?,?,?,?,?,?,?)",
                (ev.watch_id, ev.at.isoformat(), ev.kind, ev.title, ev.body, ev.url,
                 json.dumps(ev.data, ensure_ascii=False)),
            )
            ev.id = cur.lastrowid
            for text, silent in outbox:
                self._insert_message(text, silent, utcnow().isoformat())

    # ---------- history / events ----------
    def history(self, watch_id: str, since: datetime | None = None) -> list[dict]:
        q = "SELECT at, ok, total_free, cars, cabins, error FROM checks WHERE watch_id=?"
        args: list = [watch_id]
        if since:
            q += " AND at>=?"
            args.append(since.isoformat())
        rows = self._db.execute(q + " ORDER BY at", args).fetchall()
        return [dict(r) for r in rows]

    def events(self, watch_id: str | None = None, kinds: list[str] | None = None,
               before_id: int | None = None, limit: int = 50) -> list[dict]:
        q, args = "SELECT * FROM events WHERE 1=1", []
        if watch_id:
            q += " AND watch_id=?"
            args.append(watch_id)
        if kinds:
            q += f" AND kind IN ({','.join('?' * len(kinds))})"
            args += kinds
        if before_id:
            q += " AND id<?"
            args.append(before_id)
        q += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        out = []
        for r in self._db.execute(q, args).fetchall():
            d = dict(r)
            d["data"] = json.loads(d["data"] or "{}")
            out.append(d)
        return out

    def prune(self) -> None:
        cutoff = (utcnow() - timedelta(days=HISTORY_DAYS)).isoformat()
        with self.tx():
            self._db.execute("DELETE FROM checks WHERE at<?", (cutoff,))
            self._db.execute("DELETE FROM events WHERE at<? AND kind IN ('report','info')", (cutoff,))

    # ---------- push subscriptions ----------
    def add_push_sub(self, sub: dict, user_agent: str | None) -> None:
        self._db.execute(
            "INSERT INTO push_subs(endpoint, data, created_at, user_agent) VALUES(?,?,?,?) "
            "ON CONFLICT(endpoint) DO UPDATE SET data=excluded.data",
            (sub["endpoint"], json.dumps(sub), utcnow().isoformat(), (user_agent or "")[:300]),
        )

    def remove_push_sub(self, endpoint: str) -> None:
        self._db.execute("DELETE FROM push_subs WHERE endpoint=?", (endpoint,))

    def push_subs(self) -> list[dict]:
        return [json.loads(r["data"]) for r in self._db.execute("SELECT data FROM push_subs").fetchall()]

    # ---------- outbox ----------
    def _insert_message(self, text: str, silent: bool, now: str) -> None:
        self._db.execute(
            "INSERT INTO outbox(text, created_at, next_attempt_at, silent) VALUES(?, ?, ?, ?)",
            (text, now, now, int(silent)),
        )

    def enqueue(self, text: str, silent: bool = False) -> None:
        self._insert_message(text, silent, utcnow().isoformat())

    def due_messages(self, limit: int = 20) -> list[OutboxItem]:
        rows = self._db.execute(
            "SELECT id, text, created_at, attempts, silent FROM outbox "
            "WHERE next_attempt_at<=? ORDER BY id LIMIT ?",
            (utcnow().isoformat(), limit),
        ).fetchall()
        return [OutboxItem(r["id"], r["text"], _dt(r["created_at"]), r["attempts"], bool(r["silent"]))
                for r in rows]

    def outbox_size(self) -> int:
        return self._db.execute("SELECT COUNT(*) FROM outbox").fetchone()[0]

    def delete_message(self, msg_id: int) -> None:
        self._db.execute("DELETE FROM outbox WHERE id=?", (msg_id,))

    def reschedule_message(self, msg_id: int, attempts: int, next_at: datetime) -> None:
        self._db.execute(
            "UPDATE outbox SET attempts=?, next_attempt_at=? WHERE id=?",
            (attempts, next_at.isoformat(), msg_id),
        )

    def close(self) -> None:
        self._db.close()
