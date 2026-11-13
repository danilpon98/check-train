"""Сборка приложения: один процесс = мониторинг + веб-интерфейс + Telegram + Web Push."""
from __future__ import annotations

import asyncio
import logging
import webbrowser

import uvicorn
from pydantic import ValidationError

from .config import AppConfig, RuntimeSettings, WatchConfig
from .fetcher import Fetcher
from .hub import Hub
from .monitor import Monitor, make_event
from .state import Store, utcnow
from .telegram import TelegramService, esc
from .web import create_app
from .webpush import PushService

log = logging.getLogger("trainwatch")


class App:
    def __init__(self, cfg: AppConfig, fetch=None):
        self.cfg = cfg
        self.started_at = utcnow()
        cfg.data_dir.mkdir(parents=True, exist_ok=True)
        self.store = Store(cfg.db_path)
        self.hub = Hub(self.store, cfg)
        self.fetcher = Fetcher(cfg.request_timeout_seconds)
        self.monitor = Monitor(self.store, fetch or self.fetcher.get, self.hub)
        self.telegram = TelegramService(self.store, self.hub, self.monitor.handle_command)
        self.hub.telegram = self.telegram
        try:
            self.push: PushService | None = PushService(self.store, cfg.data_dir, cfg.vapid_subject)
        except Exception:
            log.exception("Web Push недоступен")
            self.push = None
        self.hub.push = self.push
        self.hub.on_settings_changed.append(self._on_settings)
        self._import_seed()

    @property
    def url(self) -> str:
        host = "localhost" if self.cfg.host in ("127.0.0.1", "0.0.0.0", "::") else self.cfg.host
        return f"http://{host}:{self.cfg.port}/"

    def _import_seed(self) -> None:
        """Первый запуск: поезда из config.yaml переносятся в базу, дальше управляются из интерфейса."""
        if self.store.list_watches() or not self.cfg.seed_watches:
            return
        for raw in self.cfg.seed_watches:
            try:
                w = WatchConfig.model_validate(raw)
            except ValidationError as e:
                log.error("config.yaml: пропускаю некорректный поезд %r: %s", raw.get("url"), e)
                continue
            self.store.upsert_watch(w)
            log.info("Импортирован из config.yaml: %s", w.title)

    def _on_settings(self, old: RuntimeSettings, new: RuntimeSettings) -> None:
        if old.check_interval_minutes != new.check_interval_minutes or old.jitter_seconds != new.jitter_seconds:
            self.monitor.interval_changed()
        tg_keys = ("telegram_enabled", "telegram_token", "telegram_chat_id")
        if any(getattr(old, k) != getattr(new, k) for k in tg_keys):
            self.telegram.retry_now()
            asyncio.get_running_loop().create_task(self.telegram.verify())

    async def _prune_loop(self) -> None:
        while True:
            try:
                self.store.prune()
            except Exception:
                log.exception("очистка истории")
            await asyncio.sleep(6 * 3600)

    async def run(self) -> None:
        server = uvicorn.Server(uvicorn.Config(
            create_app(self), host=self.cfg.host, port=self.cfg.port,
            log_level="warning", access_log=False, lifespan="off",
        ))
        tasks = [
            asyncio.create_task(self.monitor.run(), name="monitor"),
            asyncio.create_task(self.telegram.run_sender(), name="tg-sender"),
            asyncio.create_task(self.telegram.run_bot(), name="tg-bot"),
            asyncio.create_task(self._prune_loop(), name="prune"),
        ]
        await self.telegram.verify()

        watches = [w for w in self.store.list_watches() if w.enabled]
        titles = "\n".join(f"• {esc(w.title)}" for w in watches) or "пока ничего — добавьте поезд в веб-интерфейсе"
        self.hub.emit(make_event(
            "info", None, "🟢 Сервис запущен", f"Отслеживается поездов: {len(watches)}",
            f"🟢 Сервис запущен. Отслеживаю:\n{titles}\n\n"
            f"Проверка раз в {self.hub.settings.check_interval_minutes:g} мин. Команды: /status, /check, /interval",
            utcnow()))
        log.info("Веб-интерфейс: %s", self.url)

        async def open_browser():
            while not server.started:
                await asyncio.sleep(0.1)
            if self.cfg.open_browser:
                webbrowser.open(self.url)

        tasks.append(asyncio.create_task(open_browser(), name="browser"))
        try:
            await server.serve()       # завершается по Ctrl+C
        finally:
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await self.fetcher.aclose()
            self.store.close()
            log.info("Остановлено")
