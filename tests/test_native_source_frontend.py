"""Native executable parses Python source, checks it and emits runnable Rust."""

import json
import os
import subprocess
from pathlib import Path

import pytest

from py2rust.compiler.native.emitter import emit_document
from py2rust.compiler.native.source_frontend import compile_sources
from py2rust.compiler.project import create_project
from py2rust.compiler.project_output import write_service_project
from tools.bootstrap_native import stage_sources

from .test_native_emitter import build_project


@pytest.fixture(scope="module")
def source_compiler(tmp_path_factory) -> Path:
    base = tmp_path_factory.mktemp("native-source")
    source = stage_sources(base, source_mode=True)
    create_project(source, base / "rust", binary_name="py2rust-native-source")
    return build_project(base / "rust", "py2rust-native-source", base / "compiler")


def source_file(name: str, source: str) -> dict:
    return {"name": name, "package": "", "path": name + ".py", "source": source}


def invoke(binary: Path, sources: list[dict], tmp_path: Path) -> subprocess.CompletedProcess:
    (tmp_path / "sources.json").write_text(json.dumps(sources))
    return subprocess.run(
        [str(binary)],
        capture_output=True,
        text=True,
        check=False,
        env=dict(
            os.environ,
            PATH="/nonexistent",
            PYTHONHOME="/nonexistent",
            PYTHONPATH="/nonexistent",
            PY2RUST_SOURCE_INPUT=str(tmp_path / "sources.json"),
            PY2RUST_RUST_OUTPUT=str(tmp_path / "main.rs"),
        ),
    )


@pytest.mark.parametrize(
    "sources,expected",
    [
        (
            [
                source_file(
                    "main",
                    """def twice(value: int) -> int:
    return value * 2

def main() -> None:
    result: int = twice(21)
    print(result, "世界")

if __name__ == "__main__":
    main()
""",
                )
            ],
            "42 世界\n",
        ),
        (
            [
                source_file(
                    "main",
                    """from helper import choose as answer

if __name__ == "__main__":
    print(answer(9), answer(2))
""",
                ),
                source_file(
                    "helper",
                    """def choose(value: int) -> str:
    if value > 3:
        return "big"
    else:
        return "small"
""",
                ),
            ],
            "big small\n",
        ),
        (
            [
                source_file(
                    "main",
                    """def choose(flag: bool) -> int:
    if flag:
        value: int = 1
    else:
        value: int = 2
    return value

if __name__ == "__main__":
    print(choose(True), choose(False), 7 // 2, 7 % 2, 1 / 2)
""",
                )
            ],
            "1 2 3 1 0.5\n",
        ),
    ],
)
def test_native_source_compiles_and_runs(
    source_compiler: Path, tmp_path: Path, sources: list[dict], expected: str
) -> None:
    result = invoke(source_compiler, sources, tmp_path)
    assert result.returncode == 0, result.stderr
    code = (tmp_path / "main.rs").read_text()
    assert code == emit_document(compile_sources(sources, "main"))
    write_service_project(code, tmp_path / "rust")
    binary = build_project(tmp_path / "rust", "py2rust-service", tmp_path / "application")
    run = subprocess.run(
        [str(binary)],
        capture_output=True,
        text=True,
        check=True,
        env=dict(os.environ, PATH="/nonexistent", PYTHONHOME="/nonexistent", PYTHONPATH="/nonexistent"),
    )
    assert run.stdout == expected
    return


@pytest.mark.parametrize(
    "source,message",
    [
        ('def f() -> int:\n    return "wrong"\n', "return type mismatch"),
        ('def f() -> None:\n    value: int = "wrong"\n', "assignment type mismatch"),
        (
            "def f(flag: bool) -> int:\n    if flag:\n        value: int = 1\n    return value\n",
            "not definitely assigned",
        ),
        ('def f(value: int) -> int:\n    return value\n\nf("bad")\n', "argument type mismatch"),
        ("def f(flag: bool) -> int:\n    if flag:\n        return 1\n", "may exit without returning"),
    ],
)
def test_native_source_diagnostics(source_compiler: Path, tmp_path: Path, source: str, message: str) -> None:
    output = tmp_path / "main.rs"
    output.write_text("preserve existing output")
    result = invoke(source_compiler, [source_file("main", source)], tmp_path)
    assert result.returncode != 0
    assert "main.py:" in result.stderr and message in result.stderr
    assert output.read_text() == "preserve existing output"
    return


