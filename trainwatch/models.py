from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class PageStatus(str, Enum):
    OK = "ok"          # страница с вагонами
    EMPTY = "empty"    # сайт явно сказал «поиск не дал результатов»


@dataclass(frozen=True)
class Cabin:
    """Кабинка (div.cabin): 4 основных места — купе или отсек плацкарта (без боковых)."""
    seats: tuple[str, ...]
    for_disabled: bool = False   # места для маломобильных пассажиров (data-inv-place="1")

    @property
    def label(self) -> str:
        return f"{self.seats[0]}–{self.seats[-1]}" if self.seats else "?"

    def to_dict(self) -> dict:
        return {"seats": list(self.seats), "for_disabled": self.for_disabled}

    @classmethod
    def from_dict(cls, d: dict) -> "Cabin":
        return cls(tuple(d["seats"]), d.get("for_disabled", False))


@dataclass(frozen=True)
class Car:
    direction: str
    number: str
    car_type: str
    service_class: str
    free_seats: int
    price: str | None = None
    signs: str = ""
    free_cabins: tuple[Cabin, ...] = ()   # кабинки, где свободны все 4 места
    # схема вагона для веб-интерфейса
    layout_cabins: tuple[tuple[str, ...], ...] = ()   # номера мест по кабинкам (div.cabin)
    layout_sides: tuple[tuple[str, ...], ...] = ()    # боковые места плацкарта (div.half-cabin), i-я пара напротив i-й кабинки
    free_numbers: tuple[str, ...] = ()                # номера всех свободных мест

    @property
    def key(self) -> str:
        return f"{self.direction}:{self.number}"

    def cabin_keys(self) -> set[str]:
        return {f"{self.key}:{c.label}" for c in self.free_cabins}

    def to_dict(self) -> dict:
        return {
            "direction": self.direction, "number": self.number, "car_type": self.car_type,
            "service_class": self.service_class, "free_seats": self.free_seats, "price": self.price,
            "signs": self.signs, "free_cabins": [c.to_dict() for c in self.free_cabins],
            "layout_cabins": [list(x) for x in self.layout_cabins],
            "layout_sides": [list(x) for x in self.layout_sides],
            "free_numbers": list(self.free_numbers),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Car":
        d = dict(d)
        d["free_cabins"] = tuple(Cabin.from_dict(c) for c in d.get("free_cabins", []))
        d["layout_cabins"] = tuple(tuple(x) for x in d.get("layout_cabins", []))
        d["layout_sides"] = tuple(tuple(x) for x in d.get("layout_sides", []))
        d["free_numbers"] = tuple(d.get("free_numbers", []))
        return cls(**d)


@dataclass
class Snapshot:
    status: PageStatus
    cars: dict[str, Car] = field(default_factory=dict)
    train_info: str | None = None
    departure: datetime | None = None
