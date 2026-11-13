"""Сжатие истории проверок для графика.

График ступенчатый: число мест держится до следующей проверки. Поэтому подряд идущие
одинаковые проверки можно схлопнуть без потери вида (шаг 1). Если точек всё равно больше,
чем нужно для экрана, они прореживаются по времени (шаг 2) — с сохранением важного:
моментов со свободной кабинкой и неудачных проверок.

Строка: {"at": iso, "ok": 0|1, "total_free": int|None, "cars": int|None, "cabins": int|None, "error": str|None}
"""
from __future__ import annotations

from datetime import datetime

Row = dict


def _key(r: Row) -> tuple:
    return (r["ok"], r["total_free"], r["cars"], r["cabins"])


def collapse_runs(rows: list[Row]) -> list[Row]:
    """Шаг 1, без потерь для ступенчатого графика: из серии одинаковых проверок оставляем
    первую (там начинается ступень) и последнюю (до неё тянется линия)."""
    if len(rows) <= 2:
        return list(rows)
    out: list[Row] = [rows[0]]
    for prev, cur, nxt in zip(rows, rows[1:], rows[2:]):
        # середина серии одинаковых значений ничего не добавляет к линии;
        # неудачные проверки редки и рисуются отдельными засечками — их не схлопываем
        if cur["ok"] and _key(prev) == _key(cur) == _key(nxt):
            continue
        out.append(cur)
    out.append(rows[-1])
    return out


def _ts(r: Row) -> float:
    return datetime.fromisoformat(r["at"]).timestamp()


def _special(r: Row) -> bool:
    """Точки, которые рисуются отдельными метками: свободная кабинка или неудачная проверка."""
    return not r["ok"] or (r["cabins"] or 0) > 0


def bucket(rows: list[Row], max_points: int) -> list[Row]:
    """Шаг 2, с потерями: делим время на max_points/3 интервалов, в каждом оставляем
    до трёх строк — последнюю успешную (значение ступени) и первую/последнюю «особую»
    (кабинка или ошибка). Одиночная кабинка или ошибка в интервале не теряется никогда;
    теряются лишь «середины» плотных серий, которые на экране и так сливаются в одну метку."""
    if len(rows) <= max_points:
        return rows
    n = max(1, max_points // 3)
    t0, t1 = _ts(rows[0]), _ts(rows[-1])
    span = max(t1 - t0, 1e-9)
    buckets: list[list[Row]] = [[] for _ in range(n)]
    for r in rows:
        buckets[min(n - 1, int((_ts(r) - t0) / span * n))].append(r)

    out: list[Row] = []
    for b in buckets:
        if not b:
            continue
        keep: dict[int, Row] = {}
        ok_rows = [r for r in b if r["ok"]]
        if ok_rows:
            keep[id(ok_rows[-1])] = ok_rows[-1]
        specials = [r for r in b if _special(r)]
        for r in specials[:1] + specials[-1:]:
            keep[id(r)] = r
        out.extend(sorted(keep.values(), key=lambda r: r["at"]))
    # первую и последнюю проверку сохраняем всегда: от них считается ось времени
    if out[0] is not rows[0]:
        out.insert(0, rows[0])
    if out[-1] is not rows[-1]:
        out.append(rows[-1])
    return out


def downsample(rows: list[Row], max_points: int) -> list[Row]:
    return bucket(collapse_runs(rows), max_points)
