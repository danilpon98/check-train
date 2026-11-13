import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from fastapi.testclient import TestClient

from trainwatch.app import App
from trainwatch.config import AppConfig, RuntimeSettings, WatchConfig
from trainwatch.hub import Hub
from trainwatch.models import Cabin, Car, PageStatus, Snapshot
from trainwatch.monitor import Monitor, apply_failure, apply_success, seats_word
from trainwatch.parser import ParseError, parse_page
from trainwatch.state import Store, WatchState
from trainwatch.web import create_app, split_info

FIX = Path(__file__).parent / "fixtures"
URL = (FIX.parent.parent / "config.example.yaml").read_text(encoding="utf-8").split('url: "')[1].split('"')[0]
NOW = datetime(2026, 11, 12, 12, 0, tzinfo=timezone.utc)
CARS_HTML = (FIX / "cars.html").read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def _isolate_from_local_env(monkeypatch):
    """Тесты не должны видеть локальный .env разработчика (пароль, токен Telegram и т.п.)."""
    import trainwatch.config
    monkeypatch.setattr(trainwatch.config, "load_dotenv", lambda *a, **k: False)
    for k in ("WEB_PASSWORD", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "WEB_PORT", "PORT", "DATA_DIR",
              "VAPID_SUBJECT", "RAILWAY_PROJECT_ID", "RAILWAY_ENVIRONMENT", "RAILWAY_SERVICE_ID", "RAILWAY_PUBLIC_DOMAIN"):
        monkeypatch.delenv(k, raising=False)


def free_up_cabin(html: str, car: str, cabin_index: int) -> str:
    soup = BeautifulSoup(html, "html.parser")
    cab = soup.find("tr", id=f"car-forward-{car}").select("div.cabin")[cabin_index]
    for seat in cab.select("div.seat"):
        seat["class"] = [c for c in seat["class"] if c not in ("reserved", "disabled")]
        del seat.find("input")["disabled"]
    return str(soup)


def car(num, seats=5, t="Купе", cabins=()):
    return Car("forward", num, t, "2К", seats, free_cabins=tuple(Cabin(tuple(c)) for c in cabins))


def snap(*cars):
    return Snapshot(PageStatus.OK, {c.key: c for c in cars})


def cfg():
    return WatchConfig(url=URL)


def run(st, s, confirm=2):
    return apply_success(cfg(), st, s, NOW, confirm, next_check_at=NOW + timedelta(minutes=15))


def htmls(out):
    return [e.html for e in out.events]


def alerts(out):
    return [e for e in out.events if e.kind == "alert"]


def report(out):
    (r,) = [e for e in out.events if e.kind == "report"]
    return r


# ---------------- parser
def test_parse_real_page():
    s = parse_page(CARS_HTML)
    assert s.status is PageStatus.OK
    assert sorted(c.number for c in s.cars.values()) == ["02", "04", "05", "06", "07", "08", "09", "10"]
    c02 = s.cars["forward:02"]
    assert (c02.car_type, c02.service_class, c02.free_seats) == ("Купе", "2К", 1)
    assert all(not c.free_cabins for c in s.cars.values())
    assert s.departure == datetime(2026, 11, 27, 23, 50, tzinfo=timezone(timedelta(hours=5)))
    assert "046Х" in s.train_info


def test_parse_seat_layout():
    s = parse_page(CARS_HTML)
    c10 = s.cars["forward:10"]
    assert len(c10.layout_cabins) == 9 and c10.layout_cabins[0] == ("1", "2", "3", "4")
    assert len(c10.layout_sides) == 9 and c10.layout_sides[0] == ("37", "38")
    assert len(c10.free_numbers) == c10.free_seats == 22
    c02 = s.cars["forward:02"]
    assert c02.layout_sides == () and c02.free_numbers == ("32",)
    assert Car.from_dict(c10.to_dict()) == c10


@pytest.mark.parametrize("car_no, idx, seats", [("10", 3, ("13", "14", "15", "16")),
                                                 ("04", 0, ("1", "2", "3", "4"))])
