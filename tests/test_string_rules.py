"""Rule-driven strings preserve Python behavior and compile their own rule module."""

from pathlib import Path

import pytest

from py2rust.compiler import pipeline, service

from .test_services import parity

SOURCE = """def separator() -> str:
    print("separator first")
    return "|"

def words() -> list[str]:
    print("words second")
    return ["é", "世界"]

def failing_words() -> list[str]:
    print("words fail")
    assert False, "expected failure"
    return []

def split(text: str) -> list[str]:
    return text.split(",")

def check() -> None:
    assert split("a,,b,") == ["a", "", "b", ""]
    assert separator().join(words()) == "é|世界"
    try:
        separator().join(failing_words())
    except Exception:
        print("caught words")
    try:
        "abc".split("")
    except Exception:
        print("caught separator")
    assert "xabcxx".strip("x") == "abc"
    assert "\\x1c a\\x1f".strip() == "a"
    assert "xabcx".lstrip("x") == "abcx"
    assert "xabcx".rstrip("x") == "xabc"
    assert "é世界".find("世") == 1
    assert "é世界é".rfind("é") == 3
    assert "Straße".casefold() == "strasse"
    assert "Straße".upper() == "STRASSE"
    assert "ABC".lower() == "abc"
    assert "é世界".startswith("é")
    assert "é世界".endswith("界")
    assert "a,b".replace(",", "|") == "a|b"
    assert "é".encode().decode() == "é"
    print("string rules passed")

if __name__ == "__main__":
    check()
"""


@pytest.mark.parametrize("optimize", [False, True])
def test_string_rule_semantics(tmp_path: Path, monkeypatch, optimize: bool) -> None:
    original = service.ServiceCompiler.__init__

    def initialize(self, *args, **kwargs) -> None:
        kwargs["optimize"] = optimize
        original(self, *args, **kwargs)

    monkeypatch.setattr(service.ServiceCompiler, "__init__", initialize)
    monkeypatch.setattr(
        service.ServiceCompiler,
        "compile",
        lambda self, source: pipeline.compile_typed({"main": (tmp_path / "main.py", source)}),
    )
    assert parity(tmp_path, SOURCE) == (
        "separator first\nwords second\nseparator first\nwords fail\n"
        "caught words\ncaught separator\nstring rules passed\n"
    )


def test_split_returns_result_without_literal_allocation(tmp_path: Path) -> None:
    code = pipeline.compile_typed({"main": (tmp_path / "main.py", SOURCE)})
    body = code.split("fn py__main__split(", 1)[1].split("\nfn ", 1)[0]
    assert 'rt::str_split(text, ",")' in body
    assert "to_string" not in body and "Ok(" not in body
