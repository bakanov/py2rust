"""Bounded decimal string conversion: Python grammar, exact binary64 rounding and finite-profile errors."""

import decimal
import json
import math
import random
import struct
from pathlib import Path

import pytest
from py2rust.compiler.service import ServiceCompiler, ServiceError

from .test_services import parity, run

SOURCE = """
from py2rust.stdlib import json_array, json_loads, json_string, json_canonical, read_text
def check() -> None:
    for entry in json_array(json_loads(read_text("values.json"))):
        text: str = json_string(entry)
        try:
            value: float = float(text)
            print(json_canonical(value))
        except Exception:
            print("rejected")
    return
if __name__ == "__main__":
    check()
"""


def numbers() -> list[str]:
    values = [
        "0",
        "-0",
        "+0",
        "0.",
        ".0",
        "-.0e-100",
        "1_2.3_4e+0_2",
        "01",
        "+.5",
        "5.",
        " \t\n\r\v\f-1.25E+2 \t\n\r\v\f",
        "1e-9999",
        "-1e-9999",
        "0e9999",
        "-0e9999",
        "2.2250738585072014e-308",
        "1.7976931348623157e308",
        "4.9406564584124654e-324",
        "9007199254740993",
        "9223372036854775808",
        "0" * 4095 + "1",
        "0" * 4094 + ".1",
        " " * 4094 + "1 ",
    ]
    rng = random.Random(103)
    for _ in range(3000):
        number = struct.unpack(">d", rng.getrandbits(64).to_bytes(8, "big"))[0]
        if math.isfinite(number):
            values.extend([repr(number), format(number, ".40e")])
    for _ in range(2000):
        digits = "".join(str(rng.randrange(10)) for _ in range(rng.randrange(1, 80)))
        point = rng.randrange(len(digits) + 1)
        text = rng.choice(["", "+", "-"]) + digits[:point] + "." + digits[point:] + "e" + str(rng.randrange(-400, 310))
        if math.isfinite(float(text)):
            values.append(text)
    # Exact decimal midpoints exercise ties-to-even near zero, subnormal/normal boundaries and large powers.
    with decimal.localcontext() as context:
        context.prec = 2000
        for value in [0.0, 5e-324, 2.225073858507201e-308, 2.2250738585072014e-308, 0.1, 0.5, 1.0, 2.0, 2**53, 1e300]:
            lower = decimal.Decimal.from_float(float(value))
            upper = decimal.Decimal.from_float(math.nextafter(float(value), math.inf))
            midpoint = (lower + upper) / 2
            for exact in [midpoint, midpoint - (upper - lower) / 100, midpoint + (upper - lower) / 100]:
                values.extend([str(exact), str(-exact)])
    return values


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_decimal_strings_match_python_bits(tmp_path: Path, engine: str) -> None:
    values = numbers()
    assert len(values) > 7500 and all(len(value.encode()) <= 4096 for value in values)
    (tmp_path / "values.json").write_text(json.dumps(values))
    result = run(tmp_path, SOURCE, engine)
    assert result.returncode == 0 and not result.stderr, result.stderr
    output = result.stdout.splitlines()
    assert len(output) == len(values)
    for text, line in zip(values, output):
        assert line != "rejected", text
        actual = json.loads(line)
        assert type(actual) is float and actual.hex() == float(text).hex(), (text, actual, float(text))
    return  # noqa: PLR1711


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_invalid_decimal_grammar_is_recoverable(tmp_path: Path, engine: str) -> None:
    bad = [
        "",
        " ",
        "+",
        "-",
        ".",
        "+.",
        "1e",
        "1e+",
        "1e-",
        "e1",
        "1..0",
        "0x1p0",
        "1,2",
        "1 2",
        "\x001",
        "1\x00",
        "\x1c1",
        "1\x1f",
        "1e 2",
        "1e1.0",
        "++1",
        "--1",
        "+-1",
        "1f",
        "1d",
    ]
    for base in ["1", "1.25", ".5", "1.", "-1.5e+2", "1_000.5_0"]:
        for position in range(len(base) + 1):
            for insert in ["_", "__", " ", "e", "."]:
                candidate = base[:position] + insert + base[position:]
                try:
                    float(candidate)
                except ValueError:
                    bad.append(candidate)
    (tmp_path / "values.json").write_text(json.dumps(bad + ["1.5"]))
    result = run(tmp_path, SOURCE, engine)
    assert result.returncode == 0 and not result.stderr, result.stderr
    assert result.stdout.splitlines() == ["rejected"] * len(bad) + ["1.5e0"]
    return  # noqa: PLR1711


def test_native_float_string_profile_limits(tmp_path: Path) -> None:
    bad = [
        "nan",
        "+NaN",
        "-NAN",
        "inf",
        "+Infinity",
        "-infinity",
        "1e309",
        "-1e309",
        "9" * 4096,
        "0" * 4096 + "1",
        " " * 4095 + "1 ",
        "１.５",
        "١٢.٥",
        "\u00a01.5",
        "1.5\u2003",
        "²",
    ]
    (tmp_path / "values.json").write_text(json.dumps(bad + ["-0e99999"]))
    result = run(tmp_path, SOURCE, "rust")
    assert result.returncode == 0 and not result.stderr, result.stderr
    assert result.stdout.splitlines() == ["rejected"] * len(bad) + ["-0e0"]
    return  # noqa: PLR1711


def test_float_string_evaluation_once_and_existing_numeric_casts(tmp_path: Path) -> None:
    output = parity(
        tmp_path,
        """
from py2rust.stdlib import json_canonical
def text() -> str:
    print("called")
    return "1_2.5"
def check() -> None:
    values: list[float] = [float(text()), float(9007199254740993), float(-0.0)]
    for value in values:
        print(json_canonical(value))
    return
if __name__ == "__main__":
    check()
""",
    )
    assert output.splitlines() == ["called", "1.25e1", "9.007199254740992e15", "-0e0"]
    return  # noqa: PLR1711


@pytest.mark.parametrize("expression", ["float(b'1')", "float(None)", "float(['1'])", "float({'x': 1})"])
def test_float_rejects_unsupported_types(expression: str) -> None:
    with pytest.raises(ServiceError, match="float conversion requires") as error:
        ServiceCompiler().compile(
            "def check() -> None:\n    value: float = "
            + expression
            + '\n    return\nif __name__ == "__main__":\n    check()\n'
        )
    assert error.value.lineno == 2
    return  # noqa: PLR1711
