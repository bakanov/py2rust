"""Sequence extrema preserve scalar types, first-equal values, evaluation count and bounded memory."""

import json
import math
import random
import struct
import subprocess
from pathlib import Path

import pytest
from py2rust.compiler.service import ServiceCompiler, ServiceError

from .test_services import parity, program, run


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_sequence_extrema_match_python_float_bits(tmp_path: Path, engine: str) -> None:
    rng = random.Random(104)
    groups = [[-0.0, 0.0], [0.0, -0.0], [5e-324], [1.7976931348623157e308, -1.7976931348623157e308]]
    for _ in range(200):
        values = []
        while len(values) < rng.randrange(2, 50):
            value = struct.unpack(">d", rng.getrandbits(64).to_bytes(8, "big"))[0]
            if math.isfinite(value):
                values.append(value)
        groups.append(values)
    (tmp_path / "numbers.json").write_text(json.dumps(groups))
    result = run(
        tmp_path,
        """
from py2rust.stdlib import json_array, json_float, json_loads, read_text, json_canonical
def check() -> None:
    for row in json_array(json_loads(read_text("numbers.json"))):
        values: list[float] = []
        for item in json_array(row):
            values.append(json_float(item))
        print(json_canonical([min(values), max(values)]))
    return
if __name__ == "__main__":
    check()
""",
        engine,
    )
    assert result.returncode == 0 and not result.stderr, result.stderr
    actual = [json.loads(line) for line in result.stdout.splitlines()]
    assert len(actual) == len(groups)
    for row, values in zip(actual, groups):
        assert [value.hex() for value in row] == [min(values).hex(), max(values).hex()]
    return  # noqa: PLR1711


def test_scalar_sequences_evaluation_order_and_recovery(tmp_path: Path) -> None:
    output = parity(
        tmp_path,
        """
from py2rust.stdlib import json_canonical
def source() -> list[str]:
    print("source")
    return ["界", "😀", "a", "é"]
def index() -> int:
    print("index")
    return 0
def check() -> None:
    integers: list[int] = [-9223372036854775808, 0, 9223372036854775807]
    assert min(integers) == -9223372036854775808 and max(integers) == 9223372036854775807
    assert min([True, False]) == False and max([False, True]) == True
    assert min(source()) == "a" and max(source()) == "😀"
    assert min((3, 1, 2)) == 1 and max(("a", "界")) == "界"
    values: tuple[float, ...] = (-0.0, 0.0)
    print(json_canonical(min(values)))
    groups: list[list[int]] = [[3, -2, 7]]
    assert max(groups[index()]) == 7
    assert groups == [[3, -2, 7]]
    empty: list[int] = []
    missing: tuple[str, ...] = ()
    try:
        print(min(empty))
    except Exception:
        print("empty minimum")
    try:
        print(max(missing))
    except Exception:
        print("empty maximum")
    print("continued")
    return
if __name__ == "__main__":
    check()
""",
    )
    assert output.splitlines() == ["source", "source", "-0e0", "index", "empty minimum", "empty maximum", "continued"]
    return  # noqa: PLR1711


def test_sequence_extrema_borrow_large_strings(tmp_path: Path) -> None:
    (tmp_path / "block").write_text("x" * 1024)
    command = program(
        tmp_path,
        """
from py2rust.stdlib import read_text
def check() -> None:
    block: str = read_text("block")
    values: list[str] = []
    for index in range(80000):
        values.append(block)
    assert min(values) == block and max(values) == block
    assert len(values) == 80000
    print("bounded extrema")
    return
if __name__ == "__main__":
    check()
""",
        "rust",
        "extrema_memory",
    )
    result = subprocess.run(
        ["/usr/bin/prlimit", "--as=134217728", "--", *command],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0 and result.stdout == "bounded extrema\n", result.stderr
    return  # noqa: PLR1711


@pytest.mark.parametrize("expression", ["min(1)", "max('abc')", "min({1, 2})", "max([[1], [2]])", "min((1, 'x'))"])
def test_unsupported_extrema_inputs_are_diagnosed(expression: str) -> None:
    source = (
        "def check() -> None:\n    print(" + expression + ')\n    return\nif __name__ == "__main__":\n    check()\n'
    )
    with pytest.raises(ServiceError, match="one-argument min/max require"):
        ServiceCompiler().compile(source)
    return  # noqa: PLR1711
