"""Membership rules retain source evaluation order and recoverable byte errors."""

from pathlib import Path

import pytest

from py2rust.compiler import pipeline, service

from .test_services import run


@pytest.mark.parametrize("optimize", [False, True])
def test_typed_membership_evaluates_operands_once(tmp_path: Path, monkeypatch, optimize: bool) -> None:
    source = """from py2rust.stdlib import Json, json_loads

def needle() -> int:
    print("needle")
    return 97

def invalid() -> int:
    print("invalid")
    return 256

def buffer() -> bytes:
    print("buffer")
    return b"abc"

def text() -> str:
    print("text")
    return "a"

def mapping() -> dict[str, int]:
    print("mapping")
    return {"a": 1}

def document() -> Json:
    print("document")
    return json_loads('{"a": 1}')

def fail() -> bytes:
    print("fail")
    assert False, "container failed"
    return b""

def run_checks() -> None:
    assert needle() in buffer()
    assert not (needle() not in buffer())
    assert b"bc" in buffer()
    assert b"" in buffer()
    assert text() in mapping()
    assert text() in document()
    try:
        print(invalid() in buffer())
    except Exception:
        print("range error")
    try:
        print(invalid() in fail())
    except Exception:
        print("container error")
    return

if __name__ == "__main__":
    run_checks()
"""
    reference = run(tmp_path, source, "python")
    monkeypatch.setattr(
        service.ServiceCompiler,
        "compile",
        lambda self, text: pipeline.compile_typed({"main": (tmp_path / "main.py", text)}),
    )
    original = service.ServiceCompiler.__init__

    def initialize(self, *args, **kwargs) -> None:
        kwargs["optimize"] = optimize
        original(self, *args, **kwargs)
        return

    monkeypatch.setattr(service.ServiceCompiler, "__init__", initialize)
    native = run(tmp_path, source, "rust")
    expected = [
        "needle",
        "buffer",
        "needle",
        "buffer",
        "buffer",
        "buffer",
        "text",
        "mapping",
        "text",
        "document",
        "invalid",
        "buffer",
        "range error",
        "invalid",
        "fail",
        "container error",
    ]
    assert reference.returncode == native.returncode == 0
    assert reference.stderr == native.stderr == ""
    assert reference.stdout.splitlines() == native.stdout.splitlines() == expected
    return


@pytest.mark.parametrize("optimize", [False, True])
@pytest.mark.parametrize("case", ["chain", "sets", "nested_sets"])
def test_typed_comparison_control_flow(tmp_path: Path, monkeypatch, optimize: bool, case: str) -> None:
    from . import test_service_comparisons as scenarios

    original = service.ServiceCompiler.__init__

    def initialize(self, *args, **kwargs) -> None:
        kwargs["optimize"] = optimize
        original(self, *args, **kwargs)
        return

    monkeypatch.setattr(service.ServiceCompiler, "__init__", initialize)
    monkeypatch.setattr(
        service.ServiceCompiler,
        "compile",
        lambda self, text: pipeline.compile_typed({"main": (tmp_path / "main.py", text)}),
    )
    if case == "chain":
        scenarios.test_chained_comparisons_evaluate_in_order_once(tmp_path, "rust")
    elif case == "sets":
        scenarios.test_set_comparisons_use_inclusion_not_lexicographic_order(tmp_path, "rust")
    else:
        scenarios.test_nested_sequences_keep_set_partial_order(tmp_path, "rust")
    return
