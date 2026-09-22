from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from enum import StrEnum


class InventoryLocation(StrEnum):
    PANTRY = "pantry"
    REFRIGERATOR = "refrigerator"
    FREEZER = "freezer"


class InventoryMovementType(StrEnum):
    PURCHASE = "purchase"
    MEAL_CONSUMPTION = "meal_consumption"
    MANUAL_ADJUSTMENT = "manual_adjustment"
    WASTE = "waste"
    REVERSAL = "reversal"


class InventoryLedgerError(ValueError):
    pass


QUANTUM = Decimal("0.000001")
MAX_AMOUNT = Decimal("999999999999.999999")


def quantize_amount(amount: Decimal, *, allow_zero: bool = True) -> Decimal:
    if not amount.is_finite():
        raise InventoryLedgerError("quantity must be finite")
    try:
        normalized = amount.quantize(QUANTUM, rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:
        raise InventoryLedgerError("quantity exceeds NUMERIC(18,6) precision") from exc
    if normalized < 0 or normalized > MAX_AMOUNT:
        raise InventoryLedgerError("quantity exceeds NUMERIC(18,6) range")
    if not allow_zero and normalized == 0:
        raise InventoryLedgerError("quantity must not round to zero")
    return normalized


@dataclass(frozen=True)
class LedgerBalance:
    amount: Decimal
    unit: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "amount", quantize_amount(self.amount))

    def apply(self, delta: Decimal, unit: str) -> LedgerBalance:
        if unit != self.unit:
            raise InventoryLedgerError("movement unit does not match lot unit")
        normalized_delta = validate_delta(delta)
        try:
            next_amount = (self.amount + normalized_delta).quantize(
                QUANTUM, rounding=ROUND_HALF_UP
            )
        except InvalidOperation as exc:
            raise InventoryLedgerError("quantity exceeds NUMERIC(18,6) precision") from exc
        if next_amount < 0:
            raise InventoryLedgerError("inventory balance cannot become negative")
        if next_amount > MAX_AMOUNT:
            raise InventoryLedgerError("quantity exceeds NUMERIC(18,6) range")
        return LedgerBalance(next_amount, self.unit)


def validate_delta(delta: Decimal) -> Decimal:
    if not delta.is_finite():
        raise InventoryLedgerError("quantity must be finite")
    try:
        normalized = delta.quantize(QUANTUM, rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:
        raise InventoryLedgerError("quantity exceeds NUMERIC(18,6) precision") from exc
    if abs(normalized) > MAX_AMOUNT:
        raise InventoryLedgerError("quantity exceeds NUMERIC(18,6) range")
    if normalized == 0:
        raise InventoryLedgerError("quantity must not round to zero")
    return normalized


def validate_quantity(amount: Decimal) -> Decimal:
    return quantize_amount(amount)