def test_native_source_rejects_global_shadowing(source_compiler: Path, tmp_path: Path) -> None:
    source = "print = 1\ndef f() -> None:\n    print(2)\nf()\n"
    result = invoke(source_compiler, [source_file("main", source)], tmp_path)
    assert result.returncode != 0
    assert "module variable bindings are not yet lowered" in result.stderr
    assert not (tmp_path / "main.rs").exists()
    return


def test_native_source_control_flow(source_compiler: Path, tmp_path: Path) -> None:
    source = """def noisy() -> bool:
    print("unexpected call")
    return True

def run() -> None:
    total: int = 0
    for index in range(1, 10, 2):
        if index == 3:
            continue
        if index == 7:
            break
        total = total + index
    while total < 9:
        total = total + 1
    assert total == 9, "wrong total"
    print(total, False and noisy(), True or noisy(), not False)
    print("ok" if total == 9 else "wrong", -7 // 2, -7 % 2, ~0, +2)
    for item in range(2):
        item = item + 10
        print(item)
    for descending in range(3, 0, -1):
        print(descending)

if __name__ == "__main__":
    run()
"""
    sources = [source_file("main", source)]
    result = invoke(source_compiler, sources, tmp_path)
    assert result.returncode == 0, result.stderr
    code = (tmp_path / "main.rs").read_text()
    assert code == emit_document(compile_sources(sources, "main"))
    write_service_project(code, tmp_path / "rust")
    binary = build_project(tmp_path / "rust", "py2rust-service", tmp_path / "application")
    output = subprocess.run([str(binary)], capture_output=True, text=True, check=True)
    assert output.stdout == "9 False True True\nok -4 1 -1 2\n10\n11\n3\n2\n1\n"
    return


@pytest.mark.parametrize(
    "source,message",
    [
        (
            "def run() -> int:\n    for index in range(0):\n        value: int = 1\n    return value\n",
            "not definitely assigned",
        ),
        ("def run() -> int:\n    while False:\n        value: int = 1\n    return value\n", "not definitely assigned"),
        ("def run() -> None:\n    for index in range(True):\n        print(index)\n", "range bound requires int"),
        (
            "def run() -> None:\n    index: int = 4\n    for index in range(2):\n        print(index)\n",
            "iteration target already bound",
        ),
        ("def run() -> None:\n    print(1 and 2)\n", "boolean operand required"),
    ],
)
def test_native_source_control_flow_errors(source_compiler: Path, tmp_path: Path, source: str, message: str) -> None:
    result = invoke(source_compiler, [source_file("main", source)], tmp_path)
    assert result.returncode != 0
    assert "main.py:" in result.stderr and message in result.stderr
    assert not (tmp_path / "main.rs").exists()
    return


def test_native_source_rejects_conditional_redefinition(source_compiler: Path, tmp_path: Path) -> None:
    source = "def f() -> int:\n    return 1\nif True:\n    def f() -> int:\n        return 2\nprint(f())\n"
    result = invoke(source_compiler, [source_file("main", source)], tmp_path)
    assert result.returncode != 0
    assert "nested declarations are unsupported" in result.stderr
    return


def test_native_source_json_and_collections(source_compiler: Path, tmp_path: Path) -> None:
    source = """from py2rust.stdlib import Json, json_loads, json_int, json_string, json_bool, json_array, json_dumps

def numbers() -> list[int]:
    return []

def count(data: Json) -> int:
    return json_int(data["count"])

def run() -> None:
    empty: list[str] = []
    values: list[int] = [2, 4, 6]
    lookup: dict[str, int] = {"one": 1, "two": 2}
    vacant: dict[str, int] = {}
    print(len(empty), len(numbers()), len(vacant), lookup["two"], values[-1])
    for index in range(len(values)):
        print(values[index])
    data: Json = {"count": 7, "items": [1, "世界", True, None], "empty": []}
    print(count(data))
    entries: list[Json] = json_array(data["items"])
    print(json_int(entries[0]), json_string(entries[1]), json_bool(entries[2]))
    roundtrip: Json = json_loads(json_dumps(data))
    print(count(roundtrip))
    inferred = [8, 9]
    print(inferred[0])
    for item in values:
        print(item)
    for key in lookup:
        print(key, lookup[key])
    for character in "世界":
        print(character)
    print(4 in values, "one" in lookup, "absent" not in lookup, "世" in "世界")

if __name__ == "__main__":
    run()
"""
    sources = [source_file("main", source)]
    result = invoke(source_compiler, sources, tmp_path)
    assert result.returncode == 0, result.stderr
    code = (tmp_path / "main.rs").read_text()
    assert code == emit_document(compile_sources(sources, "main"))
    write_service_project(code, tmp_path / "rust")
    binary = build_project(tmp_path / "rust", "py2rust-service", tmp_path / "application")
    output = subprocess.run(
        [str(binary)],
        capture_output=True,
        text=True,
        check=True,
        env=dict(os.environ, PATH="/nonexistent", PYTHONHOME="/nonexistent", PYTHONPATH="/nonexistent"),
    )
    assert (
        output.stdout
        == "0 0 0 2 6\n2\n4\n6\n7\n1 世界 True\n7\n8\n2\n4\n6\none 1\ntwo 2\n世\n界\nTrue True True True\n"
    )
    return


