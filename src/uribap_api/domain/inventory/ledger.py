from dataclasses import dataclass
from decimal import Decimal
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


@dataclass(frozen=True)
class LedgerBalance:
    amount: Decimal
    unit: str

    def apply(self, delta: Decimal, unit: str) -> LedgerBalance:
        if unit != self.unit:
            raise InventoryLedgerError("movement unit does not match lot unit")
        next_amount = self.amount + delta
        if next_amount < 0:
            raise InventoryLedgerError("inventory balance cannot become negative")
        return LedgerBalance(next_amount, self.unit)


def validate_delta(delta: Decimal) -> Decimal:
    if not delta:
        raise InventoryLedgerError("movement delta cannot be zero")
    return delta


def validate_quantity(amount: Decimal) -> Decimal:
    if amount < 0:
        raise InventoryLedgerError("quantity cannot be negative")
    return amount
