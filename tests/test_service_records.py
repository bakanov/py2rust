"""Owned typed records, constructor evaluation, field updates and project linkage."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from py2rust.compiler.service import ServiceCompiler, ServiceError

from .test_project import build, sources
from .test_services import parity, run


def test_record_fields_defaults_keywords_and_collections(tmp_path: Path) -> None:
    parity(
        tmp_path,
        """
from dataclasses import dataclass
@dataclass
class Point:
    x: int
    y: int = -1
@dataclass
class Packet:
    origin: Point
    text: str = ""
    data: bytes = b""
    ready: bool = False
    elapsed: float = 0.0

def observed(number: int) -> int:
    print(number)
    return number

def update(value: Packet) -> Packet:
    value.text = "世界"
    value.data = value.data + b"xyz"
    value.ready = True
    point: Point = value.origin
    point.x = point.x + 1
    value.origin = point
    return value

def check() -> None:
    position: Point = Point(y=observed(2), x=observed(1))
    assert position.x == 1 and position.y == 2
    packet: Packet = Packet(position, data=b"abc")
    packet = update(packet)
    assert packet.origin.x == 2 and packet.origin.y == 2
    assert packet.text == "世界" and packet.data == b"abcxyz" and packet.ready and packet.elapsed == 0.0
    lookup: dict[str, Packet] = {"one": packet}
    assert "one" in lookup and "two" not in lookup
    loaded: Packet = lookup["one"]
    loaded.text = "updated"
    lookup["one"] = loaded
    assert lookup["one"].text == "updated"
    keys: list[str] = list(lookup)
    assert keys == ["one"]
    points: list[Point] = [Point(3), Point(4, 5)]
    for point in points:
        print(point.x, point.y)
    print(lookup["one"].text)
    for key in list(lookup):
        del lookup[key]
    assert len(lookup) == 0 and keys == ["one"]
    return
if __name__ == "__main__":
    check()
""",
    )
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def test_records_can_hold_scoped_resources(tmp_path: Path) -> None:
    parity(
        tmp_path,
        """
from dataclasses import dataclass
from py2rust.stdlib import FileHandle, file_open, file_write, file_read, file_seek
@dataclass
class Holder:
    handle: FileHandle
    label: str = "data"
def check() -> None:
    original: FileHandle = file_open("record.bin", "w+b")
    record: Holder = Holder(original)
    with record.handle as stream:
        file_write(stream, b"record bytes")
        file_seek(record.handle, 0, 0)
        assert file_read(original, 100) == b"record bytes"
    failed: bool = False
    try:
        file_read(record.handle, 1)
    except Exception:
        failed = True
    assert failed
    print(record.label)
    return
if __name__ == "__main__":
    check()
""",
    )
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def test_native_records_follow_owned_value_semantics(tmp_path: Path) -> None:
    result = run(
        tmp_path,
        """
from dataclasses import dataclass
@dataclass
class Record:
    text: str
    values: list[int]
def alter(value: Record) -> Record:
    value.text = "callee"
    return value
def check() -> None:
    first: Record = Record("first", [1, 2])
    second: Record = first
    second.text = "second"
    saved: list[Record] = [first]
    third: Record = saved[0]
    numbers: list[int] = third.values
    numbers.append(3)
    third.values = numbers
    changed: Record = alter(first)
    assert first.text == "first" and second.text == "second" and changed.text == "callee"
    assert len(saved[0].values) == 2 and len(third.values) == 3
    print("owned records")
    return
if __name__ == "__main__":
    check()
""",
        "rust",
    )
    assert result.returncode == 0 and result.stdout == "owned records\n", result.stderr
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def test_imported_record_types_aliases_and_defaults(tmp_path: Path) -> None:
    root = sources(
        tmp_path,
        {
            "shapes.py": """from dataclasses import dataclass as record
@record
class Point:
    x: int
    label: str = "origin"