@pytest.mark.parametrize(
    "source,message",
    [
        ('def f() -> None:\n    xs: list[int] = [1, "bad"]\n', "list item type mismatch"),
        ("def f() -> None:\n    xs: dict[str, int] = {1: 2}\n", "dictionary item type mismatch"),
        (
            'from py2rust.stdlib import Json\ndef f() -> None:\n    x: Json = {1: "bad"}\n',
            "JSON object keys require str",
        ),
        (
            "from py2rust.stdlib import json_loads\ndef f() -> None:\n    json_loads(7)\n",
            "runtime argument type mismatch",
        ),
    ],
)
def test_native_source_collection_types(source_compiler: Path, tmp_path: Path, source: str, message: str) -> None:
    result = invoke(source_compiler, [source_file("main", source)], tmp_path)
    assert result.returncode != 0
    assert "main.py:" in result.stderr and message in result.stderr
    assert not (tmp_path / "main.rs").exists()
    return


def test_native_source_compiles_production_access_rules(source_compiler: Path, tmp_path: Path) -> None:
    from py2rust.compiler.rules import access

    rule_path = Path(__file__).resolve().parents[1] / "py2rust/compiler/rules/access.py"
    driver = """from access_rules import index_rule, render_index, render_tuple_index

def run() -> None:
    for container in ["str", "list", "Json"]:
        print(render_index(index_rule(container, "int", False), "values", "position"))
    print(render_tuple_index("pair", 1))

if __name__ == "__main__":
    run()
"""
    sources = [source_file("main", driver), source_file("access_rules", rule_path.read_text())]
    result = invoke(source_compiler, sources, tmp_path)
    assert result.returncode == 0, result.stderr
    code = (tmp_path / "main.rs").read_text()
    assert code == emit_document(compile_sources(sources, "main"))
    write_service_project(code, tmp_path / "rust")
    binary = build_project(tmp_path / "rust", "py2rust-service", tmp_path / "application")
    run = subprocess.run(
        [str(binary)],
        capture_output=True,
        text=True,
        check=True,
        env=dict(os.environ, PATH="/nonexistent", PYTHONHOME="/nonexistent", PYTHONPATH="/nonexistent"),
    )
    expected = [
        access.render_index(access.index_rule(container, "int", False), "values", "position")
        for container in ["str", "list", "Json"]
    ]
    expected.append(access.render_tuple_index("pair", 1))
    assert run.stdout.splitlines() == expected
    return


def test_native_source_string_operations(source_compiler: Path, tmp_path: Path) -> None:
    source = """def run() -> None:
    text: str = "a世界😀z"
    print(text[1:-1], text[-2:], text[:2], text[4:1], text[:])
    print(text[text.find("世"):text.rfind("z")])
    print(text.startswith("a"), text.endswith("z"), text.find("界"))
    print("Straße".casefold(), "hello".upper(), "  padded  ".strip())
    words: list[str] = "a,b,c".split(",")
    print(" | ".join(words), "hello".replace("l", "r"))
    values: list[int] = [1, 2, 3, 4]
    for item in values[-3:-1]:
        print(item)
    data: bytes = "abc".encode()
    print(len(data[1:]), data[1:][0])

if __name__ == "__main__":
    run()
"""
    sources = [source_file("main", source)]
    result = invoke(source_compiler, sources, tmp_path)
    assert result.returncode == 0, result.stderr
    code = (tmp_path / "main.rs").read_text()
    assert code == emit_document(compile_sources(sources, "main"))
    write_service_project(code, tmp_path / "rust")
    binary = build_project(tmp_path / "rust", "py2rust-service", tmp_path / "application")
    output = subprocess.run([str(binary)], capture_output=True, text=True, check=True)
    assert (
        output.stdout
        == "世界😀 😀z a世  a世界😀z\n世界😀\nTrue True 2\nstrasse HELLO padded\na | b | c herro\n2\n3\n2 98\n"
    )
    return


