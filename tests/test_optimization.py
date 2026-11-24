"""Builder lowering preserves observable values, errors and evaluation order."""

# ruff: noqa: EXE002, PLR1711 - exFAT modes and explicit-return convention
from pathlib import Path

import pytest

from py2rust.compiler.optimization import StringAppend, string_append
from py2rust.compiler.service import ServiceCompiler, ServiceError

from .test_services import parity

SOURCE = """
def suffix(old: str) -> str:
    print(old)
    return old + "!"
def fail() -> str:
    assert False, "failed suffix"
    return "unreachable"
def check() -> None:
    value: str = "a"
    saved: str = value
    for index in range(3):
        value = value + "世界"
    assert saved == "a" and value == "a世界世界世界"
    value = value + suffix(value)
    assert value == "a世界世界世界a世界世界世界!"
    before: str = value
    try:
        value = value + fail()
    except Exception:
        assert value == before
    try:
        value = value + suffix("left") + fail()
    except Exception:
        assert value == before
    finally:
        assert value == before
    value = value + value
    assert value == before + before
    value = value + ""
    value = value + "[" + suffix("tail") + "]"
    assert value.endswith("[tail!]")
    print(value)
    return
if __name__ == "__main__":
    check()
"""


@pytest.mark.parametrize("optimize", [False, True])
def test_builder_semantics(tmp_path: Path, monkeypatch, optimize: bool) -> None:
    original = ServiceCompiler.compile
    monkeypatch.setattr(
        ServiceCompiler, "compile", lambda self, source: original(ServiceCompiler(optimize=optimize), source)
    )
    parity(tmp_path, SOURCE)
    return


def test_builder_decision_and_conservative_mode() -> None:
    import ast

    plan = string_append("s", "str", ast.parse('s + "x"', mode="eval").body)
    assert isinstance(plan, StringAppend) and plan.reason == "owned_string_self_append"
    assert string_append("s", "bytes", ast.parse('s + b"x"', mode="eval").body) is None
    assert string_append("s", "str", ast.parse('"x" + s', mode="eval").body) is None
    optimized = ServiceCompiler().compile(SOURCE)
    conservative = ServiceCompiler(optimize=False).compile(SOURCE)
    assert 'value.push_str("世界")' in optimized and "__append_suffix" in optimized
    assert ".push_str(" not in conservative
    return


def test_builder_rejects_wrong_type() -> None:
    with pytest.raises(ServiceError):
        ServiceCompiler().compile(
            'def f() -> None:\n    s: str = ""\n    s = s + 1\nif __name__ == "__main__":\n    f()\n'
        )
    return


def test_unicode_index_and_slice_bounds(tmp_path: Path) -> None:
    # Generate literal expectations using Python, including empty strings,
    # combining marks, non-BMP characters, and extreme signed bounds.
    lines = ["def check() -> None:"]
    for text in ["", "abc", "a世界🙂e\u0301", "🙂🙂"]:
        lines.append(f"    value: str = {text!r}" if text == "" else f"    value = {text!r}")
        bounds = [-9223372036854775808, -9, -3, -1, 0, 1, 3, 9, 9223372036854775807]
        for start in bounds:
            for end in bounds:
                lines.append(f"    assert value[{start}:{end}] == {text[start:end]!r}")
        for position in [*range(-len(text) - 1, len(text) + 1), -9223372036854775808, 9223372036854775807]:
            if -len(text) <= position < len(text):
                lines.append(f"    assert value[{position}] == {text[position]!r}")
            else:
                lines.extend(
                    [
                        "    caught: bool = False" if text == "" and position == -1 else "    caught = False",
                        "    try:",
                        f"        print(value[{position}])",
                        "    except Exception:",
                        "        caught = True",
                        "    assert caught",
                    ]
                )
    lines.extend(["    return", 'if __name__ == "__main__":', "    check()"])
    parity(tmp_path, "\n".join(lines) + "\n")
    return


