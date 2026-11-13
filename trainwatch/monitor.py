from __future__ import annotations

import asyncio
import html as htmllib
import logging
import random
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Awaitable, Callable

from .config import KZ_TZ, MAX_INTERVAL_MINUTES, MIN_INTERVAL_MINUTES, WatchConfig
from .fetcher import FetchError
from .models import Cabin, Car, Snapshot
from .parser import ParseError, parse_page
from .state import Event, Store, WatchState, utcnow
from .telegram import esc

if TYPE_CHECKING:
    from .hub import Hub

log = logging.getLogger(__name__)

MIN_GAP_BETWEEN_REQUESTS = 3.0  # секунд между любыми двумя запросами к сайту


# ---------------------------------------------------------------- форматирование
def plural(n: int, one: str, few: str, many: str) -> str:
    n10, n100 = n % 10, n % 100
    if n10 == 1 and n100 != 11:
        return one
    if 2 <= n10 <= 4 and not 12 <= n100 <= 14:
        return few
    return many


def seats_word(n: int) -> str:
    return f"{n} {plural(n, 'место', 'места', 'мест')}"


def kz_time(dt: datetime) -> str:
    return f"{dt.astimezone(KZ_TZ):%H:%M}"


def html_to_text(s: str) -> str:
    return htmllib.unescape(re.sub(r"<[^>]+>", "", s))


def car_title(c: Car) -> str:
    s = f"Вагон <b>{esc(c.number)}</b> — {esc(c.car_type or '?')}"
    return s + (f" ({esc(c.service_class)})" if c.service_class else "")


def cabin_text(c: Cabin) -> str:
    return f"места <b>{esc(c.label)}</b>" + (" ♿ для маломобильных" if c.for_disabled else "")


def header(cfg: WatchConfig, st: WatchState) -> str:
    lines = [f"<b>{esc(cfg.title)}</b>"]
    if st.train_info:
        lines.append(f"<i>{esc(st.train_info)}</i>")
    return "\n".join(lines)


def link(cfg: WatchConfig, text: str = "Открыть на сайте") -> str:
    return f'<a href="{esc(cfg.url).replace(chr(34), "&quot;")}">{text}</a>'


def by_number(cars) -> list[Car]:
    return sorted(cars, key=lambda c: (len(c.number), c.number))


def fmt_ago(dt: datetime | None, now: datetime) -> str:
    if dt is None:
        return "никогда"
    sec = int((now - dt).total_seconds())
    if sec < 60:
        return f"{sec} с назад"
    if sec < 3600:
        return f"{sec // 60} мин назад"
    return f"{dt.astimezone(KZ_TZ):%d.%m %H:%M}"


SIREN = "🚨" * 10


def alert_html(cfg: WatchConfig, st: WatchState, new_cars: list[Car],
               new_cabins: list[tuple[Car, Cabin]], already: bool = False) -> str:
    parts = [SIREN, f"🟢🟢 <b>{alert_title(new_cars, new_cabins, already)}</b> 🟢🟢", SIREN, "", header(cfg, st)]
    if new_cars:
        parts.append("")
        for c in new_cars:
            parts.append(f"🆕 {car_title(c)}\n      свободно: <b>{seats_word(c.free_seats)}</b>"
                         + (f" · {esc(c.price)}" if c.price else ""))
    if new_cabins:
        parts.append("")
        parts.append("🛏 <b>Кабинка свободна целиком (все 4 места):</b>")
        for car, cab in new_cabins:
            parts.append(f"🔥 {car_title(car)}: {cabin_text(cab)}")
    parts += ["", f"👉 <b>{link(cfg, 'КУПИТЬ НА САЙТЕ')}</b> 👈", SIREN]
    return "\n".join(parts)