@pytest.mark.parametrize(
    "source,message",
    [
        ('def f() -> None:\n    print("abc"[True:])\n', "slice bound requires int"),
        ('def f() -> None:\n    print("abc"[::2])\n', "slice steps are unsupported"),
        ('def f() -> None:\n    print("abc".replace("a", 3))\n', "string method argument type mismatch"),
        ('def f() -> None:\n    print("abc".lower(1))\n', "unsupported string method overload"),
    ],
)
def test_native_source_string_type_errors(source_compiler: Path, tmp_path: Path, source: str, message: str) -> None:
    result = invoke(source_compiler, [source_file("main", source)], tmp_path)
    assert result.returncode != 0
    assert "main.py:" in result.stderr and message in result.stderr
    assert not (tmp_path / "main.rs").exists()
    return


def test_native_source_compiles_production_control_flow(source_compiler: Path, tmp_path: Path) -> None:
    from py2rust.compiler.rules import control_flow

    rule_path = Path(__file__).resolve().parents[1] / "py2rust/compiler/rules/control_flow.py"
    driver = """from control_rules import render_function, render_if, render_result_return

def run() -> None:
    print(render_function("fn sample()", ["let x = 1;"], "Ok(())"))
    print(render_if("ready", ["yes();"], ["no();"]))
    print(render_result_return("value", "", False, False, False))

if __name__ == "__main__":
    run()
"""
    sources = [source_file("main", driver), source_file("control_rules", rule_path.read_text())]
    result = invoke(source_compiler, sources, tmp_path)
    assert result.returncode == 0, result.stderr
    code = (tmp_path / "main.rs").read_text()
    assert code == emit_document(compile_sources(sources, "main"))
    write_service_project(code, tmp_path / "rust")
    binary = build_project(tmp_path / "rust", "py2rust-service", tmp_path / "application")
    output = subprocess.run(
        [str(binary)],
        capture_output=True,
        text=True,
        check=True,
        env=dict(os.environ, PATH="/nonexistent", PYTHONHOME="/nonexistent", PYTHONPATH="/nonexistent"),
    )
    expected = [
        control_flow.render_function("fn sample()", ["let x = 1;"], "Ok(())"),
        control_flow.render_if("ready", ["yes();"], ["no();"]),
        control_flow.render_result_return("value", "", False, False, False),
    ]
    assert output.stdout == "\n".join(expected) + "\n"
    return


def test_native_source_records(source_compiler: Path, tmp_path: Path) -> None:
    model = """from dataclasses import dataclass

@dataclass
class Pair:
    first: int
    second: int
    title: str = "pair"
"""
    main = """from models import Pair as Entry
from py2rust.stdlib import Json, json_dumps, json_loads, json_string

def marker(value: int) -> int:
    print(value)
    return value

def total(pair: Entry) -> int:
    return pair.first + pair.second

def run() -> None:
    pair: Entry = Entry(second=marker(2), first=marker(1))
    print(pair.title, total(pair), pair == Entry(1, 2), pair != Entry(3, 4))
    data: Json = json_loads(json_dumps(pair))
    print(json_string(data["title"]))

if __name__ == "__main__":
    run()
"""
    sources = [source_file("main", main), source_file("models", model)]
    result = invoke(source_compiler, sources, tmp_path)
    assert result.returncode == 0, result.stderr
    code = (tmp_path / "main.rs").read_text()
    assert code == emit_document(compile_sources(sources, "main"))
    write_service_project(code, tmp_path / "rust")
    binary = build_project(tmp_path / "rust", "py2rust-service", tmp_path / "application")
    output = subprocess.run([str(binary)], capture_output=True, text=True, check=True)
    assert output.stdout == "2\n1\npair 3 True True\npair\n"
    return


@pytest.mark.parametrize(
    "call,message",
    [
        ('Entry("bad", 2)', "record argument type mismatch"),
        ("Entry(1)", "missing record argument"),
        ("Entry(1, 2, unknown=3)", "unknown record keyword"),
        ("Entry(1, 2, first=3)", "duplicate record argument"),
    ],
)
def test_native_source_record_errors(source_compiler: Path, tmp_path: Path, call: str, message: str) -> None:
    source = (
        "from dataclasses import dataclass\n@dataclass\nclass Entry:\n    first: int\n    second: int\ndef run() -> None:\n    value: Entry = "
        + call
        + "\n"
    )
    result = invoke(source_compiler, [source_file("main", source)], tmp_path)
    assert result.returncode != 0
    assert "main.py:" in result.stderr and message in result.stderr
    assert not (tmp_path / "main.rs").exists()
    return


