"""Execute Rust programs produced by the compiler's transpiled Python emitter."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from py2rust.compiler.ir_exchange import to_document
from py2rust.compiler.native.emitter import emit_document
from py2rust.compiler.pipeline import prepare_typed
from py2rust.compiler.project import create_project
from py2rust.compiler.project_output import write_service_project
from tools.bootstrap_native import stage_sources

ROOT = Path(__file__).resolve().parents[1]
TARGET = Path(os.environ.get("PY2RUST_BUILD_DIR", str(ROOT / "build"))) / "service-test-target"


def build_project(project: Path, name: str, destination: Path) -> Path:
    subprocess.run(
        ["cargo", "build", "--locked", "--offline", "--manifest-path", str(project / "Cargo.toml"), "--bin", name],
        env=dict(os.environ, CARGO_TARGET_DIR=str(TARGET), CARGO_PROFILE_DEV_DEBUG="0", CARGO_INCREMENTAL="0"),
        check=True,
        capture_output=True,
        text=True,
    )
    shutil.copyfile(TARGET / "debug" / name, destination)
    destination.chmod(0o755)
    return destination


@pytest.fixture(scope="module")
def native_emitter(tmp_path_factory) -> Path:
    directory = tmp_path_factory.mktemp("native-emitter")
    source = stage_sources(directory)
    create_project(source, directory / "rust", binary_name="py2rust-native-ir")
    return build_project(directory / "rust", "py2rust-native-ir", directory / "emitter")


CASES = [
    """def twice(value: int) -> int:
    return value * 2

