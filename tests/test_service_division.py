"""True division: exact integer ratios, finite binary64 arithmetic and recoverable errors."""

import json
import math
import random
import struct
from fractions import Fraction
from pathlib import Path

import pytest
from py2rust.compiler.service import ServiceCompiler, ServiceError

from .test_services import parity, run


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_integer_ratios_round_once(tmp_path: Path, engine: str) -> None:
    edges = [
        -(2**63),
        -(2**63) + 1,
        -(2**53) - 3,
        -(2**53) - 1,
        -3,
        -1,
        0,
        1,
        3,
        2**53 - 1,
        2**53,
        2**53 + 1,
        2**53 + 3,
        2**63 - 1,
    ]
    pairs = [(a, b) for a in edges for b in edges if b]
    pairs.extend((a, b) for a in range(-80, 81) for b in range(-80, 81) if b)
    rng = random.Random(510051)
    for _ in range(10000):
        a, b = rng.randrange(-(2**63), 2**63), rng.randrange(-(2**63), 2**63)
        if b:
            pairs.append((a, b))
    assert sum(a / b != float(a) / float(b) for a, b in pairs) > 100
    (tmp_path / "pairs.json").write_text(json.dumps(pairs))
    result = run(
        tmp_path,
        """
from py2rust.stdlib import json_array, json_loads, read_text, json_int, json_dumps
def check() -> None:
    for pair in json_array(json_loads(read_text("pairs.json"))):
        left: int = json_int(pair[0])
        right: int = json_int(pair[1])
        value: float = left / right
        print(json_dumps(value))
    return
if __name__ == "__main__":
    check()
""",
        engine,
    )
    assert result.returncode == 0, result.stderr
    actual = [json.loads(line) for line in result.stdout.splitlines()]
    assert len(actual) == len(pairs)
    for (a, b), value in zip(pairs, actual):
        expected = a / b
        assert type(value) is float and value.hex() == expected.hex(), (a, b, value, expected)
        if a:
            assert value.hex() == float(Fraction(a, b)).hex(), (a, b, value)
    return  # noqa: PLR1711


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_float_division_matches_bits(tmp_path: Path, engine: str) -> None:
    edges = [
        -1.7976931348623157e308,
        -1.0,
        -0.0,
        0.0,
        1.0,
        0.1,
        -0.3,
        1.25,
        5e-324,
        -5e-324,
        2.2250738585072014e-308,
        1.7976931348623157e308,
    ]
    pairs = [(a, b) for a in edges for b in edges if b and math.isfinite(a / b)]
    rng = random.Random(510052)
    for _ in range(10000):
        a, b = [struct.unpack(">d", rng.getrandbits(64).to_bytes(8, "big"))[0] for _ in range(2)]
        if math.isfinite(a) and math.isfinite(b) and b and math.isfinite(a / b):
            pairs.append((a, b))
    (tmp_path / "pairs.json").write_text(json.dumps(pairs))
    result = run(
        tmp_path,
        """
from py2rust.stdlib import json_array, json_loads, read_text, json_float, json_dumps
def check() -> None:
    for pair in json_array(json_loads(read_text("pairs.json"))):
        left: float = json_float(pair[0])
        right: float = json_float(pair[1])
        print(json_dumps(left / right))
    return
if __name__ == "__main__":
    check()
""",
        engine,
    )
    assert result.returncode == 0, result.stderr
    actual = [json.loads(line) for line in result.stdout.splitlines()]
    assert len(actual) == len(pairs)
    for (a, b), value in zip(pairs, actual):
        assert type(value) is float and value.hex() == (a / b).hex(), (a, b, value, a / b)
    return  # noqa: PLR1711


def test_division_evaluation_order_and_zero_errors(tmp_path: Path) -> None:
    result = parity(
        tmp_path,
        """
from py2rust.stdlib import json_dumps
def integer(label: str, value: int) -> int:
    print(label)
    return value
def number(label: str, value: float) -> float:
    print(label)
    return value
def check() -> None:
    print(json_dumps(integer("left", 9007199254740993) / integer("right", 3)))
    assert -9223372036854775808 / -1 == 9223372036854775808.0
    print(json_dumps((5 / 2) / 2.0))
    print(json_dumps(number("float left", 3.0) / number("float right", 2.0)))
    try:
        value: float = integer("zero left", 1) / integer("zero right", 0)
    except Exception as error:
        print(str(error))
    for zero in [0.0, -0.0]:
        try:
            value: float = number("zero float left", 1.0) / number("zero float right", zero)
        except Exception as error:
            print(str(error))
    return
if __name__ == "__main__":
    check()
""",
    )
    assert result.splitlines() == [
        "left",
        "right",
        "3002399751580331.0",
        "1.25",
        "float left",
        "float right",
        "1.5",
        "zero left",
        "zero right",
        "division by zero",
        *(["zero float left", "zero float right", "float division by zero"] * 2),
    ]
    return  # noqa: PLR1711


def test_native_nonfinite_division_is_recoverable(tmp_path: Path) -> None:
    result = run(
        tmp_path,
        """
def check() -> None:
    try:
        value: float = 1.7976931348623157e308 / 5e-324
    except Exception as error:
        print(str(error))
    print("continued")
    return
if __name__ == "__main__":
    check()
""",
        "rust",
    )
    assert result.returncode == 0 and result.stdout == "non-finite floating point result\ncontinued\n"
    return  # noqa: PLR1711


@pytest.mark.parametrize("expression", ["1 / 2.0", "1.0 / 2", "True / 2", "2 / False", '"x" / "y"', "[1] / [2]"])
def test_unsupported_division_operand_types(expression: str) -> None:
    with pytest.raises(ServiceError, match="unsupported arithmetic combination") as error:
        ServiceCompiler().compile(
            "def check() -> None:\n    print(" + expression + ')\n    return\nif __name__ == "__main__":\n    check()\n'
        )
    assert error.value.lineno == 2
    return  # noqa: PLR1711


def test_integer_division_result_requires_float_annotation() -> None:
    with pytest.raises(ServiceError) as error:
        ServiceCompiler().compile(
            'def check() -> None:\n    value: int = 1 / 2\n    return\nif __name__ == "__main__":\n    check()\n'
        )
    assert error.value.lineno == 2
    return  # noqa: PLR1711