@pytest.mark.parametrize("optimize", [False, True])
def test_cached_length_semantics(tmp_path: Path, monkeypatch, optimize: bool) -> None:
    original = ServiceCompiler.compile
    monkeypatch.setattr(
        ServiceCompiler, "compile", lambda self, source: original(ServiceCompiler(optimize=optimize), source)
    )
    source = """
def scan(text: str, count: int) -> int:
    total: int = 0
    for i in range(count):
        total = total + len(text)
    return total

def mutate(text: str) -> int:
    total: int = len(text)
    text = text + "🙂"
    return total + len(text)

if __name__ == "__main__":
    assert scan("a🙂世", 4) == 12
    assert scan("", 4) == 0
    assert scan("unused", 0) == 0
    assert mutate("世") == 3
"""
    parity(tmp_path, source)
    return


def test_cached_length_decisions() -> None:
    import ast

    from py2rust.compiler.optimization import cached_lengths

    unchanged = ast.parse("def f(s):\n    while len(s):\n        break").body[0]
    assert cached_lengths(unchanged, {"s"})["s"].reason == "immutable_string_parameter_length"
    for statement in ["s = 'x'", "s += 'x'", "for s in []:\n        pass"]:
        function = ast.parse("def f(s):\n    " + statement + "\n    return len(s)").body[0]
        assert not cached_lengths(function, {"s"})
    return


@pytest.mark.parametrize("optimize", [False, True])
def test_runtime_borrow_semantics(tmp_path: Path, monkeypatch, optimize: bool) -> None:
    original = ServiceCompiler.compile
    monkeypatch.setattr(
        ServiceCompiler, "compile", lambda self, source: original(ServiceCompiler(optimize=optimize), source)
    )
    parity(
        tmp_path,
        """
from py2rust.stdlib import bytes_xor, json_dumps, regex_replace, write_bytes, read_bytes

def check() -> None:
    data: bytes = b"abc"
    path: str = "payload.bin"
    write_bytes(path, data)
    assert read_bytes(path) == data
    values: list[int] = [1, 2, 3]
    assert json_dumps(values) == "[1,2,3]"
    chunks: list[bytes] = [b"a", b"b"]
    assert bytes_xor(chunks[0], chunks.pop()) == b"\\x03"
    assert len(chunks) == 1
    pieces: list[str] = ["a", "x"]
    assert regex_replace(pieces[1], pieces.pop(), "xx") == "xx"
    assert pieces == ["a"]
    return
if __name__ == "__main__":
    check()
""",
    )
    return


def test_runtime_argument_decisions() -> None:
    import ast

    from py2rust.compiler.optimization import RuntimeParameter, runtime_argument_use

    parameter = RuntimeParameter.from_type("bytes")
    pure = ast.parse("f(a, b)", mode="eval").body.args
    effectful = ast.parse("f(a, items.pop())", mode="eval").body.args
    assert runtime_argument_use(parameter, pure, 0).mode == "borrow"
    assert runtime_argument_use(parameter, effectful, 0).reason == "argument_evaluation_effects_unknown"
    source = 'from py2rust.stdlib import bytes_xor\ndef f(a: bytes, b: bytes) -> bytes:\n    return bytes_xor(a,b)\nif __name__ == "__main__":\n    print(len(f(b"a", b"b")))\n'
    assert "rt::bytes_xor(a, b)" in ServiceCompiler().compile(source)
    assert "rt::bytes_xor(&(a.clone()), &(b.clone()))" in ServiceCompiler(optimize=False).compile(source)
    return


