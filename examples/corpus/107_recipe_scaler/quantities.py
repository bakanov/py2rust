"""Exact cooking quantities and an explicit mass, volume and count conversion table."""

from py2rust.stdlib import (
    Rational,
    rational_add,
    rational_compare,
    rational_decimal,
    rational_denominator,
    rational_new,
    rational_numerator,
    regex_fullmatch,
)


def quantity(spelling: str, positive: bool) -> Rational:
    assert 1 <= len(spelling) <= 256, "quantity character limit"
    value: Rational = rational_decimal("0")
    if regex_fullmatch("[0-9]+(\\.[0-9]+)?", spelling):
        value = rational_decimal(spelling)
    else:
        assert regex_fullmatch("([0-9]+ )?[0-9]+/[0-9]+", spelling), "invalid rational quantity"
        words: list[str] = spelling.split(" ")
        parts: list[str] = words[len(words) - 1].split("/")
        assert rational_compare(rational_decimal(parts[1]), rational_decimal("0")) > 0, "zero denominator"
        remainder: Rational = rational_new(parts[0], parts[1])
        if len(words) == 2:
            assert rational_compare(remainder, rational_decimal("1")) < 0, "mixed fraction must be proper"
            value = rational_decimal(words[0])
        value = rational_add(value, remainder)
    assert not positive or rational_compare(value, rational_decimal("0")) > 0, "servings must be positive"
    return value


def rendered(value: Rational) -> str:
    numerator: str = rational_numerator(value)
    denominator: str = rational_denominator(value)
    return numerator if denominator == "1" else numerator + "/" + denominator


def unit(name: str) -> tuple[str, Rational]:
    units: dict[str, tuple[str, str]] = {
        "mg": ("g", "1/1000"),
        "g": ("g", "1"),
        "kg": ("g", "1000"),
        "mL": ("mL", "1"),
        "cL": ("mL", "10"),
        "L": ("mL", "1000"),
        "piece": ("piece", "1"),
        "dozen": ("piece", "12"),
    }
    assert name in units, "unsupported unit"
    entry: tuple[str, str] = units[name]
    return (entry[0], quantity(entry[1], True))