def test_native_source_compiles_production_numeric_rules(source_compiler: Path, tmp_path: Path) -> None:
    from py2rust.compiler.rules import numeric

    path = Path(__file__).resolve().parents[1] / "py2rust/compiler/rules/numeric.py"
    main = """from numeric_rules import NumericRule, select_numeric_rule, render_numeric

def run() -> None:
    for operation in ["+", "-", "*", "//", "%", "/", "<<"]:
        rule: NumericRule = select_numeric_rule(operation, "int", "int")
        print(rule.key)
        print(render_numeric(rule, "left()", "right()"))

if __name__ == "__main__":
    run()
"""
    sources = [source_file("main", main), source_file("numeric_rules", path.read_text())]
    result = invoke(source_compiler, sources, tmp_path)
    assert result.returncode == 0, result.stderr
    write_service_project((tmp_path / "main.rs").read_text(), tmp_path / "rust")
    binary = build_project(tmp_path / "rust", "py2rust-service", tmp_path / "application")
    output = subprocess.run(
        [str(binary)],
        capture_output=True,
        text=True,
        check=True,
        env=dict(os.environ, PATH="/nonexistent", PYTHONHOME="/nonexistent", PYTHONPATH="/nonexistent"),
    )
    expected = []
    for operation in ["+", "-", "*", "//", "%", "/", "<<"]:
        rule = numeric.select_numeric_rule(operation, "int", "int")
        expected.extend([rule.key, numeric.render_numeric(rule, "left()", "right()")])
    assert output.stdout.splitlines() == expected
    return


@pytest.mark.parametrize(
    "source,message",
    [
        ("from dataclasses import dataclass\n@dataclass\nclass Node:\n    child: Node\n", "recursive records require"),
        (
            'from dataclasses import dataclass\n@dataclass\nclass Item:\n    value: int = "bad"\n',
            "record default type mismatch",
        ),
        (
            "from dataclasses import dataclass\n@dataclass\nclass Item:\n    first: int = 1\n    second: int\n",
            "required record field follows default",
        ),
        (
            "from dataclasses import dataclass\nfrom py2rust.stdlib import Json\n@dataclass\nclass Item:\n    value: Json\ndef run() -> bool:\n    return Item(1) == Item(1.0)\n",
            "JSON-valued record equality requires",
        ),
    ],
)
def test_native_source_record_layout_and_defaults(
    source_compiler: Path, tmp_path: Path, source: str, message: str
) -> None:
    result = invoke(source_compiler, [source_file("main", source)], tmp_path)
    assert result.returncode != 0
    assert "main.py:" in result.stderr and message in result.stderr
    assert not (tmp_path / "main.rs").exists()
    return


def test_native_source_owned_mutations(source_compiler: Path, tmp_path: Path) -> None:
    source = """from py2rust.stdlib import Json, json_int

def run() -> None:
    values: list[int] = [1, 2]
    values.append(3)
    values.insert(1, 7)
    values.extend([8, 9])
    values[0] = 10
    print(values.pop(), values.pop(1))
    values.reverse()
    for item in values:
        print(item)
    data: dict[str, int] = {}
    data["one"] = 1
    data["two"] = 2
    del data["one"]
    print(data["two"])
    document: Json = {"count": 1, "remove": 0}
    document["count"] = 7
    del document["remove"]
    print(json_int(document["count"]))
    words: list[str] = "a,b".split(",")
    words[0] = "c"
    print(",".join(words))
    copy: list[int] = values.copy()
    copy.clear()
    print(len(copy), len(values))

if __name__ == "__main__":
    run()
"""
    sources = [source_file("main", source)]
    result = invoke(source_compiler, sources, tmp_path)
    assert result.returncode == 0, result.stderr
    code = (tmp_path / "main.rs").read_text()
    assert code == emit_document(compile_sources(sources, "main"))
    write_service_project(code, tmp_path / "rust")
    binary = build_project(tmp_path / "rust", "py2rust-service", tmp_path / "application")
    output = subprocess.run([str(binary)], capture_output=True, text=True, check=True)
    assert output.stdout == "9 7\n8\n3\n2\n10\n2\n7\nc,b\n0 4\n"
    return