@pytest.mark.parametrize("optimize", [False, True])
def test_parameter_value_contract(tmp_path: Path, monkeypatch, optimize: bool) -> None:
    from .test_services import run

    original = ServiceCompiler.compile
    monkeypatch.setattr(
        ServiceCompiler, "compile", lambda self, source: original(ServiceCompiler(optimize=optimize), source)
    )
    # The subset uses value/snapshot semantics. CPython aliases are not an oracle
    # for these mutation cases; compare both native lowering modes explicitly.
    source = """
def mutate(values: list[int]) -> int:
    values.append(9)
    return len(values)

def relay(values: list[int]) -> int:
    return mutate(values) + len(values)

def first(data: bytes, depth: int) -> int:
    if depth == 0:
        return len(data)
    return second(data, depth - 1)

def second(data: bytes, depth: int) -> int:
    if depth == 0:
        return len(data)
    return first(data, depth - 1)

def pair(values: list[int], last: int) -> int:
    return len(values) + last

def detached(values: list[int]) -> list[int]:
    return values

def cleanup(text: str) -> str:
    try:
        return text
    finally:
        print(text)

if __name__ == "__main__":
    items: list[int] = [1, 2]
    assert relay(items) == 5
    assert items == [1, 2]
    assert first(b"abcd", 5) == 4
    assert pair(items, items.pop()) == 4
    assert items == [1]
    result: list[int] = detached(items)
    result.append(5)
    assert items == [1] and result == [1, 5]
    assert cleanup("kept") == "kept"
"""
    result = run(tmp_path, source, "rust")
    assert result.returncode == 0, result.stderr
    assert result.stdout == "kept\n"
    return


def test_parameter_decisions_and_callback_abi() -> None:
    source = """
def key(value: str) -> int:
    return len(value)
def read(data: bytes) -> int:
    return len(data)
def change(values: list[int]) -> None:
    values.append(3)
    return
if __name__ == "__main__":
    values: list[str] = sorted(["aa", "b"], key=key)
    print(read(b"a"))
"""
    compiler = ServiceCompiler()
    output = compiler.compile(source)
    assert compiler.parameter_uses["key"]["value"].reason == "callback_owned_abi"
    assert compiler.parameter_uses["read"]["data"].mode == "borrow"
    assert compiler.parameter_uses["change"]["values"].mode == "owned"
    assert "fn read(data: &[u8])" in output
    return


@pytest.mark.parametrize("optimize", [False, True])
def test_last_use_control_flow(tmp_path: Path, monkeypatch, optimize: bool) -> None:
    original = ServiceCompiler.compile
    monkeypatch.setattr(
        ServiceCompiler, "compile", lambda self, source: original(ServiceCompiler(optimize=optimize), source)
    )
    parity(
        tmp_path,
        """
def branch(flag: bool) -> str:
    value: str = "hello"
    if flag:
        return value
    saved: str = value
    print(saved)
    return value

def walk(count: int) -> str:
    value: str = "world"
    for i in range(count):
        if i == 1:
            continue
        if i == 3:
            break
        print(value)
    return value

def guarded(flag: bool) -> str:
    value: str = "kept"
    try:
        if flag:
            return value
        assert False, "failure"
    except Exception:
        print(value)
    finally:
        print(value)
    return value

if __name__ == "__main__":
    assert branch(True) == "hello"
    assert branch(False) == "hello"
    assert walk(0) == "world"
    assert walk(5) == "world"
    assert guarded(True) == "kept"
    assert guarded(False) == "kept"
""",
    )
    return


def test_last_use_decisions_and_owned_returns() -> None:
    import ast

    from py2rust.compiler.optimization import last_uses

    function = ast.parse("""
def f():
    value = "a"
    for i in range(3):
        print(value)
    try:
        print(value)
    finally:
        print(value)
    return value
""").body[0]
    decisions = list(last_uses(function).values())
    value_uses = [use for use in decisions if use.name == "value"]
    assert [use.mode for use in sorted(value_uses, key=lambda use: use.line)] == ["copy", "copy", "copy", "move"]
    source = 'def f() -> str:\n    value: str = "a"\n    return value\nif __name__ == "__main__":\n    print(f())\n'
    assert "Ok(value)\n" in ServiceCompiler().compile(source)
    assert "return Ok(value.clone());" in ServiceCompiler(optimize=False).compile(source)
    return


