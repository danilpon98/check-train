"""Вход по паролю (WEB_PASSWORD) и сессии.

Сессия — подписанный токен в cookie (HttpOnly). На сервере сессии не хранятся: токен содержит
срок действия и подписан HMAC-SHA256 ключом = секрет из data/session_secret + отпечаток пароля.
Отсюда:
  * смена WEB_PASSWORD завершает все сессии (меняется ключ подписи);
  * «выйти на всех устройствах» = новый секрет;
  * перезапуск/деплой сессии НЕ сбрасывает (секрет лежит в постоянной папке data).

Сроки:
  * «Запомнить на этом устройстве» — 30 дней с последней активности (срок продлевается
    при использовании, не чаще раза в сутки);
  * без галочки — cookie до закрытия браузера, но не дольше 12 часов.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from collections import deque
from pathlib import Path

COOKIE = "tw_session"
REMEMBER_SECONDS = 30 * 24 * 3600
SHORT_SECONDS = 12 * 3600
RENEW_AFTER_SECONDS = 24 * 3600

MAX_FAILURES = 5
FAILURE_WINDOW_SECONDS = 15 * 60


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


class Auth:
    def __init__(self, data_dir: Path, password: str, clock=time.time):
        self.enabled = bool(password)
        self._password = password
        self._secret_path = data_dir / "session_secret"
        self._clock = clock
        self._failures: dict[str, deque[float]] = {}
        self._secret = self._load_secret() if self.enabled else b""

    # ---------- секрет подписи ----------
    def _load_secret(self) -> bytes:
        try:
            s = self._secret_path.read_bytes()
            if len(s) >= 32:
                return s
        except FileNotFoundError:
            pass
        return self._write_secret()

    def _write_secret(self) -> bytes:
        s = secrets.token_bytes(32)
        self._secret_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._secret_path.with_suffix(".tmp")
        tmp.write_bytes(s)
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        os.replace(tmp, self._secret_path)
        return s

    def rotate(self) -> None:
        """Выйти на всех устройствах: все выданные токены становятся недействительными."""
        self._secret = self._write_secret()

    def _key(self) -> bytes:
        return self._secret + hashlib.sha256(self._password.encode()).digest()

    def _sign(self, body: str) -> str:
        return _b64(hmac.new(self._key(), body.encode(), hashlib.sha256).digest())

    # ---------- токены ----------
    def issue(self, remember: bool) -> tuple[str, int | None]:
        """(токен, max_age cookie). max_age=None — cookie до закрытия браузера."""
        now = int(self._clock())
        ttl = REMEMBER_SECONDS if remember else SHORT_SECONDS
        body = _b64(json.dumps({"iat": now, "exp": now + ttl, "rem": remember}, separators=(",", ":")).encode())
        return f"{body}.{self._sign(body)}", (ttl if remember else None)

    def verify(self, token: str | None) -> dict | None:
        if not self.enabled or not token or "." not in token:
            return None
        body, sig = token.rsplit(".", 1)
        if not hmac.compare_digest(sig, self._sign(body)):
            return None
        try:
            payload = json.loads(_unb64(body))
        except (ValueError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict) or payload.get("exp", 0) <= self._clock():
            return None
        return payload

    def should_renew(self, payload: dict) -> bool:
        """«Запомненную» сессию продлеваем, если ей больше суток — активный пользователь не вылетит."""
        return bool(payload.get("rem")) and self._clock() - payload.get("iat", 0) > RENEW_AFTER_SECONDS

    # ---------- пароль и защита от перебора ----------
    def check_password(self, password: str) -> bool:
        return self.enabled and hmac.compare_digest(password.encode(), self._password.encode())

    def retry_after(self, client: str) -> int | None:
        """Сколько секунд ждать, если с этого адреса слишком много неудачных попыток."""
        q = self._failures.get(client)
        if not q:
            return None
        now = self._clock()
        while q and now - q[0] > FAILURE_WINDOW_SECONDS:
            q.popleft()
        if len(q) < MAX_FAILURES:
            return None
        return int(FAILURE_WINDOW_SECONDS - (now - q[0])) + 1

    def record_failure(self, client: str) -> int:
        """Записать неудачу; возвращает, сколько попыток осталось."""
        q = self._failures.setdefault(client, deque())
        q.append(self._clock())
        if len(self._failures) > 10_000:          # не даём словарю расти бесконечно
            self._failures.pop(next(iter(self._failures)))
        self.retry_after(client)                  # чистка старых
        return max(0, MAX_FAILURES - len(q))

    def reset_failures(self, client: str) -> None:
        self._failures.pop(client, None)