""",
            "model.py": """from dataclasses import dataclass
from enum import Enum
from shapes import Point as Position
class Phase(Enum):
    NEW = 1
    DONE = 2
@dataclass
class Envelope:
    point: Position
    phase: Phase
    payload: bytes = b""
""",
            "main.py": """from model import Envelope as Message, Phase
from shapes import Point

def main() -> None:
    value: Message = Message(point=Point(7), phase=Phase.NEW)
    assert value.point.label == "origin" and value.point.x == 7 and value.phase == Phase.NEW
    value.phase = Phase.DONE
    value.payload = b"native project"
    print(value.phase.name, value.payload.decode())
    return
if __name__ == "__main__":
    main()
""",
        },
    )
    native = build(root, tmp_path / "rust")
    python = subprocess.run([sys.executable, str(root / "main.py")], capture_output=True, text=True, check=False)
    compiled = subprocess.run(
        [str(native)],
        env=dict(os.environ, PATH="/nonexistent", PYTHONHOME="/nonexistent", PYTHONPATH="/nonexistent"),
        capture_output=True,
        text=True,
        check=False,
    )
    assert python.returncode == compiled.returncode == 0, python.stderr + compiled.stderr
    assert python.stdout == compiled.stdout == "DONE native project\n"
    assert "struct Envelope" in (tmp_path / "rust/src/model.rs").read_text()
    return  # noqa: PLR1711 - explicit return required by repository guidelines


@pytest.mark.parametrize(
    ("declaration", "message"),
    [
        ("@dataclass(frozen=True)\nclass Item:\n    number: int", "plain @dataclass"),
        ("@dataclass\nclass Item(object):\n    number: int", "no inheritance"),
        ("@dataclass\nclass Item:\n    number = 1", "annotated fields"),
        ("@dataclass\nclass Item:\n    number: int = 1\n    name: str", "required dataclass fields"),
        ("@dataclass\nclass Item:\n    data: list[int] = []", "scalar literals"),
        ("@dataclass\nclass Item:\n    number: int\n    number: int", "duplicate dataclass field"),
        (
            "@dataclass\nclass Item:\n    number: int\n    def method(self) -> int:\n        return 1",
            "annotated fields",
        ),
    ],
)
def test_unsupported_record_declarations(declaration: str, message: str) -> None:
    with pytest.raises(ServiceError, match=message):
        ServiceCompiler().compile(
            "from dataclasses import dataclass\n"
            + declaration
            + '\ndef check() -> None:\n    return\nif __name__ == "__main__":\n    check()\n'
        )
    return  # noqa: PLR1711 - explicit return required by repository guidelines


@pytest.mark.parametrize(
    ("statement", "message"),
    [
        ("value: Item = Item()", "missing required dataclass"),
        ("value: Item = Item(1, 2, 3)", "invalid positional dataclass"),
        ("value: Item = Item(1, count=2)", "duplicate dataclass"),
        ("value: Item = Item(1, unknown=2)", "unknown, expanded"),
        ("value: Item = Item(True)", "expected"),
        ('value: Item = Item(1)\n    value.count = "bad"', "expected"),
        ("value: Item = Item(1)\n    value.missing = 3", "unknown dataclass field"),
        ("value: Item = Item(1)\n    print(value == value)", "compare dataclass fields"),
        ("value: Item = Item(1)\n    print(value in [value])", "compare dataclass fields"),
    ],
)
def test_record_constructor_and_update_diagnostics(statement: str, message: str) -> None:
    source = (
        'from dataclasses import dataclass\n@dataclass\nclass Item:\n    count: int\n    label: str = ""\ndef check() -> None:\n    '
        + statement
        + '\n    return\nif __name__ == "__main__":\n    check()\n'
    )
    with pytest.raises(ServiceError, match=message):
        ServiceCompiler().compile(source)
    return  # noqa: PLR1711 - explicit return required by repository guidelines
