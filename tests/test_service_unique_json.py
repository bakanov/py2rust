"""Unique-key parsing rejects ambiguity and preserves ordinary object keys and numeric types."""

import json
import random
from pathlib import Path

import pytest

from .test_service_canonical_json import oracle
from .test_services import run


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_unique_json_values_and_reserved_keys(tmp_path: Path, engine: str) -> None:
    rng = random.Random(89001)
    rows = [
        None,
        True,
        False,
        0,
        -(2**63),
        2**63 - 1,
        0.1,
        -0.0,
        5e-324,
        {"$serde_json::private::Number": "not a number", "ordinary": "kept"},
        {"$serde_json::private::RawValue": "not JSON", "ordinary": [1, 2]},
        [{"same": 1}, {"same": 2}],
        {"": "empty", "世界": "Unicode\u2028", "a\x00b": "control"},
    ]
    rows += [{"value": rng.random(), "array": [rng.randrange(-10000, 10000), str(i)]} for i in range(80)]
    (tmp_path / "cases.json").write_text(
        json.dumps([json.dumps(row, ensure_ascii=False) for row in rows], ensure_ascii=False)
    )
    source = """
from py2rust.stdlib import Json, json_array, json_canonical, json_loads, json_loads_unique, json_string, read_text

def check() -> None:
    for item in json_array(json_loads(read_text("cases.json"))):
        text: str = json_string(item)
        strict: Json = json_loads_unique(text)
        assert json_canonical(strict) == json_canonical(json_loads(text))
        print(json_canonical(strict))
    return
if __name__ == "__main__":
    check()
"""
    result = run(tmp_path, source, engine)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "".join(oracle(row) + "\n" for row in rows)


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_unique_json_nested_and_escaped_duplicates(tmp_path: Path, engine: str) -> None:
    rows = [
        '{"x":1,"x":2}',
        '{"x":null,"x":null}',
        '[{"a":{},"a":[]}]',
        '{"outer":{"a":1,"\\u0061":2}}',
        '{"λ":1,"\\u03bb":2}',
        '{"":1,"":2}',
        '{"$serde_json::private::Number":"1","$serde_json::private::Number":"2"}',
        '{"a\\u0000b":1,"a\\u0000b":2}',
        '{"x":1e999,"x":0}',
        '{"x":9223372036854775808,"x":0}',
        '{"x":' + "[" * 65 + "0" + "]" * 65 + ',"x":0}',
    ]
    (tmp_path / "cases.json").write_text(json.dumps(rows))
    source = """
from py2rust.stdlib import json_array, json_canonical, json_loads, json_loads_unique, json_string, read_text

def check() -> None:
    failures: int = 0
    for item in json_array(json_loads(read_text("cases.json"))):
        text: str = json_string(item)
        try:
            json_loads_unique(text)
        except Exception:
            failures = failures + 1
        print(json_canonical(json_loads(text)))
    assert failures == 11
    return
if __name__ == "__main__":
    check()
"""
    result = run(tmp_path, source, engine)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "".join(oracle(json.loads(row)) + "\n" for row in rows)


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_unique_json_validation_and_depth(tmp_path: Path, engine: str) -> None:
    accepted = ["[" * 64 + "0" + "]" * 64, '{"a":' * 64 + "0" + "}" * 64, ' \r\n\t{"a":[true,null,"text"]}\t\n']
    invalid = [
        "[" * 65 + "0" + "]" * 65,
        '{"a":' * 65 + "0" + "}" * 65,
        "",
        " ",
        "{}{}",
        "0 false",
        "[1,]",
        '{"a":}',
        "NaN",
        "Infinity",
        "1e999",
        "9223372036854775808",
        "-9223372036854775809",
        '"\\ud800"',
        '{"\\ud800":0}',
    ]
    (tmp_path / "cases.json").write_text(json.dumps({"accepted": accepted, "invalid": invalid}))
    source = """
from py2rust.stdlib import Json, json_array, json_canonical, json_loads, json_loads_unique, json_string, read_text

def check() -> None:
    cases: Json = json_loads(read_text("cases.json"))
    for item in json_array(cases["accepted"]):
        print(json_canonical(json_loads_unique(json_string(item))))
    failures: int = 0
    for item in json_array(cases["invalid"]):
        try:
            json_loads_unique(json_string(item))
        except Exception:
            failures = failures + 1
    assert failures == 15
    return
if __name__ == "__main__":
    check()
"""
    result = run(tmp_path, source, engine)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "".join(oracle(json.loads(row)) + "\n" for row in accepted)


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_unique_json_large_objects_and_sibling_keys(tmp_path: Path, engine: str) -> None:
    rows = [{"same": i, "padding": "x" * 100} for i in range(4096)]
    value = {"items": rows, "wide": {str(i): i for i in range(4096)}}
    (tmp_path / "input.json").write_text(json.dumps(value))
    source = """
from py2rust.stdlib import Json, json_array, json_int, json_keys, json_loads_unique, read_text

def check() -> None:
    value: Json = json_loads_unique(read_text("input.json"))
    items: list[Json] = json_array(value["items"])
    assert len(items) == 4096 and len(json_keys(value["wide"])) == 4096
    for index in range(len(items)):
        assert json_int(items[index]["same"]) == index
    print("large unique JSON")
    return
if __name__ == "__main__":
    check()
"""
    result = run(tmp_path, source, engine)
    assert result.returncode == 0 and result.stdout == "large unique JSON\n", result.stderr