def alert_title(new_cars: list[Car], new_cabins: list, already: bool = False) -> str:
    if new_cars and new_cabins:
        return "НОВЫЙ ВАГОН И СВОБОДНАЯ КАБИНКА!"
    if new_cars:
        return "ПОЯВИЛСЯ НОВЫЙ ВАГОН!" if len(new_cars) == 1 else f"ПОЯВИЛИСЬ НОВЫЕ ВАГОНЫ ({len(new_cars)})!"
    return "ЕСТЬ СВОБОДНАЯ КАБИНКА!" if already else "ОСВОБОДИЛАСЬ КАБИНКА — 4 МЕСТА!"


def alert_short(new_cars: list[Car], new_cabins: list[tuple[Car, Cabin]]) -> str:
    lines = [f"Новый вагон {c.number} ({c.car_type}): {seats_word(c.free_seats)}" for c in new_cars]
    lines += [f"Вагон {c.number} ({c.car_type}): места {cab.label}" + (" ♿" if cab.for_disabled else "")
              for c, cab in new_cabins]
    return "\n".join(lines)


def report_html(cfg: WatchConfig, st: WatchState, now: datetime, new_cars: list[Car],
                new_cabins: list[tuple[Car, Cabin]], next_check_at: datetime | None,
                intro: str | None = None) -> str:
    cars = by_number(st.cars.values())
    all_cabins = [(c, cab) for c in cars for cab in c.free_cabins]
    lines = [intro or f"📋 Отчёт · {kz_time(now)}", header(cfg, st), ""]

    if intro is None:
        if new_cars:
            lines.append("✅ Новый вагон: " + ", ".join(f"<b>{esc(c.number)}</b>" for c in new_cars))
        else:
            lines.append("❌ Новый вагон не появился")
    if new_cabins:
        lines.append(f"✅ Освободилось кабинок: <b>{len(new_cabins)}</b>")
    if all_cabins:
        lines.append("🛏 Свободные кабинки сейчас:")
        lines += [f"   • вагон <b>{esc(c.number)}</b>: {cabin_text(cab)}" for c, cab in all_cabins]
    else:
        lines.append("❌ Свободной кабинки (4 места) нет")

    lines.append("")
    if cars:
        lines.append("Свободные места по вагонам:")
        for c in cars:
            lines.append(f"• {esc(c.number)} {esc(c.car_type)} — <b>{seats_word(c.free_seats)}</b>"
                         + (f" · {esc(c.price)}" if c.price else ""))
        total = sum(c.free_seats for c in cars)
        lines.append(f"Всего: <b>{seats_word(total)}</b> в {len(cars)} "
                     f"{plural(len(cars), 'вагоне', 'вагонах', 'вагонах')}")
    else:
        lines.append("Свободных мест в поезде нет (или продажа ещё не открыта).")
    if next_check_at:
        lines.append(f"\nСледующая проверка ≈ {kz_time(next_check_at)} · {link(cfg)}")
    return "\n".join(lines)


def report_short(st: WatchState, new_cars: list[Car]) -> str:
    cars = st.cars.values()
    cabins = sum(len(c.free_cabins) for c in cars)
    total = sum(c.free_seats for c in cars)
    return " · ".join([
        f"новый вагон: {', '.join(c.number for c in new_cars)}" if new_cars else "новых вагонов нет",
        f"свободных кабинок: {cabins}" if cabins else "кабинок нет",
        f"свободно {seats_word(total)} в {len(cars)} {plural(len(cars), 'вагоне', 'вагонах', 'вагонах')}",
    ])


def make_event(kind: str, cfg: WatchConfig | None, title: str, short: str, html: str, now: datetime,
               data: dict | None = None) -> Event:
    d = dict(data or {})
    d["text"] = html_to_text(html)
    if cfg is not None:
        d.setdefault("watch_title", cfg.title)
    return Event(kind=kind, title=title, body=short, html=html, watch_id=cfg.id if cfg else None,
                 url=cfg.url if cfg else None, data=d, at=now)


