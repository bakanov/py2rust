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
    (package / "values.py").write_text("def answer() -> int:\n    return 42\n")
    (tmp_path / "main.py").write_text(
        'from app.values import answer\nif __name__ == "__main__":\n    print(answer())\n'
    )
    assert "py__app__values__answer" in compile_project(tmp_path)
    assert not (package / "__init__.py").exists()


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
    module_paths = [line for line in (output / "src/main.rs").read_text().splitlines() if "#[path" in line]
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
