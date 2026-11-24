"""Real applications must retain the selected performance lowerings."""

# ruff: noqa: EXE002, PLR1711 - exFAT modes and explicit returns
import pytest

from py2rust.compiler.service import ServiceCompiler
from tools.check_optimization_gates import check_gates


def test_application_optimization_gates() -> None:
    assert len(check_gates()) == 6
    return


def test_gates_detect_disabled_optimization(monkeypatch) -> None:
    original = ServiceCompiler.__init__

    def initialize(self, *args, **kwargs):
        kwargs["optimize"] = False
        original(self, *args, **kwargs)
        return

    monkeypatch.setattr(ServiceCompiler, "__init__", initialize)
    with pytest.raises(ValueError, match="expected data to borrow"):
        check_gates()
    return