@pytest.mark.parametrize(
    "source",
    [
        "def f(items: list[int]) -> None:\n    items.append(1)\n",
        "def f() -> None:\n    items: list[int] = []\n    alias: list[int] = items\n    alias.append(1)\n",
        "def f() -> None:\n    items: list[int] = []\n    alias: list[int] = items\n    items.append(1)\n",
        "def f() -> None:\n    items: list[int] = []\n    held: list[list[int]] = [items]\n    items.append(1)\n",
        "def f() -> None:\n    items: list[int] = [1]\n    for item in items:\n        items.append(2)\n",
    ],
)
def test_native_source_rejects_shared_mutation(source_compiler: Path, tmp_path: Path, source: str) -> None:
    result = invoke(source_compiler, [source_file("main", source)], tmp_path)
    assert result.returncode != 0
    assert "main.py:" in result.stderr and "unshared local owner" in result.stderr
    assert not (tmp_path / "main.rs").exists()
    return


def test_native_source_compiles_identifier_rules(source_compiler: Path, tmp_path: Path) -> None:
    from py2rust.compiler.native.names import symbol

    path = Path(__file__).resolve().parents[1] / "py2rust/compiler/native/names.py"
    driver = """from identifiers import symbol

def run() -> None:
    for name in ["plain", "compiler.module_name", "世界"]:
        print(symbol(name))

if __name__ == "__main__":
    run()
"""
    sources = [source_file("main", driver), source_file("identifiers", path.read_text())]
    result = invoke(source_compiler, sources, tmp_path)
    assert result.returncode == 0, result.stderr
    write_service_project((tmp_path / "main.rs").read_text(), tmp_path / "rust")
    binary = build_project(tmp_path / "rust", "py2rust-service", tmp_path / "application")
    output = subprocess.run(
        [str(binary)],
        capture_output=True,
        text=True,
        check=True,
        env=dict(os.environ, PATH="/nonexistent", PYTHONHOME="/nonexistent", PYTHONPATH="/nonexistent"),
    )
    assert output.stdout.splitlines() == [symbol(name) for name in ["plain", "compiler.module_name", "世界"]]
    return


def test_native_source_fresh_function_result(source_compiler: Path, tmp_path: Path) -> None:
    source = """from py2rust.stdlib import Json

def empty() -> list[int]:
    return []

def run() -> None:
    items: list[int] = empty()
    items.append(42)
    print(items[0])
    left: Json = 1
    right: Json = 1.0
    print(left == right, left != right)
    data: bytes = bytes.fromhex("61 62")
    print(data[1])

if __name__ == "__main__":
    run()
"""
    result = invoke(source_compiler, [source_file("main", source)], tmp_path)
    assert result.returncode == 0, result.stderr
    write_service_project((tmp_path / "main.rs").read_text(), tmp_path / "rust")
    binary = build_project(tmp_path / "rust", "py2rust-service", tmp_path / "application")
    output = subprocess.run([str(binary)], capture_output=True, text=True, check=True)
    assert output.stdout == "42\nTrue False\n98\n"
    return


@pytest.mark.parametrize(
    "helper",
    [
        "def alias(items: list[int]) -> list[int]:\n    return items\n",
        "def alias(items: list[int]) -> list[int]:\n    value: list[int] = []\n    for index in range(2):\n        if index == 1:\n            return value\n        value = items\n    return []\n",
    ],
)
def test_native_source_rejects_mutating_returned_alias(source_compiler: Path, tmp_path: Path, helper: str) -> None:
    source = (
        helper
        + "\ndef run() -> None:\n    items: list[int] = []\n    result: list[int] = alias(items)\n    result.append(1)\n"
    )
    result = invoke(source_compiler, [source_file("main", source)], tmp_path)
    assert result.returncode != 0
    assert "unshared local owner" in result.stderr
    return


def test_native_source_copy_return_does_not_retain_owner(source_compiler: Path, tmp_path: Path) -> None:
    source = """def copied(items: dict[str, int]) -> dict[str, int]:
    return items.copy()

def run() -> None:
    items: dict[str, int] = {"value": 1}
    result: dict[str, int] = copied(items)
    items["value"] = 2
    result["value"] = 3
    print(items["value"], result["value"])

if __name__ == "__main__":
    run()
"""
    sources = [source_file("main", source)]
    result = invoke(source_compiler, sources, tmp_path)
    assert result.returncode == 0, result.stderr
    code = (tmp_path / "main.rs").read_text()
    assert code == emit_document(compile_sources(sources, "main"))
    write_service_project(code, tmp_path / "rust")
    binary = build_project(tmp_path / "rust", "py2rust-service", tmp_path / "application")
    output = subprocess.run([str(binary)], capture_output=True, text=True, check=True)
    assert output.stdout == "2 3\n"
    return


