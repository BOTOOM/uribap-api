import pytest
from pydantic import ValidationError

from uribap_api.api.schemas import Quantity


def test_quantity_preserves_decimal_as_string() -> None:
    quantity = Quantity(amount="001.250", unit="kg")

    assert quantity.amount == "1.250"
    assert quantity.unit == "kg"


@pytest.mark.parametrize("amount", ["-1", "one", "", "1e3"])
def test_quantity_rejects_invalid_amounts(amount: str) -> None:
    with pytest.raises(ValidationError):
        Quantity(amount=amount, unit="g")
