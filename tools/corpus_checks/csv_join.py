"""Compare native joins with independent CSV decoding and a nested-loop relational oracle."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import random
import selectors
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .common import Application
from .csv_json import csv_rows, csv_text


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass
class Fixture:
    work: Path
    config: dict

    @property
    def output(self) -> Path:
        return self.work / "joined"

    @property
    def config_path(self) -> Path:
        return self.work / "join.json"

    def save(self) -> None:
        self.config_path.write_text(json.dumps(self.config, ensure_ascii=False))
        return  # noqa: PLR1711

    def settings(self, mode: str = "join", **extra: str) -> dict[str, str]:
        return {"JOIN_CONFIG": str(self.config_path), "JOIN_MODE": mode, **extra}


def fixture(
    directory: Path,
    name: str,
    left_rows: list[list[str]] | None = None,
    right_rows: list[list[str]] | None = None,
    **changes: object,
) -> Fixture:
    work = directory / name
    work.mkdir(parents=True)
    config = {
        "left": {"path": "left.csv", "delimiter": ",", "keys": ["key"]},
        "right": {"path": "right.csv", "delimiter": ",", "keys": ["key"]},
        "output": "joined",
        "kind": "left",
        "duplicates": "all",
        "order": "left",
        "delimiter": ",",
        "select": [{"side": "left", "column": "value", "as": "L"}, {"side": "right", "column": "value", "as": "R"}],
        "max_rows": 10000,
        "max_field_bytes": 65536,
        "max_input_bytes": 4194304,
        "max_output_rows": 100000,
    }
    config.update(changes)
    left = left_rows if left_rows is not None else [["key", "value"], ["a", "one"], ["b", "two"], ["a", "three"]]
    right = right_rows if right_rows is not None else [["key", "value"], ["a", "four"], ["a", "five"], ["c", "six"]]
    (work / "left.csv").write_bytes(
        csv_text(left, config["left"]["delimiter"] if len(config["left"]["delimiter"]) == 1 else ",").encode()
    )
    (work / "right.csv").write_bytes(
        csv_text(right, config["right"]["delimiter"] if len(config["right"]["delimiter"]) == 1 else ",").encode()
    )
    fix = Fixture(work, config)
    fix.save()
    return fix


def oracle(fix: Fixture) -> tuple[bytes, dict]:
    config = fix.config
    raw = {side: (fix.work / config[side]["path"]).read_bytes() for side in ["left", "right"]}
    tables = {side: csv_rows(raw[side].decode(), config[side]["delimiter"]) for side in raw}
    headers = {side: table[0] for side, table in tables.items()}
    records = {side: table[1:] for side, table in tables.items()}
    keys = {
        side: [tuple(row[headers[side].index(name)] for name in config[side]["keys"]) for row in records[side]]
        for side in records
    }
    left_order = list(range(len(records["left"])))
    if config["order"] == "key":
        left_order.sort(key=lambda index: keys["left"][index])
    output = [[column["as"] for column in config["select"]]]
    matched = {"left": set(), "right": set()}
    pairs = 0
    # Intentionally scan the entire right input for each left row; the application uses a hash index.
    for i in left_order:
        matching = [j for j in range(len(records["right"])) if keys["left"][i] == keys["right"][j]]
        pairs += len(matching)
        if matching:
            matched["left"].add(i)
            matched["right"].update(matching)
        for j in matching if matching else ([-1] if config["kind"] == "left" else []):
            output.append(
                [
                    (
                        records["left"][i][headers["left"].index(item["column"])]
                        if item["side"] == "left"
                        else ("" if j == -1 else records["right"][j][headers["right"].index(item["column"])])
                    )
                    for item in config["select"]
                ]
            )
    data = csv_text(output, config["delimiter"]).encode()
    report = {
        "kind": config["kind"],
        "order": config["order"],
        "columns": output[0],
        "output_rows": len(output) - 1,
        "matched_pairs": pairs,
        "data_sha256": digest(data),
    }
    for side in ["left", "right"]:
        report[side + "_columns"] = headers[side]
        report[side + "_rows"] = len(records[side])
        report["matched_" + side] = len(matched[side])
        report[side + "_sha256"] = digest(raw[side])
        report["unmatched_" + side] = [
            {"row": i + 1, "values": row} for i, row in enumerate(records[side]) if i not in matched[side]
        ]
        report["duplicate_" + side] = [
            {"key": list(key), "rows": [i + 1 for i, value in enumerate(keys[side]) if key == value]}
            for key in sorted(set(keys[side]))
            if keys[side].count(key) > 1
        ]
    return data, report


def bundle(fix: Fixture, expected: tuple[bytes, dict]) -> None:
    data, report = expected
    assert {path.name for path in fix.output.iterdir()} == {"joined.csv", "report.json"}
    assert (fix.output / "joined.csv").read_bytes() == data
    assert json.loads((fix.output / "report.json").read_bytes()) == report
    return  # noqa: PLR1711


def run(app: Application, fix: Fixture, timeout: int = 30) -> dict:
    expected = oracle(fix)
    before = {p.name: p.read_bytes() for p in fix.work.iterdir() if p.is_file()}
    for mode in ["preview", "join"]:
        result = app.run(fix.work, fix.settings(mode), timeout=timeout)
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout) == expected[1]
        if mode == "preview":
            assert not fix.output.exists()
        else:
            bundle(fix, expected)
    assert not list(fix.work.glob(".csv-join-*"))
    assert all((fix.work / name).read_bytes() == data for name, data in before.items())
    again = app.run(fix.work, fix.settings())
    assert again.returncode != 0 and "already exists" in again.stderr
    bundle(fix, expected)
    return expected[1]


def reject(app: Application, fix: Fixture, message: str = "", **settings: str) -> None:
    before = {p.name: p.read_bytes() for p in fix.work.iterdir() if p.is_file() and not p.is_symlink()}
    result = app.run(fix.work, fix.settings(**settings), timeout=30)
    assert result.returncode != 0 and message in result.stderr, result.stderr
    assert not fix.output.exists() and not list(fix.work.glob(".csv-join-*"))
    assert all((fix.work / name).read_bytes() == data for name, data in before.items())
    return  # noqa: PLR1711


def check_joins(app: Application, directory: Path) -> int:
    rng = random.Random(440044)
    pool = ["", "a", "ab", "bc", "c", "a|b", "b|c", '"', ",", "\r\n", "😀", "世界", "é", "é", "0", "\\N", "x\0y"]
    cases = 0
    for count in range(60):
        width = count % 4 + 1
        header = [f"k{i}" for i in range(width)] + ["value"]
        templates = [rng.choices(pool, k=width) for _ in range(9)]
        left = [header] + [rng.choice(templates) + [f"left-{i}\n😀"] for i in range(rng.randrange(0, 24))]
        right = [header] + [rng.choice(templates) + [f'right-{i},"'] for i in range(rng.randrange(0, 24))]
        delim = [",", "\t", ";", "|"]
        fix = fixture(
            directory,
            f"random-{count}",
            left,
            right,
            left={"path": "left.csv", "delimiter": delim[count % 4], "keys": header[:-1]},
            right={"path": "right.csv", "delimiter": delim[(count + 1) % 4], "keys": header[:-1]},
            kind="inner" if count % 2 else "left",
            order="key" if count % 3 else "left",
            delimiter=delim[(count + 2) % 4],
        )
        if count % 5 == 0:
            fix.config["select"] = [{"side": "left", "column": "value", "as": 'Only, "left"\n'}]
            fix.save()
        run(app, fix)
        cases += 1
    for name, left, right in [
        ("empty", [["key", "value"]], [["key", "value"]]),
        ("no-right", [["key", "value"], ["", "x"]], [["key", "value"]]),
        ("no-left", [["key", "value"]], [["key", "value"], ["", "x"]]),
        (
            "literals",
            [
                ["key", "value"],
                ["", ""],
                ["0", "zero"],
                ["00", "double"],
                [" x ", "space"],
                ["é", "nfc"],
                ["é", "nfd"],
                ["\\N", "literal-null"],
            ],
            [["key", "value"], ["", "empty"], ["0", "zero"], ["x", "trimmed"], ["é", "nfc"], ["\\N", "slash"]],
        ),
    ]:
        for kind in ["left", "inner"]:
            run(app, fixture(directory, name + kind, left, right, kind=kind))
            cases += 1
    # Composite-key boundaries, embedded separators, arity and different key-column names/order.
    left = [["a", "b", "value"], ["ab", "c", "one"], ["a", "bc", "two"], ["a|b", "c", "three"], ["a", "b|c", "four"]]
    right = [
        ["x", "value", "y"],
        ["c", "first", "ab"],
        ["bc", "second", "a"],
        ["c", "third", "a|b"],
        ["b|c", "fourth", "a"],
    ]
    fix = fixture(directory, "collisions", left, right)
    fix.config["left"]["keys"] = ["a", "b"]
    fix.config["right"]["keys"] = ["y", "x"]
    fix.save()
    report = run(app, fix)
    assert report["matched_pairs"] == 4
    return cases + 1


def check_invalid(app: Application, directory: Path) -> int:
    base = fixture(directory, "base").config
    changes = [
        {"kind": "outer"},
        {"duplicates": "first"},
        {"order": "random"},
        {"delimiter": "é"},
        {"delimiter": '"'},
        {"select": []},
        {"select": base["select"] * 2},
        {"select": [{"side": "other", "column": "value", "as": "x"}]},
        {"select": [{"side": "right", "column": "absent", "as": "x"}]},
        {"select": [{"side": "left", "column": "value", "as": ""}]},
        {"select": [{"side": "left", "column": "value", "as": "x\0y"}]},
        {"select": [{"side": "left", "column": "value", "as": "x" * 257}]},
        {"select": [{"side": "left", "column": "value", "as": str(i)} for i in range(65)]},
        {"output": "missing/child"},
        {"output": "left.csv"},
        {"output": "join.json"},
        {"extra": 1},
    ]
    for field, maximum in [
        ("max_rows", 10000),
        ("max_field_bytes", 65536),
        ("max_input_bytes", 4194304),
        ("max_output_rows", 100000),
    ]:
        changes.extend({field: value} for value in [0, maximum + 1, True, "1", 1.5])
    for side in ["left", "right"]:
        for field, value in [
            ("keys", []),
            ("keys", ["key", "key"]),
            ("keys", ["absent"]),
            ("keys", ["key", "value"]),
            ("delimiter", "::"),
            ("path", "missing"),
            ("path", ""),
            ("extra", 1),
        ]:
            spec = copy.deepcopy(base[side])
            spec[field] = value
            changes.append({side: spec})
    for index, change in enumerate(changes):
        reject(app, fixture(directory, f"bad-config-{index}", **change))
    count = len(changes)
    for side in ["left", "right"]:
        for index, data in enumerate(
            [
                b"",
                b"key,key\na,b\n",
                b"key,value\na\n",
                b"key,value\na,b,c\n",
                b"\n",
                b'key,value\na,"unterminated',
                b'key,value\na,"x"tail\n',
                b"key,value\na,\xff\n",
                b"\xef\xbb\xbfkey,value\na,b\n",
                b"key,value\n\n",
                b",value\nx,y\n",
            ]
        ):
            fix = fixture(directory, f"bad-input-{side}-{index}")
            (fix.work / (side + ".csv")).write_bytes(data)
            reject(app, fix)
            count += 1
    for index, data in enumerate([b"[]", b"{}", b"{", b"\xff", b"{}" + b" " * 65536]):
        fix = fixture(directory, f"bad-document-{index}")
        fix.config_path.write_bytes(data)
        reject(app, fix)
        count += 1
    reject(app, fixture(directory, "bad-mode"), JOIN_MODE="unknown")
    reject(app, fixture(directory, "duplicate-policy", duplicates="error"), "duplicate join key")
    unique = [["key", "value"], ["a", "1"], ["b", "2"]]
    run(app, fixture(directory, "unique-policy", unique, unique, duplicates="error"))
    return count + 3


def pause(app: Application, fix: Fixture, point: str) -> subprocess.Popen:
    process = subprocess.Popen(
        app.command,
        cwd=fix.work,
        env=app.environment(fix.settings(JOIN_PAUSE=point, JOIN_CONTINUE=str(fix.work / "continue"))),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            assert selector.select(20), "join did not pause"
        assert process.stdout.readline().rstrip() == "PAUSED " + point
        return process
    except BaseException:
        process.kill()
        process.communicate()
        raise


def resume(process: subprocess.Popen, fix: Fixture) -> subprocess.CompletedProcess:
    (fix.work / "continue").touch()
    stdout, stderr = process.communicate(timeout=30)
    return subprocess.CompletedProcess(process.args, process.returncode, stdout, stderr)


def check_publication(app: Application, directory: Path) -> int:
    points = ["validated", "stage", "data", "report", "ready", "published"]
    for point in points:
        for killed in [False, True]:
            fix = fixture(directory, f"failure-{point}-{killed}")
            expected = oracle(fix)
            if killed:
                process = pause(app, fix, point)
                process.kill()
                process.communicate(timeout=10)
                assert process.returncode == -9
            else:
                result = app.run(fix.work, fix.settings(JOIN_FAIL=point))
                assert result.returncode != 0 and "injected failure: " + point in result.stderr
            if point == "published":
                bundle(fix, expected)
            else:
                assert not fix.output.exists()
            stages = list(fix.work.glob(".csv-join-*"))
            assert len(stages) == int(killed and point not in ["published", "validated"])
            for stage in stages:
                shutil.rmtree(stage)  # Operator cleanup of a verified test-owned abandoned stage.
            if point != "published":
                run(app, fix)
    count = len(points) * 2
    for point in ["validated", "ready"]:
        for name in ["left.csv", "right.csv", "join.json", "joined"]:
            fix = fixture(directory, "changed-" + point + "-" + name)
            process = pause(app, fix, point)
            try:
                if name == "joined":
                    fix.output.mkdir()
                    (fix.output / "keep").write_bytes(b"untouched")
                else:
                    target = fix.work / name
                    target.write_bytes(target.read_bytes() + b" ")
                result = resume(process, fix)
                assert result.returncode != 0
                assert not list(fix.work.glob(".csv-join-*"))
                if name == "joined":
                    assert {p.name for p in fix.output.iterdir()} == {"keep"}
                    assert (fix.output / "keep").read_bytes() == b"untouched"
                else:
                    assert not fix.output.exists() and "input changed" in result.stderr
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate()
            count += 1
    fix = fixture(directory, "permission-stage")
    process = pause(app, fix, "stage")
    stage = next(fix.work.glob(".csv-join-*"))
    try:
        assert os.getuid() != 0
        stage.chmod(0o500)
        result = resume(process, fix)
        assert result.returncode != 0 and "Permission denied" in result.stderr
        assert not fix.output.exists() and not stage.exists()
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate()
        if stage.exists():
            stage.chmod(0o700)
    (fix.work / "continue").unlink()
    run(app, fix)
    return count + 1


def check_paths(app: Application, directory: Path) -> int:
    for kind in ["symlink", "fifo", "directory", "output-file", "output-directory", "output-symlink", "permission"]:
        fix = fixture(directory, "paths-" + kind)
        source = fix.work / "left.csv"
        if kind == "symlink":
            source.rename(fix.work / "original")
            source.symlink_to("original")
        elif kind == "fifo":
            source.unlink()
            os.mkfifo(source)
        elif kind == "directory":
            source.unlink()
            source.mkdir()
        elif kind == "output-file":
            fix.output.write_bytes(b"keep")
        elif kind == "output-directory":
            fix.output.mkdir()
            (fix.output / "keep").write_bytes(b"keep")
        elif kind == "output-symlink":
            fix.output.symlink_to("missing")
        else:
            fix.work.chmod(0o500)
        try:
            result = app.run(fix.work, fix.settings(), timeout=10)
            assert result.returncode != 0
            assert not list(fix.work.glob(".csv-join-*"))
            if kind == "output-file":
                assert fix.output.read_bytes() == b"keep"
            if kind == "output-directory":
                assert (fix.output / "keep").read_bytes() == b"keep"
            if kind == "output-symlink":
                assert fix.output.is_symlink() and os.readlink(fix.output) == "missing"
        finally:
            fix.work.chmod(0o700)
    return 7


def check_limits(app: Application, directory: Path) -> dict:
    limited = Application(["/usr/bin/prlimit", "--as=268435456", "--", *app.command], app.engine)
    header = ["key", "value"]
    unique = [header] + [[str(i), f"item-{i}"] for i in range(10000)]
    single = [header, ["9999", "last"]]
    for side in ["left", "right"]:
        run(
            limited,
            fixture(
                directory,
                "limit-rows-" + side,
                unique if side == "left" else single,
                unique if side == "right" else single,
            ),
            timeout=120,
        )
    count = 100
    repeated = [header] + [["a", "v"] for _ in range(count)]
    repeated_right = [header] + [["a", "w"] for _ in range(1000)]
    report = run(limited, fixture(directory, "limit-product", repeated, repeated_right), timeout=120)
    assert report["matched_pairs"] == 100000 and report["output_rows"] == 100000
    reject(limited, fixture(directory, "over-product", repeated + [["a", "v"]], repeated_right), "row limit")
    huge = [header] + [["a", "v"] for _ in range(10000)]
    reject(limited, fixture(directory, "explosion", huge, huge), "row limit")
    for raw, changes, name in [
        (b"key,value\na,b\na,c\n", {"max_rows": 1}, "rows"),
        (b"key,value\na," + b"x" * 65537 + b"\n", {}, "field"),
        (b"key,value\na,b\n", {"max_input_bytes": 3}, "input"),
        (b"key,value\na," + b"," * 63 + b"\n", {}, "columns"),
    ]:
        fix = fixture(directory, "over-" + name, **changes)
        (fix.work / "left.csv").write_bytes(raw)
        reject(limited, fix)
    for cell in ["😀" * 16384, '"' * 65536]:
        run(
            limited,
            fixture(directory, "field-" + digest(cell.encode())[:8], [header, ["a", cell]], single),
            timeout=120,
        )
    columns = [f"k{i}" for i in range(64)]
    rows = [columns, [f"{i}世界" for i in range(64)], [""] * 64]
    spec = {"path": "left.csv", "keys": columns, "delimiter": ","}
    fix = fixture(directory, "arity-64", rows, rows)
    fix.config.update(
        left=spec,
        right={**spec, "path": "right.csv"},
        select=[{"side": "left", "column": name, "as": name} for name in columns],
    )
    fix.save()
    run(limited, fix)
    # Exactly 4 MiB of input; small key column avoids large unmatched-key diagnostics.
    raw = b"key,value\n"
    while len(raw) + 65539 <= 4194304 - 4:
        raw += b"a," + b"x" * 65536 + b"\n"
    remaining = 4194304 - len(raw)
    raw += b"a," + b"y" * (remaining - 3) + b"\n"
    assert len(raw) == 4194304
    fix = fixture(directory, "input-exact", right_rows=single, select=[{"side": "left", "column": "key", "as": "key"}])
    (fix.work / "left.csv").write_bytes(raw)
    run(limited, fix, timeout=120)
    extra = fixture(directory, "input-above")
    (extra.work / "left.csv").write_bytes(raw + b"\n")
    reject(limited, extra, "byte limit")
    wide = [header, ["a", "x" * 65536]]
    repeated = [header] + [["a", "v"] for _ in range(129)]
    reject(limited, fixture(directory, "output-bytes", wide, repeated), "exceeds 8 MiB")
    last = 8388608 - 3 - 127 * 65538 - 2
    left = [header, ["a", "x" * 65536], ["b", "y" * last]]
    right = [header] + [["a", "v"] for _ in range(127)] + [["b", "w"]]
    projection = [{"side": "left", "column": "value", "as": "L"}]
    exact_output = fixture(directory, "output-exact", left, right, select=projection)
    run(limited, exact_output, timeout=120)
    assert (exact_output.output / "joined.csv").stat().st_size == 8388608
    left[-1][-1] += "z"
    reject(limited, fixture(directory, "output-one-over", left, right, select=projection), "exceeds 8 MiB")
    report_limit = fixture(
        directory, "report-limit", right_rows=single, select=[{"side": "left", "column": "key", "as": "key"}]
    )
    (report_limit.work / "left.csv").write_bytes(
        b"key,value\n" + raw[len(b"key,value\n") :].replace(b"x", b"\0").replace(b"y", b"\0")
    )
    reject(limited, report_limit, "report exceeds 16 MiB")
    return {
        "memory_limit": 268435456,
        "input_rows": 10000,
        "output_rows": 100000,
        "keys": 64,
        "field_bytes": 65536,
        "input_bytes": 4194304,
        "rejected_product": 100000000,
    }


def check(app: Application, directory: Path) -> dict:
    return {
        "join_cases": check_joins(app, directory),
        "invalid_cases": check_invalid(app, directory),
        "publication_cases": check_publication(app, directory),
        "path_cases": check_paths(app, directory),
        "limits": check_limits(app, directory),
    }
