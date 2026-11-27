"""Excluded Python semantics must fail explicitly rather than silently drift."""

from pathlib import Path

import pytest

from py2rust.compiler.frontend import FrontendError
from py2rust.compiler.pipeline import compile_typed, prepare_typed
from py2rust.compiler.service import ServiceError


@pytest.mark.parametrize("default", ["[]", "[1]"])
def test_nonliteral_function_defaults_rejected_at_source(tmp_path: Path, default: str) -> None:
    source = f"def value(items: list[int] = {default}) -> int:\n    return 1\n"
    path = tmp_path / "defaults.py"
    with pytest.raises(FrontendError, match="literal values") as error:
        prepare_typed({"main": (path, source)})
    assert str(path) + ":1:" in str(error.value)
    return


def test_general_type_variables_not_silently_erased(tmp_path: Path) -> None:
    source = """from typing import TypeVar
T = TypeVar("T")
def identity(value: T) -> T:
    return value
"""
    path = tmp_path / "generic.py"
    with pytest.raises(FrontendError) as error:
        prepare_typed({"main": (path, source)})
    assert str(path) + ":2:" in str(error.value)
    return


@pytest.mark.parametrize("annotation", ["list[int]", "dict[str, int]", "list[int] | None"])
def test_collection_and_optional_truthiness_rejected(tmp_path: Path, annotation: str) -> None:
    source = f"def check(value: {annotation}) -> bool:\n    if value:\n        return True\n    return False\n"
    path = tmp_path / "condition.py"
    with pytest.raises(FrontendError, match="condition.bool") as error:
        prepare_typed({"main": (path, source)})
    assert str(path) + ":2:" in str(error.value)
    return


def test_round_does_not_fall_back_to_rust_rounding(tmp_path: Path) -> None:
    path = tmp_path / "rounding.py"
    source = "def rounded(value: float) -> int:\n    return round(value)\n"
    with pytest.raises(ServiceError, match="unsupported or unimported call: round") as error:
        compile_typed({"main": (path, source)})
    assert error.value.lineno == 2
    assert error.value.filename == str(path)
    return
