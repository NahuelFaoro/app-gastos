from __future__ import annotations

"""Reglas de calendario compartidas por las herramientas de trabajo.

La app históricamente trataba la semana de trabajo como lunes-viernes en
algunos módulos y lunes-domingo en otros. Centralizar esta semántica evita que
un cambio de calendario requiera editar múltiples hardcodes independientes.
"""

from datetime import date, timedelta
from typing import Iterator

from .constants import MONTHS_SHORT

WORK_WEEK_DAYS = 7
WEEKDAY_NAMES_ES = (
    "LUNES",
    "MARTES",
    "MIÉRCOLES",
    "JUEVES",
    "VIERNES",
    "SÁBADO",
    "DOMINGO",
)


def coerce_date(value: str | date) -> date:
    """Convierte una fecha ISO o :class:`date` a ``date``."""
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def week_start(value: str | date) -> date:
    """Lunes de la semana calendario que contiene ``value``."""
    day = coerce_date(value)
    return day - timedelta(days=day.weekday())


def week_start_iso(value: str | date) -> str:
    return week_start(value).isoformat()


def week_end(value: str | date) -> date:
    return week_start(value) + timedelta(days=WORK_WEEK_DAYS - 1)


def iter_week_days(value: str | date) -> Iterator[date]:
    start = week_start(value)
    for offset in range(WORK_WEEK_DAYS):
        yield start + timedelta(days=offset)


def weekday_name(value: str | date) -> str:
    return WEEKDAY_NAMES_ES[coerce_date(value).weekday()]


def compact_week_label(value: str | date, *, include_year: bool = False) -> str:
    """Etiqueta compacta usada por Viajes (ej. ``07 – 13 sep``)."""
    start = week_start(value)
    end = week_end(start)
    if start.month == end.month:
        label = f"{start.day:02d} – {end.day:02d} {MONTHS_SHORT[end.month - 1].lower()}"
    else:
        label = (
            f"{start.day:02d} {MONTHS_SHORT[start.month - 1][:3].lower()} – "
            f"{end.day:02d} {MONTHS_SHORT[end.month - 1][:3].lower()}"
        )
    return f"{label} {end.year}" if include_year else label


def full_week_label(value: str | date) -> str:
    """Etiqueta con año usada por herramientas de zonas/Flex."""
    start = week_start(value)
    end = week_end(start)
    if start.year == end.year and start.month == end.month:
        return f"{start.day} – {end.day} {MONTHS_SHORT[end.month - 1].lower()} {end.year}"
    if start.year == end.year:
        return (
            f"{start.day} {MONTHS_SHORT[start.month - 1].lower()} – "
            f"{end.day} {MONTHS_SHORT[end.month - 1].lower()} {end.year}"
        )
    return (
        f"{start.day} {MONTHS_SHORT[start.month - 1].lower()} {start.year} – "
        f"{end.day} {MONTHS_SHORT[end.month - 1].lower()} {end.year}"
    )
