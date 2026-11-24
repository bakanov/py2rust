"""Default float text must agree with Python, including shortest-digit ties."""

import json
import math
import random
import struct
from pathlib import Path

import pytest

from py2rust.compiler import pipeline, service

from .test_services import parity

SOURCE = """from py2rust.stdlib import json_array, json_loads, json_string, read_text

def text(value: float) -> str:
    return str(value)

def parse(value: str) -> float:
    return float(value)

def check() -> None:
    for entry in json_array(json_loads(read_text("values.json"))):
        value: float = parse(json_string(entry))
        print(text(value))
        print(value)

if __name__ == "__main__":
    check()
"""


def values() -> list[float]:
    result = [0.0, -0.0, 1.0, -1.0, 5e-324, 1.7976931348623157e308]
    # Equally short round-trip spellings expose Debug-vs-Python tie differences.
    result.extend([1496887933091857.25, -146076764543890.625, -130047693493788.125])
    for exponent in range(-323, 309):
        value = 10.0**exponent
        for candidate in [value, math.nextafter(value, 0.0), math.nextafter(value, math.inf)]:
            if math.isfinite(candidate):
                result.extend([candidate, -candidate])
    rng = random.Random(20261124)
    for _ in range(12000):
        value = struct.unpack(">d", rng.getrandbits(64).to_bytes(8, "big"))[0]
        if math.isfinite(value):
            result.append(value)
    return result


@pytest.mark.parametrize("frontend", ["typed", "legacy"])
def test_float_str_and_print_match_python(tmp_path: Path, monkeypatch, frontend: str) -> None:
    if frontend == "typed":
        monkeypatch.setattr(
            service.ServiceCompiler,
            "compile",
            lambda self, source: pipeline.compile_typed({"main": (tmp_path / "main.py", source)}),
        )
    entries = values()
    (tmp_path / "values.json").write_text(json.dumps([str(value) for value in entries]))
    expected = "".join(str(value) + "\n" + str(value) + "\n" for value in entries)
    assert parity(tmp_path, SOURCE) == expected


def test_decimal_conversion_borrows_input(tmp_path: Path) -> None:
    source = """def parse_float(value: str) -> float:
    return float(value)

def parse_integer(value: str) -> int:
    return int(value)
"""
    code = pipeline.compile_typed({"main": (tmp_path / "main.py", source)})
    assert "rt::float_from_decimal(value)" in code
    assert "rt::int_from_decimal(value)" in code
    assert "to_owned()" not in code and "clone()" not in code
    return