def test_parse_free_cabin(car_no, idx, seats):
    s = parse_page(free_up_cabin(CARS_HTML, car_no, idx))
    assert s.cars[f"forward:{car_no}"].free_cabins == (Cabin(seats),)


def test_parse_empty_page():
    s = parse_page((FIX / "empty.html").read_text(encoding="utf-8"))
    assert s.status is PageStatus.EMPTY and s.cars == {}


@pytest.mark.parametrize("html", ["", "<html><title>Access denied</title>" + " " * 2000 + "</html>"])
def test_parse_foreign_page_is_error_not_empty(html):
    with pytest.raises(ParseError):
        parse_page(html)


def test_split_info():
    d = split_info("046Х - АО «Пассажирские перевозки» - ТУРКЕСТАН → ПАВЛОДАР - Отправление: 27 нояб. 2026 г. 23:50 - Прибытие: 28 нояб. 2026 г. 07:21")
    assert d["route"] == "ТУРКЕСТАН → ПАВЛОДАР" and d["carrier"].startswith("АО")
    assert d["departure_text"] == "27 нояб. 2026 г. 23:50" and d["arrival_text"].startswith("28 нояб")


# ---------------- config
def test_config_from_url():
    w = cfg()
    assert w.train == "046Х"
    assert w.departure == datetime(2026, 11, 27, 23, 50, tzinfo=timezone(timedelta(hours=5)))
    assert RuntimeSettings().check_interval_minutes == 15


@pytest.mark.parametrize("url", ["https://example.com/x",
                                 "https://bilet.railways.kz/sale/default/car/search?foo=1"])
def test_config_rejects_bad_url(url):
    with pytest.raises(ValueError):
        WatchConfig(url=url)


# ---------------- logic
def test_baseline_then_regular_report():
    st = WatchState("w")
    out = run(st, snap(car("02", 1), car("04", 2)))
    assert [e.kind for e in out.events] == ["info"] and "Начинаю" in out.events[0].html
    assert st.baseline_numbers == {"02", "04"}

    out = run(st, snap(car("02", 1), car("04", 2)))
    assert alerts(out) == []
    r = report(out)
    assert "Новый вагон не появился" in r.html and "Свободной кабинки (4 места) нет" in r.html
    assert "02 Купе — <b>1 место</b>" in r.html and "Всего: <b>3 места</b> в 2 вагонах" in r.html
    assert r.body.startswith("новых вагонов нет")


def test_new_car_number_is_alert():
    st = WatchState("w")
    run(st, snap(car("02")))
    out = run(st, snap(car("02"), car("11", 36, t="Плацкартный")))
    assert [c.number for c in out.new_cars] == ["11"]
    (a,) = alerts(out)
    assert "ПОЯВИЛСЯ НОВЫЙ ВАГОН" in a.html and a.data["new_cars"] == ["11"]
    assert "11" in st.seen and "11" not in st.baseline_numbers


def test_known_car_reappearing_is_not_new():
    st = WatchState("w")
    run(st, snap(car("02"), car("03")))
    run(st, snap(car("02")))
    out = run(st, snap(car("02"), car("03")))
    assert out.new_cars == [] and alerts(out) == []


def test_free_cabin_alert_only_when_new():
    st = WatchState("w")
    plz = lambda cabins=(): car("10", t="Плацкартный", cabins=cabins)
    run(st, snap(plz()))
    out = run(st, snap(plz([("13", "14", "15", "16")])))
    (a,) = alerts(out)
    assert "ОСВОБОДИЛАСЬ КАБИНКА" in a.html and a.data["new_cabins"][0]["label"] == "13–16"
    out = run(st, snap(plz([("13", "14", "15", "16")])))
    assert alerts(out) == [] and "вагон <b>10</b>: места <b>13–16</b>" in report(out).html
    run(st, snap(plz()))
    assert alerts(run(st, snap(plz([("13", "14", "15", "16")]))))


def test_free_cabin_at_start_is_alerted():
    out = run(WatchState("w"), snap(car("04", cabins=[("1", "2", "3", "4")])))
    (a,) = alerts(out)
    assert "ЕСТЬ СВОБОДНАЯ КАБИНКА" in a.html


