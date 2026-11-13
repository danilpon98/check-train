"""Web Push (VAPID). Работает в браузере, открытом на http://localhost (это «безопасный контекст»),
даже если вкладка закрыта — нужен лишь запущенный браузер. Доставка идёт через push-сервис
производителя браузера (Google FCM / Mozilla autopush / Apple), поэтому нужен интернет.
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid02, b64urlencode
from pywebpush import WebPushException, webpush

from .state import Event, Store

log = logging.getLogger(__name__)


class PushService:
    def __init__(self, store: Store, data_dir: Path, subject: str):
        self.store = store
        self.subject = subject
        key_path = data_dir / "vapid_private.pem"
        if key_path.exists():
            self._vapid = Vapid02.from_file(str(key_path))
        else:
            self._vapid = Vapid02()
            self._vapid.generate_keys()
            self._vapid.save_key(str(key_path))
            log.info("Созданы VAPID-ключи для Web Push: %s", key_path)
        raw = self._vapid.public_key.public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
        )
        self.public_key = b64urlencode(raw)
        self.last_error: str | None = None

    def _send_one(self, sub: dict, payload: str, ttl: int, urgency: str) -> int | None:
        """Синхронно (requests) — вызывается в отдельном потоке. Возвращает HTTP-код ошибки или None."""
        try:
            webpush(
                subscription_info=sub,
                data=payload,
                vapid_private_key=self._vapid,
                vapid_claims={"sub": self.subject},
                ttl=ttl,
                headers={"Urgency": urgency},
                timeout=15,
            )
            return None
        except WebPushException as e:
            code = e.response.status_code if e.response is not None else 0
            log.warning("Web Push не доставлен (%s): %s", code, str(e)[:200])
            return code or -1
        except Exception as e:  # сеть и пр.
            log.warning("Web Push: %s", e)
            return -1

    async def send(self, payload: dict, ttl: int = 3600, urgency: str = "normal") -> dict:
        subs = self.store.push_subs()
        if not subs:
            return {"sent": 0, "failed": 0}
        data = json.dumps(payload, ensure_ascii=False)
        results = await asyncio.gather(*(
            asyncio.to_thread(self._send_one, s, data, ttl, urgency) for s in subs
        ))
        sent = failed = 0
        for sub, code in zip(subs, results):
            if code is None:
                sent += 1
            elif code in (404, 410):   # подписка отозвана браузером
                self.store.remove_push_sub(sub["endpoint"])
                log.info("Удалена недействительная push-подписка")
            else:
                failed += 1
        self.last_error = None if not failed else f"не доставлено: {failed} из {len(subs)}"
        return {"sent": sent, "failed": failed}

    async def send_event(self, e: Event) -> None:
        alert = e.kind == "alert"
        payload = {
            "title": e.title,
            "body": e.body,
            "kind": e.kind,
            "tag": f"{e.kind}:{e.watch_id}:{e.id}" if alert else f"{e.kind}:{e.watch_id}",
            "url": e.url,
            "event_id": e.id,
            "requireInteraction": alert or e.kind == "error",
        }
        # тревога неактуальна через пару часов, отчёт — через интервал
        await self.send(payload, ttl=3 * 3600 if alert else 1800, urgency="high" if alert else "normal")
