"""Unsupported frontend installations must fail before visitor hook imports."""

import json
import subprocess
import sys
from importlib.machinery import EXTENSION_SUFFIXES
from importlib.resources import files
from types import SimpleNamespace

import pytest

from py2rust.compiler.frontend import FrontendError, compatibility


def modules() -> dict:
    contract = json.loads(files("py2rust.compiler.frontend").joinpath("mypy-source.json").read_text())
    return {
        "mypy.version": SimpleNamespace(__version__=contract["wheel_version"]),
        "mypy.nodes": SimpleNamespace(__file__="nodes.py"),
        "mypy.traverser": SimpleNamespace(__file__="traverser.py", TraverserVisitor=object),
    }


def test_pinned_python_frontend_is_accepted(monkeypatch) -> None:
    available = modules()
    monkeypatch.setattr(compatibility, "import_module", available.__getitem__)
    compatibility.ensure_frontend()


def test_wrong_frontend_version_is_actionable(monkeypatch) -> None:
    available = modules()
    available["mypy.version"].__version__ = "unreviewed"
    monkeypatch.setattr(compatibility, "import_module", available.__getitem__)
    with pytest.raises(FrontendError, match="found unreviewed") as failure:
        compatibility.ensure_frontend()
    assert "--find-links" in str(failure.value)


@pytest.mark.parametrize("name", ["mypy.nodes", "mypy.traverser"])
def test_compiled_frontend_is_rejected(name: str, monkeypatch) -> None:
    available = modules()
    available[name].__file__ = name + EXTENSION_SUFFIXES[0]
    monkeypatch.setattr(compatibility, "import_module", available.__getitem__)
    with pytest.raises(FrontendError, match="compiled mypy modules are unsupported"):
        compatibility.ensure_frontend()


def test_missing_frontend_does_not_break_pipeline_import() -> None:
    script = """import importlib.abc
import sys
from pathlib import Path
class MissingMypy(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "mypy" or fullname.startswith("mypy."):
            raise ModuleNotFoundError("mypy is intentionally absent", name=fullname)
sys.meta_path.insert(0, MissingMypy())
from py2rust.compiler.pipeline import compile_typed
from py2rust.compiler.frontend import FrontendError
try:
    compile_typed({"main": (Path("main.py"), 'if __name__ == "__main__":\\n    print(1)\\n')})
except FrontendError as error:
    assert "mypy could not be loaded" in str(error)
    print(error)
else:
    raise AssertionError("missing frontend accepted")
"""
    result = subprocess.run([sys.executable, "-I", "-c", script], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert "typed-frontend extra" in result.stdout