# ---------------------------------------------------------------- чистая логика
@dataclass
class Outcome:
    events: list[Event] = field(default_factory=list)
    new_cars: list[Car] = field(default_factory=list)
    new_cabins: list[tuple[Car, Cabin]] = field(default_factory=list)
    accepted: bool = True   # False — пустой ответ ждёт подтверждения


def _alert_data(new_cars, new_cabins) -> dict:
    return {
        "new_cars": [c.number for c in new_cars],
        "new_cabins": [{"car": c.number, "car_type": c.car_type, "label": cab.label,
                        "seats": list(cab.seats), "for_disabled": cab.for_disabled} for c, cab in new_cabins],
    }


def apply_success(
    cfg: WatchConfig,
    st: WatchState,
    snap: Snapshot,
    now: datetime,
    confirm_empty_checks: int,
    next_check_at: datetime | None = None,
) -> Outcome:
    out = Outcome()
    st.last_check_at = now
    if st.failure_alert_sent:
        out.events.append(make_event("recovered", cfg, f"✅ Проверка снова работает · {cfg.title}",
                                     "Сайт снова отвечает", f"✅ Проверка снова работает\n{header(cfg, st)}", now))
    st.consecutive_failures = 0
    st.failure_alert_sent = False
    st.last_error = None
    if snap.train_info:
        st.train_info = snap.train_info
    if snap.departure:
        st.departure = snap.departure

    # Защита от ложного «пусто»: сбой бэкенда сайта иногда отдаёт «ничего не найдено».
    if not snap.cars and st.cars and st.baseline_done:
        st.pending_empty += 1
        if st.pending_empty < confirm_empty_checks:
            log.info("[%s] пустой ответ, жду подтверждения (%s/%s)",
                     cfg.title, st.pending_empty, confirm_empty_checks)
            out.accepted = False
            return out
    st.pending_empty = 0
    st.last_ok_at = now
    cur = snap.cars

    if not st.baseline_done:
        # Точка отсчёта: всё, что есть сейчас, — «старые» вагоны.
        st.baseline_done = True
        st.started_at = now
        st.cars = cur
        st.seen = {c.number: now.isoformat() for c in cur.values()}
        st.baseline_numbers = set(st.seen)
        existing = [(c, cab) for c in by_number(cur.values()) for cab in c.free_cabins]
        if existing:
            out.new_cabins = existing
            out.events.append(make_event(
                "alert", cfg, f"🚨 {alert_title([], existing, True)} · {cfg.title}",
                alert_short([], existing), alert_html(cfg, st, [], existing, already=True), now,
                _alert_data([], existing)))
        html = (report_html(cfg, st, now, [], [], next_check_at, intro="👀 <b>Начинаю отслеживание</b>")
                + "\n\nНовым считается вагон с номером, которого нет в списке выше.")
        out.events.append(make_event("info", cfg, f"👀 Начинаю отслеживание · {cfg.title}",
                                     report_short(st, []), html, now))
        return out

    prev_cabins = set().union(*(c.cabin_keys() for c in st.cars.values())) if st.cars else set()

    for c in by_number(cur.values()):
        if c.number not in st.seen:
            out.new_cars.append(c)
        for cab in c.free_cabins:
            if f"{c.key}:{cab.label}" not in prev_cabins:
                out.new_cabins.append((c, cab))

    gone = set(st.cars) - set(cur)
    if gone:
        log.info("[%s] исчезли из списка (нет мест): %s", cfg.title, ", ".join(sorted(gone)))

    st.cars = cur
    for c in out.new_cars:
        st.seen[c.number] = now.isoformat()

    if out.new_cars or out.new_cabins:
        log.info("[%s] СОБЫТИЕ: новые вагоны %s, кабинки %s", cfg.title,
                 [c.number for c in out.new_cars], [f"{c.number}:{cab.label}" for c, cab in out.new_cabins])
        out.events.append(make_event(
            "alert", cfg, f"🚨 {alert_title(out.new_cars, out.new_cabins)} · {cfg.title}",
            alert_short(out.new_cars, out.new_cabins), alert_html(cfg, st, out.new_cars, out.new_cabins), now,
            _alert_data(out.new_cars, out.new_cabins)))
    out.events.append(make_event(
        "report", cfg, f"📋 Отчёт {kz_time(now)} · {cfg.title}", report_short(st, out.new_cars),
        report_html(cfg, st, now, out.new_cars, out.new_cabins, next_check_at), now))
    return out