def test_last_use_retains_resource_lifetimes() -> None:
    compiler = ServiceCompiler()
    assert not compiler.move_safe_type(compiler.named_type("FileHandle"))
    assert not compiler.move_safe_type(compiler.named_type("list[FileHandle]"))
    source = 'from py2rust.stdlib import FileHandle\ndef keep(handle: FileHandle) -> FileHandle:\n    return handle\nif __name__ == "__main__":\n    pass\n'
    assert "Ok(handle.clone())\n" in compiler.compile(source)
    return


@pytest.mark.parametrize("optimize", [False, True])
def test_text_indexes_and_views(tmp_path: Path, monkeypatch, optimize: bool) -> None:
    original = ServiceCompiler.compile
    monkeypatch.setattr(
        ServiceCompiler, "compile", lambda self, source: original(ServiceCompiler(optimize=optimize), source)
    )
    parity(
        tmp_path,
        """
def scan(text: str) -> str:
    output: str = ""
    for position in range(len(text)):
        remaining: str = text[position:]
        first: str = remaining[:1]
        assert first == text[position]
        output = output + first
    return output

def changing(text: str) -> str:
    first: str = text[:1]
    text = "x"
    return first + text

def consume(text: str) -> int:
    text = text + "x"
    return len(text)

def key(text: str) -> int:
    first: str = text[:1]
    size: int = consume(text)
    return size + len(first)

def head(text: str) -> str:
    first: str = text[:2]
    return first

if __name__ == "__main__":
    assert scan("") == ""
    assert scan("a世界🙂é") == "a世界🙂é"
    assert changing("abc") == "ax"
    assert head("a🙂z") == "a🙂"
    ordered: list[str] = sorted(["long", "a"], key=key)
    assert ordered == ["a", "long"]
""",
    )
    return


def test_text_plans_reject_rebinding_and_one_off_index() -> None:
    import ast

    from py2rust.compiler.optimization import string_slice_views, text_accesses

    one = ast.parse("def f(text):\n    return text[0]").body[0]
    assert not text_accesses(one, {"text"})
    changed = ast.parse("def f(text):\n    first: str = text[:1]\n    text = 'x'\n    return first").body[0]
    assert not string_slice_views(changed, {"text"})
    reused = ast.parse(
        "def f(text):\n    try:\n        first: str = text[:1]\n    except Exception as first:\n        print(first)"
    ).body[0]
    assert not string_slice_views(reused, {"text"})
    return


@pytest.mark.parametrize("optimize", [False, True])
def test_json_views_and_owned_escapes(tmp_path: Path, monkeypatch, optimize: bool) -> None:
    original = ServiceCompiler.compile
    monkeypatch.setattr(
        ServiceCompiler, "compile", lambda self, source: original(ServiceCompiler(optimize=optimize), source)
    )
    parity(
        tmp_path,
        """
from py2rust.stdlib import Json, json_loads, json_string, json_int, json_is_null, json_array

def key() -> str:
    print("key evaluated")
    return "value"

def check() -> None:
    document: Json = json_loads('{"nested":{"rows":[{"value":"old"},null]},"count":4}')
    assert json_string(document["nested"]["rows"][0]["value"]) == "old"
    assert json_is_null(document["nested"]["rows"][-1])
    assert json_int(document["count"]) == 4
    assert len(json_array(document["nested"]["rows"])) == 2
    saved: Json = document["nested"]["rows"][0]
    document["nested"] = {"changed": True}
    assert json_string(saved["value"]) == "old"
    documents: list[Json] = [{"value": "old"}, "value"]
    assert json_string(documents[0][json_string(documents.pop())]) == "old"
    assert len(documents) == 1
    caught: bool = False
    try:
        print(json_string(document["missing"][key()]))
    except Exception:
        caught = True
    assert caught
    try:
        print(json_string(document["count"]["bad"]))
    except Exception:
        print("wrong type")
    return
if __name__ == "__main__":
    check()
""",
    )
    return


