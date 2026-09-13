from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta


def money(value: float, symbol: str = "$", hidden: bool = False) -> str:
    if hidden:
        return f"{symbol} ••••••"
    value = float(value or 0)
    sign = "-" if value < 0 else ""
    value = abs(value)
    text = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if text.endswith(",00"):
        text = text[:-3]
    return f"{sign}{symbol} {text}"



def parse_money_text(text: str | None) -> float:
    """Parsea importes escritos con convención AR o decimal con punto.

    Ejemplos válidos: 18500, 18.500, 18500,50, 18.500,50, 18500.50.
    """
    text = (text or "").strip().replace(" ", "").replace("$", "")
    if not text or text in {"-", ".", ","}:
        return 0.0
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        if text.count(",") > 1:
            parts = text.split(",")
            text = "".join(parts[:-1]) + "." + parts[-1]
        else:
            text = text.replace(",", ".")
    elif "." in text:
        parts = text.split(".")
        if len(parts) > 2:
            if len(parts[-1]) <= 2:
                text = "".join(parts[:-1]) + "." + parts[-1]
            else:
                text = "".join(parts)
        elif len(parts) == 2 and len(parts[-1]) == 3:
            text = "".join(parts)
    try:
        return float(text)
    except ValueError:
        return 0.0

def percent_change(current: float, previous: float) -> float | None:
    current = float(current or 0)
    previous = float(previous or 0)
    if previous == 0:
        return None if current == 0 else 100.0
    return ((current - previous) / abs(previous)) * 100.0


def month_bounds(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    return start, end


def previous_month(year: int, month: int) -> tuple[int, int]:
    if month == 1:
        return year - 1, 12
    return year, month - 1


def add_months(value: date, months: int, anchor_day: int | None = None) -> date:
    total = value.year * 12 + (value.month - 1) + months
    year, month0 = divmod(total, 12)
    month = month0 + 1
    target_day = anchor_day or value.day
    day = min(target_day, monthrange(year, month)[1])
    return date(year, month, day)


def advance_recurrence(value: date, frequency: str, interval: int = 1, anchor_day: int | None = None) -> date:
    interval = max(1, int(interval or 1))
    if frequency == "daily":
        return value + timedelta(days=interval)
    if frequency == "weekly":
        return value + timedelta(weeks=interval)
    if frequency == "monthly":
        return add_months(value, interval, anchor_day)
    if frequency == "yearly":
        try:
            return value.replace(year=value.year + interval)
        except ValueError:
            return value.replace(year=value.year + interval, day=28)
    raise ValueError("Frecuencia inválida")


def human_date(iso_date: str) -> str:
    try:
        d = date.fromisoformat(iso_date)
    except Exception:
        return iso_date
    today = date.today()
    if d == today:
        return "Hoy"
    if d == today - timedelta(days=1):
        return "Ayer"
    return d.strftime("%d/%m/%Y")
