"""Independent exact arithmetic, decimal rounding, normalization and resource-boundary checks."""

import decimal
import json
import random
from fractions import Fraction
from pathlib import Path

import pytest

from .test_services import parity, run

IMPORTS = """
from py2rust.stdlib import (
    Rational, rational_new, rational_decimal, rational_add, rational_sub, rational_mul,
    rational_div, rational_compare, rational_numerator, rational_denominator, rational_fixed,
    json_array, json_string, json_int, json_loads, json_canonical, read_text
)
"""


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_exact_rationals_against_fraction_and_decimal(tmp_path: Path, engine: str) -> None:
    rng = random.Random(106)
    cases = [["0", "-3", "1", "3", 2], ["1", "8", "-3", "8", 2]]
    for _ in range(600):
        cases.append([str(rng.randrange(-(10**50), 10**50)) for _ in range(4)] + [rng.randrange(19)])
    (tmp_path / "values.json").write_text(json.dumps(cases))
    source = IMPORTS + """
def parts(value: Rational) -> list[str]:
    return [rational_numerator(value), rational_denominator(value)]
def check() -> None:
    for row in json_array(json_loads(read_text("values.json"))):
        left: Rational = rational_new(json_string(row[0]), json_string(row[1]))
        right: Rational = rational_new(json_string(row[2]), json_string(row[3]))
        print(json_canonical([parts(rational_add(left, right)), parts(rational_sub(left, right)),
            parts(rational_mul(left, right)), parts(rational_div(left, right)),
            rational_compare(left, right), rational_fixed(left, json_int(row[4]))]))
    for text in ["-0", "+000.50", "1.005", "1.015", "-1.005", "-1.015", "-0.005", "-0.006"]:
        value: Rational = rational_decimal(text)
        print(json_canonical([parts(value), rational_fixed(value, 2)]))
    return
if __name__ == "__main__":
    check()
"""
    result = run(tmp_path, source, engine)
    assert result.returncode == 0 and not result.stderr, result.stderr
    rows = [json.loads(line) for line in result.stdout.splitlines()]
    with decimal.localcontext() as ctx:
        ctx.prec = 200
        for case, row in zip(cases, rows):
            a, b, c, d = map(int, case[:4])
            left, right = Fraction(a, b), Fraction(c, d)
            expected = [
                [str(v.numerator), str(v.denominator)] for v in [left + right, left - right, left * right, left / right]
            ]
            value = decimal.Decimal(left.numerator) / decimal.Decimal(left.denominator)
            rounded = value.quantize(decimal.Decimal(1).scaleb(-case[4]), rounding=decimal.ROUND_HALF_EVEN)
            expected += [(left > right) - (left < right), format(abs(rounded) if rounded == 0 else rounded, "f")]
            assert row == expected
    assert rows[-8:] == [
        [["0", "1"], "0.00"],
        [["1", "2"], "0.50"],
        [["201", "200"], "1.00"],
        [["203", "200"], "1.02"],
        [["-201", "200"], "-1.00"],
        [["-203", "200"], "-1.02"],
        [["-1", "200"], "0.00"],
        [["-3", "500"], "-0.01"],
    ]
    return  # noqa: PLR1711


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_rational_limits_and_recovery(tmp_path: Path, engine: str) -> None:
    (tmp_path / "limit.txt").write_text("1" + "0" * 4095)
    source = IMPORTS + """
def check() -> None:
    for text in ["", "+", "-", " 1", "1 ", "1_0", "1e2", "nan", "inf", "１", ".5", "1.", "1..0"]:
        try:
            rational_decimal(text)
        except Exception:
            print("invalid decimal")
        try:
            rational_new(text, "1")
        except Exception:
            print("invalid integer")
    print(rational_fixed(rational_decimal(read_text("limit.txt")), 0))
    try:
        rational_decimal(read_text("limit.txt") + "0")
    except Exception:
        print("text limit")
    two: Rational = rational_decimal("2")
    value: Rational = two
    for step in range(15):
        value = rational_mul(value, value)
    edge: Rational = rational_mul(value, rational_div(value, two))
    print(rational_numerator(edge))
    reciprocal: Rational = rational_div(rational_decimal("1"), edge)
    print(rational_denominator(reciprocal))
    print(rational_fixed(rational_mul(edge, reciprocal), 18))
    try:
        rational_mul(edge, two)
    except Exception:
        print("numerator limit")
    try:
        rational_div(reciprocal, two)
    except Exception:
        print("denominator limit")
    try:
        rational_new("1", "0")
    except Exception:
        print("zero denominator")
    try:
        rational_div(two, rational_decimal("0"))
    except Exception:
        print("zero divisor")
    for places in [-1, 19]:
        try:
            rational_fixed(two, places)
        except Exception:
            print("places")
    print(rational_fixed(two, 0))
    return
if __name__ == "__main__":
    check()
"""
    result = run(tmp_path, source, engine)
    assert result.returncode == 0 and not result.stderr, result.stderr
    with decimal.localcontext() as ctx:
        ctx.prec = 22000
        edge = format(decimal.Decimal(2) ** 65535, "f")
    assert result.stdout.splitlines() == [
        *[item for _ in range(13) for item in ["invalid decimal", "invalid integer"]],
        "1" + "0" * 4095,
        "text limit",
        edge,
        edge,
        "1.000000000000000000",
        "numerator limit",
        "denominator limit",
        "zero denominator",
        "zero divisor",
        "places",
        "places",
        "2",
    ]
    return  # noqa: PLR1711


def test_rational_owned_records_lists_and_single_evaluation(tmp_path: Path) -> None:
    output = parity(
        tmp_path,
        IMPORTS + """
from dataclasses import dataclass
@dataclass
class Amount:
    value: Rational
def observe() -> Rational:
    print("called")
    return rational_decimal("0.125")
def check() -> None:
    value: Amount = Amount(observe())
    values: list[Rational] = [value.value, rational_add(value.value, observe())]
    print(rational_fixed(values[0], 3))
    print(rational_fixed(values[1], 3))
    print(rational_fixed(value.value, 3))
    return
if __name__ == "__main__":
    check()
""",
    )
    assert output.splitlines() == ["called", "called", "0.125", "0.250", "0.125"]
    return  # noqa: PLR1711