def test_json_view_lowering() -> None:
    source = 'from py2rust.stdlib import Json, json_int\ndef f(value: Json) -> int:\n    return json_int(value["a"][0]["b"])\nif __name__ == "__main__":\n    pass\n'
    code = ServiceCompiler().compile(source)
    assert 'rt::json_key_ref(value, "a")?' in code
    assert "rt::json_index_ref(" in code
    assert "rt::json_key(" not in code
    return


def test_json_array_length_uses_a_view() -> None:
    source = 'from py2rust.stdlib import Json, json_array\ndef f(value: Json) -> int:\n    return len(json_array(value))\nif __name__ == "__main__":\n    pass\n'
    code = ServiceCompiler().compile(source)
    assert "rt::json_array_ref(value)?" in code
    assert "rt::json_array(" not in code
    return


@pytest.mark.parametrize("optimize", [False, True])
def test_iteration_snapshot_and_item_ownership(tmp_path: Path, monkeypatch, optimize: bool) -> None:
    from .test_services import run

    original = ServiceCompiler.compile
    monkeypatch.setattr(
        ServiceCompiler, "compile", lambda self, source: original(ServiceCompiler(optimize=optimize), source)
    )
    source = """
from py2rust.stdlib import Json, json_array, json_loads, json_int

def check() -> None:
    values: list[int] = [1, 2, 3]
    total: int = 0
    for item in values:
        values.clear()
        total = total + item
    assert total == 6 and len(values) == 0
    rows: list[list[int]] = [[1], [2]]
    for row in rows:
        row.append(9)
    assert rows == [[1], [2]]
    escaped: list[list[int]] = []
    for row in rows:
        escaped.append(row)
    escaped[0].append(5)
    assert rows == [[1], [2]]
    total = 0
    for row in rows:
        for number in row:
            total = total + number
    assert total == 3
    document: Json = json_loads('{"rows":[{"v":10},{"v":32}]}')
    total = 0
    for entry in json_array(document["rows"]):
        total = total + json_int(entry["v"])
    assert total == 42
    return
if __name__ == "__main__":
    check()
"""
    result = run(tmp_path, source, "rust")
    assert result.returncode == 0, result.stderr
    return


def test_iteration_decisions() -> None:
    import ast

    from py2rust.compiler.optimization import iteration_use

    readonly = ast.parse("for item in values:\n    print(item)").body[0]
    mutating = ast.parse("for item in values:\n    values.clear()").body[0]
    item_mutation = ast.parse("for item in values:\n    item.append(1)").body[0]
    assert iteration_use(readonly).borrow_item
    assert iteration_use(mutating).reason == "iteration_source_may_change"
    assert iteration_use(item_mutation).mode == "borrow" and not iteration_use(item_mutation).borrow_item
    return


@pytest.mark.parametrize("optimize", [False, True])
def test_array_views_and_borrowed_serialization(tmp_path: Path, monkeypatch, optimize: bool) -> None:
    original = ServiceCompiler.compile
    monkeypatch.setattr(
        ServiceCompiler, "compile", lambda self, source: original(ServiceCompiler(optimize=optimize), source)
    )
    parity(
        tmp_path,
        """
from py2rust.stdlib import Json, json_loads, json_array, json_dumps, json_int

def inspect(document: Json) -> str:
    entries: list[Json] = json_array(document["rows"])
    total: int = 0
    for entry in entries:
        total = total + json_int(entry)
    assert total == 3
    return json_dumps(entries)

def changed(document: Json) -> int:
    entries: list[Json] = json_array(document["rows"])
    document["rows"] = [9]
    return len(entries)

def change_entries(document: Json) -> str:
    entries: list[Json] = json_array(document["rows"])
    entries.append(3)
    assert len(json_array(document["rows"])) == 2
    return json_dumps(entries)

def encode(values: list[int], text: str) -> str:
    return json_dumps(values) + json_dumps(text)

if __name__ == "__main__":
    assert inspect(json_loads('{"rows":[1,2]}')) == "[1,2]"
    assert changed(json_loads('{"rows":[1,2]}')) == 2
    assert change_entries(json_loads('{"rows":[1,2]}')) == "[1,2,3]"
    assert encode([1,2], "ok") == '[1,2]"ok"'
""",
    )
    return


