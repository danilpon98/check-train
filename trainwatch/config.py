"""Конфигурация.

AppConfig       — параметры запуска процесса (порт, папка данных); из env / config.yaml, меняются перезапуском.
RuntimeSettings — всё, что редактируется в веб-интерфейсе; хранится в SQLite.
WatchConfig     — отслеживаемый поезд; хранится в SQLite, добавляется из интерфейса.

config.yaml не обязателен: при первом запуске из него (если есть) импортируются поезда и настройки.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator

# Казахстан с 2024 г. живёт в едином поясе UTC+5, сайт отдаёт время с +05:00
KZ_TZ = timezone(timedelta(hours=5))
MIN_INTERVAL_MINUTES = 1
MAX_INTERVAL_MINUTES = 24 * 60


class WatchConfig(BaseModel):
    name: str | None = None
    url: str
    enabled: bool = True

    @field_validator("url")
    @classmethod
    def _check_url(cls, v: str) -> str:
        v = v.strip()
        u = urlparse(v)
        if u.scheme != "https" or u.netloc != "bilet.railways.kz" or "/car/search" not in u.path:
            raise ValueError("ожидается ссылка вида https://bilet.railways.kz/sale/default/car/search?...")
        q = {k: vals[0] for k, vals in parse_qs(u.query).items()}
        if not q.get("car_search_form[forwardDirection][train]") or not q.get("car_search_form[departureStation]"):
            raise ValueError("в ссылке нет номера поезда или станции — откройте страницу выбора вагона и скопируйте её адрес")
        return v

    @field_validator("name")
    @classmethod
    def _clean_name(cls, v: str | None) -> str | None:
        v = (v or "").strip()
        return v[:120] or None

    @property
    def query(self) -> dict[str, str]:
        return {k: vals[0] for k, vals in parse_qs(urlparse(self.url).query).items()}

    @property
    def train(self) -> str:
        return self.query.get("car_search_form[forwardDirection][train]", "?")

    @property
    def departure(self) -> datetime | None:
        raw = self.query.get("car_search_form[forwardDirection][departureTime]")
        if not raw:
            return None
        try:
            dt = datetime.fromisoformat(raw)
        except ValueError:
            return None
        return dt if dt.tzinfo else dt.replace(tzinfo=KZ_TZ)

    @property
    def id(self) -> str:
        q = self.query
        parts = [
            q.get("car_search_form[departureStation]", ""),
            q.get("car_search_form[arrivalStation]", ""),
            q.get("car_search_form[forwardDirection][departureTime]", ""),
            self.train,
        ]
        return re.sub(r"[^\w\-:]+", "_", "|".join(parts))

    @property
    def title(self) -> str:
        if self.name:
            return self.name
        dep = self.departure
        return f"Поезд {self.train}" + (f" {dep:%d.%m %H:%M}" if dep else "")


class RuntimeSettings(BaseModel):
    check_interval_minutes: float = Field(default=15, ge=MIN_INTERVAL_MINUTES, le=MAX_INTERVAL_MINUTES)
    jitter_seconds: int = Field(default=30, ge=0, le=600)
    retry_delay_seconds: int = Field(default=60, ge=10, le=3600)   # первая пауза после ошибки, дальше ×2
    failure_alert_threshold: int = Field(default=3, ge=1, le=100)
    confirm_empty_checks: int = Field(default=2, ge=1, le=10)
    # Telegram
    telegram_enabled: bool = True
    telegram_token: str = ""
    telegram_chat_id: str = ""
    telegram_commands: bool = True
    telegram_reports: bool = True   # False — в Telegram только тревоги, ошибки и «поезд ушёл», без отчётов
    quiet_reports: bool = True      # плановые отчёты в Telegram без звука; тревоги — всегда со звуком
    # Web Push
    push_reports: bool = False      # слать в браузер и плановые отчёты (тревоги и ошибки — всегда)


class AppConfig(BaseModel):
    data_dir: Path = Path("data")
    host: str = "127.0.0.1"
    port: int = 8765
    open_browser: bool = True
    request_timeout_seconds: int = 40
    web_password: str = ""           # если задан — HTTP Basic (логин любой)
    vapid_subject: str = "mailto:trainwatch@example.com"
    # переопределения из .env (имеют приоритет над настройками из интерфейса)
    env_telegram_token: str = ""
    env_telegram_chat_id: str = ""
    # содержимое config.yaml для первичного импорта
    seed_settings: dict = Field(default_factory=dict)
    seed_watches: list[dict] = Field(default_factory=list)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "state.sqlite3"


def on_public_hosting() -> bool:
    """Запущены на публичном хостинге (интерфейс доступен из интернета)."""
    return any(os.environ.get(k) for k in ("RAILWAY_PROJECT_ID", "RAILWAY_ENVIRONMENT", "RAILWAY_SERVICE_ID"))


_RUNTIME_KEYS = set(RuntimeSettings.model_fields)
# старые имена ключей config.yaml
_LEGACY = {"check_interval_seconds": ("check_interval_minutes", lambda v: max(1, v / 60))}


def load_app_config(path: str | os.PathLike = "config.yaml") -> AppConfig:
    load_dotenv()
    raw: dict = {}
    p = Path(path)
    if p.exists():
        raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}

    seed = {}
    for k, v in raw.items():
        if k in _LEGACY:
            k, conv = _LEGACY[k]
            v = conv(v)
        if k in _RUNTIME_KEYS:
            seed[k] = v

    env = os.environ
    cfg = AppConfig(
        data_dir=Path(env.get("DATA_DIR") or raw.get("data_dir") or "data"),
        host=env.get("WEB_HOST") or raw.get("web_host") or "127.0.0.1",
        # PORT задаёт хостинг (Railway, Render, Heroku…) — он важнее нашего WEB_PORT
        port=int(env.get("PORT") or env.get("WEB_PORT") or raw.get("web_port") or 8765),
        open_browser=(env.get("OPEN_BROWSER", "1") not in ("0", "false", "no")) and raw.get("open_browser", True),
        request_timeout_seconds=int(raw.get("request_timeout_seconds", 40)),
        web_password=env.get("WEB_PASSWORD", "").strip(),
        # контакт для push-сервисов (Apple требует настоящий): на Railway — адрес самого сервиса
        vapid_subject=env.get("VAPID_SUBJECT", "").strip()
        or (f"https://{env['RAILWAY_PUBLIC_DOMAIN']}" if env.get("RAILWAY_PUBLIC_DOMAIN") else "")
        or "mailto:trainwatch@example.com",
        env_telegram_token=env.get("TELEGRAM_BOT_TOKEN", "").strip(),
        env_telegram_chat_id=env.get("TELEGRAM_CHAT_ID", "").strip(),
        seed_settings=seed,
        seed_watches=list(raw.get("watches") or []),
    )
    return cfg
