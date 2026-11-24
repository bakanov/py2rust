"""End-to-end project linking and direct native Rust import checks."""

import http.client
import json
import os
import shutil
import subprocess
import sys

import pytest
from py2rust.compiler.project import MARKER, Project, create_project
from py2rust.compiler.rust_imports import ProjectError
from py2rust.compiler.service import ServiceError

from .test_services import ROOT, TARGET, server_process


def sources(tmp_path, files):
    root = tmp_path / "source"
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return root


def build(root, output, entry="main.py"):
    create_project(root, output, entry)
    result = subprocess.run(
        [
            "cargo",
            "build",
            "--locked",
            "--offline",
            "--manifest-path",
            str(output / "Cargo.toml"),
        ],
        env=dict(
            os.environ,
            CARGO_TARGET_DIR=str(TARGET),
            CARGO_PROFILE_DEV_DEBUG="0",
            CARGO_INCREMENTAL="0",
        ),
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    executable = output / "program"
    shutil.copyfile(TARGET / "debug" / "py2rust-service", executable)
    executable.chmod(0o755)
    return executable


def run_project(root, output, entry="main.py"):
    return subprocess.run(
        [str(build(root, output, entry))],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


def test_shipped_mixed_project(tmp_path):
    root = tmp_path / "app"
    shutil.copytree(
        ROOT / "examples/projects/json_app",
        root,
        ignore=shutil.ignore_patterns(".py2rust", "__pycache__"),
    )
    result = run_project(root, tmp_path / "rust")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "bytes": 6,
        "message": "Hello, 世界",
        "path": "/hello",
        "status": "ok",
        "version": 1,
    }


@pytest.mark.parametrize(
    "extension,implementation",
    [
        ("py", "def sqrt(value: float) -> float:\n    return value + 40.0\n"),
        ("rs", "pub fn sqrt(value: f64) -> f64 { value + 40.0 }\n"),
    ],
)
def test_local_math_module_precedes_stdlib_fallback(tmp_path, extension, implementation):
    root = sources(
        tmp_path,
        {
            "main.py": """import math
def main() -> None:
    assert math.sqrt(2.0) == 42.0
    print("local math")
    return
if __name__ == "__main__":
    main()
""",
            "math." + extension: implementation,
        },
    )
    result = run_project(root, tmp_path / "rust")
    assert result.returncode == 0, result.stderr
    assert result.stdout == "local math\n"


def test_python_packages_aliases_scopes_and_enums(tmp_path):
    root = sources(
        tmp_path,
        {
            "main.py": """import one.math
import two.math as second
from one import PublicState as State
from one.math import value as first
from py2rust.stdlib import pretty as display
def calculate(first: int) -> int:
    return first + 1
def main() -> None:
    status: State = State.OK
    assert status.value == "ok"
    assert one.math.value() == 12
    assert second.value() == 20
    assert first() == 12
    assert calculate(4) == 5
    print(display([first(), second.value()]))
if __name__ == "__main__":
    main()
""",
            "one/__init__.py": "from .models import State as PublicState\n",
            "one/models.py": 'from enum import Enum\nclass State(Enum):\n    OK = "ok"\n',
            "one/math.py": "VALUE: int = 12\ndef value() -> int:\n    return VALUE\n",
            "two/math.py": "def value() -> int:\n    return 20\n",
        },
    )
    result = run_project(root, tmp_path / "rust")
    assert result.returncode == 0, result.stderr
    reference = subprocess.run(
        [sys.executable, str(root / "main.py")],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout == reference.stdout


def test_nested_entry_and_relative_import(tmp_path):
    root = sources(
        tmp_path,
        {
            "app/__init__.py": '"""Package."""\n',
            "app/__main__.py": "from .helpers import message\nprint(message())\n",
            "app/helpers.py": 'def message() -> str:\n    return "package entry"\n',
        },
    )
    result = run_project(root, tmp_path / "rust", "app/__main__.py")
    assert result.returncode == 0, result.stderr
    assert result.stdout == "package entry\n"


def test_native_types_results_and_submodules(tmp_path):
    root = sources(
        tmp_path,
        {
            "main.py": """from native import add, label, echo, count, checked, emit, total, toggle, ratio
from py2rust.stdlib import Json, json_int
def main() -> None:
    assert add(2, 3) == 5
    assert label() == "native"
    assert echo(b"hi") == b"hi"
    assert count("世界") == 2
    assert checked(4) == 8
    assert total([2, 3]) == 5
    assert not toggle(True)
    assert ratio(1.5) == 3.0
    data: Json = emit()
    assert json_int(data["answer"]) == 42
    print("native types work")
if __name__ == "__main__":
    main()
""",
            "native.rs": """mod helper;
pub fn add(a: i32, b: u16) -> i32 { helper::add(a, b as i32) }
pub fn label() -> &'static str { "native" }
pub fn echo(data: &[u8]) -> Vec<u8> { data.to_vec() }
pub fn count(data: &str) -> usize { data.chars().count() }
pub fn checked(n: i64) -> Result<i64, String> { if n < 0 { Err("negative".into()) } else { Ok(n * 2) } }
pub fn emit() -> serde_json::Value { serde_json::json!({"answer": 42}) }
pub fn total(values: Vec<i64>) -> i64 { values.iter().sum() }
pub fn toggle(value: bool) -> bool { !value }
pub fn ratio(value: f64) -> f64 { value * 2.0 }
""",
            "native/helper.rs": "pub fn add(a: i32, b: i32) -> i32 { a + b }\n",
        },
    )
    result = run_project(root, tmp_path / "rust")
    assert result.returncode == 0, result.stderr
    assert result.stdout == "native types work\n"


@pytest.mark.parametrize("call", ["small(256)", "failure()", "huge()", "nan()", "nan_list()"])
def test_native_range_and_result_errors(tmp_path, call):
    root = sources(
        tmp_path,
        {
            "main.py": f"from native import small, failure, huge, nan, nan_list\n{call}\n",
            "native.rs": """pub fn small(n: u8) -> i64 { n as i64 }
pub fn failure() -> Result<i64, String> { Err("native failure".into()) }
pub fn huge() -> u64 { u64::MAX }
pub fn nan() -> f64 { f64::NAN }
pub fn nan_list() -> Vec<f64> { vec![f64::INFINITY] }
""",
        },
    )
    result = run_project(root, tmp_path / "rust")
    assert result.returncode != 0
    assert "panicked" not in result.stderr


def test_cross_module_http_handler_and_rust_call(tmp_path):
    root = tmp_path / "app"
    shutil.copytree(
        ROOT / "examples/projects/json_app",
        root,
        ignore=shutil.ignore_patterns(".py2rust", "__pycache__"),
    )
    server = root / "server.py"
    server.write_text(server.read_text().replace("8080", "0"))
    executable = build(root, tmp_path / "rust", "server.py")
    with server_process([str(executable)]) as (process, port):
        client = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        try:
            client.request("POST", "/", json.dumps({"name": "世界", "path": "/hello?x=1"}))
            response = client.getresponse()
            assert response.status == 200
            assert json.loads(response.read())["bytes"] == 6
        finally:
            client.close()
        process.communicate(timeout=5)
        assert process.returncode == 0


def test_rebuild_after_python_and_rust_changes(tmp_path):
    root = sources(
        tmp_path,
        {
            "main.py": "from helpers import value\nprint(value())\n",
            "helpers.py": "from native import number\ndef value() -> int:\n    return number()\n",
            "native.rs": "pub fn number() -> i64 { 3 }\n",
        },
    )
    output = tmp_path / "rust"
    assert run_project(root, output).stdout == "3\n"
    before = {
        p: p.stat().st_mtime_ns
        for p in [
            output / "src/main.rs",
            output / "src/native/native.rs",
            output / "Cargo.toml",
        ]
    }
    create_project(root, output)
    assert all(p.stat().st_mtime_ns == stamp for p, stamp in before.items())
    (root / "native.rs").write_text("pub fn number() -> i64 { 7 }\n")
    assert run_project(root, output).stdout == "7\n"
    (root / "helpers.py").write_text("def value() -> int:\n    return 9\n")
    (root / "native.rs").unlink()
    assert run_project(root, output).stdout == "9\n"
    assert not (output / "src/native/native.rs").exists()


@pytest.mark.parametrize(
    "files,message",
    [
        ({"main.py": "import missing\n"}, "cannot resolve"),
        (
            {
                "main.py": "from helper import absent\n",
                "helper.py": "def present() -> int:\n    return 1\n",
            },
            "no exported name",
        ),
        (
            {"main.py": "import helper\n", "helper.py": "print('side effect')\n"},
            "top-level statements",
        ),
        (
            {"main.py": "import helper\n", "helper.py": "import main\n"},
            "circular imports",
        ),
        ({"main.py": "from helper import *\n", "helper.py": ""}, "star imports"),
        (
            {"main.py": "import helper\n", "helper.py": "", "helper.rs": ""},
            "ambiguous module",
        ),
        (
            {"main.py": "from native import hidden\n", "native.rs": "fn hidden() {}"},
            "no exported name",
        ),
        (
            {"main.py": "import native\n", "native.rs": "pub async fn f() {}"},
            "synchronous",
        ),
        (
            {"main.py": "import native\n", "native.rs": "pub fn f<T>(x: T) -> T { x }"},
            "nongeneric",
        ),
        (
            {
                "main.py": "import native\n",
                "native.rs": "pub fn f() -> Option<i64> { None }",
            },
            "boundary type",
        ),
        (
            {"main.py": "import native\n", "native.rs": "pub fn f( {"},
            "invalid Rust syntax",
        ),
        ({"main.py": "from .. import bad\n"}, "escapes"),
    ],
)
def test_rejected_projects(tmp_path, files, message):
    root = sources(tmp_path, files)
    output = tmp_path / "rust"
    with pytest.raises((ProjectError, ServiceError), match=message):
        create_project(root, output)
    assert not output.exists()


@pytest.mark.parametrize(
    "helper",
    [
        "def broken() -> int:\n    value: int = 'wrong'\n    return value\n",
        "def broken() -> int:\n    return identity(value=1)\ndef identity(value: int) -> int:\n    return value\n",
    ],
)
def test_diagnostics_preserve_source_path_and_line(tmp_path, helper):
    root = sources(
        tmp_path,
        {
            "main.py": "from helper import broken\nprint(broken())\n",
            "helper.py": helper,
        },
    )
    with pytest.raises(ServiceError) as error:
        create_project(root, tmp_path / "rust")
    assert error.value.filename == str(root / "helper.py")
    assert error.value.lineno == 2


def test_output_preserves_local_changes_and_unmanaged_directories(tmp_path):
    root = sources(tmp_path, {"main.py": 'print("hi")\n'})
    output = tmp_path / "rust"
    output.mkdir()
    keep = output / "Cargo.toml"
    keep.write_text("user owned")
    with pytest.raises(ProjectError, match="not empty"):
        create_project(root, output)
    assert keep.read_text() == "user owned"
    keep.unlink()
    create_project(root, output)
    (output / "src/main.rs").write_text("hand edit")
    with pytest.raises(ProjectError, match="local edits"):
        create_project(root, output)
    assert (output / "src/main.rs").read_text() == "hand edit"
    with pytest.raises(ProjectError, match="source root"):
        create_project(root, root)


def test_generated_path_and_source_symlinks_cannot_escape(tmp_path):
    root = sources(tmp_path, {"main.py": 'print("hi")\n'})
    outside = tmp_path / "outside.rs"
    outside.write_text("do not replace")
    (root / "native.rs").symlink_to(outside)
    with pytest.raises(ProjectError, match="symlink escapes"):
        create_project(root, tmp_path / "rust")
    (root / "native.rs").unlink()
    output = tmp_path / "rust"
    create_project(root, output)
    generated = output / "src/main.rs"
    generated.unlink()
    generated.symlink_to(outside)
    with pytest.raises(ProjectError, match="escapes"):
        create_project(root, output)
    assert outside.read_text() == "do not replace"


def test_main_guards_in_dependencies_are_not_executed(tmp_path):
    root = sources(
        tmp_path,
        {
            "main.py": "from helper import value\nprint(value())\n",
            "helper.py": 'def value() -> int:\n    return 42\nif __name__ == "__main__":\n    assert False\n',
        },
    )
    result = run_project(root, tmp_path / "rust")
    assert result.returncode == 0, result.stderr
    assert result.stdout == "42\n"


def test_manifest_maps_symbols_to_python_and_rust_sources(tmp_path):
    root = sources(
        tmp_path,
        {
            "main.py": "from native import number\nprint(number())\n",
            "native.rs": "pub fn number() -> i64 { 4 }",
        },
    )
    output = tmp_path / "rust"
    create_project(root, output)
    metadata = json.loads((output / MARKER).read_text())
    assert any(item["file"] == "native.rs" and item["line"] == 1 for item in metadata["symbols"].values())
    assert "src/native/native.rs" in metadata["files"]


def test_importing_project_does_not_execute_it(tmp_path):
    root = sources(tmp_path, {"main.py": 'print("runtime only")\n'})
    code = Project(root).compile()
    assert "runtime only" in code
    assert not (root / ".py2rust").exists()


def test_exception_binding_shadows_import(tmp_path):
    root = sources(
        tmp_path,
        {
            "main.py": """from helper import failure
def main() -> None:
    try:
        assert False, "caught"
    except Exception as failure:
        assert str(failure) == "caught"
        print(str(failure))
    return
if __name__ == "__main__":
    main()
""",
            "helper.py": 'def failure() -> str:\n    return "imported"\n',
        },
    )
    result = run_project(root, tmp_path / "rust")
    assert result.returncode == 0, result.stderr
    assert result.stdout == "caught\n"


def test_unique_binary_names_reuse_shared_build_cache(tmp_path):
    commands = []
    for name, message in [("project_a", "first"), ("project_b", "second")]:
        root = sources(tmp_path / name, {"main.py": f'print("{message}")\n'})
        output = tmp_path / name / "rust"
        create_project(root, output, binary_name=name)
        assert json.loads((output / MARKER).read_text())["binary_name"] == name
        commands.append((output, name, message))
    # Rebuilding A after B must still select A, including Cargo's fresh-cache path.
    for output, name, expected in [*commands, commands[0]]:
        result = subprocess.run(
            ["cargo", "build", "--locked", "--offline", "--manifest-path", str(output / "Cargo.toml"), "--bin", name],
            env=dict(os.environ, CARGO_TARGET_DIR=str(TARGET), CARGO_PROFILE_DEV_DEBUG="0", CARGO_INCREMENTAL="0"),
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        result = subprocess.run([str(TARGET / "debug" / name)], capture_output=True, text=True, check=True)
        assert result.stdout == expected + "\n"


@pytest.mark.parametrize("name", ["../escape", "", "1starts-with-number", 'bad"name', "name/other"])
def test_invalid_binary_name_is_rejected_before_writing(tmp_path, name):
    root = sources(tmp_path, {"main.py": 'print("hello")\n'})
    output = tmp_path / "rust"
    with pytest.raises(ProjectError, match="binary name"):
        create_project(root, output, binary_name=name)
    assert not output.exists()