@pytest.mark.parametrize("optimize", [False, True])
def test_consumed_iteration_and_binding_shadow(tmp_path: Path, monkeypatch, optimize: bool) -> None:
    from .test_services import run

    original = ServiceCompiler.compile
    monkeypatch.setattr(
        ServiceCompiler, "compile", lambda self, source: original(ServiceCompiler(optimize=optimize), source)
    )
    # Preserve the conservative compiler's scoped loop-binding behavior.
    source = """
def check() -> str:
    value: str = "old"
    saved: str = value
    for value in ["new"]:
        print(value)
    items: list[str] = ["a", "b"]
    total: int = 0
    for item in items:
        total = total + len(item)
    assert total == 2
    return saved + value
if __name__ == "__main__":
    assert check() == "oldold"
"""
    result = run(tmp_path, source, "rust")
    assert result.returncode == 0, result.stderr
    assert result.stdout == "new\n"
    return


@pytest.mark.parametrize("optimize", [False, True])
def test_sequence_views_bounds_and_owned_escape(tmp_path: Path, monkeypatch, optimize: bool) -> None:
    original = ServiceCompiler.compile
    monkeypatch.setattr(
        ServiceCompiler, "compile", lambda self, source: original(ServiceCompiler(optimize=optimize), source)
    )
    parity(
        tmp_path,
        """
from py2rust.stdlib import json_dumps, int_from_bytes

def inspect(data: bytes, values: list[str], start: int, end: int) -> str:
    chunk: bytes = data[start:end]
    tail: bytes = chunk[1:]
    entries: list[str] = values[start:end]
    return chunk.hex() + ":" + tail.hex() + ":" + json_dumps(entries)

def escape(data: bytes) -> bytes:
    chunk: bytes = data[1:]
    return chunk

def direct(data: bytes) -> int:
    return int_from_bytes(data[1:3], "big")

if __name__ == "__main__":
    for start in [-9223372036854775807, -8, -1, 0, 2, 4, 9223372036854775807]:
        for end in [-9223372036854775807, -8, -1, 0, 2, 4, 9223372036854775807]:
            print(inspect(b"abcd", ["a", "b", "c", "d"], start, end))
    assert escape(b"abcd") == b"bcd"
    assert direct(b"abcd") == 25187
""",
    )
    return


@pytest.mark.parametrize("optimize", [False, True])
def test_sequence_views_preserve_snapshots(tmp_path: Path, monkeypatch, optimize: bool) -> None:
    from .test_services import run

    original = ServiceCompiler.compile
    monkeypatch.setattr(
        ServiceCompiler, "compile", lambda self, source: original(ServiceCompiler(optimize=optimize), source)
    )
    source = """
def changed(values: list[str]) -> str:
    chunk: list[str] = values[:]
    values[0] = "changed"
    return chunk[0]

def change_view(values: list[str]) -> str:
    chunk: list[str] = values[:]
    chunk[0] = "changed"
    return values[0]

def detach(values: list[str]) -> list[str]:
    chunk: list[str] = values[1:]
    saved: list[str] = chunk
    saved[0] = "changed"
    assert chunk[0] == "b"
    return chunk

def effectful_bound(values: list[int]) -> list[int]:
    chunk: list[int] = values[values.pop():]
    assert values == [1, 2]
    return chunk

def read(values: list[int], ignored: int) -> int:
    return len(values)

def effectful_argument(values: list[int]) -> int:
    return read(values[:], values.pop())

def byte_view(values: bytearray) -> bytearray:
    chunk: bytearray = values[1:]
    return chunk

if __name__ == "__main__":
    assert changed(["a"]) == "a"
    assert change_view(["a"]) == "a"
    assert detach(["a", "b"]) == ["b"]
    assert byte_view(bytearray(b"ab")) == bytearray(b"b")
    assert effectful_bound([1, 2, 1]) == [2, 1]
    assert effectful_argument([1, 2, 1]) == 3
"""
    result = run(tmp_path, source, "rust")
    assert result.returncode == 0, result.stderr
    return