def test_spurious_empty_is_not_accepted():
    st = WatchState("w")
    run(st, snap(car("02", cabins=[("1", "2", "3", "4")])))
    out = run(st, Snapshot(PageStatus.EMPTY))
    assert not out.accepted and out.events == [] and st.cars
    assert alerts(run(st, snap(car("02", cabins=[("1", "2", "3", "4")])))) == []


def test_confirmed_empty_reports_no_seats():
    st = WatchState("w")
    run(st, snap(car("02")))
    run(st, Snapshot(PageStatus.EMPTY))
    out = run(st, Snapshot(PageStatus.EMPTY))
    assert st.cars == {} and "Свободных мест в поезде нет" in report(out).html


def test_failure_alert_once_and_recovery():
    st = WatchState("w")
    evs = []
    for _ in range(7):
        evs += apply_failure(cfg(), st, ParseError("x"), NOW, threshold=3).events
    assert len(evs) == 1 and evs[0].kind == "error" and "3 раз подряд" in evs[0].html
    st.baseline_done = True
    assert run(st, snap(car("02"))).events[0].kind == "recovered"


def test_plural():
    assert [seats_word(n) for n in (1, 2, 5, 11, 21, 22)] == [
        "1 место", "2 места", "5 мест", "11 мест", "21 место", "22 места"]


# ---------------- hub: каналы
def test_telegram_outbox_respects_settings(tmp_path):
    store = Store(tmp_path / "db.sqlite3")
    hub = Hub(store, AppConfig(data_dir=tmp_path))
    st = WatchState("w")
    run(st, snap(car("02")))
    out = run(st, snap(car("02"), car("11")))
    assert hub.telegram_outbox(out.events) == []          # Telegram не настроен — очередь не копится
    hub.update_settings({"telegram_token": "1:x", "telegram_chat_id": "5"})
    msgs = hub.telegram_outbox(out.events)
    assert [silent for _, silent in msgs] == [False, True]   # тревога со звуком, отчёт тихо
    hub.update_settings({"quiet_reports": False})
    assert [silent for _, silent in hub.telegram_outbox(out.events)] == [False, False]
    # отчёты выключены — уходит только тревога
    hub.update_settings({"telegram_reports": False})
    assert [html for html, _ in hub.telegram_outbox(out.events)] == [out.events[0].html]
    assert "ПОЯВИЛСЯ НОВЫЙ ВАГОН" in out.events[0].html
    # ошибки и «снова работает» по-прежнему приходят
    err = apply_failure(cfg(), WatchState("w2"), ParseError("x"), NOW, threshold=1).events
    assert len(hub.telegram_outbox(err)) == 1
    st2 = WatchState("w3")
    run(st2, snap(car("02")))                       # «Начинаю отслеживание» — это отчёт, не уходит
    assert hub.telegram_outbox(run(WatchState("w4"), snap(car("02"))).events) == []


def test_env_telegram_overrides_ui(tmp_path):
    hub = Hub(Store(tmp_path / "db.sqlite3"), AppConfig(data_dir=tmp_path, env_telegram_token="9:env"))
    hub.update_settings({"telegram_token": "1:ui", "telegram_chat_id": "5"})
    assert hub.telegram_creds() == ("9:env", "5", "env")


# ---------------- интеграция: веб-API поверх реального приложения
class FakeSite:
    def __init__(self):
        self.pages = [CARS_HTML]
        self.calls = 0

    async def __call__(self, url):
        self.calls += 1
        return self.pages[min(self.calls - 1, len(self.pages) - 1)]


@pytest.fixture
def client(tmp_path):
    site = FakeSite()
    app = App(AppConfig(data_dir=tmp_path, open_browser=False), fetch=site)
    with TestClient(create_app(app)) as c:
        c.app_obj, c.site = app, site
        yield c
    app.store.close()


