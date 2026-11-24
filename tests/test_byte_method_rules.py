"""Bytes join must evaluate its separator before its iterable, including failures."""

from pathlib import Path

import pytest

from py2rust.compiler import pipeline, service

from .test_services import run

SOURCE = """def separator(fail: bool) -> bytes:
    print("separator")
    assert not fail, "separator failed"
    return b"|"

def parts(fail: bool) -> list[bytes]:
    print("parts")
    assert not fail, "parts failed"
    return [b"a", b"b"]

def check() -> None:
    assert separator(False).join(parts(False)) == b"a|b"
    assert separator(False).join([]) == b""
    try:
        print(separator(True).join(parts(False)).hex())
    except Exception:
        print("caught separator")
    try:
        print(separator(False).join(parts(True)).hex())
    except Exception:
        print("caught parts")
    return

if __name__ == "__main__":
    check()
"""


@pytest.mark.parametrize("frontend", ["legacy", "typed"])
@pytest.mark.parametrize("optimize", [False, True])
def test_join_receiver_and_argument_order(tmp_path: Path, monkeypatch, frontend: str, optimize: bool) -> None:
    reference = run(tmp_path, SOURCE, "python")
    original = service.ServiceCompiler.__init__

    def initialize(self, *args, **kwargs) -> None:
        kwargs["optimize"] = optimize
        original(self, *args, **kwargs)
        return

    monkeypatch.setattr(service.ServiceCompiler, "__init__", initialize)
    if frontend == "typed":
        monkeypatch.setattr(
            service.ServiceCompiler,
            "compile",
            lambda self, text: pipeline.compile_typed({"main": (tmp_path / "main.py", text)}),
        )
    native = run(tmp_path, SOURCE, "rust")
    assert reference.returncode == native.returncode == 0, native.stderr
    assert reference.stderr == native.stderr == ""
    assert (
        reference.stdout.splitlines()
        == native.stdout.splitlines()
        == [
            "separator",
            "parts",
            "separator",
            "separator",
            "caught separator",
            "separator",
            "parts",
            "caught parts",
        ]
    )
    return