def test_sequence_slice_lowering() -> None:
    code = ServiceCompiler().compile("""
from py2rust.stdlib import int_from_bytes

def inspect(data: bytes) -> int:
    chunk: bytes = data[1:]
    return int_from_bytes(chunk[:2], "big")
if __name__ == "__main__":
    assert inspect(b"abcd") == 25187
""")
    assert "let chunk: &[u8] = rt::slice_view" in code
    assert "rt::int_from_bytes(rt::slice_view(chunk" in code
    assert "rt::bytes_slice" not in code
    return


@pytest.mark.parametrize("optimize", [False, True])
def test_direct_serialization_contract(tmp_path: Path, monkeypatch, optimize: bool) -> None:
    original = ServiceCompiler.compile
    monkeypatch.setattr(
        ServiceCompiler, "compile", lambda self, source: original(ServiceCompiler(optimize=optimize), source)
    )
    parity(
        tmp_path,
        """
from py2rust.stdlib import Json, json_loads, json_dumps, json_canonical, pretty

def encode(value: Json, rows: list[list[str]], pair: tuple[str, bool], mapping: dict[str, int]) -> None:
    print(json_dumps(value))
    print(pretty(value))
    print(json_canonical(value))
    print(json_dumps(rows))
    print(pretty(rows))
    print(json_dumps(pair))
    print(json_dumps(mapping))
    print(pretty(mapping))
    return

if __name__ == "__main__":
    encode(json_loads('{"z":[null,true,"世界"],"a":1}'), [["x", "世界"], []], ("ok", True), {"z": 1, "a": 2})
""",
    )
    return


def test_idiomatic_binding_decisions() -> None:
    import ast

    from py2rust.compiler.optimization import mutable_bindings

    function = ast.parse("""
def check(value):
    readonly: int = 1
    total: int = 0
    rows: list[int] = []
    for item in [1, 2]:
        total = total + item
        rows.append(item)
    return total
""").body[0]
    assert mutable_bindings(function) == {"total", "rows"}
    return


@pytest.mark.parametrize("idioms", [False, True])
def test_idiomatic_returns_and_mutation(tmp_path: Path, monkeypatch, idioms: bool) -> None:
    original = ServiceCompiler.__init__

    def initialize(self, *args, **kwargs):
        original(self, *args, **kwargs)
        self.optimize_idioms = idioms
        return

    monkeypatch.setattr(ServiceCompiler, "__init__", initialize)
    parity(
        tmp_path,
        """
from py2rust.stdlib import json_loads, json_int
import heapq

def parse(value: str) -> int:
    return json_int(json_loads(value))

def guarded(value: str) -> int:
    try:
        return parse(value)
    except Exception:
        return 7
    finally:
        print("cleanup")

def accumulate(limit: int) -> int:
    rows: list[int] = [2, 1]
    heapq.heapify(rows)
    total: int = heapq.heappop(rows)
    for item in range(limit):
        item = item + 1
        total = total + item
    limit = limit + 1
    return total + limit

if __name__ == "__main__":
    assert guarded("3") == 3
    assert guarded("true") == 7
    assert accumulate(3) == 11
""",
    )
    return


def test_string_comparison_representations(tmp_path: Path) -> None:
    parity(
        tmp_path,
        """
def compare(bound: str, values: list[str]) -> int:
    total: int = 0
    local: str = "a"
    view: str = bound[:]
    assert local < bound and "a" < view
    assert bound >= local and "z" > local
    for item in values:
        if item < bound and item > "a":
            total = total + 1
    return total
if __name__ == "__main__":
    assert compare("z", ["b", "c", "世界"]) == 2
""",
    )
    return