def test_web_index_and_static(client):
    r = client.get("/")
    assert r.status_code == 200 and "trainwatch" in r.text
    assert '<div id="app">' in r.text                     # собранное Vue-приложение
    assert client.get("/sw.js").headers["service-worker-allowed"] == "/"
    assert client.get("/manifest.webmanifest").json()["short_name"] == "trainwatch"
    # все ассеты, на которые ссылается index.html, реально отдаются
    import re
    assets = re.findall(r'(?:src|href)="(/static/[^"]+)"', r.text)
    assert any(a.endswith(".js") for a in assets) and any(a.endswith(".css") for a in assets)
    for a in assets:
        assert client.get(a).status_code == 200, a


def test_web_watch_lifecycle(client):
    r = client.post("/api/watches/preview", json={"url": URL})
    assert r.status_code == 200 and r.json()["totals"]["cars"] == 8 and not r.json()["exists"]
    assert client.post("/api/watches/preview", json={"url": "https://example.com"}).status_code == 400

    r = client.post("/api/watches", json={"url": URL, "name": "Домой"})
    assert r.status_code == 200
    wid = r.json()["id"]
    assert client.post("/api/watches", json={"url": URL}).status_code == 409

    client.site.pages = [CARS_HTML, CARS_HTML, free_up_cabin(CARS_HTML, "10", 3)]
    client.app_obj.monitor.stop(wid)        # фоновая задача не мешает детерминированному тесту
    client.site.calls = 0
    for _ in range(3):
        assert client.post(f"/api/watches/{wid}/check").status_code == 200

    st = client.get("/api/state").json()
    (w,) = st["watches"]
    assert w["name"] == "Домой" and w["route"] == "ТҮРКІСТАН → ПАВЛОДАР"
    assert w["totals"]["cabins"] == 1 and w["totals"]["known"] == 8
    c10 = next(c for c in w["cars"] if c["number"] == "10")
    assert c10["free_cabins"][0]["seats"] == ["13", "14", "15", "16"] and len(c10["layout_cabins"]) == 9

    kinds = [e["kind"] for e in client.get("/api/events").json()]
    assert "alert" in kinds and "report" in kinds and "info" in kinds
    assert [e["kind"] for e in client.get("/api/events?kinds=alert").json()] == ["alert"]
    hist = client.get(f"/api/history/{wid}?hours=0").json()
    assert len(hist) == 3 and hist[-1]["cabins"] == 1

    assert client.patch(f"/api/watches/{wid}", json={"enabled": False}).json()["status"] == "paused"
    assert client.delete(f"/api/watches/{wid}").status_code == 200
    assert client.get("/api/state").json()["watches"] == []
    assert client.get(f"/api/history/{wid}?hours=0").json() == []


def test_web_settings(client):
    s = client.get("/api/settings").json()
    assert s["check_interval_minutes"] == 15 and "telegram_token" not in s
    r = client.put("/api/settings", json={"check_interval_minutes": 10, "telegram_token": "123:secretTOKEN"})
    assert r.status_code == 200
    s = r.json()
    assert s["check_interval_minutes"] == 10 and s["telegram_token_masked"].endswith("OKEN")
    assert "secret" not in str(s)
    # маска обратно не затирает токен
    client.put("/api/settings", json={"telegram_token": s["telegram_token_masked"]})
    assert client.app_obj.hub.settings.telegram_token == "123:secretTOKEN"
    assert client.put("/api/settings", json={"check_interval_minutes": 0}).status_code == 400
    # настройки пережили перезапуск
    assert client.app_obj.store.load_settings().check_interval_minutes == 10


def test_web_push_subscriptions(client):
    st = client.get("/api/state").json()
    assert len(st["push"]["public_key"]) == 87          # P-256 uncompressed point, base64url
    assert client.post("/api/push/subscribe", json={"subscription": {"endpoint": "http://x"}}).status_code == 400
    sub = {"endpoint": "https://push.example/abc", "keys": {"p256dh": "x", "auth": "y"}}
    assert client.post("/api/push/subscribe", json={"subscription": sub}).status_code == 200
    assert client.get("/api/state").json()["push"]["subscriptions"] == 1
    client.post("/api/push/unsubscribe", json={"endpoint": sub["endpoint"]})
    assert client.get("/api/state").json()["push"]["subscriptions"] == 0


