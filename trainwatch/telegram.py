from __future__ import annotations

import asyncio
import html
import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Awaitable, Callable

import httpx

from .state import Store, utcnow

if TYPE_CHECKING:
    from .hub import Hub

log = logging.getLogger(__name__)

MAX_LEN = 4000              # лимит Telegram 4096, оставляем запас
MAX_MESSAGE_AGE = timedelta(hours=12)


def esc(s: object) -> str:
    return html.escape(str(s), quote=False)


class TelegramError(Exception):
    def __init__(self, message: str, retry_after: float | None = None, permanent: bool = False):
        super().__init__(message)
        self.retry_after = retry_after
        self.permanent = permanent


class TelegramClient:
    def __init__(self, token: str, chat_id: str = ""):
        self._base = f"https://api.telegram.org/bot{token}"
        self.chat_id = str(chat_id)
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(70, connect=15))

    async def call(self, method: str, **params) -> object:
        try:
            resp = await self._client.post(f"{self._base}/{method}", json=params)
        except httpx.HTTPError as e:
            # токен в URL — не логируем исключение целиком
            raise TelegramError(f"сетевая ошибка Telegram: {e.__class__.__name__}") from None
        except RuntimeError:  # клиент закрыт при смене токена
            raise TelegramError("клиент Telegram пересоздан") from None
        try:
            data = resp.json()
        except ValueError:
            raise TelegramError(f"Telegram вернул не-JSON, HTTP {resp.status_code}") from None
        if data.get("ok"):
            return data["result"]
        desc = data.get("description", f"HTTP {resp.status_code}")
        retry_after = (data.get("parameters") or {}).get("retry_after")
        permanent = resp.status_code in (400, 401, 403, 404) and retry_after is None
        raise TelegramError(f"Telegram: {desc}", retry_after=retry_after, permanent=permanent)

    async def send(self, text: str, chat_id: str | None = None, silent: bool = False) -> None:
        if len(text) > MAX_LEN:
            text = text[:MAX_LEN] + "\n…"
        await self.call(
            "sendMessage",
            chat_id=chat_id or self.chat_id,
            text=text,
            parse_mode="HTML",
            disable_web_page_preview=True,
            disable_notification=silent,
        )

    async def aclose(self) -> None:
        await self._client.aclose()


CommandHandler = Callable[[str, list[str]], Awaitable[str]]


