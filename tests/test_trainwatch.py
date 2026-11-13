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
    assert client.get("/sw.js").headers["service-worker-allowed"] == "/"
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/manifest.webmanifest").json()["short_name"] == "trainwatch"


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
@pytest.mark.parametrize("name", ["app.js", "sw.js"])
def test_frontend_js_syntax(name):
    import shutil
    import subprocess
    node = shutil.which("node")
    if not node:
        pytest.skip("node не установлен")
    path = Path(__file__).parent.parent / "trainwatch" / "static" / name
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
