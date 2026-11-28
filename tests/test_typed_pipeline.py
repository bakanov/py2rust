"""Execute Rust produced from mypy-derived IR, including inferred local bindings."""

import os
import subprocess
import sys
from pathlib import Path

from py2rust.compiler.pipeline import compile_project, compile_typed
from py2rust.compiler.service import write_service_project

from .test_services import TARGET


def test_complete_typed_program(tmp_path: Path) -> None:
    helper = """from dataclasses import dataclass
from py2rust.stdlib import Json

@dataclass
class Payload:
    value: Json

@dataclass
class Summary:
    count: int
    label: str = "saved"

def summary(count: int) -> Summary:
    return Summary(count)

def rank(value: str) -> int:
    print(value)
    return len(value)

def label() -> str:
    print("label first")
    return "named"

def count() -> int:
    print("count second")
    return 9

def total(values: list[int]) -> int:
    result = 0
    for value in values:
        if 0 < value < 10:
            result = result + value
    return result
"""
    main = """from dataclasses import dataclass
from helper import Summary
import heapq
import zlib
import binascii
import logging
import json
import math
import time
from py2rust.stdlib import Json, json_kind, json_string, json_int, json_get, datetime_parse, write_text, read_text, FileHandle, file_open, file_write, file_size, file_read
from py2rust.stdlib import parallel_map, crc32
from helper import total as sum_values, summary
from native_math import byte_count as size
import native_math
import helper

@dataclass
class Envelope:
    items: list[Summary]

def field_null(document: helper.Payload) -> bool:
    if None is document.value:
        return True
    if document.value is not None:
        return False
    return False

def parallel_identity(value: Json) -> Json:
    return value

def container_value(values: list[Json]) -> int:
    return json_int(values[0]["id"])

def nested_value(values: dict[str, tuple[Json, int]]) -> int:
    return json_int(values["entry"][0]["id"]) + values["entry"][1]

def document_kind(value: Json) -> str:
    return json_kind(value)

def describe_null(value: Json) -> str:
    if value is None:
        return "null"
    if None is not value:
        return "value"
    return "unreachable"

def tuple_result() -> tuple[list[Json], Json]:
    rows: list[Json] = []
    return (rows, None)

def checked_document(valid: bool) -> Json:
    if valid:
        return {"ok": True}
    else:
        assert False, "invalid"
    return None

def conditional_document(flag: bool) -> Json:
    values: list[int] = [1, 2]
    return {"items": values if flag else [], "meta": {"ready": True} if flag else {}}

def literal_tail() -> tuple[bytes, int]:
    label: bytes = b"ready"
    while True:
        return (label, 7)
    return (label, 0)

def container_tail() -> tuple[list[str], dict[str, int]]:
    while True:
        return (["ready"], {"count": 7})
    return ([], {})

def empty_document() -> Json:
    return {}

def nested_document() -> Json:
    return {"items": [], "meta": {}}

def scoped_size(handle: FileHandle) -> int:
    with handle as resource:
        return file_size(resource)

def choose(value: int) -> int:
    try:
        assert value > 0, "positive required"
        return value
    except Exception:
        return 7
    finally:
        value = 0

def run() -> None:
    heap = [3, 1, 2]
    heapq.heapify(heap)
    heapq.heappush(heap, 0)
    assert heapq.heappop(heap) == 0
    assert heapq.heapreplace(heap, 4) == 1
    assert heapq.heappushpop(heap, heapq.heappop(heap)) == 2
    assert heapq.heappop(heap) == 3
    assert heapq.heappop(heap) == 4
    empty_heap = False
    try:
        heapq.heappop(heap)
    except Exception:
        empty_heap = True
    assert empty_heap
    assert container_value([{"id": 7}]) == 7
    assert nested_value({"entry": ({"id": 7}, 2)}) == 9
    total = 0
    for scratch in [1, 2]:
        total = total + scratch
    scratch: str = "after"
    assert total == 3 and scratch == "after"
    values = [1, 2, 30]
    ordered = sorted(["bb", "a", "cc"], reverse=True, key=helper.rank)
    assert ordered == ["bb", "cc", "a"]
    answer = sum_values(values)
    print(answer)
    print(choose(0))
    print(choose(4))
    assert answer == 3
    assert size(b"abc") == 3
    assert field_null(helper.Payload(None))
    assert not field_null(helper.Payload({"ok": True}))
    assert literal_tail() == (b"ready", 7)
    assert container_tail()[1]["count"] == 7
    assert crc32(b"123456789") == 3421780262
    assert zlib.crc32(b"123456789") == binascii.crc32(bytearray(b"123456789"))
    assert crc32(b"56789", crc32(b"1234")) == 3421780262
    interactive = False
    assert ("\\r\\n" if interactive else "\\n").join(["a", "b"]) == "a\\nb"
    byte_number = 513
    assert bytes.fromhex("02 01") == b"\\x02\\x01"
    assert bytearray.fromhex("02 01") == bytearray(b"\\x02\\x01")
    assert byte_number.to_bytes(2, "big") == b"\\x02\\x01"
    assert byte_number.to_bytes(2, "little") == b"\\x01\\x02"
    assert int.from_bytes(b"\\x02\\x01", "big") == byte_number
    assert int.from_bytes(b"\\x01\\x02", "little") == byte_number
    overflow = False
    try:
        byte_number.to_bytes(1, "big")
    except Exception:
        overflow = True
    assert overflow
    assert native_math.positive(4) == 4
    caught = False
    try:
        native_math.positive(-1)
    except Exception:
        caught = True
    assert caught
    record = helper.summary(answer)
    assert record.count == 3
    assert record.label == "saved"
    envelope = Envelope([record])
    assert envelope.items[0].count == 3
    record.count = 8
    assert record.count == 8
    named = helper.Summary(label=helper.label(), count=helper.count())
    assert named.count == 9 and named.label == "named"
    words: tuple[str, ...] = tuple(["hello", "world"])
    assert len(words) == 2 and words[-1] == "world"
    payload = json.loads('{"message":"hello"}')
    assert json_kind(payload) == "object"
    assert "message" in payload
    assert "absent" not in payload
    assert logging.INFO == 20
    assert datetime_parse("2025-01-01T00:00:00Z") < datetime_parse("2025-01-02T00:00:00Z")
    disposable: Json = {"delete": 1}
    disposable = {"delete": 2}
    del disposable["delete"]
    assert "delete" not in disposable
    assert json_string(json_get(payload, "absent", "fallback")) == "fallback"
    assert json_kind(json_get(payload, "absent", [])) == "array"
    tuple_value = tuple_result()
    assert json_kind(tuple_value[1]) == "null"
    assert json_kind(checked_document(True)) == "object"
    assert describe_null(None) == "null"
    assert describe_null({}) == "value"
    nested_null: Json = {"value": None}
    assert nested_null["value"] is None
    assert document_kind({}) == "object"
    assert document_kind("hello") == "string"
    nested_rows: dict[str, list[Json]] = {"items": [{"id": 1}, None]}
    assert json_int(nested_rows["items"][0]["id"]) == 1
    assert json_kind(nested_rows["items"][1]) == "null"
    assert nested_rows["items"][1] is None
    assert nested_rows["items"][0] is not None
    pair: tuple[bytes, Json] = (b"ok", {"count": 1})
    pair = (b"next", {"count": 2})
    assert pair[0] == b"next" and json_int(pair[1]["count"]) == 2
    documents: list[Json] = [{"name": "initial"}]
    documents = []
    documents.append({"name": "old"})
    documents[0] = {"name": "entry"}
    assert json_string(documents[0]["name"]) == "entry"
    copied = parallel_map(parallel_identity, documents, 2)
    assert json_string(copied[0]["name"]) == "entry"
    empty = empty_document()
    empty["count"] = 4
    empty["items"] = []
    assert json_int(empty["count"]) == 4
    assert json_kind(empty["items"]) == "array"
    assert json_int(conditional_document(True)["items"][0]) == 1
    assert json_kind(conditional_document(False)["items"]) == "array"
    assert json_kind(conditional_document(False)["meta"]) == "object"
    nested = nested_document()
    assert json_kind(nested["meta"]) == "object"
    assembled: Json = {"name": "saved", "count": answer, "items": [1, 2], "empty": None}
    assert json_string(assembled["name"]).strip().upper() == "SAVED"
    assert json_int(assembled["count"]) == 3
    assert json_string(payload["message"]) == "hello"
    sequence = json.loads("[1,2,3]")
    assert json_int(sequence[-1]) == 3
    missing = False
    try:
        json_string(payload["missing"])
    except Exception:
        missing = True
    assert missing
    content = json.dumps(payload)
    write_text("typed-payload.json", content)
    assert read_text("typed-payload.json") == content
    assert math.sqrt(9.0) == 3.0
    assert time.monotonic() > 0.0
    with file_open("typed-data.bin", "w+b") as output:
        file_write(output, b"abc")
    saved = file_open("typed-data.bin", "rb")
    assert scoped_size(saved) == 3
    closed = False
    try:
        file_read(saved, 1)
    except Exception:
        closed = True
    assert closed
    failed = file_open("typed-data.bin", "rb")
    try:
        with failed as resource:
            assert False, "exit resource through exception"
    except Exception:
        pass
    closed = False
    try:
        file_read(failed, 1)
    except Exception:
        closed = True
    assert closed

if __name__ == "__main__":
    run()
"""
    sources = {"helper": (tmp_path / "helper.py", helper), "main": (tmp_path / "main.py", main)}
    for path, source in sources.values():
        path.write_text(source)
    native = tmp_path / "native_math.rs"
    native.write_text(
        "pub fn byte_count(data: &[u8]) -> usize { data.len() }\n"
        'pub fn positive(value: i64) -> Result<i64, String> { if value > 0 { Ok(value) } else { Err("positive required".to_owned()) } }'
    )
    code = compile_project(tmp_path)
    (tmp_path / "native_math.py").write_text(
        "def byte_count(data: bytes) -> int:\n    return len(data)\n"
        'def positive(value: int) -> int:\n    if value <= 0:\n        raise ValueError("positive required")\n    return value\n'
    )
    assert "py__helper__total" in code
    assert "let mut result: i64" in code
    output = tmp_path / "rust"
    write_service_project(code, output)
    env = dict(os.environ, CARGO_TARGET_DIR=str(TARGET), CARGO_PROFILE_DEV_DEBUG="0", CARGO_INCREMENTAL="0")
    build = subprocess.run(
        ["cargo", "build", "--locked", "--offline", "--manifest-path", str(output / "Cargo.toml")],
        check=False,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert build.returncode == 0, build.stderr + code
    rust = subprocess.run(
        [str(TARGET / "debug" / "py2rust-service")],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
        cwd=tmp_path,
    )
    python = subprocess.run(
        [sys.executable, str(tmp_path / "main.py")],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
        cwd=tmp_path,
    )
    assert rust.returncode == python.returncode == 0, rust.stderr + python.stderr
    assert rust.stdout == python.stdout == "bb\na\ncc\n3\n7\n4\nlabel first\ncount second\n"


def test_typed_pipeline_uses_declared_binding_type(tmp_path: Path) -> None:
    source = """def answer() -> float:
    value: float = 1
    return value
if __name__ == "__main__":
    print(answer())
"""
    code = compile_typed({"main": (tmp_path / "main.py", source)})
    assert "let value: f64" in code


def test_typed_pipeline_keeps_source_locations(tmp_path: Path) -> None:
    import pytest

    from py2rust.compiler.service import ServiceError

    path = tmp_path / "unsupported.py"
    # The frontend can type this, but the current backend deliberately rejects
    # signed-integer overflow rather than generating an invalid Rust literal.
    source = """def answer() -> int:
    return 9223372036854775808
if __name__ == "__main__":
    print(answer())
"""
    with pytest.raises(ServiceError) as failure:
        compile_typed({"main": (path, source)})
    assert failure.value.filename == str(path)
    assert failure.value.lineno == 2


def test_runtime_contracts_preserve_json_type_and_import_aliases(tmp_path: Path) -> None:
    source = """from json import loads as parse
from py2rust.stdlib import json_kind as kind

def run() -> None:
    data = parse("null")
    assert kind(data) == "null"
if __name__ == "__main__":
    run()
"""
    code = compile_typed({"main": (tmp_path / "main.py", source)})
    assert "rt::json_loads" in code
    assert "rt::json_kind" in code
    assert "rt::Json" in code


def test_runtime_contracts_cannot_be_shadowed_by_project_modules(tmp_path: Path) -> None:
    import pytest

    from py2rust.compiler.frontend import FrontendError

    with pytest.raises(FrontendError, match="shadow reserved runtime contracts"):
        compile_typed({"py2rust.stdlib": (tmp_path / "stdlib.py", "")})


def test_typed_library_signature_is_not_a_rust_implementation(tmp_path: Path) -> None:
    import pytest

    from py2rust.compiler.frontend import FrontendError

    source = """from re import escape

def run() -> None:
    print(escape("hello"))
if __name__ == "__main__":
    run()
"""
    with pytest.raises(FrontendError, match="no library replacement for re.escape"):
        compile_typed({"main": (tmp_path / "main.py", source)})


def test_json_coercion_rejects_resource_handles(tmp_path: Path) -> None:
    import pytest

    from py2rust.compiler.service import ServiceError

    source = """from py2rust.stdlib import Json, FileHandle

def invalid(handle: FileHandle) -> Json:
    value: Json = handle
    return value
if __name__ == "__main__":
    pass
"""
    with pytest.raises(ServiceError, match="Json.*FileHandle"):
        compile_typed({"main": (tmp_path / "main.py", source)})
    nested = source.replace("value: Json = handle", "value: list[Json] = [handle]").replace(
        "return value", "return value[0]"
    )
    with pytest.raises(ServiceError, match="Json.*FileHandle"):
        compile_typed({"main": (tmp_path / "main.py", nested)})


def test_typed_project_discovers_namespace_packages(tmp_path: Path) -> None:
    package = tmp_path / "app"
    package.mkdir()
    (package / "values.py").write_text(
        "def __getattr__(name: str) -> object:\n    return globals()[name]\n\n" "def answer() -> int:\n    return 42\n"
    )
    (tmp_path / "main.py").write_text(
        'from app.values import answer\nif __name__ == "__main__":\n    print(answer())\n'
    )
    assert "py__app__values__answer" in compile_project(tmp_path)
    assert not (package / "__init__.py").exists()


def test_typed_record_methods_and_properties_run(tmp_path: Path, monkeypatch) -> None:
    from py2rust.compiler.service import ServiceCompiler

    from .test_services import run

    monkeypatch.setattr(
        ServiceCompiler, "compile", lambda self, source: compile_typed({"main": (tmp_path / "main.py", source)})
    )
    source = """from dataclasses import dataclass, field, replace

@dataclass
class Item:
    count: int
    label: str

    def total(self, extra: int) -> int:
        return self.count + extra

    def formatted(self) -> str:
        return f"{self.count:04d}:{self.label!r}"

    @classmethod
    def make(cls, count: int) -> "Item":
        return cls(count, "made")

    @classmethod
    def build(cls, count: int = 2) -> "Item":
        return cls.make(count=count)

    @property
    def title(self) -> str:
        return self.label.upper()

@dataclass
class Other:
    value: int = 0

@dataclass
class Holder:
    item: Other = field(default_factory=Other)

Choice = Item | Other

@dataclass
class Container:
    items: list[int] = field(default_factory=list)
    other: Other | None = field(default=None, init=False, repr=False)

@dataclass
class Pair:
    left: int
    right: int = 0

def selected(flag: bool) -> Choice:
    if flag:
        return Item(1, "one")
    return Other(2)

if __name__ == "__main__":
    item = Item(4, "ready")
    print(item.total(3))
    print(item.title)
    print(item.formatted())
    print(replace(item, count=6, label="new").total(1))
    print(Item.make(5).total(0))
    print(Item.build().total(0))
    print(type(item).__name__)
    print(type(selected(False)).__name__)
    print(len(Container().items))
    print(Container().other is None)
    print(Holder().item.value)
    print(Pair(*(value for value in [4, 5])).left)
    print(Pair(*[4]).right)
    optional: Item | None = Item(1, "optional")
    assert optional is not None
    optional.count += 2
    optional.count = 8
    print(optional.total(1))
    optional.count, optional.label = 10, "changed"
    print(str(optional.total(0)) + optional.title)
    optional.count = item.count = 12
    print(optional.total(0))
    left = right = 3
    print(left + right)
    records = [Item(0, "indexed")]
    records[0].count += 2
    print(records[0].total(0))
"""
    result = run(tmp_path, source, "rust")
    assert result.returncode == 0, result.stderr
    assert result.stdout == "7\nREADY\n0004:'ready'\n7\n5\n2\nItem\nOther\n0\nTrue\n0\n4\n0\n9\n10CHANGED\n12\n6\n2\n"


def test_typed_keyword_calls_preserve_evaluation_order(tmp_path: Path, monkeypatch) -> None:
    from py2rust.compiler.service import ServiceCompiler

    from .test_services import run

    monkeypatch.setattr(
        ServiceCompiler, "compile", lambda self, source: compile_typed({"main": (tmp_path / "main.py", source)})
    )
    source = """from dataclasses import dataclass

def label() -> str:
    print("label")
    return "value"

def number() -> int:
    print("number")
    return 3

def annotate(text: str, *, suffix: str = "!") -> str:
    return text + suffix

def count(items: tuple[int, ...] = (), flags: frozenset[int] = frozenset()) -> int:
    return len(items) + len(flags)

def render(text: str, count: int, enabled: bool) -> str:
    if enabled:
        return text.upper() + ":" + str(count)
    return text.lower() + ":" + str(count)

@dataclass(frozen=True)
class Default:
    value: int = 3

def default_value(value: Default = Default()) -> int:
    return value.value

@dataclass
class Item:
    value: int

    def render(self, enabled: bool) -> str:
        return "yes" if enabled else "no"

    def coordinates(self, left: int = 0, right: int = 0) -> str:
        return str(left) + ":" + str(right)

if __name__ == "__main__":
    print(render(count=number(), text=label(), enabled=True))
    print(annotate("done") + annotate("yes", suffix="?") + str(count()) + str(len(frozenset([1, 1, 2]))) + str(default_value()))
    print(Item(0).render(enabled=False))
    values = [4, 5]
    print(Item(0).coordinates(*(value for value in values)))
    empty: list[int] = []
    print(Item(0).coordinates(*empty))
"""
    result = run(tmp_path, source, "rust")
    assert result.returncode == 0, result.stderr
    assert result.stdout == "number\nlabel\nVALUE:3\ndone!yes?023\nno\n4:5\n0:0\n"


def test_typed_explicit_raises_are_recoverable(tmp_path: Path, monkeypatch) -> None:
    from py2rust.compiler.service import ServiceCompiler

    from .test_services import run

    monkeypatch.setattr(
        ServiceCompiler, "compile", lambda self, source: compile_typed({"main": (tmp_path / "main.py", source)})
    )
    source = """def validate(value: int) -> int:
    if value <= 0:
        raise ValueError("positive required")
    return value

if __name__ == "__main__":
    try:
        validate(0)
    except (ValueError, OSError) as error:
        print("caught: " + str(error))
    try:
        raise RuntimeError()
    except Exception as error:
        print("empty: " + str(error))
    print("continued")
"""
    result = run(tmp_path, source, "rust")
    assert result.returncode == 0, result.stderr
    assert result.stdout == "caught: positive required\nempty: \ncontinued\n"


def test_typed_starred_list_construction_runs_in_source_order(tmp_path: Path, monkeypatch) -> None:
    from py2rust.compiler.service import ServiceCompiler

    from .test_services import run

    monkeypatch.setattr(
        ServiceCompiler, "compile", lambda self, source: compile_typed({"main": (tmp_path / "main.py", source)})
    )
    source = """from py2rust.stdlib import json_canonical

def values() -> list[int]:
    print("expanded")
    return [1, 2]

if __name__ == "__main__":
    result = [0, *values(), 3]
    print(json_canonical(result))
    labels = []
    labels.append("done")
    print(json_canonical(labels))
"""
    result = run(tmp_path, source, "rust")
    assert result.returncode == 0, result.stderr
    assert result.stdout == 'expanded\n[0,1,2,3]\n["done"]\n'


def test_filtered_next_uses_default_without_temporary_list(tmp_path: Path, monkeypatch) -> None:
    from py2rust.compiler.service import ServiceCompiler

    from .test_services import run

    monkeypatch.setattr(
        ServiceCompiler, "compile", lambda self, source: compile_typed({"main": (tmp_path / "main.py", source)})
    )
    source = """from py2rust.stdlib import json_canonical

def search(values: list[int], minimum: int) -> int:
    return next((value * 10 for value in values if value > minimum), 0)

if __name__ == "__main__":
    print(search([1, 4, 6], 3))
    print(search([1, 2], 3))
    print(next((left for left, right in [(1, 0), (2, 3)] if right > 0), 0))
    print(sum(left for (left, right), flag in [((1, 2), True), ((3, 4), False)] if flag))
    print(next((left for (left, right), flag in [((1, 2), False), ((3, 4), True)] if flag), 0))
    print(json_canonical([value * 2 for value in [1, 2, 3, 4] if value % 2 == 0]))
    print("|".join(str(value) for value in [1, 2, 3] if value > 1))
    print(["a", "b"].index("b"))
    print(json_canonical([index * 10 + value for index, value in [(0, 4), (1, 5)]]))
    print(json_canonical([left * right for left in [1, 2] if left > 1 for right in [3, 4] if right < 4]))
    print(sum(value % 2 == 0 for pair in [[1, 2], [3, 4, 6]] for value in pair))
    print(len({value % 3 for pair in [[1, 2], [3, 4, 6]] for value in pair}))
    print(len(set().union([1, 2], [2, 3])))
    print(len(set().union(*[[1, 2], [2, 3]])))
    print(len({1, *[2, 3]}))
    print({str(value): value for value in [1, 2, 3] if value > 1}["2"])
    print(json_canonical([doubled for value in [1, 2, 3] if (doubled := value * 2) > 2]))
    print(min([(2, "b"), (1, "a"), (1, "c")], key=lambda pair: pair[0])[1])
    print(max([(2, "b"), (1, "a")], key=lambda pair: pair[0])[1])
    print(sorted([(2, "b"), (1, "a"), (1, "c")], key=lambda pair: pair[0])[0][1])
    print(sorted([(2, "b"), (1, "a"), (1, "c")], key=lambda pair: pair[0], reverse=True)[0][1])
    empty: list[tuple[int, str]] = []
    best = max(empty, key=lambda pair: pair[0], default=None)
    print(best is None)
    numbers: list[int] = []
    print(max((value for value in numbers), default=-1))
    print(max((value for value in [3, 2]), default=-1))
    print(sum(float(value) for value in [1, 2, 3]))
    print(sum(value for value in (1, *[2, 3])))
    print(sum(left * right for left, right in zip([1, 2], [3, 4], strict=True)))
    print(sum(left * right for left, right in zip([1, 2], [3])))
    total = 0
    for index, value in [(0, 4), (1, 5)]:
        total += index + value
    for (left, right), flag in [((1, 2), True), ((3, 4), False)]:
        if flag:
            total += left + right
    print(total)
"""
    result = run(tmp_path, source, "rust")
    assert result.returncode == 0, result.stderr
    assert (
        result.stdout
        == "40\n0\n2\n1\n3\n[4,8]\n2|3\n1\n[4,15]\n[6]\n3\n3\n3\n3\n3\n2\n[4,6]\na\nb\na\nb\nTrue\n-1\n3\n6.0\n6\n11\n3\n13\n"
    )
    assert ".collect" not in (tmp_path / "app" / "src" / "main.rs").read_text()


def test_nested_functions_capture_read_only_values(tmp_path: Path, monkeypatch) -> None:
    from py2rust.compiler.service import ServiceCompiler

    from .test_services import run

    monkeypatch.setattr(
        ServiceCompiler, "compile", lambda self, source: compile_typed({"main": (tmp_path / "main.py", source)})
    )
    source = """from dataclasses import dataclass

@dataclass
class Item:
    value: int

    def labels(self, count: int) -> str:
        def process(line: str) -> str:
            try:
                return line + ":" + str(self.value)
            except (ValueError, OSError) as error:
                return str(error)

        result = []
        for index in range(count):
            result.append(process(str(index)))
        return ",".join(result)

if __name__ == "__main__":
    print(Item(7).labels(3))
"""
    result = run(tmp_path, source, "rust")
    assert result.returncode == 0, result.stderr
    assert result.stdout == "0:7,1:7,2:7\n"


def test_pathlib_construction_and_file_io_run(tmp_path: Path, monkeypatch) -> None:
    from py2rust.compiler.service import ServiceCompiler

    from .test_services import run

    monkeypatch.setattr(
        ServiceCompiler, "compile", lambda self, source: compile_typed({"main": (tmp_path / "main.py", source)})
    )
    text = tmp_path / "typed-path.txt"
    data = tmp_path / "typed-path.bin"
    source = f"""from pathlib import Path

if __name__ == "__main__":
    text = Path({str(text)!r})
    text.write_text("hello")
    print(text.read_text())
    print(text.read_text(encoding="utf-8-sig"))
    print(text.exists())
    print(text.suffix)
    print(text.name)
    print((Path("folder") / "file.txt").suffix)
    data = Path({str(data)!r})
    data.write_bytes(b"bytes")
    print(data.read_bytes().decode())
    print(text.parent == Path({str(tmp_path)!r}))
    print(text.parent.is_dir())
    print(text.is_file())
    print(len(list(text.parent.iterdir())))
"""
    result = run(tmp_path, source, "rust")
    assert result.returncode == 0, result.stderr
    assert result.stdout == "hello\nhello\nTrue\n.txt\ntyped-path.txt\n.txt\nbytes\nTrue\nTrue\nTrue\n4\n"


def test_shlex_split_matches_python_quoting(tmp_path: Path, monkeypatch) -> None:
    from py2rust.compiler.service import ServiceCompiler

    from .test_services import run

    monkeypatch.setattr(
        ServiceCompiler, "compile", lambda self, source: compile_typed({"main": (tmp_path / "main.py", source)})
    )
    source = """import re
import shlex
import sys
from py2rust.stdlib import json_canonical, json_loads

if __name__ == "__main__":
    sys.stdout.write("stream\\n")
    sys.stdout.flush()
    print(json_canonical(shlex.split("load 'two words' \\"three words\\" plain")))
    print(json_canonical(shlex.split("say a\\ b '' \\"x\\\\\\"y\\" #literal")))
    print(type(json_loads("1")) is int)
    print(type(json_loads("1")) is str)
    print(type(json_loads("1")) in (str, int))
    print(type(json_loads("1")) not in (str, bool))
    print(re.sub("_", " ", "HELLO_WORLD"))
"""
    result = run(tmp_path, source, "rust")
    assert result.returncode == 0, result.stderr
    assert (
        result.stdout
        == 'stream\n["load","two words","three words","plain"]\n["say","a b","","x\\"y","#literal"]\nTrue\nFalse\nTrue\nTrue\nHELLO WORLD\n'
    )


def test_signed_int_from_bytes_matches_python(tmp_path: Path, monkeypatch) -> None:
    from py2rust.compiler.service import ServiceCompiler

    from .test_services import run

    monkeypatch.setattr(
        ServiceCompiler, "compile", lambda self, source: compile_typed({"main": (tmp_path / "main.py", source)})
    )
    source = """import struct

if __name__ == "__main__":
    print(int.from_bytes(b"\\xff\\xff\\xff\\xff", "little", signed=True))
    print(int.from_bytes(b"\\x80\\x00", "big", signed=True))
    print(int.from_bytes(b"\\x00\\x80", "little", signed=True))
    print(int.from_bytes(b"\\xff", "big", signed=False))
    print(b"\\x80".decode("cp1252", errors="replace"))
    print(b"a\\xffb".decode("utf-8", errors="replace"))
    print(struct.unpack("<f", struct.pack("<f", 1.0))[0])
"""
    result = run(tmp_path, source, "rust")
    assert result.returncode == 0, result.stderr
    assert result.stdout == "-1\n-32768\n-32768\n255\n€\na�b\n1.0\n"


def test_counter_construction_counts_typed_items(tmp_path: Path, monkeypatch) -> None:
    from py2rust.compiler.service import ServiceCompiler

    from .test_services import run

    monkeypatch.setattr(
        ServiceCompiler, "compile", lambda self, source: compile_typed({"main": (tmp_path / "main.py", source)})
    )
    source = """from collections import Counter, defaultdict, deque

if __name__ == "__main__":
    counts = Counter([1, 2, 1])
    print(counts[1])
    counts[1] += 2
    print(counts[1])
    print(counts.get(3, 0))
    empty: Counter[int] = Counter()
    print(len(empty))
    print(len(deque(dict.fromkeys([1, 1, 2]))))
    groups: defaultdict[int, list[int]] = defaultdict(list)
    groups[1].append(3)
    groups[1].append(4)
    print(len(groups[1]))
    print(len(groups))
    owners: defaultdict[int, set[int]] = defaultdict(set)
    owners[1].add(3)
    owners[1].add(3)
    print(len(owners[1]))
    merged = {**{"a": 1}, "b": 2, **{"a": 3}}
    print(merged["a"])
    print(len(merged))
    values = [1, 2]
    values[0], values[1] = values[1], values[0]
    print(values[0])
    values[:] = [3, 4, 5]
    print(len(values))
    del values[-2:]
    print(len(values))
"""
    result = run(tmp_path, source, "rust")
    assert result.returncode == 0, result.stderr
    assert result.stdout == "2\n4\n0\n0\n2\n2\n1\n1\n3\n2\n2\n3\n1\n"


def test_typed_callable_parameters_run(tmp_path: Path, monkeypatch) -> None:
    from py2rust.compiler.service import ServiceCompiler

    from .test_services import run

    monkeypatch.setattr(
        ServiceCompiler, "compile", lambda self, source: compile_typed({"main": (tmp_path / "main.py", source)})
    )
    source = """from collections.abc import Callable

def apply(callback: Callable[[int], int], value: int) -> int:
    return callback(value)

def double(value: int) -> int:
    return value * 2

if __name__ == "__main__":
    print(apply(double, 4))
"""
    result = run(tmp_path, source, "rust")
    assert result.returncode == 0, result.stderr
    assert result.stdout == "8\n"


def test_protocol_field_layouts_support_structural_reads(tmp_path: Path, monkeypatch) -> None:
    from py2rust.compiler.service import ServiceCompiler

    from .test_services import run

    monkeypatch.setattr(
        ServiceCompiler, "compile", lambda self, source: compile_typed({"main": (tmp_path / "main.py", source)})
    )
    source = """from dataclasses import dataclass
from typing import Protocol

class Point(Protocol):
    x: int
    y: int

@dataclass
class GridPoint:
    x: int
    y: int

def sum_point(point: Point) -> int:
    return point.x + point.y

if __name__ == "__main__":
    print(sum_point(GridPoint(3, 4)))
"""
    result = run(tmp_path, source, "rust")
    assert result.returncode == 0, result.stderr
    assert result.stdout == "7\n"


def test_generator_functions_iterate_as_typed_sequences(tmp_path: Path, monkeypatch) -> None:
    from py2rust.compiler.service import ServiceCompiler

    from .test_services import run

    monkeypatch.setattr(
        ServiceCompiler, "compile", lambda self, source: compile_typed({"main": (tmp_path / "main.py", source)})
    )
    source = """from collections.abc import Iterator
from itertools import accumulate, count
from py2rust.stdlib import json_canonical

def values(limit: int) -> Iterator[int]:
    yield 1
    for value in range(limit):
        if value % 2 == 0:
            yield value * 10

if __name__ == "__main__":
    print(sum(values(5)))
    print(sum(values(0)))
    serial = count()
    print(next(serial))
    print(next(serial))
    print(json_canonical(accumulate([1, 2, 3], initial=0)))
"""
    result = run(tmp_path, source, "rust")
    assert result.returncode == 0, result.stderr
    assert result.stdout == "61\n1\n0\n1\n[0,1,3,6]\n"


def test_random_seed_and_randrange_match_python(tmp_path: Path, monkeypatch) -> None:
    from py2rust.compiler.service import ServiceCompiler

    from .test_services import run

    monkeypatch.setattr(
        ServiceCompiler, "compile", lambda self, source: compile_typed({"main": (tmp_path / "main.py", source)})
    )
    source = """from dataclasses import dataclass, field
from random import Random
from py2rust.stdlib import json_canonical

@dataclass
class Generator:
    random: Random = field(default_factory=Random)

if __name__ == "__main__":
    random = Random(7)
    print(random.randrange(100))
    print(random.random())
    print(random.randrange(90, 110))
    print(0 <= Generator().random.randrange(10) < 10)
    values = [1, 2, 3, 4]
    Random(7).shuffle(values)
    print(json_canonical(values))
    print(Random(7).choice([1, 2, 3]))
"""
    result = run(tmp_path, source, "rust")
    assert result.returncode == 0, result.stderr
    assert result.stdout == "41\n0.9478653606090632\n102\nTrue\n[4,2,1,3]\n2\n"


def test_int_flag_bitwise_conditions_run(tmp_path: Path, monkeypatch) -> None:
    from py2rust.compiler.service import ServiceCompiler

    from .test_services import run

    monkeypatch.setattr(
        ServiceCompiler,
        "compile",
        lambda self, source: compile_typed({"main": (tmp_path / "main.py", source)}, python_scope=True),
    )
    source = """from enum import Enum, IntEnum, IntFlag

class EntryIntent(Enum):
    MOVE = 1
    FIGHT = 2

    @property
    def peaceful(self) -> bool:
        return self == self.MOVE

    @classmethod
    def default(cls) -> "EntryIntent":
        return cls.MOVE

from enum import auto

class CitizenMood(IntEnum):
    HAPPY = 0
    CONTENT = 1
    UNHAPPY = auto()
    INVALID = -1

class UnitOrder(IntFlag):
    MOVE = 1 << 0
    BOMB = 1 << 1

def selected(orders: UnitOrder) -> str:
    if orders & UnitOrder.BOMB:
        return "bomb"
    if not orders & UnitOrder.MOVE:
        return "none"
    return "move"

def mood(mood: CitizenMood) -> str:
    return "content" if mood else "happy"

def present(value: EntryIntent | None) -> bool:
    return True if value else False

if __name__ == "__main__":
    print(selected(UnitOrder.MOVE))
    print(selected(UnitOrder.BOMB))
    print(mood(CitizenMood.HAPPY))
    print(mood(CitizenMood.CONTENT))
    print(mood(CitizenMood.UNHAPPY))
    print(mood(CitizenMood.INVALID))
    print(mood(CitizenMood(0)))
    print(EntryIntent.MOVE.peaceful)
    print(EntryIntent.default().peaceful)
    print(EntryIntent(1).peaceful)
    print(UnitOrder.MOVE.name)
    print(CitizenMood.UNHAPPY.name)
    print(present(EntryIntent.MOVE))
    print(present(None))
    print({"a": 1}.get("b") is None)
    print(EntryIntent.__members__["MOVE"].peaceful)
"""
    result = run(tmp_path, source, "rust")
    assert result.returncode == 0, result.stderr
    assert (
        result.stdout
        == "move\nbomb\nhappy\ncontent\ncontent\ncontent\nhappy\nTrue\nTrue\nTrue\nMOVE\nUNHAPPY\nTrue\nFalse\nTrue\nTrue\n"
    )


def test_python_scope_enables_checked_truthiness(tmp_path: Path, monkeypatch) -> None:
    from py2rust.compiler.service import ServiceCompiler

    from .test_services import run

    monkeypatch.setattr(
        ServiceCompiler,
        "compile",
        lambda self, source: compile_typed({"main": (tmp_path / "main.py", source)}, python_scope=True),
    )
    source = """def select(values: list[int], count: int) -> str:
    result = "nonempty" if values else "empty"
    if count:
        return result
    return "zero"

def optional_length(values: list[int] | None) -> int:
    return 1 if values else 0

def optional_number(value: int | None) -> int:
    return 1 if value else 0

if __name__ == "__main__":
    print(select([], 0))
    print(select([1], 1))
    empty: list[int] | None = []
    some: list[int] | None = [2]
    print(optional_length(None))
    print(optional_length(empty))
    print(optional_length(some))
    print(optional_number(None))
    print(optional_number(0))
    print(optional_number(2))
"""
    result = run(tmp_path, source, "rust")
    assert result.returncode == 0, result.stderr
    assert result.stdout == "zero\nnonempty\n0\n0\n1\n0\n0\n1\n"


def test_optional_values_and_narrowed_record_fields_run(tmp_path: Path, monkeypatch) -> None:
    from py2rust.compiler.service import ServiceCompiler

    from .test_services import run

    monkeypatch.setattr(
        ServiceCompiler,
        "compile",
        lambda self, source: compile_typed({"main": (tmp_path / "main.py", source)}, python_scope=True),
    )
    source = """from dataclasses import dataclass

@dataclass
class Item:
    count: int

@dataclass
class Other:
    count: int

def union_field(item: Item | Other | None) -> int:
    if item is None:
        return -1
    return item.count

def select(value: int | None) -> int | None:
    if value is not None:
        return value
    return None

def field(item: Item | None) -> int:
    if item is None:
        return -1
    return item.count

def wrap(value: int) -> int | None:
    return value

def present_union(item: Item | Other) -> bool:
    return True if item else False

def present(item: Item | None) -> bool:
    if item is not None:
        return True if item else False
    return False

def choose(value: int | None = None, fallback: int = 7) -> int:
    if value is None:
        return fallback
    return value

if __name__ == "__main__":
    print(choose())
    print(choose(2))
    print(choose(fallback=9))
    print(choose(value=3, fallback=8))
    print(union_field(Item(5)))
    print(union_field(Other(6)))
    print(union_field(None))
    print(select(None) is None)
    print(select(2) is not None)
    print(field(Item(4)))
    print(field(None))
    print(present(Item(1)))
    print(present(None))
    print(present_union(Other(2)))
    print(wrap(3) is not None)
    left, right = (3, 4)
    print(left * 10 + right)
    left += 1
    print(left)
"""
    result = run(tmp_path, source, "rust")
    assert result.returncode == 0, result.stderr
    assert result.stdout == "7\n2\n9\n3\n5\n6\n-1\nTrue\nTrue\n4\n-1\nTrue\nFalse\nTrue\nTrue\n34\n4\n"


def test_block_local_redeclarations_and_generated_name_collisions(tmp_path: Path) -> None:
    source = """def choose(flag: bool) -> int:
    value__block_1: int = 5
    if flag:
        value: str = "yes"
        return len(value) + value__block_1
    if not flag:
        value: int = 7
        return value + value__block_1
    return 0
if __name__ == "__main__":
    assert choose(True) == 8
    assert choose(False) == 12
"""
    code = compile_typed({"main": (tmp_path / "main.py", source)})
    assert "value__block_1: i64" in code
    assert "value__block_2: String" in code


def test_block_local_names_do_not_leak(tmp_path: Path) -> None:
    import pytest

    from py2rust.compiler.frontend import FrontendError

    source = """def invalid(flag: bool) -> str:
    if flag:
        local: str = "inside"
    return local
if __name__ == "__main__":
    pass
"""
    with pytest.raises(FrontendError, match='Name "local" is not defined'):
        compile_typed({"main": (tmp_path / "main.py", source)})


def test_logging_severity_mapping_and_argument_validation(tmp_path: Path) -> None:
    import pytest

    from py2rust.compiler.frontend import FrontendError

    source = """import logging
if __name__ == "__main__":
    logging.error("failed")
"""
    code = compile_typed({"main": (tmp_path / "main.py", source)})
    assert "rt::log" in code and "40i64" in code
    unsupported = source.replace('logging.error("failed")', 'logging.error("failed %s", "detail")')
    with pytest.raises(FrontendError, match="requires 1 positional arguments"):
        compile_typed({"main": (tmp_path / "main.py", unsupported)})


def test_container_argument_conversions_remain_checked(tmp_path: Path) -> None:
    import pytest

    from py2rust.compiler.frontend import FrontendError
    from py2rust.compiler.service import ServiceError

    source = """from py2rust.stdlib import Json, FileHandle

def consume(values: list[Json]) -> None:
    return

def invalid(handle: FileHandle) -> None:
    consume([handle])
    return

if __name__ == "__main__":
    pass
"""
    with pytest.raises(ServiceError, match="Json.*FileHandle"):
        compile_typed({"main": (tmp_path / "main.py", source)})
    incompatible = source.replace("    consume([handle])", "    values: list[int] = [1]\n    consume(values)")
    with pytest.raises(FrontendError, match="incompatible type"):
        compile_typed({"main": (tmp_path / "main.py", incompatible)})


def test_record_dependency_cycles_have_source_diagnostics(tmp_path: Path) -> None:
    import pytest

    source = """from dataclasses import dataclass
@dataclass
class First:
    children: list["Second"]
@dataclass
class Second:
    children: list[First]
if __name__ == "__main__":
    pass
"""
    with pytest.raises(ValueError, match=r"main.py:.*mutually recursive records.*main.First.*main.Second"):
        compile_typed({"main": (tmp_path / "main.py", source)})


def test_typed_loop_bindings_preserve_subset_scope(tmp_path: Path, monkeypatch) -> None:
    from py2rust.compiler.service import ServiceCompiler

    from .test_services import run

    monkeypatch.setattr(
        ServiceCompiler, "compile", lambda self, source: compile_typed({"main": (tmp_path / "main.py", source)})
    )
    source = """def check() -> str:
    value: str = "outer"
    for value in [1, 2]:
        assert value > 0
    return value
if __name__ == "__main__":
    assert check() == "outer"
"""
    result = run(tmp_path, source, "rust")
    assert result.returncode == 0, result.stderr


def test_packaged_typed_native_project_is_relocatable(tmp_path: Path, monkeypatch) -> None:
    import json

    from py2rust.compiler.project import MARKER, Project, create_project

    root = tmp_path / "source"
    (root / "bridge/math").mkdir(parents=True)
    (root / "main.py").write_text(
        "from bridge.math import double\ndef run() -> None:\n    result = double(21)\n    print(result)\n"
        'if __name__ == "__main__":\n    run()\n'
    )
    (root / "bridge/math.rs").write_text("mod detail;\npub fn double(value: i64) -> i64 { detail::double(value) }\n")
    (root / "bridge/math/detail.rs").write_text("pub fn double(value: i64) -> i64 { value * 2 }\n")

    def reject_legacy(self, **kwargs):
        raise AssertionError("typed packaging must not invoke the legacy frontend")

    monkeypatch.setattr(Project, "compile", reject_legacy)
    output = tmp_path / "generated"
    create_project(root, output, frontend="typed")
    metadata = json.loads((output / MARKER).read_text())
    assert metadata["frontend"] == "typed"
    assert metadata["symbols"]
    module_paths = [line for line in (output / "src/bridge/math.rs").read_text().splitlines() if "#[path" in line]
    assert module_paths and all(str(root) not in line for line in module_paths)
    root.rename(tmp_path / "unavailable-source")
    relocated = tmp_path / "relocated"
    output.rename(relocated)
    build = subprocess.run(
        ["cargo", "build", "--locked", "--offline", "--manifest-path", str(relocated / "Cargo.toml")],
        env=dict(os.environ, CARGO_TARGET_DIR=str(TARGET), CARGO_PROFILE_DEV_DEBUG="0", CARGO_INCREMENTAL="0"),
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert build.returncode == 0, build.stderr
    result = subprocess.run(
        [str(TARGET / "debug/py2rust-service")], capture_output=True, text=True, check=False, timeout=10
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "42\n"
