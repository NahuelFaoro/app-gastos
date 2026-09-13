"""Cálculos monetarios decimales; float sólo en el límite con SQLite/UI."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def decimal_amount(value: Decimal | float | int | str) -> Decimal:
    """Normaliza a centavos y rechaza importes no finitos o fuera de rango."""
    try:
        amount = Decimal(str(value))
        if not amount.is_finite():
            raise ValueError("El importe debe ser un número finito.")
        return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError) as exc:
        raise ValueError("El importe no es válido.") from exc


def installment_amount(total: float, base: float, count: int, number: int) -> float:
    """La última cuota absorbe la diferencia exacta en centavos."""
    amount = decimal_amount(base)
    if number == count:
        amount = decimal_amount(total) - amount * (count - 1)
    return float(amount)
