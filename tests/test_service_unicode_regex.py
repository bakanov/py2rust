"""Unicode regex matching with the profile's ASCII shorthand-class semantics."""

import re
from pathlib import Path

from .test_services import parity


def test_unicode_regex_against_python_ascii_classes(tmp_path: Path) -> None:
    patterns = [
        r"\w+",
        r"\W+",
        r"\d+",
        r"\D+",
        r"\s+",
        r"\S+",
        r"[\w-]+",
        r"[\W_]+",
        r"[^\W]+",
        r"\bword\b",
        r"[\b]",
        r"\\w",
        ".",
        "世界+",
        "[éя😀]+",
        r"[^\x00-\x1f\x7f]+",
    ]
    texts = ["", "word", "éwordя", "é_я", "世界😀", "éя😀", "١2３", "\t \u00a0\u2003", "ab-Я", "\x08", r"\w"]
    checks = []
    for pattern in patterns:
        compiled = re.compile(pattern, re.ASCII)
        for text in texts:
            checks.append(f"    assert regex_search({pattern!r}, {text!r}) == {compiled.search(text) is not None!r}")
            checks.append(
                f"    assert regex_fullmatch({pattern!r}, {text!r}) == {compiled.fullmatch(text) is not None!r}"
            )
    source = """from py2rust.stdlib import regex_search, regex_fullmatch, regex_findall, regex_replace
def run() -> None:
"""
    source += "\n".join(checks)
    source += """
    assert regex_findall(".", "éя😀") == ["é", "я", "😀"]
    assert regex_replace("[éя]", "$1", "éя😀") == "$1$1😀"
    assert not regex_search("[\\x00-\\x1f\\x7f]", "Заметка 世界😀")
    print("unicode regex passed")
    return
if __name__ == "__main__":
    run()
"""
    assert parity(tmp_path, source) == "unicode regex passed\n"


def test_membership_conversions_are_emitted(tmp_path: Path) -> None:
    source = """from py2rust.stdlib import Json, json_array
def run() -> None:
    numbers: list[float] = [1.0, 2.5]
    assert 1 in numbers
    assert 2 not in numbers
    words: Json = ["rust", "世界", 4]
    assert "世界" in json_array(words)
    assert "missing" not in json_array(words)
    assert 4 in json_array(words)
    print("membership passed")
    return
if __name__ == "__main__":
    run()
"""
    assert parity(tmp_path, source) == "membership passed\n"