def test_push_sent_only_for_important_events(tmp_path):
    sent = []

    class FakePush:
        async def send_event(self, e):
            sent.append(e.kind)

    async def go():
        hub = Hub(Store(tmp_path / "db.sqlite3"), AppConfig(data_dir=tmp_path))
        hub.push = FakePush()
        st = WatchState("w")
        run(st, snap(car("02")))
        out = run(st, snap(car("02"), car("11")))
        hub.publish(out.events)
        await asyncio.sleep(0)
        hub.update_settings({"push_reports": True})
        hub.publish(out.events)
        await asyncio.sleep(0)

    asyncio.run(go())
    assert sent == ["alert", "alert", "report"]


def test_seed_import_from_config_yaml(tmp_path):
    app = App(AppConfig(data_dir=tmp_path, seed_watches=[{"url": URL}, {"url": "bad"}],
                        seed_settings={"check_interval_minutes": 20}))
    assert [w.train for w in app.store.list_watches()] == ["046Х"]
    assert app.hub.settings.check_interval_minutes == 20
    app.store.close()


def test_interval_change_and_manual_check_reschedule(tmp_path):
    calls = []

    async def fake_fetch(url):
        calls.append(1)
        return CARS_HTML

    async def go():
        store = Store(tmp_path / "db.sqlite3")
        hub = Hub(store, AppConfig(data_dir=tmp_path))
        m = Monitor(store, fake_fetch, hub)
        w = cfg()
        store.upsert_watch(w)
        delays = iter([1000.0, 0.01, 1000.0, 1000.0])
        m._regular_delay = lambda: next(delays)
        m.start(w)
        for _ in range(200):
            await asyncio.sleep(0.01)
            if calls:
                break
        m.interval_changed()      # спящий цикл пересчитывает паузу (0.01 с) и проверяет снова
        for _ in range(300):
            await asyncio.sleep(0.01)
            if len(calls) >= 2:
                break
        assert len(calls) == 2
        await m.check_now(w.id)   # ручная проверка: следующая плановая — через интервал от неё
        await asyncio.sleep(0.1)
        assert len(calls) == 3 and m.is_running(w.id)
        m.stop(w.id)

    asyncio.run(go())


