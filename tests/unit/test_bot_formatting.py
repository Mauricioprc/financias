from decimal import Decimal

from bot.formatting import money, parse_amount


def test_money_formats_pt_br():
    assert money(Decimal("1234.5")) == "R$ 1.234,50"
    assert money(Decimal("50")) == "R$ 50,00"
    assert money(Decimal("-30.25")) == "-R$ 30,25"
    assert money("100.00") == "R$ 100,00"


def test_parse_amount_accepts_common_formats():
    assert parse_amount("50") == Decimal("50")
    assert parse_amount("50,00") == Decimal("50.00")
    assert parse_amount("50.00") == Decimal("50.00")
    assert parse_amount("R$ 50,00") == Decimal("50.00")
    assert parse_amount("1.234,56") == Decimal("1234.56")


def test_parse_amount_rejects_invalid():
    assert parse_amount("") is None
    assert parse_amount("abc") is None
    assert parse_amount("0") is None
    assert parse_amount("-10") is None
