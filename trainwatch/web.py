from __future__ import annotations

import asyncio
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ValidationError

from . import __version__
from .auth import COOKIE, REMEMBER_SECONDS
from .config import RuntimeSettings, WatchConfig
from .fetcher import FetchError
from .monitor import by_number
from .parser import ParseError
from .state import WatchState, utcnow
from .telegram import TelegramClient, TelegramError

if TYPE_CHECKING:
    from .app import App

STATIC = Path(__file__).parent / "static"
MASK = "••••••"
# Без входа доступны: страница приложения и его код (там нет данных — данные только в /api),
# проверка здоровья, файлы, которые браузер запрашивает без cookie (манифест, Service Worker, иконки).
PUBLIC_PATHS = {"/", "/api/health", "/sw.js", "/manifest.webmanifest"}
AUTH_OPEN_PATHS = {"/api/auth/status", "/api/auth/login", "/api/auth/logout"}


def is_public_asset(path: str) -> bool:
    return path.startswith("/static/")


def is_https(request: Request) -> bool:
    # за прокси хостинга (Railway) приложение видит http, исходный протокол — в заголовке
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    return proto.split(",")[0].strip() == "https"


def same_origin(request: Request) -> bool:
    origin = request.headers.get("origin")
    if not origin or origin == "null":
        return True                 # не браузерный запрос или запрос со своей страницы без Origin
    host = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
    return urlparse(origin).netloc == host.split(",")[0].strip()


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "?"
# прокси хостингов обрывают долгие HTTP-запросы (Railway — через 15 мин); закрываем поток сами
# раньше, браузер переподключается через 3 с (retry), интерфейс этого не замечает
SSE_MAX_SECONDS = 10 * 60


# ---------------------------------------------------------------- представления
def split_info(info: str | None) -> dict:
    parts = [p.strip() for p in (info or "").split(" - ")]
    out = {"carrier": None, "route": None, "departure_text": None, "arrival_text": None}
    for p in parts[1:]:
        if "→" in p:
            out["route"] = p
        elif p.lower().startswith(("отправление", "жөнелтілу", "departure")):
            out["departure_text"] = p.split(":", 1)[-1].strip()
        elif p.lower().startswith(("прибытие", "жету", "arrival")):
            out["arrival_text"] = p.split(":", 1)[-1].strip()
        elif out["carrier"] is None:
            out["carrier"] = p
    return out


def car_view(c, st: WatchState) -> dict:
    d = c.to_dict()
    d["is_new"] = st.baseline_done and c.number not in st.baseline_numbers
    d["first_seen"] = st.seen.get(c.number)
    return d


def watch_view(app: "App", cfg: WatchConfig) -> dict:
    st = app.store.load_watch(cfg.id)
    m = app.monitor
    cars = by_number(st.cars.values())
    present = {c.number for c in cars}
    if st.finished:
        status = "finished"
    elif not cfg.enabled:
        status = "paused"
    elif cfg.id in m.checking:
        status = "checking"
    elif st.consecutive_failures:
        status = "error"
    elif not st.baseline_done:
        status = "starting"
    else:
        status = "ok"
    nxt = m.next_check_at.get(cfg.id)
    return {
        "id": cfg.id,
        "name": cfg.name,
        "title": cfg.title,
        "url": cfg.url,
        "enabled": cfg.enabled,
        "train": cfg.train,
        "departure": (st.departure or cfg.departure).isoformat() if (st.departure or cfg.departure) else None,
        "train_info": st.train_info,
        **split_info(st.train_info),
        "status": status,
        "started_at": st.started_at.isoformat() if st.started_at else None,
        "last_check_at": st.last_check_at.isoformat() if st.last_check_at else None,
        "last_ok_at": st.last_ok_at.isoformat() if st.last_ok_at else None,
        "next_check_at": nxt.isoformat() if nxt and cfg.enabled and not st.finished else None,
        "consecutive_failures": st.consecutive_failures,
        "last_error": st.last_error,
        "pending_empty": st.pending_empty,
        "cars": [car_view(c, st) for c in cars],
        "absent_known": [{"number": n, "first_seen": st.seen[n], "is_new": n not in st.baseline_numbers}
                         for n in sorted(st.seen, key=lambda n: (len(n), n)) if n not in present],
        "totals": {
            "free": sum(c.free_seats for c in cars),
            "cars": len(cars),
            "cabins": sum(len(c.free_cabins) for c in cars),
            "known": len(st.seen),
            "new_cars": sum(1 for n in st.seen if st.baseline_done and n not in st.baseline_numbers),
        },
    }


