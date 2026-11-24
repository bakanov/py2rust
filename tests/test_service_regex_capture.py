"""Numbered capture text, Unicode character spans, full matches and concurrent cache isolation."""

import json
import random
import re
from pathlib import Path

import pytest
from py2rust.compiler.service import ServiceCompiler, ServiceError

from .test_services import parity, run


def expected(pattern: str, text: str, full: bool) -> dict | None:
    compiled = re.compile(pattern, re.ASCII)
    matched = compiled.fullmatch(text) if full else compiled.search(text)
    if matched is None:
        return None
    groups = [matched.group(index) for index in range(compiled.groups + 1)]
    return {
        "groups": groups,
        "spans": [list(matched.span(index)) if value is not None else None for index, value in enumerate(groups)],
    }


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_capture_vectors_against_python_re(tmp_path: Path, engine: str) -> None:
    patterns = [
        "",
        "()",
        "(a)?(b*)",
        "(é)(😀)?",
        "((a)?b)+",
        "(a(b)?)+",
        "(a|(b))+",
        "(a|ab)",
        "(a+?)(a*)",
        "(a*)(a*)",
        "((a|b){1,3})",
        "([^\n]*)(\n)?",
        r"(\w+)-(\d+)",
        r"([^\w]+)(\w*)",
        r"([\w-]+)",
        r"\b(word)\b",
        r"([\s]+)(\S*)",
        r"([\b])",
        r"(\\w)",
        "(世界+)(.)",
        "([éя😀]+)",
        r"([^\x00-\x1f\x7f]+)",
    ]
    texts = [
        "",
        "a",
        "aa",
        "ab",
        "abb",
        "aba",
        "abab",
        "b",
        "a\n",
        "\n",
        "é😀",
        "pré é😀!",
        "世界世😀",
        "éя😀",
        "éwordя",
        "abc-12",
        "١2３",
        "\t \u00a0",
        "\x08",
        r"\w",
    ]
    cases = [
        {"pattern": pattern, "text": text, "full": full}
        for pattern in patterns
        for text in texts
        for full in [False, True]
    ]
    cases += [{"pattern": "(a)$", "text": text, "full": full} for text in ["a", "a\n"] for full in [False, True]]
    rng = random.Random(71071)
    for _index in range(200):
        cases.append(
            {
                "pattern": rng.choice(patterns),
                "text": "".join(rng.choice("abé😀 \n12-_") for _ in range(rng.randrange(20))),
                "full": rng.choice([False, True]),
            }
        )
    (tmp_path / "cases.json").write_text(json.dumps(cases, ensure_ascii=False))
    source = """from py2rust.stdlib import Json, json_loads, json_array, json_string, json_bool, json_dumps, read_text, regex_capture
def check() -> None:
    results: list[Json] = []
    for row in json_array(json_loads(read_text("cases.json"))):
        results.append(regex_capture(json_string(row["pattern"]), json_string(row["text"]), json_bool(row["full"])))
    print(json_dumps(results))
    return
if __name__ == "__main__":
    check()
"""
    result = run(tmp_path, source, engine)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [expected(row["pattern"], row["text"], row["full"]) for row in cases]


def test_capture_limits_recovery_and_zero_width(tmp_path: Path) -> None:
    patterns = ["a" * 4096, "é" * 2048, "()" * 64]
    texts = ["a" * 4096, "é" * 2048, ""]
    values = [{"pattern": pattern, "text": text} for pattern, text in zip(patterns, texts, strict=True)]
    values.append({"pattern": "(.*)", "text": "é" * 32768})
    (tmp_path / "valid.json").write_text(json.dumps(values))
    invalid = [
        {"pattern": "a" * 4097, "text": ""},
        {"pattern": "é" * 2048 + "a", "text": ""},
        {"pattern": "()" * 65, "text": ""},
        {"pattern": "z", "text": "a" * 65537},
        {"pattern": "z", "text": "é" * 32768 + "a"},
    ]
    invalid += [
        {"pattern": pattern, "text": "abc"} for pattern in ["[", "(", "a{3,2}", "(?=a)", r"(a)\1", "(?P<name>a)"]
    ]
    (tmp_path / "invalid.json").write_text(json.dumps(invalid))
    output = parity(
        tmp_path,
        """from py2rust.stdlib import Json, json_loads, json_array, json_string, json_int, json_equal, regex_capture, read_text
def check() -> None:
    for row in json_array(json_loads(read_text("valid.json"))):
        result: Json = regex_capture(json_string(row["pattern"]), json_string(row["text"]), True)
        assert result is not None
        assert json_string(result["groups"][0]) == json_string(row["text"])
        assert json_int(result["spans"][0][1]) == len(json_string(row["text"]))
    errors: int = 0
    for row in json_array(json_loads(read_text("invalid.json"))):
        try:
            bad: Json = regex_capture(json_string(row["pattern"]), json_string(row["text"]), False)
        except Exception:
            errors = errors + 1
        assert json_equal(regex_capture("(x)?()", "", True), {"groups": ["", None, ""], "spans": [[0, 0], None, [0, 0]]})
    print(errors)
    return
if __name__ == "__main__":
    check()
""",
    )
    assert output == str(len(invalid)) + "\n"


def test_capture_argument_order_and_fresh_results(tmp_path: Path) -> None:
    output = parity(
        tmp_path,
        """from py2rust.stdlib import Json, regex_capture, json_equal
def pattern() -> str:
    print("pattern")
    return "(a|ab)"
def text() -> str:
    print("text")
    return "ab"
def full() -> bool:
    print("full")
    return True
def check() -> None:
    first: Json = regex_capture(pattern(), text(), full())
    assert json_equal(first, {"groups": ["ab", "ab"], "spans": [[0, 2], [0, 2]]})
    first["groups"] = []
    assert json_equal(regex_capture("(a|ab)", "ab", True), {"groups": ["ab", "ab"], "spans": [[0, 2], [0, 2]]})
    assert json_equal(regex_capture("(a|ab)", "ab", False), {"groups": ["a", "a"], "spans": [[0, 1], [0, 1]]})
    return
if __name__ == "__main__":
    check()
""",
    )
    assert output == "pattern\ntext\nfull\n"


def test_capture_parallel_pattern_and_mode_isolation(tmp_path: Path) -> None:
    output = parity(
        tmp_path,
        """from py2rust.stdlib import Json, regex_capture, parallel_map, json_int, json_equal
def capture(value: Json) -> Json:
    number: int = json_int(value)
    if number % 2 == 0:
        return regex_capture("(é)(😀)?", "pré é😀!", False)
    return regex_capture("(a|ab)", "ab", True)
def check() -> None:
    values: list[Json] = []
    for index in range(128):
        values.append(index)
    results: list[Json] = parallel_map(capture, values, 8)
    for index in range(128):
        assert json_equal(results[index], capture(index))
    print("128 independent capture results")
    return
if __name__ == "__main__":
    check()
""",
    )
    assert output == "128 independent capture results\n"


@pytest.mark.parametrize(
    "expression",
    [
        'regex_capture("a", "a")',
        'regex_capture("a", "a", 1)',
        'regex_capture(1, "a", True)',
        'regex_capture("a", b"a", True)',
    ],
)
def test_capture_signature_diagnostics(expression: str) -> None:
    source = f"from py2rust.stdlib import Json, regex_capture\ndef check() -> None:\n    value: Json = {expression}\n    return\n"
    with pytest.raises(ServiceError):
        ServiceCompiler().compile(source)
