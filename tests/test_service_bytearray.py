"""Byte buffers: ordinary Python behavior, checked growth and explicit native value semantics."""

from pathlib import Path

import pytest
from py2rust.compiler.service import ServiceCompiler, ServiceError

from .test_services import parity, run


def test_bytearray_construction_mutation_and_conversion(tmp_path: Path) -> None:
    parity(
        tmp_path,
        """
from dataclasses import dataclass
@dataclass
class Packet:
    data: bytearray
def check() -> None:
    data: bytearray = bytearray()
    assert len(data) == 0 and bytes() == b""
    for number in range(256):
        data.append(number)
    assert list(data) == list(bytes(data))
    pair: tuple[int, ...] = tuple(data)
    assert pair[255] == 255
    for number in range(256):
        data[number] = data[number] ^ 255
    assert data[0] == 255 and data[-1] == 0
    copied: bytearray = data.copy()
    copied.reverse()
    assert copied[0] == 0 and data[0] == 255
    assert bytearray.fromhex(copied.hex()) == bytes(copied)
    for start in [-9223372036854775808, -300, -256, -1, 0, 1, 256, 300, 9223372036854775807]:
        for end in [-300, -1, 0, 1, 256, 300]:
            assert bytes(data[start:end]) == bytes(data)[start:end]
    copied.clear()
    copied.extend(b"abc")
    copied.extend(copied)
    assert copied.decode() == "abcabc"
    assert copied.pop() == 99
    assert copied.pop(-2) == 97
    del copied[1]
    assert copied == b"acb"
    assert bytearray(3) == b"\x00\x00\x00" and bytes(2) == b"\x00\x00"
    values: list[int] = [0, 127, 128, 255]
    assert bytes(values) == bytearray(values)
    packet: Packet = Packet(bytearray(b"old"))
    local: bytearray = packet.data.copy()
    local[0] = 110
    packet.data = local
    assert packet.data.decode() == "nld"
    total: int = 0
    for number in bytes(data):
        total = total + number
    assert total == 32640
    return
if __name__ == "__main__":
    check()
""".replace("\x00", "\\x00"),
    )
    return  # noqa: PLR1711


def test_bytearray_membership_and_evaluation_order(tmp_path: Path) -> None:
    output = parity(
        tmp_path,
        """
def observed(value: int) -> int:
    print(value)
    return value
def needle() -> bytes:
    print("needle")
    return b"bc"
def container() -> bytearray:
    print("container")
    return bytearray(b"abcd")
def check() -> None:
    assert needle() in container()
    data: bytearray = bytearray(b"abcd")
    assert 97 in data and 255 not in data and b"" in data
    assert bytearray(b"bc") in b"abcd" and b"dc" not in data
    assert data == b"abcd" and b"abcc" < data and data <= bytearray(b"abcd")
    data[observed(-1)] = observed(100)
    data.append(data.pop(0))
    assert data == b"bcda"
    data[data.pop() - 97] = data.pop(0)
    assert data == b"bd"
    print(data.hex())
    return
if __name__ == "__main__":
    check()
""",
    )
    assert output == "needle\ncontainer\n100\n-1\n6264\n"
    return  # noqa: PLR1711


def test_bytearray_invalid_values_and_indices_leave_buffer_unchanged(tmp_path: Path) -> None:
    parity(
        tmp_path,
        """
def check() -> None:
    data: bytearray = bytearray(b"ab")
    errors: int = 0
    for invalid in [-9223372036854775808, -1, 256, 9223372036854775807]:
        try:
            data.append(invalid)
        except Exception:
            errors = errors + 1
        try:
            data[0] = invalid
        except Exception:
            errors = errors + 1
        try:
            value: bytes = bytes([0, invalid])
        except Exception:
            errors = errors + 1
        try:
            present: bool = invalid in data
        except Exception:
            errors = errors + 1
    for position in [-9223372036854775808, -3, 2, 9223372036854775807]:
        try:
            data[position] = 65
        except Exception:
            errors = errors + 1
        try:
            data.pop(position)
        except Exception:
            errors = errors + 1
        try:
            del data[position]
        except Exception:
            errors = errors + 1
    assert errors == 28 and data == b"ab"
    for length in [-1, -9223372036854775808]:
        try:
            bytearray(length)
        except Exception:
            errors = errors + 1
    assert errors == 30
    return
if __name__ == "__main__":
    check()
""",
    )
    return  # noqa: PLR1711


