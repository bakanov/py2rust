"""Readable shared references preserve temporaries and expression evaluation."""

from pathlib import Path

import pytest

from py2rust.compiler import parameter_policy, pipeline, service

from .test_services import parity

SOURCE = """def trim(text: str) -> str:
    return text.strip()

def parts(text: str) -> list[str]:
    return text.split(",")

def folded(text: str) -> str:
    return text.casefold()

def changed(text: str) -> str:
    text = text + "!"
    return text.strip()

def receiver() -> str:
    print("receiver")
    return "a,b"

def pattern() -> str:
    print("pattern")
    return "a"

def failed() -> str:
    print("failure")
    assert False
    return "unused"

def check() -> None:
    assert trim(" hello ") == "hello"
    assert parts("a,b") == ["a", "b"]
    original: str = "Straße"
    assert folded(original) == "strasse"
    assert original == "Straße"
    assert changed(" x ") == "x !"
    assert receiver().replace(pattern(), "x") == "x,b"
    assert "-".join(parts("a,b")) == "a-b"
    try:
        receiver().find(failed())
    except Exception:
        print("caught")
    print("references passed")

if __name__ == "__main__":
    check()
"""


def test_borrowed_receiver_rendering(tmp_path: Path) -> None:
    code = pipeline.compile_typed({"main": (tmp_path / "main.py", SOURCE)})
    assert "rt::str_strip(text)" in code
    assert "rt::casefold(text)" in code
    assert "rt::str_split(text," in code
    assert "rt::str_strip(&text)" in code
    assert "rt::str_strip(&(text))" not in code
    assert "rt::str_strip(&(&text))" not in code
    return  # noqa: PLR1711


@pytest.mark.parametrize("optimize", [False, True])
def test_native_reference_lifetimes_and_order(tmp_path: Path, monkeypatch, optimize: bool) -> None:
    original = service.ServiceCompiler.__init__

    def initialize(self, *args, **kwargs) -> None:
        kwargs["optimize"] = optimize
        original(self, *args, **kwargs)
        return  # noqa: PLR1711

    monkeypatch.setattr(service.ServiceCompiler, "__init__", initialize)
    monkeypatch.setattr(
        service.ServiceCompiler,
        "compile",
        lambda self, source: pipeline.compile_typed({"main": (tmp_path / "main.py", source)}),
    )
    assert parity(tmp_path, SOURCE) == "receiver\npattern\nreceiver\nfailure\ncaught\nreferences passed\n"
    return  # noqa: PLR1711


def test_casefold_borrows_retained_input(tmp_path: Path, monkeypatch) -> None:
    source = {"main": (tmp_path / "main.py", SOURCE)}
    with monkeypatch.context() as patch:
        patch.setattr(parameter_policy, "stable_string_method", lambda expression: False)
        before = pipeline.compile_typed(source)
    prepared = pipeline.prepare_typed(source)
    after = pipeline.emit_rust(prepared)
    plans = {plan.function: plan for plan in prepared.memory.parameters}
    assert plans["main.folded"].parameters[0].mode == "borrow"
    assert plans["main.changed"].parameters[0].mode == "owned"
    assert "fn py__main__folded(mut text: String)" in before
    assert "fn py__main__folded(text: &str)" in after
    assert "py__main__folded(original.clone())" in before
    assert "py__main__folded(&original)" in after
    return  # noqa: PLR1711
