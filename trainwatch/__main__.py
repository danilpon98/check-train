from __future__ import annotations

import argparse
import asyncio
import logging
import logging.handlers
import os
import socket
import sys
import webbrowser
from pathlib import Path

from .config import WatchConfig, load_app_config, on_public_hosting
from .fetcher import Fetcher
from .monitor import by_number
from .parser import parse_page
from .state import Store

log = logging.getLogger("trainwatch")


def setup_logging(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    root = logging.getLogger()
    root.setLevel(os.environ.get("LOG_LEVEL", "INFO"))
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    fh = logging.handlers.RotatingFileHandler(
        data_dir / "trainwatch.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8"
    )
    fh.setFormatter(fmt)
    root.handlers[:] = [sh, fh]
    logging.getLogger("httpx").setLevel(logging.WARNING)  # иначе в лог попадёт URL с токеном бота


def port_busy(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return False
        except OSError:
            return True


def cmd_run(config: str) -> None:
    from .app import App

    cfg = load_app_config(config)
    if on_public_hosting() and not cfg.web_password:
        # без пароля любой, кто узнает адрес, сможет менять поезда и настройки (в т.ч. Telegram)
        print("ОШИБКА: сервис запущен на публичном хостинге без пароля.\n"
              "Задайте переменную WEB_PASSWORD (Railway → сервис → Variables) и перезапустите.", file=sys.stderr)
        sys.exit(2)
    if port_busy(cfg.host, cfg.port):
        url = f"http://localhost:{cfg.port}/"
        print(f"Порт {cfg.port} занят — похоже, trainwatch уже запущен. Открываю {url}")
        if cfg.open_browser:
            webbrowser.open(url)
        return
    setup_logging(cfg.data_dir)
    app = App(cfg)
    asyncio.run(app.run())


async def cmd_check(config: str, urls: list[str]) -> None:
    """Разовая проверка без уведомлений: указанных ссылок или всех поездов из базы."""
    cfg = load_app_config(config)
    if urls:
        watches = [WatchConfig(url=u) for u in urls]
    else:
        store = Store(cfg.db_path)
        watches = store.list_watches()
        store.close()
        if not watches:
            print("В базе нет поездов. Укажите ссылку: python -m trainwatch check \"https://bilet.railways.kz/...\"")
    fetcher = Fetcher(cfg.request_timeout_seconds)
    try:
        for w in watches:
            print(f"\n=== {w.title}\n{w.url}")
            try:
                snap = parse_page(await fetcher.get(w.url))
            except Exception as e:
                print(f"ОШИБКА: {e}")
                continue
            print(f"Статус: {snap.status.value}; {snap.train_info or ''}")
            for c in by_number(snap.cars.values()):
                cabins = ", ".join(cab.label + ("(инв)" if cab.for_disabled else "") for cab in c.free_cabins)
                print(f"  вагон {c.number:>3} {c.car_type:<12} {c.service_class:<4} мест: {c.free_seats:<3} "
                      f"{c.price or '':<14} свободные кабинки: {cabins or 'нет'}")
            if not snap.cars:
                print("  вагонов нет")
    finally:
        await fetcher.aclose()


def main() -> None:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(prog="trainwatch", description="Отслеживание вагонов на bilet.railways.kz")
    p.add_argument("-c", "--config", default=os.environ.get("TRAINWATCH_CONFIG", "config.yaml"),
                   help="необязательный config.yaml (импорт поездов и настроек при первом запуске)")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("run", help="запустить сервис с веб-интерфейсом (по умолчанию)")
    chk = sub.add_parser("check", help="разовая проверка без уведомлений")
    chk.add_argument("urls", nargs="*")
    a = p.parse_args()
    try:
        if a.cmd == "check":
            asyncio.run(cmd_check(a.config, a.urls))
        else:
            cmd_run(a.config)
    except KeyboardInterrupt:
        print("Остановлено.")


if __name__ == "__main__":
    main()
