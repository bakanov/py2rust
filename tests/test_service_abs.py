"""Absolute-value numeric types, signed zeros, boundary overflow and single evaluation."""

import json
import math
import random
import struct
from pathlib import Path

import pytest
from py2rust.compiler.service import ServiceCompiler, ServiceError

from .test_services import parity, run


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_absolute_values_match_numeric_bits(tmp_path: Path, engine: str) -> None:
    rng = random.Random(103103)
    integers = [-(2**63) + 1, -1, 0, 1, 2**63 - 1] + [rng.randrange(-(2**63) + 1, 2**63) for _ in range(1000)]
    floats = [-0.0, 0.0, -5e-324, 5e-324, -1.7976931348623157e308, -2.2250738585072014e-308]
    for _ in range(2000):
        value = struct.unpack(">d", rng.getrandbits(64).to_bytes(8, "big"))[0]
        if math.isfinite(value):
            floats.append(value)
    (tmp_path / "values.json").write_text(json.dumps({"integers": integers, "floats": floats}))
    result = run(
        tmp_path,
        """
from py2rust.stdlib import json_array, json_loads, json_int, json_float, json_canonical, read_text, Json
def check() -> None:
    values: Json = json_loads(read_text("values.json"))
    for entry in json_array(values["integers"]):
        result: int = abs(json_int(entry))
        print(json_canonical(result))
    for entry in json_array(values["floats"]):
        result: float = abs(json_float(entry))
        print(json_canonical(result))
    return
if __name__ == "__main__":
    check()
""",
        engine,
    )
    assert result.returncode == 0 and not result.stderr, result.stderr
    output = [json.loads(line) for line in result.stdout.splitlines()]
    assert len(output) == len(integers) + len(floats)
    assert output[: len(integers)] == [abs(value) for value in integers]
    assert all(type(value) is int for value in output[: len(integers)])
    for actual, original in zip(output[len(integers) :], floats):
        assert type(actual) is float and actual.hex() == abs(original).hex()
    return  # noqa: PLR1711


def test_absolute_value_evaluates_once(tmp_path: Path) -> None:
    output = parity(
        tmp_path,
        """
from py2rust.stdlib import json_canonical
def integer() -> int:
    print("integer called")
    return -3
def number() -> float:
    print("float called")
    return -0.0
def check() -> None:
    print(json_canonical(abs(integer())))
    print(json_canonical(abs(number())))
    return
if __name__ == "__main__":
    check()
""",
    )
    assert output.splitlines() == ["integer called", "3", "float called", "0e0"]
    return  # noqa: PLR1711


def test_native_minimum_integer_absolute_overflow_is_recoverable(tmp_path: Path) -> None:
    result = run(
        tmp_path,
        """
def check() -> None:
    try:
        value: int = abs(-9223372036854775808)
    except Exception as error:
        print(str(error))
    print("continued")
    return
if __name__ == "__main__":
    check()
""",
        "rust",
    )
    assert result.returncode == 0 and result.stdout == "integer overflow\ncontinued\n" and not result.stderr
    return  # noqa: PLR1711


@pytest.mark.parametrize("expression", ["abs(True)", "abs(None)", "abs('1')", "abs([1])"])
def test_absolute_value_rejects_unsupported_types(expression: str) -> None:
    with pytest.raises(ServiceError, match="abs requires an int or float") as error:
        ServiceCompiler().compile(
            "def check() -> None:\n    print(" + expression + ')\n    return\nif __name__ == "__main__":\n    check()\n'
        )
    assert error.value.lineno == 2
    return  # noqa: PLR1711
