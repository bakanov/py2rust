"""Replacement contracts must drive both frontend typing and executable Rust."""

from pathlib import Path

import pytest

from py2rust.compiler.frontend import FrontendError
from py2rust.compiler.libraries import Replacement
from py2rust.compiler.libraries.third_party import REPLACEMENTS
from py2rust.compiler.pipeline import compile_typed
from py2rust.compiler.service import ServiceCompiler

from .test_services import run

SOURCE = """from fixture_vendor import decode as parse
import fixture_vendor.codec
from py2rust.stdlib import json_get, json_int

def check() -> None:
    first = parse('{"count": 41}')
    second = fixture_vendor.codec.decode('{"count": 42}')
    print(json_int(json_get(first, "count", None)))
    print(json_int(json_get(second, "count", None)))

if __name__ == "__main__":
    check()
"""


def test_third_party_contract_types_and_executes(tmp_path: Path, monkeypatch) -> None:
    for name in ("fixture_vendor.decode", "fixture_vendor.codec.decode"):
        monkeypatch.setitem(REPLACEMENTS, name, Replacement(name, "json_loads", "Json", ("str",), True, "third-party"))
    monkeypatch.setattr(
        ServiceCompiler, "compile", lambda self, source: compile_typed({"main": (tmp_path / "main.py", source)})
    )
    result = run(tmp_path, SOURCE, "rust")
    assert result.returncode == 0, result.stderr
    assert result.stdout == "41\n42\n"
    invalid = SOURCE.replace("parse('{\"count\": 41}')", "parse(41)")
    with pytest.raises(FrontendError, match="incompatible type"):
        compile_typed({"main": (tmp_path / "main.py", invalid)})
    with pytest.raises(FrontendError, match="shadow reserved runtime contracts"):
        compile_typed(
            {
                "main": (tmp_path / "main.py", SOURCE),
                "fixture_vendor": (tmp_path / "fixture_vendor.py", ""),
            }
        )


def test_missing_replacement_does_not_gain_an_implementation(tmp_path: Path) -> None:
    with pytest.raises(FrontendError, match="fixture_vendor"):
        compile_typed({"main": (tmp_path / "main.py", SOURCE)})