# ---------------- фронтенд и Web Push
def test_service_worker_syntax():
    """sw.js не проходит через сборщик — проверяем его синтаксис отдельно (Vue-код проверяет vue-tsc)."""
    import shutil
    import subprocess
    node = shutil.which("node")
    if not node:
        pytest.skip("node не установлен")
    path = Path(__file__).parent.parent / "trainwatch" / "static" / "sw.js"
    r = subprocess.run([node, "--check", str(path)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_webpush_real_encryption_and_vapid(tmp_path):
    """Отправка в локальный «push-сервис»: payload зашифрован (aes128gcm), есть VAPID-подпись."""
    import base64
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    from trainwatch.webpush import PushService

    got = {}

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            got["headers"] = dict(self.headers)
            got["body"] = self.rfile.read(int(self.headers["Content-Length"]))
            self.send_response(201 if not got.get("gone") else 410)
            self.end_headers()

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    b64 = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=").decode()
    key = ec.generate_private_key(ec.SECP256R1())
    sub = {
        "endpoint": f"http://127.0.0.1:{srv.server_port}/push/abc",
        "keys": {"p256dh": b64(key.public_key().public_bytes(serialization.Encoding.X962,
                                                              serialization.PublicFormat.UncompressedPoint)),
                 "auth": b64(b"0123456789abcdef")},
    }
    store = Store(tmp_path / "db.sqlite3")
    store.add_push_sub(sub, "test")
    push = PushService(store, tmp_path, "mailto:test@example.com")
    try:
        res = asyncio.run(push.send({"title": "🚨 тест", "body": "вагон 10"}, urgency="high"))
        assert res == {"sent": 1, "failed": 0}
        h = {k.lower(): v for k, v in got["headers"].items()}
        assert h["content-encoding"] == "aes128gcm" and h["urgency"] == "high"
        assert h["authorization"].lower().startswith("vapid t=") and push.public_key in h["authorization"]
        assert "вагон".encode() not in got["body"]          # payload не в открытом виде
        # 410 Gone — подписка удаляется
        got["gone"] = True
        asyncio.run(push.send({"title": "x"}))
        assert store.push_subs() == []
        # ключи сохраняются между перезапусками
        assert PushService(store, tmp_path, "mailto:t@e.com").public_key == push.public_key
    finally:
        srv.shutdown()


# ---------------- история: сжатие для графика и журнал для таблицы
from trainwatch.history import bucket, collapse_runs, downsample


def _hist(values, start=NOW, step_min=15):
    """values: число мест, None — неудачная проверка, (мест, кабинок) — с кабинкой."""
    out = []
    for i, v in enumerate(values):
        at = (start + timedelta(minutes=step_min * i)).isoformat()
        if v is None:
            out.append({"at": at, "ok": 0, "total_free": None, "cars": None, "cabins": None, "error": "HTTP 503"})
        else:
            free, cab = v if isinstance(v, tuple) else (v, 0)
            out.append({"at": at, "ok": 1, "total_free": free, "cars": 8, "cabins": cab, "error": None})
    return out


def _step_line(rows):
    """Значение ступенчатой линии в каждый момент исходных проверок."""
    pts = [(r["at"], r["total_free"]) for r in rows if r["ok"]]
    return lambda at: [v for t, v in pts if t <= at][-1]


def test_collapse_runs_is_lossless_for_step_chart():
    rows = _hist([75] * 50 + [80] * 30 + [None] * 5 + [80] * 40 + [72])
    small = collapse_runs(rows)
    assert len(small) < 15
    assert small[0] is rows[0] and small[-1] is rows[-1]
    full, comp = _step_line(rows), _step_line(small)
    assert all(full(r["at"]) == comp(r["at"]) for r in rows if r["ok"])   # линия та же
    assert sum(1 for r in small if not r["ok"]) == 5                        # ни одна ошибка не потерялась


def test_bucket_lone_cabin_and_failure_in_same_interval_both_survive():
    vals = [70 + (i % 7) for i in range(3000)]
    vals[1500] = (71, 1)
    vals[1502] = None                                  # в том же интервале, что и кабинка
    out = downsample(_hist(vals, step_min=1), 300)
    assert sum(1 for r in out if r["ok"] and r["cabins"]) == 1
    assert sum(1 for r in out if not r["ok"]) == 1


def test_bucket_keeps_cabins_and_failures():
    vals = [70 + (i % 7) for i in range(3000)]       # «шумные» данные: схлопывать нечего
    vals[1234] = (71, 1)
    vals[2500] = None
    rows = _hist(vals, step_min=1)
    out = downsample(rows, 200)
    assert len(out) <= 200 + 2
    assert any(r["cabins"] for r in out if r["ok"])                 # момент с кабинкой сохранён
    assert any(not r["ok"] for r in out)                             # неудачная проверка сохранена
    assert out[0]["at"] == rows[0]["at"] and out[-1]["at"] == rows[-1]["at"]
    assert [r["at"] for r in out] == sorted(r["at"] for r in out)    # порядок по времени


def test_bucket_noop_when_small():
    rows = _hist([1, 2, 3])
    assert bucket(rows, 100) == rows


def test_checks_page_cursor(tmp_path):
    store = Store(tmp_path / "db.sqlite3")
    st = WatchState("w")
    for i in range(45):
        store.save_watch(st, check={"at": (NOW + timedelta(minutes=i)).isoformat(), "ok": True,
                                    "total_free": i, "cars": 8, "cabins": 0})
    p1 = store.checks_page("w", limit=20)
    assert [r["total_free"] for r in p1[:3]] == [44, 43, 42]           # от новых к старым
    p2 = store.checks_page("w", before_id=p1[-1]["id"], limit=20)
    p3 = store.checks_page("w", before_id=p2[-1]["id"], limit=20)
    assert len(p1) == 20 and len(p2) == 20 and len(p3) == 5
    assert len({r["id"] for r in p1 + p2 + p3}) == 45                   # без пропусков и дублей
    store.save_watch(st, check={"at": (NOW + timedelta(hours=2)).isoformat(), "ok": False, "error": "x"})
    new = store.checks_page("w", after_id=p1[0]["id"])
    assert len(new) == 1 and new[0]["ok"] == 0                          # только новые


def test_web_history_and_checks_endpoints(client):
    # поезд кладём прямо в базу: POST /api/watches запустил бы фоновую проверку,
    # и она могла бы успеть дописать в историю лишнюю строку (гонка → плавающий тест)
    store = client.app_obj.store
    w = WatchConfig(url=URL)
    store.upsert_watch(w)
    wid = w.id
    st = store.load_watch(wid)
    for i in range(300):
        store.save_watch(st, check={"at": (NOW + timedelta(minutes=i)).isoformat(), "ok": True,
                                    "total_free": 70 + (i // 50), "cars": 8, "cabins": 0})
    full = client.get(f"/api/history/{wid}?hours=0").json()
    small = client.get(f"/api/history/{wid}?hours=0&max_points=100").json()
    assert len(full) == 300 and len(small) <= 15                        # 6 ступеней → ~12 точек
    page = client.get(f"/api/checks/{wid}?limit=20").json()
    assert len(page) == 20 and page[0]["id"] > page[-1]["id"]
    nxt = client.get(f"/api/checks/{wid}?limit=20&before={page[-1]['id']}").json()
    assert nxt[0]["id"] < page[-1]["id"]
    assert client.get(f"/api/checks/{wid}?limit=1000").status_code == 200
    assert len(client.get(f"/api/checks/{wid}?limit=1000").json()) == 100   # лимит страницы


# ---------------- развёртывание на хостинге (Railway)
from trainwatch.config import load_app_config


def test_port_from_hosting_overrides(monkeypatch, tmp_path):
    monkeypatch.setenv("WEB_PORT", "8765")
    monkeypatch.setenv("PORT", "4321")
    assert load_app_config(tmp_path / "none.yaml").port == 4321
    monkeypatch.delenv("PORT")
    assert load_app_config(tmp_path / "none.yaml").port == 8765


def test_vapid_subject_uses_public_domain(monkeypatch, tmp_path):
    monkeypatch.delenv("VAPID_SUBJECT", raising=False)
    monkeypatch.setenv("RAILWAY_PUBLIC_DOMAIN", "trainwatch-production.up.railway.app")
    assert load_app_config(tmp_path / "none.yaml").vapid_subject == "https://trainwatch-production.up.railway.app"


def test_refuses_to_start_publicly_without_password(monkeypatch, tmp_path, capsys):
    from trainwatch.__main__ import cmd_run
    monkeypatch.setenv("RAILWAY_PROJECT_ID", "p1")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("WEB_PASSWORD", raising=False)
    with pytest.raises(SystemExit) as e:
        cmd_run(str(tmp_path / "none.yaml"))
    assert e.value.code == 2 and "WEB_PASSWORD" in capsys.readouterr().err


# ---------------- вход по паролю и сессии
from trainwatch.auth import COOKIE, MAX_FAILURES, REMEMBER_SECONDS, SHORT_SECONDS, Auth


class Clock:
    def __init__(self, t=1_800_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


def test_session_token_lifetime_and_renewal(tmp_path):
    clock = Clock()
    a = Auth(tmp_path, "s3cret", clock=clock)
    tok, max_age = a.issue(remember=True)
    assert max_age == REMEMBER_SECONDS and a.verify(tok)["rem"] is True
    assert not a.should_renew(a.verify(tok))
    clock.t += 2 * 86400                                   # через 2 дня — пора продлить
    assert a.should_renew(a.verify(tok))
    clock.t += REMEMBER_SECONDS                            # через 30+ дней — истёк
    assert a.verify(tok) is None

    short, max_age = a.issue(remember=False)
    assert max_age is None                                 # cookie до закрытия браузера
    clock.t += SHORT_SECONDS + 1
    assert a.verify(short) is None                         # и не дольше 12 часов


def test_session_invalidated_by_tamper_rotate_and_password_change(tmp_path):
    a = Auth(tmp_path, "s3cret")
    tok, _ = a.issue(True)
    body, sig = tok.rsplit(".", 1)
    assert a.verify(body + "x." + sig) is None             # подделка
    assert Auth(tmp_path, "s3cret").verify(tok)            # перезапуск сервиса — сессия жива
    assert Auth(tmp_path, "new-password").verify(tok) is None   # сменили пароль — все вышли
    a.rotate()
    assert a.verify(tok) is None                           # «выйти на всех устройствах»


def test_bruteforce_lockout(tmp_path):
    clock = Clock()
    a = Auth(tmp_path, "s3cret", clock=clock)
    for _ in range(MAX_FAILURES):
        assert a.retry_after("1.2.3.4") is None
        a.record_failure("1.2.3.4")
    assert a.retry_after("1.2.3.4") > 0
    assert a.retry_after("5.6.7.8") is None                # другой адрес не затронут
    clock.t += 15 * 60 + 1
    assert a.retry_after("1.2.3.4") is None                # блокировка снята


@pytest.fixture
def secured(tmp_path):
    app = App(AppConfig(data_dir=tmp_path, open_browser=False, web_password="s3cret"), fetch=FakeSite())
    with TestClient(create_app(app), base_url="https://tw.example") as c:
        c.app_obj = app
        yield c
    app.store.close()


def test_login_page_flow(secured):
    c = secured
    # страница и её код открываются, данные — нет
    assert c.get("/").status_code == 200
    assert c.get("/api/auth/status").json() == {"required": True, "authenticated": False, "remember_days": 30}
    for path in ("/api/state", "/api/settings", "/api/stream", "/api/events", "/api/docs"):
        assert c.get(path).status_code == 401, path
    # файлы, которые браузер берёт без cookie, — без входа
    assert c.get("/api/health").json()["ok"] is True
    for path in ("/sw.js", "/manifest.webmanifest", "/static/icon-192.png"):
        assert c.get(path).status_code == 200, path

    r = c.post("/api/auth/login", json={"password": "wrong"})
    assert r.status_code == 401 and "Неверный пароль" in r.json()["detail"]

    r = c.post("/api/auth/login", json={"password": "s3cret", "remember": True})
    assert r.status_code == 200
    cookie = r.headers["set-cookie"]
    assert COOKIE in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie
    assert "Secure" in cookie and f"Max-Age={REMEMBER_SECONDS}" in cookie
    assert c.get("/api/state").status_code == 200
    assert c.get("/api/auth/status").json()["authenticated"] is True

    c.post("/api/auth/logout")
    assert c.get("/api/state").status_code == 401


def test_login_without_remember_sets_browser_session_cookie(secured):
    r = secured.post("/api/auth/login", json={"password": "s3cret", "remember": False})
    assert "Max-Age" not in r.headers["set-cookie"] and "expires" not in r.headers["set-cookie"].lower()


def test_logout_everywhere(secured, tmp_path):
    c = secured
    c.post("/api/auth/login", json={"password": "s3cret"})
    other = c.cookies.get(COOKIE)                          # «другое устройство» с той же сессией
    assert c.post("/api/auth/logout-all").status_code == 200
    c.cookies.set(COOKIE, other)
    assert c.get("/api/state").status_code == 401


def test_login_bruteforce_returns_429(secured):
    c = secured
    for _ in range(MAX_FAILURES):
        c.post("/api/auth/login", json={"password": "nope"})
    r = c.post("/api/auth/login", json={"password": "s3cret"})   # даже верный — пока заблокировано
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0


def test_cross_site_requests_rejected(secured):
    c = secured
    c.post("/api/auth/login", json={"password": "s3cret"})
    evil = {"Origin": "https://evil.example"}
    assert c.put("/api/settings", json={"check_interval_minutes": 1}, headers=evil).status_code == 403
    assert c.post("/api/auth/login", json={"password": "s3cret"}, headers=evil).status_code == 403
    ok = {"Origin": "https://tw.example"}
    assert c.put("/api/settings", json={"check_interval_minutes": 20}, headers=ok).status_code == 200


def test_no_password_means_open_access(client):
    assert client.get("/api/auth/status").json()["required"] is False
    assert client.get("/api/state").status_code == 200