@pytest.mark.parametrize(
    "helper",
    [
        "def held(items: list[int]) -> list[list[int]]:\n    return [items]\n",
        "def held(items: list[int]) -> list[list[int]]:\n    result: list[list[int]] = []\n    result.append(items)\n    return result.copy()\n",
        "def wrapped(items: list[int]) -> list[list[int]]:\n    return [items]\n\ndef held(items: list[int]) -> list[list[int]]:\n    return wrapped(items)\n",
    ],
)
def test_native_source_returned_contents_retain_owner(source_compiler: Path, tmp_path: Path, helper: str) -> None:
    source = helper + """
def run() -> None:
    items: list[int] = [1]
    result: list[list[int]] = held(items)
    items.append(2)
    print(result[0][0])
"""
    sources = [source_file("main", source)]
    with pytest.raises(AssertionError, match="unshared local owner"):
        compile_sources(sources, "main")
    result = invoke(source_compiler, sources, tmp_path)
    assert result.returncode != 0
    assert "unshared local owner" in result.stderr
    assert not (tmp_path / "main.rs").exists()
    return


def test_native_source_named_reads_avoid_collection_copies() -> None:
    source = """def inspect(values: list[int]) -> int:
    if 1 in values:
        return len(values) + values[0] + len(values[1:])
    return 0
"""
    code = emit_document(compile_sources([source_file("main", source)], "main"))
    # Copying the receiver would turn each constant-time len/index into O(n).
    # A slice allocates its result, but need not first clone the whole input.
    assert "py_values.clone()" not in code
    assert "rt::at(&(py_values)" in code
    return


def test_native_source_rebuilds_portable_compiler(source_compiler: Path, tmp_path: Path) -> None:
    root = stage_sources(tmp_path / "source", source_mode=True)
    sources = []
    for path in sorted(root.rglob("*.py")):
        parts = list(path.relative_to(root).with_suffix("").parts)
        if parts[-1] == "__init__":
            parts.pop()
            package = ".".join(parts)
        else:
            package = ".".join(parts[:-1])
        sources.append({"name": ".".join(parts), "package": package, "path": str(path), "source": path.read_text()})
    result = invoke(source_compiler, sources, tmp_path)
    assert result.returncode == 0, result.stderr
    code = (tmp_path / "main.rs").read_text()
    assert code == emit_document(compile_sources(sources, "main"))
    write_service_project(code, tmp_path / "rust")
    rebuilt = build_project(tmp_path / "rust", "py2rust-service", tmp_path / "compiler-rebuilt")
    # Exercise the compiler generated from Python sources, not a host-produced IR
    # fixture. The helper disables Python paths for every compiler invocation.
    selected = tmp_path / "selected"
    selected.mkdir()
    test_native_source_records(rebuilt, selected)
    invalid = tmp_path / "invalid"
    invalid.mkdir()
    test_native_source_diagnostics(rebuilt, invalid, 'def f() -> int:\n    return "bad"\n', "return type mismatch")
    return


def test_native_source_borrowed_calls_and_rebinding(source_compiler: Path, tmp_path: Path) -> None:
    source = """def inspect(items: list[int], extra: int) -> int:
    return len(items) + items[0] + extra

def rebound(items: list[int]) -> int:
    items = [9]
    return items[0]

def tagged(items: list[int], label: str) -> int:
    return len(items) + len(label)

def marker() -> int:
    print("marker")
    return 2

def run() -> None:
    values: list[int] = [4, 5]
    print(inspect(values, 1))
    print(inspect(values, marker()))
    print(rebound(values), values[0])
    label: str = "prefix:test"
    print(tagged(values, label[7:]))

if __name__ == "__main__":
    run()
"""
    sources = [source_file("main", source)]
    result = invoke(source_compiler, sources, tmp_path)
    assert result.returncode == 0, result.stderr
    code = (tmp_path / "main.rs").read_text()
    assert code == emit_document(compile_sources(sources, "main"))
    assert "fn py_main_dinspect(py_items: &Vec<i64>" in code
    assert "fn py_main_drebound(mut py_items: Vec<i64>" in code
    assert "py_main_dinspect(&(py_values)," in code
    assert "py_main_dinspect(&(py_values.clone())," in code
    assert "py_main_dtagged(&(py_values)," in code
    write_service_project(code, tmp_path / "rust")
    binary = build_project(tmp_path / "rust", "py2rust-service", tmp_path / "application")
    output = subprocess.run([str(binary)], capture_output=True, text=True, check=True)
    assert output.stdout == "7\nmarker\n8\n9 4\n6\n"
    return


