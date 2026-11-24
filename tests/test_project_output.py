"""Packaging emitted Rust must not import the compiler or its frontends."""

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