def run() -> None:
    total: int = 0
    for index in range(5):
        total = total + twice(index)
    while total > 15:
        total = total - 1
    print(total, -7 // 2, -7 % 2, 1 / 2)
    print(-9223372036854775808)

if __name__ == "__main__":
    run()
""",
    """def marker(value: int) -> int:
    print(value)
    return value

def run() -> None:
    print(marker(3) < marker(2) < marker(1))
    print(False and marker(9) == 9)
    print(True or marker(8) == 8)
    greeting: str = "世界"
    result: str = greeting + " 😀" if True else "unreachable"
    print(result, str(1.0), str(-0.0), int(" 12 "), float("2.5"))
    assert result != "", "missing greeting"

if __name__ == "__main__":
    run()
""",
    """def inverse(value: int) -> float:
    return 1 / value

if __name__ == "__main__":
    print(inverse(0))
""",
]


CASES.append("""def run() -> None:
    values: list[int] = [1, 2]
    values.append(3)
    values.insert(1, 7)
    print(values.pop(), values[-1], len(values))
    values[0] = 10
    for value in values:
        print(value)
    lookup: dict[str, int] = {"one": 1, "two": 2}
    lookup["one"] = 5
    del lookup["two"]
    lookup["three"] = 3
    for key in lookup:
        print(key, lookup[key])
    print("one" in lookup, "two" not in lookup, 7 in values)
    labels: list[str] = ["hello", "世界"]
    print(", ".join(labels), "hello".upper(), len("héllo"))
    data: bytes = b"abc"
    print(data[1], len(data))
    for byte in data:
        print(byte)

if __name__ == "__main__":
    run()
""")


@pytest.mark.parametrize("source", CASES)
def test_native_emitter_produces_executable_programs(tmp_path: Path, native_emitter: Path, source: str) -> None:
    python_path = tmp_path / "main.py"
    python_path.write_text(source)
    prepared = prepare_typed({"main": (python_path, source)})
    document = to_document(prepared.modules, prepared.entry)
    input_path, output_path = tmp_path / "program.json", tmp_path / "main.rs"
    input_path.write_text(json.dumps(document))
    env = dict(
        os.environ,
        PATH="/nonexistent",
        PYTHONHOME="/nonexistent",
        PYTHONPATH="/nonexistent",
        PY2RUST_IR_INPUT=str(input_path),
        PY2RUST_RUST_OUTPUT=str(output_path),
    )
    subprocess.run([str(native_emitter)], env=env, check=True, capture_output=True)
    generated = output_path.read_text()
    assert generated == emit_document(document)
    write_service_project(generated, tmp_path / "rust")
    binary = build_project(tmp_path / "rust", "py2rust-service", tmp_path / "application")
    native = subprocess.run([str(binary)], env=env, capture_output=True, text=True, check=False)
    reference = subprocess.run([sys.executable, str(python_path)], capture_output=True, text=True, check=False)
    assert native.stdout == reference.stdout
    assert (native.returncode == 0) == (reference.returncode == 0)
    if reference.returncode:
        assert "division by zero" in native.stderr
    return


@pytest.mark.parametrize(
    "source,line,message",
    [
        (
            "def run(values: list[int]) -> None:\n    print(len(values[values.pop():]))\n",
            2,
            "native slice needs proven effect-free bounds",
        ),
        (
            "def run() -> None:\n    values: list[int] = [0, 1]\n    print(values[values.pop()])\n",
            3,
            "native index needs a proven effect-free key",
        ),
    ],
)
def test_native_emitter_reports_source_for_unsupported_construct(
    tmp_path: Path, native_emitter: Path, source: str, line: int, message: str
) -> None:
    prepared = prepare_typed({"main": (tmp_path / "unsupported.py", source)})
    path = tmp_path / "program.json"
    path.write_text(json.dumps(to_document(prepared.modules, prepared.entry)))
    destination = tmp_path / "unchanged.rs"
    destination.write_text("keep existing output")
    result = subprocess.run(
        [str(native_emitter)],
        check=False,
        capture_output=True,
        text=True,
        env=dict(
            os.environ,
            PATH="/nonexistent",
            PYTHONHOME="/nonexistent",
            PYTHONPATH="/nonexistent",
            PY2RUST_IR_INPUT=str(path),
            PY2RUST_RUST_OUTPUT=str(destination),
        ),
    )
    assert result.returncode != 0
    assert "unsupported.py:" + str(line) + ":" in result.stderr
    assert message in result.stderr
    assert destination.read_text() == "keep existing output"
    return


def test_native_emitter_links_project_modules(tmp_path: Path, native_emitter: Path) -> None:
    helper = "def answer(value: int) -> int:\n    return value * 2\n"
    main = 'from helper import answer\n\nif __name__ == "__main__":\n    print(answer(21))\n'
    prepared = prepare_typed({"main": (tmp_path / "main.py", main), "helper": (tmp_path / "helper.py", helper)})
    document = to_document(prepared.modules, prepared.entry)
    source, destination = tmp_path / "project.json", tmp_path / "main.rs"
    source.write_text(json.dumps(document))
    env = dict(
        os.environ,
        PATH="/nonexistent",
        PYTHONHOME="/nonexistent",
        PYTHONPATH="/nonexistent",
        PY2RUST_IR_INPUT=str(source),
        PY2RUST_RUST_OUTPUT=str(destination),
    )
    subprocess.run([str(native_emitter)], env=env, capture_output=True, check=True)
    write_service_project(destination.read_text(), tmp_path / "rust")
    executable = build_project(tmp_path / "rust", "py2rust-service", tmp_path / "application")
    result = subprocess.run([str(executable)], env=env, capture_output=True, text=True, check=True)
    assert result.stdout == "42\n"
    return


def test_native_emitter_compiles_production_control_flow_rules(tmp_path: Path, native_emitter: Path) -> None:
    from py2rust.compiler.rules import control_flow

    rule_path = Path(control_flow.__file__)
    driver = """from rule_module import render_function, render_if, render_result_return

def run() -> None:
    print(render_function("fn example()", ["first();", "second();"], "Ok(())"))
    print(render_if("condition", ["body();"], ["otherwise();"]))
    print(render_result_return("value", "", False, False, False))

if __name__ == "__main__":
    run()
"""
    prepared = prepare_typed(
        {"main": (tmp_path / "main.py", driver), "rule_module": (rule_path, rule_path.read_text())}
    )
    source, destination = tmp_path / "rules.json", tmp_path / "rules.rs"
    source.write_text(json.dumps(to_document(prepared.modules, prepared.entry)))
    env = dict(
        os.environ,
        PATH="/nonexistent",
        PYTHONHOME="/nonexistent",
        PYTHONPATH="/nonexistent",
        PY2RUST_IR_INPUT=str(source),
        PY2RUST_RUST_OUTPUT=str(destination),
    )
    subprocess.run([str(native_emitter)], env=env, capture_output=True, text=True, check=True)
    write_service_project(destination.read_text(), tmp_path / "rust")
    binary = build_project(tmp_path / "rust", "py2rust-service", tmp_path / "rules")
    result = subprocess.run([str(binary)], env=env, capture_output=True, text=True, check=True)
    expected = (
        control_flow.render_function("fn example()", ["first();", "second();"], "Ok(())")
        + "\n"
        + control_flow.render_if("condition", ["body();"], ["otherwise();"])
        + "\n"
        + control_flow.render_result_return("value", "", False, False, False)
        + "\n"
    )
    assert result.stdout == expected
    return


CASES.append("""from dataclasses import dataclass

@dataclass
class Pair:
    first: int
    second: int
    label: str = "pair"

def marker(value: int) -> int:
    print(value)
    return value

def run() -> None:
    item: Pair = Pair(second=marker(2), first=marker(1))
    item.first = item.first + 10
    print(item.label, item.first, item.second)
    print(item == Pair(11, 2), item != Pair(12, 2))

if __name__ == "__main__":
    run()
""")


def test_native_emitter_compiles_production_numeric_rules(tmp_path: Path, native_emitter: Path) -> None:
    from py2rust.compiler.rules import numeric

    rule_path = Path(numeric.__file__)
    driver = """from rule_module import NumericRule, select_numeric_rule, render_numeric

def run() -> None:
    for operation in ["+", "-", "*", "//", "%", "/", "<<", "**"]:
        rule: NumericRule = select_numeric_rule(operation, "int", "int")
        print(rule.key)
        print(render_numeric(rule, "left()", "right()"))

if __name__ == "__main__":
    run()
"""
    prepared = prepare_typed(
        {"main": (tmp_path / "main.py", driver), "rule_module": (rule_path, rule_path.read_text())}
    )
    source, destination = tmp_path / "numeric.json", tmp_path / "numeric.rs"
    source.write_text(json.dumps(to_document(prepared.modules, prepared.entry)))
    env = dict(
        os.environ,
        PATH="/nonexistent",
        PYTHONHOME="/nonexistent",
        PYTHONPATH="/nonexistent",
        PY2RUST_IR_INPUT=str(source),
        PY2RUST_RUST_OUTPUT=str(destination),
    )
    subprocess.run([str(native_emitter)], env=env, capture_output=True, text=True, check=True)
    write_service_project(destination.read_text(), tmp_path / "rust")
    binary = build_project(tmp_path / "rust", "py2rust-service", tmp_path / "numeric")
    result = subprocess.run([str(binary)], env=env, capture_output=True, text=True, check=True)
    expected = ""
    for operation in ["+", "-", "*", "//", "%", "/", "<<", "**"]:
        rule = numeric.select_numeric_rule(operation, "int", "int")
        expected += rule.key + "\n" + numeric.render_numeric(rule, "left()", "right()") + "\n"
    assert result.stdout == expected
    return


CASES.append("""from py2rust.stdlib import Json, json_array, json_int, json_loads, json_dumps, json_keys

def run() -> None:
    document: Json = {"count": 2, "items": [1, 3], "title": "世界"}
    document["count"] = 7
    print(json_int(document["count"]))
    values: list[Json] = json_array(document["items"])
    for value in values:
        print(json_int(value))
    print(json_dumps(document))
    parsed: Json = json_loads("{\\"ok\\": true}")
    print(json_dumps(parsed))

if __name__ == "__main__":
    run()
""")


def test_native_runtime_contracts_match_production_registry() -> None:
    from py2rust.compiler.library_contracts import (
        LIBRARY,
        RUNTIME_PARAMETERS,
        RUNTIME_VALUE_READERS,
    )
    from py2rust.compiler.native.runtime_contracts import runtime_contract
    from tools.generate_native_contracts import DESTINATION, render_source

    assert DESTINATION.read_text() == render_source()
    for name, (result, parameters, fallible) in LIBRARY.items():
        contract = runtime_contract(name)
        assert contract.name == name and contract.result == result
        assert contract.parameters == list(parameters)
        assert contract.shared == [parameter.passing == "shared" for parameter in RUNTIME_PARAMETERS[name]]
        assert contract.fallible == fallible
        assert contract.value_reader == (name in RUNTIME_VALUE_READERS)
    return


CASES.append("""def run() -> None:
    text: str = "a世界😀z"
    print(text[1:], text[:-1], text[-3:99], text[4:1], text[:])
    values: list[int] = [1, 2, 3, 4]
    for value in values[-3:-1]:
        print(value)
    data: bytes = b"abcd"
    print(len(data[1:3]), data[1:3][0])

if __name__ == "__main__":
    run()
""")


def test_native_emitter_compiles_production_ir_reader(tmp_path: Path, native_emitter: Path) -> None:
    from py2rust.compiler.native.ir_schema import validate_document

    rule_path = ROOT / "py2rust/compiler/native/ir_schema.py"
    driver = """from py2rust.stdlib import env_get, json_loads_unique, read_text
from schema_module import validate_document

def run() -> None:
    for name in validate_document(json_loads_unique(read_text(env_get("DOCUMENT", "")))):
        print(name)

if __name__ == "__main__":
    run()
"""
    prepared = prepare_typed(
        {"main": (tmp_path / "main.py", driver), "schema_module": (rule_path, rule_path.read_text())}
    )
    document = to_document(prepared.modules, prepared.entry)
    source, destination = tmp_path / "schema.json", tmp_path / "schema.rs"
    source.write_text(json.dumps(document))
    env = dict(
        os.environ,
        PATH="/nonexistent",
        PYTHONHOME="/nonexistent",
        PYTHONPATH="/nonexistent",
        PY2RUST_IR_INPUT=str(source),
        PY2RUST_RUST_OUTPUT=str(destination),
        DOCUMENT=str(source),
    )
    subprocess.run([str(native_emitter)], env=env, capture_output=True, text=True, check=True)
    write_service_project(destination.read_text(), tmp_path / "rust")
    binary = build_project(tmp_path / "rust", "py2rust-service", tmp_path / "schema")
    result = subprocess.run([str(binary)], env=env, capture_output=True, text=True, check=True)
    assert result.stdout.splitlines() == validate_document(document)
    document["format"] = 99
    source.write_text(json.dumps(document))
    rejected = subprocess.run([str(binary)], env=env, capture_output=True, text=True, check=False)
    assert rejected.returncode != 0
    assert "unsupported IR format version" in rejected.stderr
    return


CASES.append("""from py2rust.stdlib import Json, json_int

def run() -> None:
    position: Json = {"offset": 1}
    values: list[int] = [10, 20]
    print(values[json_int(position["offset"])])
    print(ord("世"), ord(b"a"))
    print(bytes.fromhex("61 62")[1])

if __name__ == "__main__":
    run()
""")


def test_native_emitter_rebuilds_portable_compiler(tmp_path: Path, native_emitter: Path) -> None:
    source = stage_sources(tmp_path / "compiler")
    sources = {}
    for path in source.rglob("*.py"):
        parts = list(path.relative_to(source).with_suffix("").parts)
        if parts[-1] == "__init__":
            parts.pop()
        sources[".".join(parts)] = (path, path.read_text())
    prepared = prepare_typed(sources)
    document = to_document(prepared.modules, prepared.entry)
    ir_file, rust_file = tmp_path / "compiler.json", tmp_path / "compiler.rs"
    ir_file.write_text(json.dumps(document))
    env = dict(
        os.environ,
        PATH="/nonexistent",
        PYTHONHOME="/nonexistent",
        PYTHONPATH="/nonexistent",
        PY2RUST_IR_INPUT=str(ir_file),
        PY2RUST_RUST_OUTPUT=str(rust_file),
    )
    subprocess.run([str(native_emitter)], env=env, capture_output=True, text=True, check=True, timeout=120)
    write_service_project(rust_file.read_text(), tmp_path / "rust")
    rebuilt = build_project(tmp_path / "rust", "py2rust-service", tmp_path / "rebuilt-emitter")
    program = 'def run() -> None:\n    print(6 * 7)\n\nif __name__ == "__main__":\n    run()\n'
    selected = prepare_typed({"main": (tmp_path / "selected.py", program)})
    selected_document = to_document(selected.modules, selected.entry)
    ir_file.write_text(json.dumps(selected_document))
    subprocess.run([str(rebuilt)], env=env, capture_output=True, text=True, check=True, timeout=120)
    assert rust_file.read_text() == emit_document(selected_document)
    write_service_project(rust_file.read_text(), tmp_path / "application")
    application = build_project(tmp_path / "application", "py2rust-service", tmp_path / "selected")
    result = subprocess.run([str(application)], env=env, capture_output=True, text=True, check=True)
    assert result.stdout == "42\n"
    return


def test_native_emitter_keeps_mutated_parameters_owned(tmp_path: Path, native_emitter: Path) -> None:
    source = """def consume(values: list[int], mapping: dict[str, int]) -> int:
    values[0] = 7
    values.append(9)
    del mapping["old"]
    mapping["new"] = 4
    return values.pop() + mapping["new"]

if __name__ == "__main__":
    print(consume([1], {"old": 2}))
"""
    test_native_emitter_produces_executable_programs(tmp_path, native_emitter, source)
    code = (tmp_path / "main.rs").read_text()
    assert "mut py_values: Vec<i64>" in code
    assert "mut py_mapping: indexmap::IndexMap<String, i64>" in code
    return
