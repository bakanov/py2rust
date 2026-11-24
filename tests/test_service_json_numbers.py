"""Exact scalar order and bounded JSON-number arithmetic across integer/float boundaries."""

import json
import math
import random
import struct
from fractions import Fraction
from pathlib import Path

import pytest
from py2rust.compiler.service import ServiceCompiler, ServiceError

from .test_services import run


def pairs() -> list[tuple[int | float, int | float]]:
    edges = [
        -(2**63),
        -(2**63) + 1,
        -(2**53) - 1,
        -1,
        0,
        1,
        2**53 - 1,
        2**53,
        2**53 + 1,
        2**63 - 1,
        -1.7976931348623157e308,
        -float(2**63),
        math.nextafter(-float(2**63), -math.inf),
        math.nextafter(float(2**63), -math.inf),
        float(2**63),
        1.7976931348623157e308,
        -0.0,
        0.0,
        -0.5,
        0.5,
        -5e-324,
        5e-324,
        float(2**53),
        1.25,
        -1.25,
    ]
    values = [(left, right) for left in edges for right in edges]
    rng = random.Random(490049)
    for _ in range(2000):
        bits = rng.getrandbits(64)
        value = struct.unpack(">d", bits.to_bytes(8, "big"))[0]
        if math.isfinite(value):
            integer = rng.randrange(-(2**63), 2**63)
            values.extend([(integer, value), (value, integer), (value, rng.choice(edges))])
    return values


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_numeric_order_and_addition_reference(tmp_path: Path, engine: str) -> None:
    values = pairs()
    (tmp_path / "numbers.json").write_text(json.dumps(values))
    result = run(
        tmp_path,
        """
from py2rust.stdlib import Json, json_loads, json_array, read_text, json_dumps, json_number_add, json_scalar_compare
def check() -> None:
    for pair in json_array(json_loads(read_text("numbers.json"))):
        result: Json = {"order": json_scalar_compare(pair[0], pair[1])}
        try:
            result["sum"] = json_number_add(pair[0], pair[1])
        except Exception as error:
            result["error"] = str(error)
        print(json_dumps(result))
    return
if __name__ == "__main__":
    check()
""",
        engine,
    )
    assert result.returncode == 0, result.stderr
    actual = [json.loads(line) for line in result.stdout.splitlines()]
    assert len(actual) == len(values)
    for (left, right), got in zip(values, actual):
        a, b = Fraction(left), Fraction(right)
        assert got["order"] == int(a > b) - int(a < b), (left, right, got)
        total = left + right
        if type(total) is int and not -(2**63) <= total < 2**63:
            assert got["error"] == "integer overflow"
        elif type(total) is float and not math.isfinite(total):
            assert got["error"] == "non-finite floating point result"
        else:
            assert "error" not in got and type(got["sum"]) is type(total)
            if type(total) is float:
                assert got["sum"].hex() == total.hex(), (left, right, got)
            else:
                assert got["sum"] == total
    return  # noqa: PLR1711


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_scalar_kinds_errors_and_evaluation_order(tmp_path: Path, engine: str) -> None:
    result = run(
        tmp_path,
        """
from py2rust.stdlib import Json, json_scalar_compare, json_number_add

def observed(label: str, value: Json) -> Json:
    print(label)
    return value

def check() -> None:
    assert json_scalar_compare(None, None) == 0
    assert json_scalar_compare(False, True) == -1
    assert json_scalar_compare(True, False) == 1
    assert json_scalar_compare("é", "e\\u0301") == 1
    assert json_scalar_compare("😀", "世界") == 1
    assert json_scalar_compare("a\\0", "a") == 1
    assert json_scalar_compare("", "") == 0
    print(json_scalar_compare(observed("left", 9007199254740993), observed("right", 9007199254740992.0)))
    invalid: list[Json] = [None, False, "1", [], {}]
    for value in invalid:
        try:
            added: Json = json_number_add(observed("add left", value), observed("add right", 1))
        except Exception as error:
            print(str(error))
        try:
            compared: int = json_scalar_compare(observed("compare left", value), observed("compare right", 1))
        except Exception as error:
            print(str(error))
    for value in invalid:
        try:
            ignored: Json = json_number_add(1, value)
        except Exception as error:
            print(str(error))
    containers: list[Json] = [[], {}]
    for container in containers:
        try:
            ignored_order: int = json_scalar_compare(container, container)
        except Exception as error:
            print(str(error))
    return
if __name__ == "__main__":
    check()
""",
        engine,
    )
    assert result.returncode == 0, result.stderr
    pattern = [
        "add left",
        "add right",
        "expected JSON numbers",
        "compare left",
        "compare right",
        "expected compatible JSON scalars",
    ]
    assert result.stdout.splitlines() == [
        "left",
        "right",
        "1",
        *(pattern * 5),
        *(["expected JSON numbers"] * 5),
        *(["expected compatible JSON scalars"] * 2),
    ]
    return  # noqa: PLR1711


@pytest.mark.parametrize("call", ["json_scalar_compare(1)", "json_number_add(1, 2, 3)", "json_scalar_compare()"])
def test_json_scalar_arity_rejection(call: str) -> None:
    with pytest.raises(ServiceError) as error:
        ServiceCompiler().compile(
            "from py2rust.stdlib import json_scalar_compare, json_number_add\ndef check() -> None:\n    "
            + call
            + '\n    return\nif __name__ == "__main__":\n    check()\n'
        )
    assert error.value.lineno == 3
    return  # noqa: PLR1711
