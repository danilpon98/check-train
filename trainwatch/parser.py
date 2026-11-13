"""Разбор HTML-страницы bilet.railways.kz/sale/default/car/search.

Опираемся на data-атрибуты (они не зависят от языка интерфейса):
  <div class="ticket" data-direction=.. data-car-number=.. data-car-type=.. ...>
  <tr id="car-{direction}-{number}"> ... <div class="seat ... reserved disabled"> ...

Три исхода:
  * OK: есть #car-list, вагоны разобраны;
  * EMPTY: страница сайта с предупреждением «поиск не дал результатов»;
  * ParseError: что угодно другое (WAF, техработы, смена вёрстки). Это НЕ «0 вагонов».
"""
from __future__ import annotations

import re
from datetime import datetime

from bs4 import BeautifulSoup, Tag

from .models import Cabin, Car, PageStatus, Snapshot


class ParseError(Exception):
    pass


_WS = re.compile(r"\s+")
_INT = re.compile(r"\d+")


def _text(el: Tag | None) -> str:
    return _WS.sub(" ", el.get_text(" ", strip=True)).strip() if el else ""


CABIN_SIZE = 4


def _seat_is_free(seat: Tag) -> bool:
    classes = seat.get("class", [])
    if "reserved" in classes or "disabled" in classes:
        return False
    inp = seat.find("input")
    return not (inp is not None and inp.has_attr("disabled"))


def _seat_number(seat: Tag) -> str:
    inp = seat.find("input")
    if inp is not None and inp.get("value"):
        return inp["value"].strip()
    return _text(seat.find("label"))


def _count_free_seats_on_map(row: Tag) -> int:
    return sum(1 for seat in row.select("div.seat") if _seat_is_free(seat))


def _free_cabins(row: Tag | None) -> tuple[Cabin, ...]:
    """Кабинки (div.cabin), где свободны все 4 места. И в купе, и в плацкарте div.cabin —
    это 4 основных места; боковые места плацкарта лежат отдельно в div.half-cabins."""
    if row is None:
        return ()
    result = []
    for cabin in row.select("div.cabin"):
        seats = cabin.select("div.seat")
        if len(seats) >= CABIN_SIZE and all(_seat_is_free(s) for s in seats):
            result.append(Cabin(
                seats=tuple(_seat_number(s) for s in seats),
                for_disabled=any(s.get("data-inv-place") == "1" for s in seats),
            ))
    return tuple(result)


def _layout(row: Tag | None) -> tuple[tuple, tuple, tuple]:
    if row is None:
        return (), (), ()
    cabins = tuple(tuple(_seat_number(s) for s in cab.select("div.seat")) for cab in row.select("div.cabin"))
    sides = tuple(tuple(_seat_number(s) for s in hc.select("div.seat")) for hc in row.select("div.half-cabin"))
    free = tuple(_seat_number(s) for s in row.select("div.seat") if _seat_is_free(s))
    return cabins, sides, free


def _free_seats(soup: BeautifulSoup, ticket: Tag, direction: str, number: str) -> int:
    # 1) число из шапки «орындар N» / «мест N» — то, что показывает сам сайт
    beds = _INT.search(_text(ticket.select_one(".ticket__beds")))
    if beds:
        return int(beds.group())
    # 2) запасной вариант — посчитать по схеме вагона
    row = soup.find("tr", id=f"car-{direction}-{number}")
    if row is not None:
        return _count_free_seats_on_map(row)
    raise ParseError(f"не удалось определить число мест в вагоне {number}")


def parse_page(html: str) -> Snapshot:
    if not html or len(html) < 1000:
        raise ParseError("пустой или слишком короткий ответ")

    soup = BeautifulSoup(html, "html.parser")
    is_site_page = soup.find("form", attrs={"name": "route_search_form"}) is not None
    car_list = soup.find(id="car-list")

    if car_list is None:
        if is_site_page and soup.select_one("div.ui.warning.message"):
            return Snapshot(status=PageStatus.EMPTY)
        title = _text(soup.title) or "без заголовка"
        raise ParseError(f"неожиданная страница (нет списка вагонов): {title[:120]}")

    cars: dict[str, Car] = {}
    departure: datetime | None = None
    for ticket in car_list.select("div.ticket[data-car-number]"):
        direction = ticket.get("data-direction", "forward")
        number = ticket["data-car-number"].strip()
        price_el = ticket.select_one(".ticket__price")
        row = soup.find("tr", id=f"car-{direction}-{number}")
        layout_cabins, layout_sides, free_numbers = _layout(row)
        car = Car(
            direction=direction,
            number=number,
            car_type=(ticket.get("data-car-type") or "").strip(),
            service_class=(ticket.get("data-car-service") or "").strip(),
            free_seats=_free_seats(soup, ticket, direction, number),
            price=_text(price_el) or None,
            signs=(ticket.get("data-add-signs") or "").strip(),
            free_cabins=_free_cabins(row),
            layout_cabins=layout_cabins,
            layout_sides=layout_sides,
            free_numbers=free_numbers,
        )
        if departure is None and ticket.get("data-departure-datetime"):
            try:
                departure = datetime.fromisoformat(ticket["data-departure-datetime"])
            except ValueError:
                pass
        prev = cars.get(car.key)
        if prev is not None:
            # один вагон может идти несколькими тарифами — суммируем места
            car = Car(
                direction=prev.direction, number=prev.number, car_type=prev.car_type,
                service_class=prev.service_class, free_seats=prev.free_seats + car.free_seats,
                price=prev.price, signs=prev.signs,
                free_cabins=tuple(dict.fromkeys(prev.free_cabins + car.free_cabins)),
                layout_cabins=prev.layout_cabins or car.layout_cabins,
                layout_sides=prev.layout_sides or car.layout_sides,
                free_numbers=tuple(dict.fromkeys(prev.free_numbers + car.free_numbers)),
            )
        cars[car.key] = car

    info = _text(soup.select_one("#forward-direction-train-info .route-info__text")) or None
    return Snapshot(status=PageStatus.OK, cars=cars, train_info=info, departure=departure)
