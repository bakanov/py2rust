"""Packaging emitted Rust must not import the compiler or its frontends."""

import json
import subprocess
import sys
from pathlib import Path


def test_packaging_has_no_frontend_dependency(tmp_path: Path) -> None:
    source = """import importlib.abc
import sys
from pathlib import Path

class NoCompiler(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in {"py2rust.compiler.service", "py2rust.compiler.pipeline"} or fullname.startswith(("mypy", "py2rust.compiler.frontend")):
            raise AssertionError("packaging imported compiler dependency: " + fullname)
        return None

sys.meta_path.insert(0, NoCompiler())
from py2rust.compiler.project_output import write_service_project
write_service_project('fn main() { println!("世界"); }\\n', Path(sys.argv[1]))
"""
    result = subprocess.run([sys.executable, "-c", source, str(tmp_path)], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "src/main.rs").read_text() == 'fn main() { println!("世界"); }\n'
    assert (tmp_path / "Cargo.lock").is_file()
    assert (tmp_path / "src/lib.rs").is_file()
    assert 'name = "py2rust-service"' in (tmp_path / "Cargo.toml").read_text()
    return


def test_application_source_utilities_exclude_native_rust(tmp_path: Path) -> None:
    from py2rust.compiler.project_output import (
        application_source_digest,
        application_source_files,
        application_source_text,
    )

    (tmp_path / "src/native").mkdir(parents=True)
    (tmp_path / "src/main.rs").write_text("fn main() {}\n")
    (tmp_path / "src/entry.rs").write_text("pub(crate) fn run() {}\n")
    (tmp_path / "src/native/input.rs").write_text("pub fn native() {}\n")
    assert [path.name for path in application_source_files(tmp_path)] == ["entry.rs", "main.rs"]
    assert "pub(crate) fn run" in application_source_text(tmp_path)
    assert "native" not in application_source_text(tmp_path)
    assert application_source_digest(tmp_path) == application_source_digest(tmp_path)

    (tmp_path / "src/native/mod.rs").write_text("pub(crate) mod helper;\n")
    (tmp_path / ".py2rust-project.json").write_text(
        json.dumps({"modules": {"main": "src/entry.rs", "native": "src/native/mod.rs"}})
    )
    files = application_source_files(tmp_path)
    assert [path.relative_to(tmp_path).as_posix() for path in files] == [
        "src/entry.rs",
        "src/main.rs",
        "src/native/mod.rs",
    ]
    assert "pub fn native" not in application_source_text(tmp_path)
