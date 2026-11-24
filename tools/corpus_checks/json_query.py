"""Independent query algebra, precision, grammar diagnostics and saved-result acceptance checks."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import random
from dataclasses import dataclass
from fractions import Fraction
from functools import cmp_to_key
from pathlib import Path

from .common import Application
from .csv_json import canonical

MISSING = object()


def kind(value: object) -> str:
    if type(value) in (int, float):
        return "number"
    return type(value).__name__


def equal(left: object, right: object) -> bool:
    if kind(left) != kind(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(equal(value, right[name]) for name, value in left.items())
    if isinstance(left, list):
        return len(left) == len(right) and all(equal(a, b) for a, b in zip(left, right))
    return left == right


def get(row: object, path: str) -> object:
    if not path:
        return row
    value = row
    for part in path[1:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(value, dict):
            value = value.get(part, MISSING)
        elif (
            isinstance(value, list) and part.isascii() and part.isdigit() and (part == "0" or not part.startswith("0"))
        ):
            index = int(part)
            value = value[index] if index < len(value) else MISSING
        else:
            return MISSING
    return value


def test(row: object, node: tuple) -> bool:
    operator = node[0]
    if operator == "not":
        return not test(row, node[1])
    if operator in {"and", "or"}:
        # Recursive short-circuit reference, independent of the application's postfix stack.
        return (
            (test(row, node[1]) and test(row, node[2]))
            if operator == "and"
            else (test(row, node[1]) or test(row, node[2]))
        )
    actual = get(row, node[1])
    if operator == "exists":
        return actual is not MISSING
    if operator == "missing":
        return actual is MISSING
    if actual is MISSING:
        return False
    expected = node[2]
    if operator in {"==", "!="}:
        return equal(actual, expected) if operator == "==" else not equal(actual, expected)
    if operator == "in":
        return any(equal(actual, candidate) for candidate in expected)
    if operator == "contains":
        if isinstance(actual, list):
            return any(equal(candidate, expected) for candidate in actual)
        return type(actual) is str and type(expected) is str and expected in actual
    if kind(actual) != kind(expected) or isinstance(actual, (dict, list)):
        return False
    comparison = 0 if actual is None else int(actual > expected) - int(actual < expected)
    return {"<": comparison < 0, "<=": comparison <= 0, ">": comparison > 0, ">=": comparison >= 0}[operator]


def quote(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def expression(node: tuple) -> str:
    if node[0] == "not":
        return "not (" + expression(node[1]) + ")"
    if node[0] in {"and", "or"}:
        return "(" + expression(node[1]) + " " + node[0] + " " + expression(node[2]) + ")"
    if node[0] in {"exists", "missing"}:
        return node[0] + " " + quote(node[1])
    return quote(node[1]) + " " + node[0] + " " + quote(node[2])


def text(stages: list[tuple]) -> str:
    commands = []
    for stage in stages:
        command = stage[0]
        if command == "filter":
            commands.append("filter " + expression(stage[1]))
        elif command == "order":
            commands.append(
                "order " + ", ".join(quote(path) + (" desc" if desc else " asc") for path, desc in stage[1])
            )
        else:
            columns = ", ".join(quote(path) + " as " + quote(name) for path, name in stage[1])
            if command == "group" and stage[2]:
                columns += " sum " + ", ".join(quote(path) + " as " + quote(name) for path, name in stage[2])
            commands.append(command + " " + columns)
    return " | ".join(commands)


def oracle(rows: list, stages: list[tuple]) -> list:
    result = copy.deepcopy(rows)
    for stage in stages:
        command = stage[0]
        if command == "filter":
            result = [row for row in result if test(row, stage[1])]
        elif command == "select":
            result = [{name: get(row, path) for path, name in stage[1]} for row in result]
            assert all(value is not MISSING for row in result for value in row.values())
        elif command == "order":

            def compare(left: object, right: object, fields: list = stage[1]) -> int:
                for path, desc in fields:
                    a, b = get(left, path), get(right, path)
                    assert kind(a) == kind(b) and a is not MISSING and not isinstance(a, (dict, list))
                    comparison = 0 if a is None else int(a > b) - int(a < b)
                    if comparison:
                        return -comparison if desc else comparison
                return 0

            result.sort(key=cmp_to_key(compare))
        elif command == "group":
            groups = {}
            for row in result:
                values = [get(row, path) for path, name in stage[1]]
                assert all(value is not MISSING and not isinstance(value, (dict, list)) for value in values)
                signature = tuple(
                    (kind(value), Fraction(value) if kind(value) == "number" else value) for value in values
                )
                key = {}
                for (_, name), value in zip(stage[1], values):
                    if type(value) is float and value.is_integer() and -(2**63) <= value < 2**63:
                        value = int(value)
                    key[name] = value
                item = groups.setdefault(signature, {"key": key, "count": 0, "sums": {}})
                item["count"] += 1
                for path, name in stage[2]:
                    value = get(row, path)
                    assert kind(value) == "number"
                    total = item["sums"].get(name, 0) + value
                    assert (type(total) is float and math.isfinite(total)) or (
                        type(total) is int and -(2**63) <= total < 2**63
                    )
                    item["sums"][name] = total
            result = list(groups.values())
        else:
            raise AssertionError(command)
    return result


@dataclass
class Fixture:
    work: Path
    config: dict

    def save(self) -> None:
        (self.work / "query-job.json").write_text(quote(self.config))
        return  # noqa: PLR1711

    def settings(self, mode: str = "write", **extra: str) -> dict:
        return {"QUERY_CONFIG": str(self.work / "query-job.json"), "QUERY_MODE": mode, "QUERY_FAIL": "", **extra}

    @property
    def output(self) -> Path:
        return self.work / self.config["output"]


def fixture(directory: Path, name: str, rows: list, query_text: str, **changes: object) -> Fixture:
    work = directory / name
    work.mkdir(parents=True)
    (work / "dataset.json").write_text(quote(rows))
    fix = Fixture(work, {"input": "dataset.json", "output": "result.json", "query": query_text, **changes})
    fix.save()
    return fix


def success(app: Application, fix: Fixture, expected: list, mode: str = "write", **extra: str) -> list:
    source = fix.work / fix.config["input"]
    before = source.read_bytes()
    result = app.run(fix.work, fix.settings(mode, **extra), timeout=45)
    assert result.returncode == 0 and result.stderr == "", (result.stdout[:1000], result.stderr, fix.config)
    actual = json.loads(result.stdout)
    assert canonical(actual) == canonical(expected), (fix.config, actual, expected)
    assert result.stdout.startswith("[\n") if actual else result.stdout == "[]\n"
    assert source.read_bytes() == before
    if mode == "write":
        assert fix.output.read_text() == result.stdout
        assert json.loads(fix.output.read_bytes()) == actual
    else:
        assert not fix.output.exists()
    assert not list(fix.work.glob(".json-query-*"))
    return actual


def failure(app: Application, fix: Fixture, message: str, **extra: str) -> None:
    existed = fix.output.exists() or fix.output.is_symlink()
    original = fix.output.read_bytes() if fix.output.is_file() else None
    result = app.run(fix.work, fix.settings(**extra), timeout=45)
    assert result.returncode == 2 and message in result.stderr and result.stdout == "", (fix.config, message, result)
    assert (fix.output.exists() or fix.output.is_symlink()) == existed
    if original is not None:
        assert fix.output.read_bytes() == original
    assert not list(fix.work.glob(".json-query-*"))
    return  # noqa: PLR1711


def sample() -> list:
    return [
        {
            "id": i,
            "name": ["Zoë", "李", "alice", "😀"][i % 4],
            "age": (i * 11) % 67,
            "team": ["red", "blue", "red"][i % 3],
            "score": i + (0.25 if i % 3 else 0),
            "active": i % 2 == 0,
            "tags": ["work", i % 3],
            "meta": {"a/b": {"~": [i, None]}},
            "": i,
            **({"optional": None} if i % 4 == 0 else {"optional": "present"} if i % 4 == 1 else {}),
        }
        for i in range(24)
    ]


def check(app: Application, directory: Path) -> dict:
    rows = sample()
    observations = []
    scenarios: list[tuple[list, list[tuple]]] = [(rows, []), ([], []), ([], [("group", [("/x", "x")], [])])]
    atoms = [(operator, "/age", 18) for operator in ["==", "!=", "<", "<=", ">", ">="]] + [
        ("exists", "/optional"),
        ("missing", "/optional"),
        ("==", "/optional", None),
        ("!=", "/optional", None),
        ("contains", "/tags", "work"),
        ("contains", "/tags", 1.0),
        ("contains", "/name", "ë"),
        ("contains", "/name", ""),
        ("in", "/team", ["blue", None]),
        ("==", "/meta/a~1b/~0/0", 9),
        ("==", "/", 7),
        ("missing", "/tags/01"),
        ("missing", "/tags/-1"),
        ("missing", "/tags/9999999999999999999999999"),
        ("missing", "/tags/١"),
        ("missing", "/age/child"),
        ("missing", "/tags/2"),
    ]
    scenarios.extend((rows, [("filter", node)]) for node in atoms)
    mixed = [{"x": value} for value in [None, False, True, 0, 1, 1.0, "1", [], {}, [True], [1.0], {"a": [1]}]] + [{}]
    scenarios.extend(
        (mixed, [("filter", (op, "/x", value))])
        for op, value in [
            ("==", 1),
            ("!=", 1),
            ("==", True),
            ("==", [1]),
            ("==", {"a": [1.0]}),
            ("in", [False, 1.0, None, []]),
            ("contains", 1),
            ("contains", "1"),
            ("<", 1),
            ("<=", None),
            (">=", False),
            ("<=", "1"),
        ]
    )
    fields = [("/team", "team"), ("/name", "name"), ("/score", "score"), ("/id", "id")]
    scenarios.extend(
        [
            (rows, [("select", fields)]),
            (rows, [("order", [("/team", False), ("/age", True), ("/name", False)])]),
            (rows, [("group", [("/team", "team")], [("/score", "score"), ("/id", "ids")])]),
            (rows, [("group", [("/active", "active"), ("/team", "team")], [])]),
            (
                rows,
                [
                    ("filter", (">=", "/age", 18)),
                    ("select", fields),
                    ("group", [("/team", "team")], [("/score", "total")]),
                    ("order", [("/sums/total", True)]),
                    ("select", [("/key/team", "team"), ("/count", "count"), ("/sums/total", "score")]),
                ],
            ),
            (rows, [("select", [("/meta/a~1b/~0/1", "nil"), ("/", "empty/key"), ("/id", "~")])]),
            (
                [
                    1,
                    1.0,
                    True,
                    False,
                    0,
                    -0.0,
                    0.0,
                    None,
                    "1",
                    2**53 + 1,
                    float(2**53),
                    2**63 - 1,
                    float(2**63),
                    -(2**63),
                    -float(2**63),
                    0.5,
                    -0.5,
                    5e-324,
                ],
                [("group", [("", "value")], [])],
            ),
            ([None, None, None], [("order", [("", True)])]),
            ([True, False, True, False], [("order", [("", False)])]),
            (["é", "e\u0301", "😀", "世界", "", "a\x00", "a"], [("order", [("", False)])]),
            ([{"x": [], "id": 1}, {"x": [], "id": 2}], [("filter", ("==", "/x", []))]),
        ]
    )
    numbers = [
        2**63 - 1,
        float(2**63),
        -(2**63),
        math.nextafter(-float(2**63), -math.inf),
        -1.25,
        -1,
        -0.5,
        -5e-324,
        -0.0,
        0,
        5e-324,
        0.5,
        1,
        1.0,
        1.25,
        2**53 + 1,
        float(2**53),
    ]
    scenarios.extend((numbers, [("order", [("", direction)])]) for direction in [False, True])
    scenarios.extend(
        (numbers, [("filter", (operator, "", value))])
        for operator in ["==", "!=", "<", "<=", ">", ">="]
        for value in numbers
    )
    rng = random.Random(490049)
    random_rows = [
        {"id": i, "team": rng.randrange(6), "score": rng.randrange(-100, 100) / 4, "age": rng.randrange(90)}
        for i in range(2000)
    ]
    scenarios.append((random_rows, [("order", [("/team", True), ("/score", False)])]))
    scenarios.append((random_rows, [("group", [("/team", "team")], [("/score", "score")])]))
    for _ in range(40):
        a, b, c = rng.choices(atoms, k=3)
        condition = (rng.choice(["and", "or"]), ("not", a), ("or", b, c))
        scenarios.append((rows, [("filter", condition), ("order", [("/team", False), ("/age", True)])]))
    for index, (data, stages) in enumerate(scenarios):
        fix = fixture(directory, f"valid-{index}", data, text(stages))
        observations.append(success(app, fix, oracle(data, stages)))

    equivalents = [
        (
            'filter "/age" >= 18 and "/active" == true or "/team" == "blue"',
            ("or", ("and", (">=", "/age", 18), ("==", "/active", True)), ("==", "/team", "blue")),
        ),
        ('filter not not exists "/optional"', ("exists", "/optional")),
        (
            'filter not ("/age" < 18 or "/team" == "red")',
            ("and", ("not", ("<", "/age", 18)), ("not", ("==", "/team", "red"))),
        ),
        ('filter missing "/optional"', ("not", ("exists", "/optional"))),
        ('filter "/age" in [0, 11, 22]', ("or", ("==", "/age", 0), ("or", ("==", "/age", 11), ("==", "/age", 22)))),
    ]
    for index, (query, condition) in enumerate(equivalents):
        expected = oracle(rows, [("filter", condition)])
        for variant, spelling in enumerate([query, text([("filter", condition)])]):
            observations.append(
                success(app, fixture(directory, f"equivalent-{index}-{variant}", rows, spelling), expected)
            )
    for index, query in enumerate(
        [
            'filter "/x" == {"q": "a\\"|b", "a": [true, null, [1]]}',
            'filter\n\t"/x"=={"a":[true,null,[1.0]],"q":"a\\"|b"}',
        ]
    ):
        data = [{"x": {"q": 'a"|b', "a": [True, None, [1]]}}, {"x": {}}]
        observations.append(success(app, fixture(directory, f"escaped-{index}", data, query), data[:1]))

    invalid = [
        ("wat", 0, "expected filter"),
        ("filter", 6, "expected a predicate"),
        ('filter "/x"', 11, "expected a comparison operator"),
        ('filter "/x" ==', 14, "expected a JSON literal"),
        ('filter "/x" = 1', 12, "expected a comparison operator"),
        ('filter "/x" == potato', 15, "expected a JSON literal"),
        ('filter "/x" in 1', 15, "in requires an array"),
        ('filter "/x" < []', 14, "ordered comparison requires"),
        ('filter "/x" == 1e309', 15, "invalid JSON literal"),
        ('filter "/x" == 9223372036854775808', 15, "invalid JSON literal"),
        ('filter "/x" == "oops', 15, "unterminated JSON literal"),
        ('filter "/x" == [1,}', 15, "invalid JSON literal"),
        ('filter "/x" == {"a":1', 15, "unterminated JSON literal"),
        ('filter "/x" == "\\ud800"', 15, "invalid JSON literal"),
        ('filter "x" == 1', 7, "invalid field path"),
        ('filter "/~2" == 1', 7, "invalid field path"),
        ('filter "/~" == 1', 7, "invalid field path"),
        ("filter 1 == 1", 7, "expected a quoted field path"),
        ("filter exists", 13, "expected a quoted field path"),
        ('filter (exists "/x"', 7, "unclosed parenthesis"),
        ('filter exists "/x")', 18, "unmatched closing parenthesis"),
        ('filter exists "/x" and', 22, "expected a predicate"),
        ('filter exists "/x" exists "/y"', 19, "expected a boolean operator"),
        ("filter ()", 8, "expected a quoted field path"),
        ('select "/x"', 11, "expected as"),
        ('select "/x" as 1', 15, "expected a quoted output name"),
        ('select "/x" as ""', 15, "empty, oversized or duplicate"),
        ('select "/x" as "x", "/y" as "x"', 28, "empty, oversized or duplicate"),
        ('order "/x"', 10, "expected asc or desc"),
        ('order "/x" asc,', 15, "expected a quoted field path"),
        ('group "/x" as "x" sum', 21, "expected a quoted field path"),
        ('select "/x" as "x" select', 19, "expected pipeline separator"),
        ('filter exists "" |', 18, "expected pipeline stage"),
        ('filter "/é" == "😀"\n and ?', 24, "expected a quoted field path"),
    ]
    for index, (query, position, message) in enumerate(invalid):
        # Fixtures give character offsets; the console promises zero-based UTF-8 byte offsets.
        prefix = query[:position]
        where = f"byte {len(prefix.encode())}, line {prefix.count(chr(10)) + 1}, column {len(prefix.rsplit(chr(10), 1)[-1]) + 1}: "
        failure(app, fixture(directory, f"syntax-{index}", [], query), where + message)

    runtime = [
        ([{}], 'select "/x" as "x"', "missing field /x"),
        ([{}], 'order "/x" asc', "missing field /x"),
        ([{}], 'group "/x" as "x"', "missing field /x"),
        ([{"x": []}], 'order "/x" asc', "expected compatible JSON scalars"),
        ([{"x": {}}], 'group "/x" as "x"', "group requires scalar keys"),
        ([{"x": 1}, {"x": True}], 'order "/x" asc', "expected compatible JSON scalars"),
        ([{"a": 1, "b": None}, {"a": 2, "b": 1}], 'order "/a" asc, "/b" asc', "expected compatible JSON scalars"),
        ([{"x": "a", "v": True}], 'group "/x" as "x" sum "/v" as "v"', "expected JSON numbers"),
        ([{"x": "a"}], 'group "/x" as "x" sum "/v" as "v"', "missing field /v"),
        ([{"x": "a", "v": 2**63 - 1}, {"x": "a", "v": 1}], 'group "/x" as "x" sum "/v" as "v"', "integer overflow"),
        (
            [{"x": "a", "v": 1.7e308}, {"x": "a", "v": 1.7e308}],
            'group "/x" as "x" sum "/v" as "v"',
            "non-finite floating point result",
        ),
    ]
    for index, (data, query, message) in enumerate(runtime):
        failure(app, fixture(directory, f"runtime-{index}", data, query), message)

    counts = boundaries(app, directory)
    default = fixture(directory, "default-preview", rows, 'filter "/age" < 18')
    success(app, default, oracle(rows, [("filter", ("<", "/age", 18))]), "preview")
    success(app, default, rows, "preview", QUERY_TEXT="")
    success(app, default, oracle(rows, [("filter", (">", "/age", 60))]), QUERY_TEXT='filter "/age" > 60')
    failure(app, default, "output already exists")
    failed = fixture(directory, "injected", rows, "")
    failure(app, failed, "injected failure: ready", QUERY_FAIL="ready")
    success(app, failed, rows)
    for name in ["file", "directory", "symlink", "dangling", "hardlink"]:
        fix = fixture(directory, "existing-" + name, rows, "")
        if name == "file":
            fix.output.write_bytes(b"keep me")
        elif name == "directory":
            fix.output.mkdir()
        elif name == "hardlink":
            fix.output.hardlink_to(fix.work / "dataset.json")
        else:
            fix.output.symlink_to(fix.work / ("dataset.json" if name == "symlink" else "absent"))
        failure(app, fix, "output already exists")
    for name in ["input", "config"]:
        fix = fixture(directory, "symlink-" + name, rows, "")
        path = fix.work / ("dataset.json" if name == "input" else "query-job.json")
        original = path.with_suffix(".original")
        path.rename(original)
        path.symlink_to(original)
        failure(app, fix, "input must be a regular file")
    result_hash = hashlib.sha256(canonical(observations).encode()).hexdigest()
    return {
        "queries": len(scenarios),
        "equivalent_queries": len(equivalents) * 2,
        "escaped_literals": 2,
        "syntax_errors": len(invalid),
        "runtime_errors": len(runtime),
        "result_sha256": result_hash,
        "saved_result_checks": 13,
        **counts,
    }


def boundaries(app: Application, directory: Path) -> dict:
    invalid = [
        ({"query": 1}, "expected JSON string"),
        ({"input": ""}, "invalid document path"),
        ({"output": ""}, "invalid document path"),
        ({"output": "\x00"}, "invalid document path"),
        ({"extra": True}, "expected input, output and query"),
        ({"input": False}, "expected JSON string"),
    ]
    for index, (changes, message) in enumerate(invalid):
        failure(app, fixture(directory, f"config-{index}", [], "", **changes), message)
    fix = fixture(directory, "mode", [], "")
    failure(app, fix, "invalid query mode", QUERY_MODE="bad")
    malformed = [b"{}", b"true", b"null", b"[1,]", b"[NaN]", b"[Infinity]", b"[9223372036854775808]", b"[\xff]"]
    for index, data in enumerate(malformed):
        fix = fixture(directory, f"malformed-{index}", [], "")
        (fix.work / "dataset.json").write_bytes(data)
        failure(app, fix, "")
    too_many_rows = fixture(directory, "rows-over", [0] * 2001, "")
    failure(app, too_many_rows, "dataset exceeds 2000 rows")
    query_limits = [
        (" " * 8193, "query exceeds 8192 UTF-8 bytes"),
        ("filter " + "not " * 511 + 'exists ""', "query exceeds 512 tokens"),
        (" | ".join(['filter exists ""'] * 9), "pipeline exceeds 8 stages"),
        ("select " + ", ".join(f'"/x" as "c{i}"' for i in range(9)), "stage exceeds 8 fields"),
        ("filter " + quote("/x" * 17) + " == 1", "field path exceeds 16 levels"),
        ("filter " + quote("/" + "x" * 1024) + " == 1", "invalid field path"),
        ('select "/x" as ' + quote("é" * 65), "empty, oversized or duplicate"),
        ('filter "" == ' + "[" * 17 + "]" * 17, "literal nesting exceeds 16"),
    ]
    for index, (query, message) in enumerate(query_limits):
        failure(app, fixture(directory, f"query-limit-{index}", [], query), message)
    valid_limits = [
        ([], " " * 8192),
        ([], "filter " + "not " * 509 + 'exists ""'),
        ([1], " | ".join(['filter exists ""'] * 8)),
        ([{"x": 1}], "select " + ", ".join(f'"/x" as "c{i}"' for i in range(8))),
        ([{"x" * 1023: 1}], "filter " + quote("/" + "x" * 1023) + " == 1"),
        ([{"x": 1}], 'select "/x" as ' + quote("é" * 64)),
    ]
    for index, (rows, query) in enumerate(valid_limits):
        expected = rows
        if index == 3:
            expected = [{f"c{i}": 1 for i in range(8)}]
        elif index == 5:
            expected = [{"é" * 64: 1}]
        success(app, fixture(directory, f"query-boundary-{index}", rows, query), expected)
    data = "[0]" + " " * (4194304 - 3)
    fix = fixture(directory, "input-boundary", [], "")
    (fix.work / "dataset.json").write_text(data)
    success(app, fix, [0])
    fix = fixture(directory, "input-over", [], "")
    (fix.work / "dataset.json").write_text(data + " ")
    failure(app, fix, "input byte limit exceeded")
    fix = fixture(directory, "config-boundary", [], "")
    path = fix.work / "query-job.json"
    data = path.read_text()
    path.write_text(data + " " * (65536 - len(data.encode())))
    success(app, fix, [])
    fix = fixture(directory, "config-over", [], "")
    (fix.work / "query-job.json").write_text(" " * 65537)
    failure(app, fix, "input byte limit exceeded")
    large = fixture(
        directory, "output-over", [{"x": "x" * 2200000}], "select " + ", ".join(f'"/x" as "c{i}"' for i in range(8))
    )
    failure(app, large, "result exceeds 16 MiB")
    return {
        "configuration_errors": len(invalid) + 1,
        "malformed_datasets": len(malformed),
        "capacity_checks": len(query_limits) + len(valid_limits) + 6,
    }
