"""Execute the portable declaration pass as Rust on actual Python source files."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from py2rust.compiler.native.declarations import declarations
from py2rust.compiler.project import create_project
from py2rust.stdlib import python_syntax_tree

from .test_native_emitter import build_project

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def declaration_binary(tmp_path_factory) -> Path:
    base = tmp_path_factory.mktemp("native-declarations")
    source = base / "source"
    source.mkdir()
    shutil.copy2(ROOT / "py2rust/compiler/native/declarations.py", source / "declarations.py")
    (source / "main.py").write_text(
        """from py2rust.stdlib import Json, env_get, read_text, write_text, json_loads, json_array, json_string, json_dumps, python_syntax_tree
from declarations import declarations

def main() -> None:
    modules: list[Json] = []
    for source in json_array(json_loads(read_text(env_get("INPUT", "")))):
        modules.append({"name": source["name"], "package": source["package"], "path": source["path"], "tree": python_syntax_tree(json_string(source["source"]))})
    write_text(env_get("OUTPUT", ""), json_dumps(declarations(modules)))
    return

if __name__ == "__main__":
    main()
"""
    )
    create_project(source, base / "rust", binary_name="declaration-reader")
    return build_project(base / "rust", "declaration-reader", base / "reader")


def run_reader(binary: Path, sources: list[dict], tmp_path: Path) -> subprocess.CompletedProcess:
    path = tmp_path / "sources.json"
    path.write_text(json.dumps(sources))
    return subprocess.run(
        [str(binary)],
        env=dict(
            os.environ,
            PATH="/nonexistent",
            PYTHONHOME="/nonexistent",
            PYTHONPATH="/nonexistent",
            INPUT=str(path),
            OUTPUT=str(tmp_path / "declarations.json"),
        ),
        capture_output=True,
        text=True,
        check=False,
    )


def test_native_declarations_resolve_project(declaration_binary: Path, tmp_path: Path) -> None:
    sources = [
        {
            "name": "app.main",
            "package": "app",
            "path": "main.py",
            "source": "from .models import Message as Note\nfrom py2rust.stdlib import Json\ndef send(note: Note, metadata: Json) -> list[Note]:\n    return [note]\n",
        },
        {
            "name": "app.models",
            "package": "app",
            "path": "models.py",
            "source": "from dataclasses import dataclass\n@dataclass\nclass Message:\n    text: str\n    tags: list[str]\n",
        },
    ]
    result = run_reader(declaration_binary, sources, tmp_path)
    assert result.returncode == 0, result.stderr
    actual = json.loads((tmp_path / "declarations.json").read_text())
    reference = declarations([{**item, "tree": python_syntax_tree(item["source"])} for item in sources])
    assert actual == reference
    function = actual["modules"][0]["functions"][0]
    assert function["parameters"][0]["type"]["name"] == "app.models.Message"
    assert function["result"]["arguments"][0]["name"] == "app.models.Message"
    return


def test_native_declarations_read_compiler(declaration_binary: Path, tmp_path: Path) -> None:
    files = ["native/declarations.py", "native/ir_schema.py", "rules/numeric.py"]
    sources = [
        {
            "name": "compiler." + name[:-3].replace("/", "."),
            "package": "compiler." + name.split("/")[0],
            "path": name,
            "source": (ROOT / "py2rust/compiler" / name).read_text(),
        }
        for name in files
    ]
    result = run_reader(declaration_binary, sources, tmp_path)
    assert result.returncode == 0, result.stderr
    actual = json.loads((tmp_path / "declarations.json").read_text())
    assert actual == declarations([{**item, "tree": python_syntax_tree(item["source"])} for item in sources])
    return


@pytest.mark.parametrize(
    "source,message",
    [
        ("def f(x: Missing) -> int:\n    return 1\n", "unknown or unsupported type: Missing"),
        ("def f(x: dict[str]) -> int:\n    return 1\n", "invalid generic arity"),
        ("from . import value\n", "invalid relative import"),
        ("def f(x: int) -> int:\n    return x\ndef f(x: int) -> int:\n    return x\n", "duplicate binding: f"),
    ],
)
def test_native_declarations_reject_invalid(
    declaration_binary: Path, tmp_path: Path, source: str, message: str
) -> None:
    sources = [{"name": "main", "package": "", "path": "invalid.py", "source": source}]
    result = run_reader(declaration_binary, sources, tmp_path)
    assert result.returncode != 0
    assert "invalid.py:" in result.stderr and message in result.stderr
    assert not (tmp_path / "declarations.json").exists()
    return