def test_native_source_tcp_json_and_files(source_compiler: Path, tmp_path: Path) -> None:
    source = """from py2rust.stdlib import Json, TcpListener, TcpStream, tcp_listen, tcp_port, tcp_connect, tcp_accept_timeout, tcp_sendall, tcp_recv, tcp_close, tcp_close_listener, env_get, write_text, read_text, json_dumps, json_loads, json_string, json_int

def run() -> None:
    listener: TcpListener = tcp_listen("127.0.0.1", 0)
    client: TcpStream = tcp_connect("127.0.0.1", tcp_port(listener), 1000)
    server: TcpStream = tcp_accept_timeout(listener, 1000, 1000)
    tcp_sendall(client, b"Z")
    received: bytes = tcp_recv(server, 1)
    tcp_sendall(server, received)
    print(tcp_recv(client, 1)[0])
    tcp_close(server)
    tcp_close(client)
    tcp_close_listener(listener)
    path: str = env_get("OUTPUT_PATH", "")
    write_text(path, json_dumps({"message": "世界", "count": len(received)}))
    saved: Json = json_loads(read_text(path))
    print(json_string(saved["message"]), json_int(saved["count"]))

if __name__ == "__main__":
    run()
"""
    sources = [source_file("main", source)]
    result = invoke(source_compiler, sources, tmp_path)
    assert result.returncode == 0, result.stderr
    code = (tmp_path / "main.rs").read_text()
    assert code == emit_document(compile_sources(sources, "main"))
    write_service_project(code, tmp_path / "rust")
    binary = build_project(tmp_path / "rust", "py2rust-service", tmp_path / "application")
    destination = tmp_path / "message.json"
    output = subprocess.run(
        [str(binary)],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
        env=dict(
            os.environ,
            PATH="/nonexistent",
            PYTHONHOME="/nonexistent",
            PYTHONPATH="/nonexistent",
            OUTPUT_PATH=str(destination),
        ),
    )
    assert output.stdout == "90\n世界 1\n"
    assert json.loads(destination.read_text()) == {"message": "世界", "count": 1}
    return


@pytest.mark.parametrize(
    "body,message",
    [
        ("def f(value: TcpStream) -> Json:\n    return value\n", "opaque resources are not JSON"),
        ("def f(value: TcpStream) -> bool:\n    return value == value\n", "unsupported comparison type"),
        (
            "def f(value: TcpStream, items: list[TcpStream]) -> bool:\n    return value in items\n",
            "opaque resource membership",
        ),
        ("def f(items: dict[TcpStream, int]) -> None:\n    return\n", "opaque resource key type"),
        (
            "from dataclasses import dataclass\n@dataclass\nclass Item:\n    stream: TcpStream\n",
            "opaque resource record fields",
        ),
    ],
)
def test_native_source_rejects_resource_value_operations(
    source_compiler: Path, tmp_path: Path, body: str, message: str
) -> None:
    sources = [source_file("main", "from py2rust.stdlib import TcpStream, Json\n" + body)]
    with pytest.raises(AssertionError, match=message):
        compile_sources(sources, "main")
    result = invoke(source_compiler, sources, tmp_path)
    assert result.returncode != 0
    assert message in result.stderr and "main.py:" in result.stderr
    assert not (tmp_path / "main.rs").exists()
    return


def test_native_source_membership_evaluation_order(source_compiler: Path, tmp_path: Path) -> None:
    source = """def needle() -> int:
    print("needle")
    return 2

def container() -> list[int]:
    print("container")
    return [2]

def run() -> None:
    values: list[int] = [2]
    print(needle() in values)
    print(needle() in container())
    print(2 in values == [2])

if __name__ == "__main__":
    run()
"""
    sources = [source_file("main", source)]
    result = invoke(source_compiler, sources, tmp_path)
    assert result.returncode == 0, result.stderr
    code = (tmp_path / "main.rs").read_text()
    assert code == emit_document(compile_sources(sources, "main"))
    write_service_project(code, tmp_path / "rust")
    binary = build_project(tmp_path / "rust", "py2rust-service", tmp_path / "application")
    output = subprocess.run([str(binary)], capture_output=True, text=True, check=True)
    assert output.stdout == "needle\nTrue\nneedle\ncontainer\nTrue\nTrue\n"
    return