def apply_failure(cfg: WatchConfig, st: WatchState, err: Exception, now: datetime, threshold: int) -> Outcome:
    out = Outcome()
    st.last_check_at = now
    st.consecutive_failures += 1
    st.last_error = str(err)
    if st.consecutive_failures >= threshold and not st.failure_alert_sent:
        st.failure_alert_sent = True
        html = (f"⚠️ Не удаётся проверить наличие вагонов ({st.consecutive_failures} раз подряд)\n"
                f"{header(cfg, st)}\n\nОшибка: <code>{esc(err)}</code>\n"
                "Продолжаю попытки; сообщу, когда заработает.")
        out.events.append(make_event("error", cfg, f"⚠️ Не удаётся проверить · {cfg.title}", str(err), html, now))
    return out


# ---------------------------------------------------------------- сервис
Fetch = Callable[[str], Awaitable[str]]


class Monitor:
    """Планировщик проверок. Поезда добавляются/удаляются на лету из веб-интерфейса."""

    def __init__(self, store: Store, fetch: Fetch, hub: "Hub"):
        self.store = store
        self.fetch = fetch
        self.hub = hub
        self._tasks: dict[str, asyncio.Task] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._wake: dict[str, asyncio.Event] = {}
        self._regular: dict[str, bool] = {}          # последняя пауза — плановая (не ретрай)
        self.next_check_at: dict[str, datetime] = {}
        self._last_delay: dict[str, float] = {}
        self._reset: set[str] = set()
        self.checking: set[str] = set()
        self._site_sem = asyncio.Semaphore(1)
        self._last_request = 0.0

    @property
    def settings(self):
        return self.hub.settings

    # ---------- управление поездами ----------
    def watches(self) -> list[WatchConfig]:
        return self.store.list_watches()

    def start(self, cfg: WatchConfig, start_delay: float = 0) -> None:
        if not cfg.enabled or (cfg.id in self._tasks and not self._tasks[cfg.id].done()):
            return
        self._locks.setdefault(cfg.id, asyncio.Lock())
        self._wake.setdefault(cfg.id, asyncio.Event())
        self._regular.setdefault(cfg.id, True)
        self._tasks[cfg.id] = asyncio.create_task(self.run_watch(cfg.id, start_delay), name=f"watch:{cfg.id}")

    def stop(self, watch_id: str) -> None:
        t = self._tasks.pop(watch_id, None)
        if t:
            t.cancel()
        self.next_check_at.pop(watch_id, None)

    def is_running(self, watch_id: str) -> bool:
        t = self._tasks.get(watch_id)
        return t is not None and not t.done()

    def interval_changed(self) -> None:
        for ev in self._wake.values():
            ev.set()

    def _regular_delay(self) -> float:
        s = self.settings
        return s.check_interval_minutes * 60 + random.uniform(0, s.jitter_seconds)

    # ---------- проверка ----------
    async def fetch_snapshot(self, url: str) -> Snapshot:
        async with self._site_sem:
            loop = asyncio.get_running_loop()
            gap = self._last_request + MIN_GAP_BETWEEN_REQUESTS - loop.time()
            if gap > 0:
                await asyncio.sleep(gap)
            try:
                html = await self.fetch(url)
            finally:
                self._last_request = loop.time()
        # разбор ~100 мс CPU — в отдельном потоке, чтобы не задерживать ответы веб-интерфейсу
        return await asyncio.to_thread(parse_page, html)

    async def check(self, watch_id: str) -> float:
        """Одна проверка. Возвращает паузу до следующей (секунды), -1 — отслеживание завершено."""
        lock = self._locks.setdefault(watch_id, asyncio.Lock())
        async with lock:
            cfg = self.store.get_watch(watch_id)
            if cfg is None:
                return -1
            s = self.settings
            st = self.store.load_watch(cfg.id)
            now = utcnow()
            if st.finished:
                return -1
            dep = cfg.departure
            if dep is not None and now >= dep:
                st.finished = True
                ev = make_event("finished", cfg, f"🏁 Поезд отправился · {cfg.title}", "Отслеживание завершено",
                                f"🏁 Поезд отправился, отслеживание завершено\n{header(cfg, st)}", now)
                self.store.save_watch(st, [ev], self.hub.telegram_outbox([ev]))
                self.hub.publish([ev])
                return -1

            regular = self._regular_delay()
            retry_after = None
            self.checking.add(watch_id)
            self.hub.state_changed()
            try:
                snap = await self.fetch_snapshot(cfg.url)
            except (FetchError, ParseError) as e:
                log.warning("[%s] ошибка проверки: %s", cfg.title, e)
                retry_after = getattr(e, "retry_after", None)
                out = apply_failure(cfg, st, e, now, s.failure_alert_threshold)
                check = {"at": now.isoformat(), "ok": False, "error": str(e)[:500]}
            else:
                out = apply_success(cfg, st, snap, now, s.confirm_empty_checks,
                                    next_check_at=now + timedelta(seconds=regular))
                cars = st.cars.values()
                check = {"at": now.isoformat(), "ok": out.accepted,
                         "total_free": sum(c.free_seats for c in cars) if out.accepted else None,
                         "cars": len(st.cars) if out.accepted else None,
                         "cabins": sum(len(c.free_cabins) for c in cars) if out.accepted else None,
                         "error": None if out.accepted else "пустой ответ, ждёт подтверждения"}
                log.info("[%s] ок: %s", cfg.title, ", ".join(
                    f"{c.number}:{c.free_seats}м/{len(c.free_cabins)}к" for c in by_number(snap.cars.values())
                ) or "вагонов нет")
            finally:
                self.checking.discard(watch_id)

            self.store.save_watch(st, out.events, self.hub.telegram_outbox(out.events), check)

            if st.consecutive_failures:
                delay = min(s.retry_delay_seconds * 2 ** (st.consecutive_failures - 1), regular)
                if retry_after:
                    delay = max(delay, retry_after)
                self._regular[watch_id] = False
            elif not out.accepted:  # пустой ответ — быстро перепроверить
                delay = s.retry_delay_seconds
                self._regular[watch_id] = False
            else:
                delay = regular
                self._regular[watch_id] = True
            self.next_check_at[watch_id] = now + timedelta(seconds=delay)
            self._last_delay[watch_id] = delay
            self.hub.publish(out.events)
            return delay

    async def run_watch(self, watch_id: str, start_delay: float) -> None:
        loop = asyncio.get_running_loop()
        await asyncio.sleep(start_delay)
        ev = self._wake[watch_id]
        while True:
            # сигнал сбрасываем ДО проверки: смена интервала во время проверки не потеряется
            ev.clear()
            try:
                delay = await self.check(watch_id)
            except asyncio.CancelledError:
                raise
            except Exception:
                # что бы ни случилось — цикл не должен умирать
                log.exception("[%s] непредвиденная ошибка", watch_id)
                delay = self.settings.retry_delay_seconds
                self._regular[watch_id] = False
            if delay < 0:
                log.info("[%s] отслеживание завершено", watch_id)
                self.next_check_at.pop(watch_id, None)
                self.hub.state_changed()
                return
            started = loop.time()
            wall_start = utcnow()
            while (remaining := started + delay - loop.time()) > 0:
                try:
                    await asyncio.wait_for(ev.wait(), timeout=remaining)
                except asyncio.TimeoutError:
                    break
                ev.clear()
                if watch_id in self._reset:       # была ручная проверка — отсчёт заново от неё
                    self._reset.discard(watch_id)
                    started, wall_start = loop.time(), utcnow()
                    delay = self._last_delay.get(watch_id, delay)
                    continue
                if self._regular.get(watch_id):   # интервал изменили — пересчитываем от прошлой проверки
                    delay = self._regular_delay()
                    self.next_check_at[watch_id] = wall_start + timedelta(seconds=delay)
                    self.hub.state_changed()

    async def run(self) -> None:
        for i, w in enumerate(self.watches()):
            self.start(w, start_delay=i * 5)
        await asyncio.Event().wait()   # живём, пока живо приложение

    async def check_now(self, watch_id: str) -> None:
        """Внеплановая проверка (кнопка в интерфейсе, /check); плановая сдвигается на интервал от неё."""
        delay = await self.check(watch_id)
        if self.is_running(watch_id):
            if delay < 0:
                self.stop(watch_id)
            else:
                self._reset.add(watch_id)
                self._wake[watch_id].set()

    async def check_all(self) -> None:
        for w in self.watches():
            if w.enabled:
                await self.check_now(w.id)

    # ---------------------------------------------------------------- команды Telegram
    def status_text(self) -> str:
        now = utcnow()
        blocks = [f"📊 Статус · интервал проверки: <b>{self.settings.check_interval_minutes:g} мин</b>"]
        for cfg in self.watches():
            st = self.store.load_watch(cfg.id)
            lines = [f"<b>{esc(cfg.title)}</b>"]
            if st.finished:
                lines.append("завершено (поезд отправился)")
            elif not cfg.enabled:
                lines.append("на паузе")
            else:
                lines.append(f"проверка: {fmt_ago(st.last_check_at, now)}, успешная: {fmt_ago(st.last_ok_at, now)}")
                if st.consecutive_failures:
                    lines.append(f"⚠️ ошибок подряд: {st.consecutive_failures} — <code>{esc(st.last_error)}</code>")
                cars = by_number(st.cars.values())
                lines.append(f"вагонов с местами: {len(cars)}, свободно: {seats_word(sum(c.free_seats for c in cars))}")
                cabins = [f"{esc(c.number)}: {esc(cab.label)}" for c in cars for cab in c.free_cabins]
                lines.append("свободные кабинки: " + (", ".join(cabins) if cabins else "нет"))
                lines.append("известные номера вагонов: " + (", ".join(sorted(st.seen)) or "—"))
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks)

    async def handle_command(self, cmd: str, args: list[str] | None = None) -> str:
        args = args or []
        if cmd == "/status":
            return self.status_text()
        if cmd == "/check":
            await self.check_all()
            return "✔️ Проверка выполнена — отчёт отдельным сообщением."
        if cmd == "/interval":
            cur = self.settings.check_interval_minutes
            if not args:
                return (f"Сейчас проверка раз в <b>{cur:g} мин</b>.\n"
                        f"Изменить: <code>/interval 10</code> (минуты, {MIN_INTERVAL_MINUTES}–{MAX_INTERVAL_MINUTES})")
            try:
                minutes = float(args[0].replace(",", "."))
            except ValueError:
                return "Укажите число минут, например <code>/interval 10</code>"
            if not MIN_INTERVAL_MINUTES <= minutes <= MAX_INTERVAL_MINUTES:
                return f"Допустимо от {MIN_INTERVAL_MINUTES} до {MAX_INTERVAL_MINUTES} минут."
            self.hub.update_settings({"check_interval_minutes": minutes})
            warn = "\n⚠️ Чаще раза в 5 минут — риск блокировки сайтом." if minutes < 5 else ""
            return f"✅ Теперь проверка раз в <b>{minutes:g} мин</b> (отсчёт от последней проверки).{warn}"
        return ("Команды:\n/status — текущее состояние\n/check — проверить прямо сейчас\n"
                "/interval [мин] — показать или изменить интервал проверки\n\n"
                "Всё остальное — в веб-интерфейсе.")
