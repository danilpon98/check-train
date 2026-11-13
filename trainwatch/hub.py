"""Хаб: текущие настройки и доставка событий по каналам.

Событие проверки ──► SQLite (events, outbox для Telegram — в одной транзакции с состоянием)
                 └─► publish(): Web Push во все подписанные браузеры + SSE в открытые вкладки
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Callable

from .config import AppConfig, RuntimeSettings
from .state import Event, Store

if TYPE_CHECKING:
    from .telegram import TelegramService
    from .webpush import PushService

log = logging.getLogger(__name__)

PUSH_ALWAYS = {"alert", "error", "recovered", "finished"}
TELEGRAM_IMPORTANT = {"alert", "error", "recovered", "finished"}


class Broker:
    """Server-Sent Events: у каждой открытой вкладки своя очередь."""

    def __init__(self):
        self._clients: set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        self._clients.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._clients.discard(q)

    @property
    def clients(self) -> int:
        return len(self._clients)

    def send(self, msg: dict) -> None:
        data = json.dumps(msg, ensure_ascii=False)
        for q in list(self._clients):
            try:
                q.put_nowait(data)
            except asyncio.QueueFull:   # вкладка не читает — отключаем, она переподключится
                self._clients.discard(q)


class Hub:
    def __init__(self, store: Store, app: AppConfig):
        self.store = store
        self.app = app
        self.broker = Broker()
        self.telegram: "TelegramService | None" = None
        self.push: "PushService | None" = None
        self.on_settings_changed: list[Callable[[RuntimeSettings, RuntimeSettings], None]] = []
        s = store.load_settings()
        if s is None:
            s = RuntimeSettings.model_validate(app.seed_settings)
            store.save_settings(s)
        self.settings: RuntimeSettings = s
        self._bg: set[asyncio.Task] = set()

    # ---------- настройки ----------
    def update_settings(self, patch: dict) -> RuntimeSettings:
        new = RuntimeSettings.model_validate({**self.settings.model_dump(), **patch})
        old, self.settings = self.settings, new
        self.store.save_settings(new)
        for cb in self.on_settings_changed:
            try:
                cb(old, new)
            except Exception:
                log.exception("ошибка обработчика смены настроек")
        self.state_changed()
        return new

    def telegram_creds(self) -> tuple[str, str, str]:
        """(token, chat_id, источник). Значения из .env важнее введённых в интерфейсе."""
        s = self.settings
        token = self.app.env_telegram_token or s.telegram_token
        chat = self.app.env_telegram_chat_id or s.telegram_chat_id
        src = "env" if (self.app.env_telegram_token or self.app.env_telegram_chat_id) else "ui"
        return token.strip(), str(chat).strip(), src

    def telegram_active(self) -> bool:
        token, chat, _ = self.telegram_creds()
        return self.settings.telegram_enabled and bool(token and chat)

    def telegram_outbox(self, events: list[Event]) -> list[tuple[str, bool]]:
        if not self.telegram_active():
            return []
        s = self.settings
        if not s.telegram_reports:
            # только важное: тревоги, ошибки (и их снятие), «поезд ушёл»
            events = [e for e in events if e.kind in TELEGRAM_IMPORTANT]
        return [(e.html, s.quiet_reports and e.kind in ("report", "recovered", "info")) for e in events]

    # ---------- доставка ----------
    def publish(self, events: list[Event]) -> None:
        """Вызывается ПОСЛЕ записи событий в БД."""
        for e in events:
            self.broker.send({"type": "event", "event": e.to_api()})
            if self.push and (e.kind in PUSH_ALWAYS or (e.kind == "report" and self.settings.push_reports)):
                self._spawn(self.push.send_event(e))
        if events and self.telegram:
            self.telegram.wakeup()
        self.state_changed()

    def emit(self, e: Event) -> None:
        """Событие не от проверки (запуск сервиса и т.п.)."""
        self.store.add_event(e, self.telegram_outbox([e]))
        self.publish([e])

    def state_changed(self) -> None:
        self.broker.send({"type": "state"})

    def _spawn(self, coro) -> None:
        t = asyncio.create_task(coro)
        self._bg.add(t)
        t.add_done_callback(self._bg.discard)
