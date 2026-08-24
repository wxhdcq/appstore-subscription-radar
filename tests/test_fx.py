from decimal import Decimal

from app.services.fx import FxService


def test_convert_cross_currency() -> None:
    rates = {"USD": Decimal("1"), "CNY": Decimal("7.2"), "EUR": Decimal("0.9")}
    assert FxService.convert(Decimal("9"), "EUR", "CNY", rates) == Decimal("72.000000")


def test_convert_returns_none_for_missing_rate() -> None:
    rates = {"USD": Decimal("1"), "CNY": Decimal("7.2")}
    assert FxService.convert(Decimal("10"), "NGN", "CNY", rates) is None