class TelegramService:
    """Отправка очереди (outbox) + команды бота. Подхватывает смену токена/chat_id из интерфейса."""

    def __init__(self, store: Store, hub: "Hub", handler: CommandHandler):
        self.store = store
        self.hub = hub
        self.handler = handler
        self._wake = asyncio.Event()
        self._client: TelegramClient | None = None
        self._creds: tuple[str, str] | None = None
        self.bot_username: str | None = None
        self.last_error: str | None = None
        self.last_sent_at: datetime | None = None
        self.seen_chats: dict[str, str] = {}   # chat_id -> имя (кто писал боту)

    def wakeup(self) -> None:
        self._wake.set()

    def _current(self) -> TelegramClient | None:
        token, chat, _ = self.hub.telegram_creds()
        if not token:
            return None
        if self._creds != (token, chat):
            if self._client is not None:
                asyncio.create_task(self._client.aclose())
            self._client = TelegramClient(token, chat)
            self._creds = (token, chat)
            self.bot_username = None
            self.last_error = None
        return self._client

    async def verify(self) -> None:
        tg = self._current()
        if tg is None:
            return
        try:
            me = await tg.call("getMe")
            self.bot_username = me.get("username")
            log.info("Telegram-бот: @%s", self.bot_username)
        except TelegramError as e:
            self.last_error = str(e)
            log.error("Проверка Telegram не прошла: %s", e)

    # ---------- отправка ----------
    async def run_sender(self) -> None:
        while True:
            try:
                if self.hub.telegram_active():
                    await self._drain()
            except Exception:
                log.exception("ошибка в отправщике Telegram")
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=5)
            except asyncio.TimeoutError:
                pass
            self._wake.clear()

    async def _drain(self) -> None:
        tg = self._current()
        if tg is None or not tg.chat_id:
            return
        for item in self.store.due_messages():
            if utcnow() - item.created_at > MAX_MESSAGE_AGE:
                log.error("сообщение #%s устарело и не доставлено, удаляю", item.id)
                self.store.delete_message(item.id)
                continue
            try:
                await tg.send(item.text, silent=item.silent)
            except TelegramError as e:
                attempts = item.attempts + 1
                delay = e.retry_after or min(10 * 2 ** (attempts - 1), 600)
                if e.permanent:
                    delay = max(delay, 120)  # ошибка конфигурации: chat not found, бот заблокирован и т.п.
                self.last_error = str(e)
                log.warning("не удалось отправить #%s (попытка %s): %s; повтор через %ss",
                            item.id, attempts, e, int(delay))
                self.store.reschedule_message(item.id, attempts, utcnow() + timedelta(seconds=delay))
                self.hub.state_changed()
                return  # сохраняем порядок сообщений
            self.store.delete_message(item.id)
            self.last_error = None
            self.last_sent_at = utcnow()
            await asyncio.sleep(0.5)  # с запасом ниже лимита 1 msg/s на чат

    def retry_now(self) -> None:
        """После смены настроек — не ждать паузу между повторами."""
        self.store._db.execute("UPDATE outbox SET next_attempt_at=?", (utcnow().isoformat(),))
        self.wakeup()

    # ---------- команды ----------
    async def run_bot(self) -> None:
        offset: int | None = None
        creds = None
        backoff = 5
        while True:
            s = self.hub.settings
            tg = self._current() if s.telegram_enabled else None
            if tg is None:
                await asyncio.sleep(5)
                continue
            if creds != self._creds:
                creds = self._creds
                offset = await self._skip_old_updates(tg)
            try:
                updates = await tg.call("getUpdates", offset=offset, timeout=25, allowed_updates=["message"])
                backoff = 5
            except TelegramError as e:
                if "Conflict" in str(e):
                    log.warning("getUpdates: бот опрашивается другим процессом/вебхуком — команды недоступны")
                    await asyncio.sleep(60)
                    continue
                await asyncio.sleep(e.retry_after or backoff)
                backoff = min(backoff * 2, 300)
                continue
            for upd in updates:
                offset = upd["update_id"] + 1
                msg = upd.get("message") or {}
                chat = msg.get("chat") or {}
                chat_id = str(chat.get("id", ""))
                if chat_id:
                    self.seen_chats[chat_id] = (chat.get("username") and "@" + chat["username"]) \
                        or chat.get("first_name") or chat.get("title") or chat_id
                    self.hub.state_changed()
                text = (msg.get("text") or "").strip()
                if not text.startswith("/") or not s.telegram_commands:
                    continue
                if chat_id != tg.chat_id:
                    if text.startswith("/start"):
                        try:
                            await tg.send(f"Ваш chat_id: <code>{esc(chat_id)}</code>\n"
                                          "Укажите его в настройках веб-интерфейса trainwatch.", chat_id=chat_id)
                        except TelegramError:
                            pass
                    continue
                parts = text.split()
                cmd = parts[0].split("@")[0].lower()
                try:
                    reply = await self.handler(cmd, parts[1:])
                    await tg.send(reply)
                except Exception:
                    log.exception("ошибка обработки команды %s", cmd)

    async def _skip_old_updates(self, tg: TelegramClient) -> int | None:
        try:
            updates = await tg.call("getUpdates", offset=-1, timeout=0)
        except TelegramError as e:
            self.last_error = str(e)
            return None
        for upd in updates:
            chat = (upd.get("message") or {}).get("chat") or {}
            if chat.get("id"):
                self.seen_chats[str(chat["id"])] = chat.get("username") or chat.get("first_name") or str(chat["id"])
        return updates[-1]["update_id"] + 1 if updates else None

    def status(self) -> dict:
        token, chat, src = self.hub.telegram_creds()
        return {
            "enabled": self.hub.settings.telegram_enabled,
            "configured": bool(token and chat),
            "has_token": bool(token),
            "has_chat": bool(chat),
            "source": src,
            "bot_username": self.bot_username,
            "last_error": self.last_error,
            "last_sent_at": self.last_sent_at.isoformat() if self.last_sent_at else None,
            "queue": self.store.outbox_size(),
            "seen_chats": [{"id": k, "name": v} for k, v in self.seen_chats.items()],
        }
