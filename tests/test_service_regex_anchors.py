"""Independent CPython checks for final-LF anchors, ASCII boundaries and empty matches."""

import json
import random
import re
import subprocess
from pathlib import Path

import pytest

from .test_services import program, run


def oracle(pattern: str, text: str, operation: str, full: bool) -> dict:
    compiled = re.compile(pattern, re.ASCII)
    if operation in ["search", "fullmatch"]:
        value = compiled.search(text) if operation == "search" else compiled.fullmatch(text)
        return {"value": value is not None}
    if operation == "capture":
        match = compiled.fullmatch(text) if full else compiled.search(text)
        if match is None:
            return {"value": None}
        groups = [match.group(index) for index in range(compiled.groups + 1)]
        return {
            "value": {
                "groups": groups,
                "spans": [list(match.span(index)) if value is not None else None for index, value in enumerate(groups)],
            }
        }
    matches = list(compiled.finditer(text))
    if any(match.start() == match.end() for match in matches):
        return {"error": True}
    if operation == "findall":
        return {"value": [match.group(0) for match in matches]}
    return {"value": compiled.sub(lambda _match: r"$1\1\g<name>世界", text)}


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_all_operations_against_cpython(tmp_path: Path, engine: str) -> None:
    patterns = [
        r"a$",
        r"(a$)|a[^\n]*$",
        r"a$\n",
        r"a($)\n",
        r"($)\n",
        r"$",
        r"\$$",
        r"[$]$",
        r"((a+)$)",
        r"(a|b)$",
        r".+$",
        r"[a\n]+$",
        r"\A.+$",
        r"a\Z",
        r"\bword$",
        r"\bword\b$",
        r"word\B$",
        r"\Ba$",
        r"\B$",
        r"\b$",
        r"(\b|a)$",
        r"(\B|a)$",
        r"(\B|)$",
        r".*",
        r".*$",
        r"a|\b",
        r"\w+",
        r"\W+",
        r"[\d_]+",
        r"\d+",
        r"\s+",
        r"[^\w]+",
        r"(a(b)?)+",
        r"(a)?(b*)",
        r"[^^]$",
        r"[^$]+$",
        r"[]$]+$",
        r"[^]a]$",
        r"a\b",
        r"\Ba",
        r"\B",
        r"\b",
        r"[^a-z]$",
        r"\\$",
        r"\\\$",
        r"(a{1,3}?)(a*)$",
        r"[(]a[)]$",
        r"\t$",
        r"[\b]$",
        r"(a|ab)$",
    ]
    texts = [
        "",
        "word",
        "word\n",
        "éword\n",
        "wordé\n",
        "a",
        "a\n",
        "a\r\n",
        "a\nb\n",
        " a\n",
        "éa\n",
        "\n",
        " \n",
        "aa\n",
        "é",
        "😀\n",
        "word\n\n",
        "ab\n",
        "ba\n",
        "aé\n",
        "$\n",
        "]\n",
        "^\n",
        "\\\n",
        "\x08\n",
        "(a)\n",
        "aba",
        "abaa",
    ]
    rng = random.Random(781)
    texts += ["".join(rng.choice("aab$\n\ré界 \t") for _ in range(rng.randrange(40))) for _ in range(25)]
    cases = [
        {"pattern": pattern, "text": text, "operation": operation, "full": full}
        for pattern in patterns
        for operation, full in [
            ("search", False),
            ("fullmatch", False),
            ("capture", False),
            ("capture", True),
            ("findall", False),
            ("replace", False),
        ]
        for text in texts
    ]
    (tmp_path / "cases.json").write_text(json.dumps(cases))
    source = r"""from py2rust.stdlib import Json, json_array, json_bool, json_string, json_loads, json_dumps, read_text, regex_search, regex_fullmatch, regex_capture, regex_findall, regex_replace
def check() -> None:
    results: list[Json] = []
    for row in json_array(json_loads(read_text("cases.json"))):
        pattern: str = json_string(row["pattern"])
        text: str = json_string(row["text"])
        operation: str = json_string(row["operation"])
        value: Json = None
        try:
            if operation == "search":
                value = regex_search(pattern, text)
            elif operation == "fullmatch":
                value = regex_fullmatch(pattern, text)
            elif operation == "capture":
                value = regex_capture(pattern, text, json_bool(row["full"]))
            elif operation == "findall":
                value = regex_findall(pattern, text)
            else:
                value = regex_replace(pattern, "$1\\1\\g<name>世界", text)
            results.append({"value": value})
        except Exception:
            results.append({"error": True})
    print(json_dumps(results))
    return
if __name__ == "__main__":
    check()
"""
    result = subprocess.run(
        program(tmp_path, source, engine), cwd=tmp_path, capture_output=True, text=True, timeout=60, check=False
    )
    assert result.returncode == 0 and not result.stderr, result
    assert json.loads(result.stdout) == [oracle(**case) for case in cases]


def test_native_assertion_budget_and_recovery(tmp_path: Path) -> None:
    (tmp_path / "hard.txt").write_text("a" * 2000 + "!")
    result = run(
        tmp_path,
        r"""from py2rust.stdlib import Json, regex_search, regex_fullmatch, regex_capture, regex_findall, regex_replace, json_equal, read_text
def check() -> None:
    failures: int = 0
    for pattern in ["(a|aa)+$", "(a+)+$", "(a|a?)+$"]:
        for operation in ["search", "fullmatch", "capture", "findall", "replace"]:
            text: str = read_text("hard.txt")
            try:
                if operation == "search":
                    found: bool = regex_search(pattern, text)
                elif operation == "fullmatch":
                    complete: bool = regex_fullmatch(pattern, text)
                elif operation == "capture":
                    captured: Json = regex_capture(pattern, text, False)
                elif operation == "findall":
                    matches: list[str] = regex_findall(pattern, text)
                else:
                    replaced: str = regex_replace(pattern, "x", text)
            except Exception:
                failures = failures + 1
            assert json_equal(regex_capture("\\b(word)$", "é word\n", False), {"groups": ["word", "word"], "spans": [[2, 6], [2, 6]]})
    print(failures)
    return
if __name__ == "__main__":
    check()
""",
        "rust",
    )
    assert result.returncode == 0 and result.stdout == "15\n", result
