"""Canonical JSON agrees across runtimes and preserves every tested binary64 value."""

import json
import math
import random
import struct
import sys
from pathlib import Path

import pytest

from .test_services import run


def oracle(value: object) -> str:
    import decimal

    if type(value) is float:
        if value == 0.0:
            return "-0e0" if math.copysign(1.0, value) < 0 else "0e0"
        with decimal.localcontext() as context:
            context.prec = 1100
            context.rounding = decimal.ROUND_HALF_EVEN
            mantissa, exponent = format(decimal.Decimal.from_float(value), ".16e").split("e")
        return mantissa.rstrip("0").rstrip(".") + "e" + str(int(exponent))
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(oracle(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{" + ",".join(oracle(key) + ":" + oracle(value[key]) for key in sorted(value)) + "}"
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_canonical_json_float_vectors_and_roundtrip(tmp_path: Path, engine: str) -> None:
    rng = random.Random(3601)
    values = [
        0.0,
        -0.0,
        1.0,
        -1.0,
        0.1,
        1.1,
        2.675,
        1e-7,
        1e23,
        5e-324,
        -5e-324,
        sys.float_info.max,
        -sys.float_info.max,
        sys.float_info.min,
        math.nextafter(1.0, 2.0),
    ]
    while len(values) < 3000:
        candidate = struct.unpack(">d", rng.getrandbits(64).to_bytes(8, "big"))[0]
        if math.isfinite(candidate):
            values.append(candidate)
    document = {
        "z": values,
        "😀": "Unicode\u2028世界",
        "control": '\x00\b\f\n\r\t\\"/',
        "ints": [-(2**63), 2**63 - 1],
        "empty": [None, True, False, [], {}],
        "float-v-int": [1, 1.0, -0.0, 0],
    }
    (tmp_path / "input.json").write_text(json.dumps(document, ensure_ascii=False))
    result = run(
        tmp_path,
        """
from py2rust.stdlib import read_text, json_loads, json_canonical

def check() -> None:
    print(json_canonical(json_loads(read_text("input.json"))))
    return
if __name__ == "__main__":
    check()
""",
        engine,
    )
    assert result.returncode == 0, result.stderr
    actual = result.stdout.rstrip("\n")
    assert actual == oracle(document)
    assert '"float-v-int":[1,1e0,-0e0,0]' in actual
    decoded = json.loads(actual)
    assert [struct.pack(">d", v) for v in decoded["z"]] == [struct.pack(">d", v) for v in values]
    assert oracle(decoded) == actual
    return  # noqa: PLR1711 - explicit return required by repository guidelines


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_canonical_json_numeric_spelling_and_validation(tmp_path: Path, engine: str) -> None:
    result = run(
        tmp_path,
        """
from py2rust.stdlib import json_canonical, json_loads

def check() -> None:
    for text in ["1.0", "1e0", "10e-1", "0.1e1"]:
        assert json_canonical(json_loads(text)) == "1e0"
    assert json_canonical(json_loads("-0")) == "0"
    assert json_canonical(json_loads("-0.0")) == "-0e0"
    assert json_canonical(json_loads("0e-999")) == "0e0"
    failed: int = 0
    for text in ["1e999", "9223372036854775808", "NaN", "Infinity", "[1,]"]:
        try:
            json_canonical(json_loads(text))
        except Exception:
            failed = failed + 1
    assert failed == 5
    print("canonical validation")
    return
if __name__ == "__main__":
    check()
""",
        engine,
    )
    assert result.returncode == 0 and result.stdout == "canonical validation\n", result.stderr
    return  # noqa: PLR1711 - explicit return required by repository guidelines