def test_bytearray_native_bound_and_owned_copies(tmp_path: Path) -> None:
    result = run(
        tmp_path,
        """
def mutate(value: bytearray) -> bytearray:
    value[0] = 42
    return value
def check() -> None:
    first: bytearray = bytearray(b"a")
    second: bytearray = first
    second[0] = 98
    assert first == b"a" and mutate(first)[0] == 42 and first == b"a"
    errors: int = 0
    for length in [67108865, 9223372036854775807]:
        try:
            bytearray(length)
        except Exception:
            errors = errors + 1
        try:
            bytes(length)
        except Exception:
            errors = errors + 1
    large: bytearray = bytearray(67108864)
    large[-1] = 17
    try:
        large.append(0)
    except Exception:
        errors = errors + 1
    try:
        large.extend(b"x")
    except Exception:
        errors = errors + 1
    assert errors == 6 and len(large) == 67108864 and large[-1] == 17
    print("bounded owned buffers")
    return
if __name__ == "__main__":
    check()
""",
        "rust",
    )
    assert result.returncode == 0 and result.stdout == "bounded owned buffers\n", result.stderr
    return  # noqa: PLR1711


@pytest.mark.parametrize(
    "statement",
    [
        'data: bytearray = bytearray("text")',
        "data: bytearray = bytearray(True)",
        "data: bytearray = bytearray([1.2])",
        'data: bytearray = bytearray(b"x", "utf8")',
        "data: bytearray = bytearray(); data.append(True)",
        "data: bytearray = bytearray(); data.extend([1])",
        'data: bytearray = bytearray(); data[0:1] = b"x"',
        "data: bytearray = bytearray(); del data[:]",
        "data: bytearray = bytearray(); data[::1]",
        "data: bytearray = bytearray(); data.append(value=1)",
        "data: bytearray = bytearray(); data[0] = 1.0",
        "bytearray: int = 1",
    ],
)
def test_bytearray_unsupported_operations_have_diagnostics(statement: str) -> None:
    with pytest.raises(
        ServiceError,
        match="byte constructors|expected Type.*int|bytearray.extend|new locals|del supports|slice steps|keyword arguments|reserved binding",
    ):
        ServiceCompiler().compile(
            "def check() -> None:\n    " + statement + '\n    return\nif __name__ == "__main__":\n    check()\n'
        )
    return  # noqa: PLR1711


def test_bytearray_generated_operation_sequences(tmp_path: Path) -> None:
    import random

    rng = random.Random(5617)
    expected = bytearray()
    statements = ["data: bytearray = bytearray([])", 'assert bytes([]) == b""']
    for _ in range(350):
        action = rng.choice(["append", "set", "pop", "extend", "delete", "reverse"]) if expected else "append"
        number = rng.randrange(256)
        if action == "append":
            expected.append(number)
            statements.append(f"data.append({number})")
        elif action == "extend":
            suffix = bytes(rng.randrange(256) for _ in range(rng.randrange(6)))
            expected.extend(suffix)
            statements.append(f"data.extend({suffix!r})")
        elif action == "reverse":
            expected.reverse()
            statements.append("data.reverse()")
        else:
            position = rng.randrange(-len(expected), len(expected))
            if action == "set":
                expected[position] = number
                statements.append(f"data[{position}] = {number}")
            elif action == "pop":
                statements.append(f"assert data.pop({position}) == {expected.pop(position)}")
            else:
                del expected[position]
                statements.append(f"del data[{position}]")
        statements.append(f'assert data.hex() == "{expected.hex()}"')
    source = "def check() -> None:\n" + "\n".join("    " + statement for statement in statements)
    source += '\n    return\nif __name__ == "__main__":\n    check()\n'
    parity(tmp_path, source)
    return  # noqa: PLR1711


def test_bytearray_and_math_in_complete_project(tmp_path: Path) -> None:
    import os
    import subprocess
    import sys

    from .test_project import build, sources

    root = sources(
        tmp_path,
        {
            "buffers.py": """from dataclasses import dataclass
import math as formulas
@dataclass
class Bits:
    data: bytearray
def allocate(count: int) -> Bits:
    return Bits(bytearray(formulas.ceil(count / 8)))
def position(probability: float) -> int:
    return formulas.floor(-formulas.log(probability))
""",
            "main.py": """from buffers import Bits as Store, allocate, position
def main() -> None:
    state: Store = allocate(17)
    data: bytearray = state.data.copy()
    data[2] = 1 << position(0.5)
    state.data = data
    assert state.data.hex() == "000001"
    print(state.data.hex())
    return
if __name__ == "__main__":
    main()
""",
        },
    )
    binary = build(root, tmp_path / "rust")
    expected = subprocess.run([sys.executable, str(root / "main.py")], capture_output=True, text=True, check=True)
    actual = subprocess.run(
        [str(binary)],
        env=dict(os.environ, PATH="/nonexistent", PYTHONHOME="/nonexistent", PYTHONPATH="/nonexistent"),
        capture_output=True,
        text=True,
        check=True,
    )
    assert actual.stdout == expected.stdout == "000001\n"
    return  # noqa: PLR1711
