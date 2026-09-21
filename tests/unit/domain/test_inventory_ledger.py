from decimal import Decimal

import pytest

from uribap_api.domain.inventory.ledger import (
    InventoryLedgerError,
    LedgerBalance,
    operation_fingerprint,
    validate_delta,
    validate_quantity,
)


def test_ledger_applies_decimal_delta_without_float_drift() -> None:
    balance = LedgerBalance(Decimal("0.1"), "kg")
    assert balance.apply(Decimal("0.2"), "kg").amount == Decimal("0.3")


def test_ledger_rejects_negative_balance_and_unit_mismatch() -> None:
    balance = LedgerBalance(Decimal("2"), "unit")
    with pytest.raises(InventoryLedgerError):
        balance.apply(Decimal("-3"), "unit")
    with pytest.raises(InventoryLedgerError):
        balance.apply(Decimal("1"), "kg")


def test_ledger_rejects_zero_deltas_and_negative_quantities() -> None:
    with pytest.raises(InventoryLedgerError):
        validate_delta(Decimal("0"))
    with pytest.raises(InventoryLedgerError):
        validate_quantity(Decimal("-0.1"))


def test_ledger_rejects_nonfinite_and_overprecision_values() -> None:
    for value in (Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")):
        with pytest.raises(InventoryLedgerError):
            validate_quantity(value)
    with pytest.raises(InventoryLedgerError):
        validate_delta(Decimal("0.0000001"))
    with pytest.raises(InventoryLedgerError):
        LedgerBalance(Decimal("-1"), "unit")


def test_operation_fingerprint_is_stable_and_payload_sensitive() -> None:
    first = operation_fingerprint("inventory_adjustment", {"lot_id": "a", "delta": "-1"})
    same = operation_fingerprint("inventory_adjustment", {"delta": "-1", "lot_id": "a"})
    different = operation_fingerprint("inventory_adjustment", {"lot_id": "b", "delta": "-1"})
    assert first == same
    assert first != different
