"""Immutable string operations do not require snapshots of earlier JSON arguments."""

from pathlib import Path

import pytest

from py2rust.compiler import memory_oracle, pipeline, service

from .test_services import parity

SOURCE = """from py2rust.stdlib import Json, json_get, json_int, json_string

def clean(text: str) -> str:
    return text.strip().lower()

def direct(document: Json, text: str) -> Json:
    return json_get(document, "selected", text.strip())

def wrapped(document: Json, text: str) -> Json:
    return json_get(document, "selected", clean(text))

def split_checked(document: Json, text: str, separator: str) -> Json:
    return json_get(document, "selected", text.split(separator))

def uncertain(document: Json, parts: list[str]) -> Json:
    return json_get(document, "selected", parts.pop().strip())

def noisy() -> str:
    print("fallback evaluated")
    return " X "

def effectful(document: Json) -> Json:
    return json_get(document, "selected", noisy().strip())

def check() -> None:
    present: Json = {"selected": 7, "payload": [1, 2, 3]}
    missing: Json = {}
    assert json_int(direct(present, " ignored ")) == 7
    assert json_string(direct(missing, " Héllo ")) == "Héllo"
    assert json_string(wrapped(missing, " WORLD ")) == "world"
    try:
        split_checked(present, "abc", "")
        assert False
    except Exception:
        print("split failed")
    assert json_int(present["selected"]) == 7
    assert json_string(uncertain(missing, [" last "])) == "last"
    assert json_int(effectful(present)) == 7
    print("strings passed")

if __name__ == "__main__":
    check()
"""


def test_document_copies_removed_only_with_proven_operands(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "main.py"
    with monkeypatch.context() as patch:
        patch.setattr(memory_oracle, "stable_string_method", lambda expression: False)
        before = pipeline.compile_typed({"main": (path, SOURCE)})
    prepared = pipeline.prepare_typed({"main": (path, SOURCE)})
    after = pipeline.emit_rust(prepared)
    assert "main.clean" in prepared.memory.nonmutating_functions
    for name in ("direct", "wrapped", "split_checked"):
        old = before.split(f"fn py__main__{name}(")[1].split("\nfn ")[0]
        new = after.split(f"fn py__main__{name}(")[1].split("\nfn ")[0]
        assert 'rt::json_get(&((*document).clone()), "selected",' in old
        assert 'rt::json_get(document, "selected",' in new
    for name in ("uncertain", "effectful"):
        body = after.split(f"fn py__main__{name}(")[1].split("\nfn ")[0]
        assert 'rt::json_get(&((*document).clone()), "selected",' in body
    blocked = [
        proof
        for expr, proof in prepared.memory.evaluations
        if expr.operation == "method_call" and expr.value == "strip" and not proof.stable
    ]
    assert {proof.blocker.detail for proof in blocked} == {"pop", "main.noisy"}
    return  # noqa: PLR1711


@pytest.mark.parametrize("optimize", [False, True])
def test_eager_failures_and_values(tmp_path: Path, monkeypatch, optimize: bool) -> None:
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
    assert parity(tmp_path, SOURCE) == "split failed\nfallback evaluated\nstrings passed\n"
    return  # noqa: PLR1711
