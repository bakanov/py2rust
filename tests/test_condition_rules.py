"""Truthiness is rejected before emission; boolean operations remain lazy."""

from pathlib import Path

import pytest

from py2rust.compiler.frontend import FrontendError
from py2rust.compiler.pipeline import compile_typed, prepare_typed
from py2rust.compiler.service import ServiceCompiler

from .test_services import parity


@pytest.mark.parametrize(
    "body",
    [
        "if text:\n        return True\n    return False",
        "while text:\n        return True\n    return False",
        "assert text\n    return True",
        "return True if text else False",
        "return not text",
        'result = text or "default"\n    return result == "default"',
        'result = text and "default"\n    return result == "default"',
    ],
)
def test_truthiness_rejected_at_source_boundary(tmp_path: Path, body: str) -> None:
    source = "def check(text: str) -> bool:\n    " + body + "\n"
    path = tmp_path / "truthiness.py"
    with pytest.raises(FrontendError, match="condition.bool: expected bool") as error:
        prepare_typed({"main": (path, source)})
    assert str(path) + ":2:" in str(error.value)


def test_boolean_short_circuit_executes_once(tmp_path: Path, monkeypatch) -> None:
    source = """def event(value: bool) -> bool:
    print(value)
    return value

def fail() -> bool:
    assert False, "must remain unevaluated"
    return False

def check() -> None:
    enabled: bool = True
    disabled: bool = False
    assert enabled or fail()
    assert not (disabled and fail())
    assert event(True) and event(True)
    assert event(False) or event(True)
    assert (1 if enabled else 0) == 1

if __name__ == "__main__":
    check()
"""
    monkeypatch.setattr(
        ServiceCompiler,
        "compile",
        lambda self, text: compile_typed({"main": (tmp_path / "main.py", text)}),
    )
    assert parity(tmp_path, source) == "True\nTrue\nFalse\nTrue\n"