def settings_view(app: "App") -> dict:
    s = app.hub.settings.model_dump()
    tok = s.pop("telegram_token")
    s["telegram_token_set"] = bool(tok)
    s["telegram_token_masked"] = (MASK + tok[-4:]) if tok else ""
    s["telegram_env"] = bool(app.cfg.env_telegram_token or app.cfg.env_telegram_chat_id)
    return s


# ---------------------------------------------------------------- запросы
class WatchIn(BaseModel):
    url: str
    name: str | None = None


class WatchPatch(BaseModel):
    name: str | None = None
    enabled: bool | None = None


class PushSubIn(BaseModel):
    subscription: dict


class TelegramTestIn(BaseModel):
    token: str | None = None
    chat_id: str | None = None


class LoginIn(BaseModel):
    password: str
    remember: bool = True


def _validate_watch(data: dict) -> WatchConfig:
    try:
        return WatchConfig.model_validate(data)
    except ValidationError as e:
        msg = "; ".join(err["msg"].removeprefix("Value error, ") for err in e.errors())
        raise HTTPException(400, msg)


def create_app(app: "App") -> FastAPI:
    api = FastAPI(title="trainwatch", version=__version__, docs_url="/api/docs", redoc_url=None)
    store, hub, monitor = app.store, app.hub, app.monitor

    # ---------- вход по паролю (если задан WEB_PASSWORD) ----------
    auth = app.auth

    def set_session(resp: Response, request: Request, remember: bool) -> None:
        token, max_age = auth.issue(remember)
        resp.set_cookie(
            COOKIE, token, max_age=max_age, httponly=True, samesite="lax", path="/",
            secure=is_https(request),
        )

    @api.middleware("http")
    async def require_session(request: Request, call_next):
        path = request.url.path
        # подделка запроса с чужого сайта: изменяющий запрос с чужим Origin — отклоняем
        if request.method not in ("GET", "HEAD", "OPTIONS") and not same_origin(request):
            return JSONResponse({"detail": "Запрос с чужого сайта отклонён"}, status_code=403)
        if not auth.enabled or path in PUBLIC_PATHS or path in AUTH_OPEN_PATHS or is_public_asset(path):
            return await call_next(request)
        payload = auth.verify(request.cookies.get(COOKIE))
        if payload is None:
            return JSONResponse({"detail": "Требуется вход"}, status_code=401)
        resp = await call_next(request)
        if auth.should_renew(payload):          # активный пользователь не вылетает через 30 дней
            set_session(resp, request, remember=True)
        return resp

    @api.get("/api/auth/status")
    async def auth_status(request: Request):
        return {
            "required": auth.enabled,
            "authenticated": (not auth.enabled) or auth.verify(request.cookies.get(COOKIE)) is not None,
            "remember_days": REMEMBER_SECONDS // 86400,
        }

    @api.post("/api/auth/login")
    async def auth_login(body: LoginIn, request: Request):
        if not auth.enabled:
            return {"ok": True}
        client = client_ip(request)
        wait = auth.retry_after(client)
        if wait:
            raise HTTPException(429, f"Слишком много попыток. Повторите через {max(1, round(wait / 60))} мин.",
                                headers={"Retry-After": str(wait)})
        if not auth.check_password(body.password):
            left = auth.record_failure(client)
            await asyncio.sleep(0.4)            # замедляет перебор
            msg = "Неверный пароль." + (f" Осталось попыток: {left}." if left <= 2 else "")
            if left == 0:
                msg = "Неверный пароль. Вход заблокирован на 15 минут."
            raise HTTPException(401, msg)
        auth.reset_failures(client)
        resp = JSONResponse({"ok": True})
        set_session(resp, request, body.remember)
        return resp

    @api.post("/api/auth/logout")
    async def auth_logout():
        resp = JSONResponse({"ok": True})
        resp.delete_cookie(COOKIE, path="/")
        return resp

    @api.post("/api/auth/logout-all")
    async def auth_logout_all():
        """Завершить все сессии на всех устройствах (требует входа — см. middleware)."""
        if auth.enabled:
            auth.rotate()
        resp = JSONResponse({"ok": True})
        resp.delete_cookie(COOKIE, path="/")
        return resp

    # ---------- статика ----------
    api.mount("/static", StaticFiles(directory=STATIC), name="static")

    @api.get("/", include_in_schema=False)
    async def index():
        return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})

    @api.get("/api/health", include_in_schema=False)
    async def health():
        """Для проверки хостингом при деплое и перезапусках: процесс жив и отвечает."""
        return {"ok": True, "version": __version__}

    @api.get("/sw.js", include_in_schema=False)
    async def service_worker():
        # Service Worker обязан лежать в корне, чтобы управлять всей страницей
        return FileResponse(STATIC / "sw.js", media_type="text/javascript",
                            headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"})

    @api.get("/manifest.webmanifest", include_in_schema=False)
    async def manifest():
        return FileResponse(STATIC / "manifest.webmanifest", media_type="application/manifest+json")

    # ---------- состояние ----------
    @api.get("/api/state")
    async def state():
        watches = [watch_view(app, w) for w in store.list_watches()]
        return {
            "server": {
                "version": __version__,
                "started_at": app.started_at.isoformat(),
                "now": utcnow().isoformat(),
                "interval_minutes": hub.settings.check_interval_minutes,
            },
            "telegram": app.telegram.status(),
            "push": {
                "public_key": app.push.public_key if app.push else None,
                "subscriptions": len(store.push_subs()),
                "last_error": app.push.last_error if app.push else None,
                "reports": hub.settings.push_reports,
            },
            "watches": watches,
        }

    @api.get("/api/stream")
    async def stream(request: Request):
        q = hub.broker.subscribe()

        async def gen():
            loop = asyncio.get_running_loop()
            deadline = loop.time() + SSE_MAX_SECONDS
            try:
                yield "retry: 3000\n\n"
                while loop.time() < deadline:
                    if await request.is_disconnected():
                        break
                    try:
                        data = await asyncio.wait_for(q.get(), timeout=20)
                        yield f"data: {data}\n\n"
                    except asyncio.TimeoutError:
                        yield ": ping\n\n"   # держим соединение живым
            finally:
                hub.broker.unsubscribe(q)

        return StreamingResponse(gen(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @api.get("/api/history/{watch_id}")
    async def history(watch_id: str, hours: float = 48, max_points: int = 0):
        """Для графика. max_points>0 — сжатие под ширину экрана (ступенчатая линия не меняется)."""
        since = utcnow() - timedelta(hours=hours) if hours > 0 else None
        mp = max(20, min(max_points, 5000)) if max_points > 0 else None
        return store.history(watch_id, since, mp)

    @api.get("/api/checks/{watch_id}")
    async def checks(watch_id: str, before: int | None = None, after: int | None = None, limit: int = 20):
        """Журнал проверок для таблицы — постранично, от новых к старым."""
        return store.checks_page(watch_id, before, after, max(1, min(limit, 100)))

    @api.get("/api/events")
    async def events(watch_id: str | None = None, kinds: str | None = None,
                     before: int | None = None, limit: int = 50):
        return store.events(watch_id, [k for k in (kinds or "").split(",") if k] or None,
                            before, max(1, min(limit, 200)))

    # ---------- поезда ----------
    @api.post("/api/watches/preview")
    async def preview(body: WatchIn):
        cfg = _validate_watch(body.model_dump())
        try:
            snap = await monitor.fetch_snapshot(cfg.url)
        except (FetchError, ParseError) as e:
            raise HTTPException(502, f"Сайт не ответил как ожидалось: {e}")
        st = WatchState(cfg.id, cars=snap.cars)
        cars = by_number(snap.cars.values())
        return {
            "id": cfg.id, "title": cfg.title, "train": cfg.train,
            "departure": cfg.departure.isoformat() if cfg.departure else None,
            "exists": store.get_watch(cfg.id) is not None,
            "status": snap.status.value, "train_info": snap.train_info, **split_info(snap.train_info),
            "cars": [car_view(c, st) for c in cars],
            "totals": {"free": sum(c.free_seats for c in cars), "cars": len(cars),
                       "cabins": sum(len(c.free_cabins) for c in cars)},
        }

    @api.post("/api/watches")
    async def add_watch(body: WatchIn):
        cfg = _validate_watch(body.model_dump())
        if store.get_watch(cfg.id):
            raise HTTPException(409, "Этот поезд уже отслеживается")
        if cfg.departure and cfg.departure <= utcnow():
            raise HTTPException(400, "Этот поезд уже отправился")
        store.upsert_watch(cfg)
        monitor.start(cfg)
        hub.state_changed()
        return watch_view(app, cfg)

    @api.patch("/api/watches/{watch_id}")
    async def patch_watch(watch_id: str, body: WatchPatch):
        cfg = store.get_watch(watch_id)
        if cfg is None:
            raise HTTPException(404, "Не найдено")
        data = cfg.model_dump()
        patch = body.model_dump(exclude_unset=True)
        data.update(patch)
        new = _validate_watch(data)
        store.upsert_watch(new)
        if "enabled" in patch:
            if new.enabled:
                monitor.start(new)
            else:
                monitor.stop(watch_id)
        hub.state_changed()
        return watch_view(app, new)

    @api.delete("/api/watches/{watch_id}")
    async def delete_watch(watch_id: str):
        monitor.stop(watch_id)
        store.delete_watch(watch_id)
        hub.state_changed()
        return {"ok": True}

    @api.post("/api/watches/{watch_id}/check")
    async def check_watch(watch_id: str):
        cfg = store.get_watch(watch_id)
        if cfg is None:
            raise HTTPException(404, "Не найдено")
        await monitor.check_now(watch_id)
        return watch_view(app, cfg)

    @api.post("/api/check-all")
    async def check_all():
        await monitor.check_all()
        return {"ok": True}

    # ---------- настройки ----------
    @api.get("/api/settings")
    async def get_settings():
        return settings_view(app)

    @api.put("/api/settings")
    async def put_settings(patch: dict):
        patch = {k: v for k, v in patch.items() if k in RuntimeSettings.model_fields}
        if "telegram_token" in patch and (patch["telegram_token"] is None or MASK in str(patch["telegram_token"])):
            patch.pop("telegram_token")
        if "telegram_chat_id" in patch:
            patch["telegram_chat_id"] = str(patch["telegram_chat_id"] or "").strip()
        try:
            hub.update_settings(patch)
        except ValidationError as e:
            raise HTTPException(400, "; ".join(f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors()))
        return settings_view(app)

    @api.post("/api/telegram/test")
    async def telegram_test(body: TelegramTestIn):
        token, chat, _ = hub.telegram_creds()
        token = (body.token if body.token and MASK not in body.token else token).strip()
        chat = (body.chat_id or chat).strip()
        if not token or not chat:
            raise HTTPException(400, "Укажите токен бота и chat_id")
        tg = TelegramClient(token, chat)
        try:
            me = await tg.call("getMe")
            await tg.send("✅ Тестовое сообщение от trainwatch: уведомления в Telegram работают.")
        except TelegramError as e:
            raise HTTPException(400, str(e))
        finally:
            await tg.aclose()
        return {"ok": True, "bot": me.get("username")}

    # ---------- Web Push ----------
    @api.post("/api/push/subscribe")
    async def push_subscribe(body: PushSubIn, request: Request):
        sub = body.subscription
        if not isinstance(sub.get("endpoint"), str) or not sub["endpoint"].startswith("https://") \
                or not isinstance(sub.get("keys"), dict):
            raise HTTPException(400, "Некорректная подписка")
        store.add_push_sub(sub, request.headers.get("user-agent"))
        hub.state_changed()
        return {"ok": True}

    @api.post("/api/push/unsubscribe")
    async def push_unsubscribe(body: dict):
        if body.get("endpoint"):
            store.remove_push_sub(body["endpoint"])
        hub.state_changed()
        return {"ok": True}

    @api.post("/api/push/test")
    async def push_test(body: dict | None = None):
        if not app.push:
            raise HTTPException(503, "Web Push недоступен")
        kind = (body or {}).get("kind", "test")
        payload = {
            "title": "🚨 Тест: так выглядит тревога" if kind == "alert" else "✅ trainwatch: push работает",
            "body": "Вагон 10 (Плацкартный): места 13–16" if kind == "alert" else "Уведомления в браузере настроены.",
            "kind": "alert" if kind == "alert" else "info",
            "tag": f"test:{utcnow().timestamp()}",
            "requireInteraction": kind == "alert",
        }
        res = await app.push.send(payload, ttl=600, urgency="high")
        if res["sent"] == 0:
            raise HTTPException(400, "Нет активных подписок или push-сервис браузера недоступен")
        return res

    @api.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        import logging
        logging.getLogger(__name__).exception("ошибка API %s", request.url.path)
        return JSONResponse({"detail": f"Внутренняя ошибка: {exc.__class__.__name__}"}, status_code=500)

    return api
