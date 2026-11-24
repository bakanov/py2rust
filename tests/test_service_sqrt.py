"""Finite square-root bit parity, domain recovery and single evaluation."""

import json
import math
import random
import struct
from pathlib import Path

import pytest

from py2rust.stdlib import math_sqrt

from .test_services import parity, run


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_square_roots_match_python_bits(tmp_path: Path, engine: str) -> None:
    rng = random.Random(105)
    values = [-0.0, 0.0, 5e-324, 2.2250738585072014e-308, 1.7976931348623157e308, 1.0, 2.0, 4.0]
    for _ in range(5000):
        value = struct.unpack(">d", rng.getrandbits(63).to_bytes(8, "big"))[0]
        if math.isfinite(value):
            values.append(value)
    (tmp_path / "values.json").write_text(json.dumps(values))
    result = run(
        tmp_path,
        """
import math
from py2rust.stdlib import json_array, json_float, json_loads, json_canonical, read_text, math_sqrt
def check() -> None:
    for raw in json_array(json_loads(read_text("values.json"))):
        value: float = json_float(raw)
        print(json_canonical([math.sqrt(value), math_sqrt(value)]))
    return
if __name__ == "__main__":
    check()
""",
        engine,
    )
    assert result.returncode == 0 and not result.stderr, result.stderr
    rows = [json.loads(line) for line in result.stdout.splitlines()]
    assert len(rows) == len(values)
    for value, row in zip(values, rows):
        assert [item.hex() for item in row] == [math.sqrt(value).hex()] * 2
    return  # noqa: PLR1711


def test_square_root_domain_single_evaluation_and_integer_conversion(tmp_path: Path) -> None:
    output = parity(
        tmp_path,
        """
import math
from py2rust.stdlib import math_sqrt, json_canonical
def observed() -> float:
    print("called")
    return 9.0
def check() -> None:
    print(json_canonical(math.sqrt(observed())))
    assert math.sqrt(16) == 4.0 and math_sqrt(16) == 4.0
    assert math.sqrt(9223372036854775807) > 3037000499.0
    for value in [-5e-324, -1.0, -1e308]:
        try:
            math.sqrt(value)
        except Exception:
            print("domain")
        try:
            math_sqrt(value)
        except Exception:
            print("domain")
    print("continued")
    return
if __name__ == "__main__":
    check()
""",
    )
    assert output.splitlines() == ["called", "3e0", *["domain"] * 6, "continued"]
    return  # noqa: PLR1711


@pytest.mark.parametrize("value", [math.inf, -math.inf, math.nan])
def test_reference_sqrt_rejects_nonfinite_profile_values(value: float) -> None:
    with pytest.raises(ValueError, match="nonnegative finite"):
        math_sqrt(value)
    return  # noqa: PLR1711
