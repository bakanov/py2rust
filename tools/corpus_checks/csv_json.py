"""Independent csv-module and typed-record oracles for complete conversion projects."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import random
import selectors
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .common import Application


def csv_text(
    rows: list[list[str]], delimiter: str = ",", ending: str = "\r\n", quoting: int = csv.QUOTE_MINIMAL
) -> str:
    stream = io.StringIO(newline="")
    csv.writer(stream, delimiter=delimiter, lineterminator=ending, quoting=quoting).writerows(rows)
    return stream.getvalue()


def csv_rows(data: str, delimiter: str = ",") -> list[list[str]]:
    return list(csv.reader(io.StringIO(data, newline=""), delimiter=delimiter, strict=True))


def canonical(value: object) -> str:
    # Independent implementation of the documented shared JSON number spelling.
    if type(value) is float:
        mantissa, exponent = format(value, ".16e").split("e")
        return mantissa.rstrip("0").rstrip(".") + "e" + str(int(exponent))
    if isinstance(value, list):
        return "[" + ",".join(canonical(item) for item in value) + "]"
    if isinstance(value, dict):
        return (
            "{"
            + ",".join(json.dumps(key, ensure_ascii=False) + ":" + canonical(value[key]) for key in sorted(value))
            + "}"
        )
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def encode(value: object, kind: str) -> str:
    if value is None:
        return "\\N"
    text = value if kind == "string" else canonical(value)
    return "\\" + text if text.startswith("\\") else text


@dataclass
class Fixture:
    work: Path
    config: dict
    source: bytes

    @property
    def input(self) -> Path:
        return self.work / "input"

    @property
    def settings_path(self) -> Path:
        return self.work / "convert.json"

    @property
    def output(self) -> Path:
        return self.work / "converted"

    def save(self) -> None:
        self.settings_path.write_text(json.dumps(self.config, ensure_ascii=False))
        return  # noqa: PLR1711 - explicit return required by repository guidelines

    def settings(self, mode: str = "convert", **extra: str) -> dict[str, str]:
        return {"CONVERT_CONFIG": str(self.settings_path), "CONVERT_MODE": mode, **extra}


def fixture(
    directory: Path, name: str, direction: str, columns: list[dict], source: bytes, **changes: object
) -> Fixture:
    work = directory / name
    work.mkdir(parents=True)
    config = {
        "input": "input",
        "output": "converted",
        "direction": direction,
        "delimiter": ",",
        "columns": columns,
        "select": [column["name"] for column in columns],
        "max_rows": 10000,
        "max_field_bytes": 65536,
        "max_input_bytes": 4194304,
    }
    config.update(changes)
    fix = Fixture(work, config, source)
    fix.input.write_bytes(source)
    fix.save()
    return fix


def column(name: str, kind: str = "string", nullable: bool = False) -> dict:
    return {"name": name, "type": kind, "nullable": nullable}


def expected_data(fix: Fixture, records: list[dict]) -> bytes:
    selected = fix.config["select"]
    if fix.config["direction"] == "csv-to-json":
        return (canonical([{name: row[name] for name in selected} for row in records]) + "\n").encode()
    kinds = {row["name"]: row["type"] for row in fix.config["columns"]}
    rows = [selected, *[[encode(row[name], kinds[name]) for name in selected] for row in records]]
    return csv_text(rows, fix.config["delimiter"]).encode()


def run(
    app: Application,
    fix: Fixture,
    records: list[dict],
    rejected: list[dict] | None = None,
    accepted_rows: list[int] | None = None,
    timeout: int = 30,
) -> dict:
    rejected = rejected or []
    accepted_rows = accepted_rows if accepted_rows is not None else list(range(1, len(records) + 1))
    data = expected_data(fix, records)
    filename = "data.json" if fix.config["direction"] == "csv-to-json" else "data.csv"
    expected = {
        "direction": fix.config["direction"],
        "columns": fix.config["select"],
        "rows": len(records) + len(rejected),
        "accepted": len(records),
        "rejected": len(rejected),
        "accepted_rows": accepted_rows,
        "errors": rejected,
        "input_sha256": hashlib.sha256(fix.source).hexdigest(),
        "data_sha256": hashlib.sha256(data).hexdigest(),
        "data_file": filename,
    }
    original_config = fix.settings_path.read_bytes()
    preview = app.run(fix.work, fix.settings("preview"), timeout=timeout)
    assert preview.returncode == bool(rejected), preview.stderr
    assert json.loads(preview.stdout) == expected
    assert not fix.output.exists() and set(fix.work.iterdir()) == {fix.input, fix.settings_path}
    result = app.run(fix.work, fix.settings(), timeout=timeout)
    assert result.returncode == bool(rejected), result.stderr
    assert json.loads(result.stdout) == expected
    assert {p.name for p in fix.output.iterdir()} == {filename, "report.json"}
    assert (fix.output / filename).read_bytes() == data
    assert json.loads((fix.output / "report.json").read_bytes()) == expected
    assert fix.input.read_bytes() == fix.source and fix.settings_path.read_bytes() == original_config
    assert not list(fix.work.glob(".csv-json-*"))
    return expected


def reject(app: Application, fix: Fixture, message: str = "", **settings: str) -> None:
    original = {p.name: p.read_bytes() for p in fix.work.iterdir() if p.is_file() and not p.is_symlink()}
    result = app.run(fix.work, fix.settings(**settings), timeout=30)
    assert result.returncode != 0, result.stdout
    assert message in result.stderr, result.stderr
    assert not fix.output.exists()
    assert not list(fix.work.glob(".csv-json-*"))
    assert all((fix.work / name).read_bytes() == data for name, data in original.items())
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def check_roundtrips(app: Application, directory: Path) -> int:
    generator = random.Random(410041)
    alphabet = ["a", "z", ",", ";", "|", "\t", '"', "\r", "\n", "\\", "\0", "é", "é", "世界", "😀", " "]
    specials = [
        "",
        "\\N",
        "\\\\N",
        "\\",
        '"',
        ",;|\t",
        "\r\n",
        "\n\r",
        "embedded\0nul",
        " é 😀 ",
        "first\nsecond",
        '""""',
    ]
    count = 0
    for delimiter in [",", ";", "\t", "|"]:
        for width in [1, 3, 8]:
            columns = [column(f"c{index}") for index in range(width)]
            values = specials + ["".join(generator.choices(alphabet, k=generator.randrange(0, 90))) for _ in range(28)]
            records = [
                {item["name"]: values[(index + number) % len(values)] for number, item in enumerate(columns)}
                for index in range(len(values))
            ]
            to_csv = fixture(
                directory,
                f"round-{count}-csv",
                "json-to-csv",
                columns,
                json.dumps(records, ensure_ascii=False).encode(),
                delimiter=delimiter,
            )
            run(app, to_csv, records)
            encoded = (to_csv.output / "data.csv").read_bytes()
            assert csv_rows(encoded.decode(), delimiter)[0] == [c["name"] for c in columns]
            to_json = fixture(directory, f"round-{count}-json", "csv-to-json", columns, encoded, delimiter=delimiter)
            run(app, to_json, records)
            assert json.loads((to_json.output / "data.json").read_bytes()) == records
            count += 1
    return count


def check_dialects(app: Application, directory: Path) -> int:
    sources = [
        b"h\n",
        b"h\r",
        b"h\r\n",
        b"h",
        b'h\n""\n',
        b'h\n""',
        b'h\n"line\r\nline"\r\n',
        b'h\r\n"a""b"\r\n',
        b'h\nx"y\n',
        b"h\r\n\r\nlast",
        b"h\n\n",
        b"h\n\n\n",
        b'h\r"a\nb"\r"c\rd"\r',
        b'h\n"a"""\n',
        b'h\n"a\0b"\n',
        b"h\nx\r\ny\rz\n",
    ]
    for index, source in enumerate(sources):
        parsed = csv_rows(source.decode())
        rows = []
        errors = []
        accepted = []
        for number, row in enumerate(parsed[1:], 1):
            if len(row) == 1:
                rows.append({"h": row[0]})
                accepted.append(number)
            else:
                errors.append(
                    {"row": number, "input": row, "errors": [{"column": "", "reason": "row width differs from header"}]}
                )
        fix = fixture(directory, f"dialect-{index}", "csv-to-json", [column("h")], source)
        run(app, fix, rows, errors, accepted)
    for index, source in enumerate([b'h\n"open', b'h\n"a" tail', b'h\n"a"\t', b'h\n"a"x\n', b'h\n"a""']):
        try:
            csv_rows(source.decode())
        except csv.Error:
            pass
        else:
            raise AssertionError("oracle accepted malformed CSV")
        reject(app, fixture(directory, f"bad-dialect-{index}", "csv-to-json", [column("h")], source))
    return len(sources) + 5


def check_types(app: Application, directory: Path) -> int:
    columns = [
        column("text", nullable=True),
        column("integer", "integer"),
        column("number", "number"),
        column("flag", "boolean"),
        column("document", "json", nullable=True),
    ]
    records = [
        {"text": "", "integer": -(2**63), "number": -0.0, "flag": False, "document": {"世界": [1, None, True]}},
        {"text": None, "integer": 2**63 - 1, "number": 1.25e-7, "flag": True, "document": ['quote"', "\n"]},
        {"text": "\\N", "integer": 0, "number": 9007199254740993, "flag": True, "document": None},
        {"text": "\\", "integer": 7, "number": 5e-324, "flag": False, "document": ""},
        {"text": "😀\r\n", "integer": -9, "number": 1.7976931348623157e308, "flag": True, "document": 1.5},
    ]
    for direction in ["json-to-csv", "csv-to-json"]:
        raw = json.dumps(records, ensure_ascii=False, allow_nan=False).encode()
        if direction == "csv-to-json":
            header = [c["name"] for c in reversed(columns)]
            kinds = {c["name"]: c["type"] for c in columns}
            rows = [[encode(row[name], kinds[name]) for name in header] for row in records]
            rows[0][header.index("integer")] = "  -0009223372036854775808\t"
            rows[3][header.index("integer")] = "+0007"
            raw = csv_text([header, *rows]).encode()
        fix = fixture(
            directory, "types-" + direction, direction, columns, raw, select=["document", "text", "number", "integer"]
        )
        run(app, fix, records)
    invalid = [
        {**records[0], "text": 4, "integer": True, "number": "1", "flag": 1},
        {"missing": True},
        None,
        [],
        {**records[0], "integer": 1.0},
    ]
    errors = [
        {
            "row": 2,
            "input": invalid[0],
            "errors": [
                {"column": name, "reason": "invalid " + kind + " value"}
                for name, kind in [
                    ("flag", "boolean"),
                    ("integer", "integer"),
                    ("number", "number"),
                    ("text", "string"),
                ]
            ],
        },
        *[
            {"row": i + 3, "input": row, "errors": [{"column": "", "reason": "record fields differ from schema"}]}
            for i, row in enumerate(invalid[1:4])
        ],
        {"row": 6, "input": invalid[4], "errors": [{"column": "integer", "reason": "invalid integer value"}]},
    ]
    fix = fixture(
        directory,
        "bad-json-rows",
        "json-to-csv",
        columns,
        json.dumps([records[0], *invalid, records[1]], ensure_ascii=False).encode(),
        select=["document"],
    )
    run(app, fix, records[:2], errors, [1, 7])
    bad_cells = [
        ("", "integer"),
        ("9223372036854775808", "integer"),
        ("1_000", "integer"),
        ("１２", "integer"),
        ("1.2", "integer"),
        ("01", "number"),
        ("+1", "number"),
        ("NaN", "number"),
        ("1e309", "number"),
        ("TRUE", "flag"),
        ("1", "flag"),
        ("null", "flag"),
        ("\\N", "flag"),
        ("{bad", "document"),
    ]
    header = [c["name"] for c in columns]
    kinds = {c["name"]: c["type"] for c in columns}
    base = [encode(records[1][name], kinds[name]) for name in header]
    rows = []
    errors = []
    for number, (text, name) in enumerate(bad_cells, 1):
        row = base.copy()
        row[header.index(name)] = text
        rows.append(row)
        errors.append(
            {"row": number, "input": row, "errors": [{"column": name, "reason": "invalid " + kinds[name] + " value"}]}
        )
    fix = fixture(directory, "bad-csv-rows", "csv-to-json", columns, csv_text([header, *rows, base]).encode())
    run(app, fix, [records[1]], errors, [len(rows) + 1])
    return len(bad_cells) + len(invalid)


def check_invalid(app: Application, directory: Path) -> int:
    changes = [
        {"direction": "other"},
        {"delimiter": ""},
        {"delimiter": "::"},
        {"delimiter": '"'},
        {"delimiter": "é"},
        {"max_rows": 0},
        {"max_rows": 10001},
        {"max_rows": True},
        {"max_field_bytes": 0},
        {"max_field_bytes": 65537},
        {"max_input_bytes": 0},
        {"max_input_bytes": 4194305},
        {"max_input_bytes": 1.5},
        {"columns": []},
        {"columns": [column("")]},
        {"columns": [column("x")] * 2},
        {"columns": [column("x", "date")]},
        {"columns": [{"name": "h", "type": "string", "nullable": "false"}]},
        {"columns": [column("x" * 257)]},
        {"columns": [column("nul\0name")]},
        {"columns": [column(str(i)) for i in range(65)]},
        {"columns": [{**column("h"), "extra": 1}]},
        {"select": []},
        {"select": ["h", "h"]},
        {"select": ["other"]},
        {"input": "missing"},
        {"extra": True},
        {"output": "missing/child"},
        {"output": "input"},
        {"output": "convert.json"},
    ]
    for index, change in enumerate(changes):
        fix = fixture(directory, f"invalid-config-{index}", "csv-to-json", [column("h")], b"h\nx\n")
        fix.config.update(change)
        fix.save()
        reject(app, fix)
    for index, source in enumerate([b"", b"other\nx\n", b"\nh\n", b"h,h\na,b\n", b"h\n\xff", b"\xef\xbb\xbfh\nx"]):
        reject(app, fixture(directory, f"invalid-input-{index}", "csv-to-json", [column("h")], source))
    for index, source in enumerate([b"{}", b"[NaN]", b"[9223372036854775808]", b'[{"h":"\\ud800"}]', b"["]):
        reject(app, fixture(directory, f"invalid-json-{index}", "json-to-csv", [column("h")], source))
    for index, data in enumerate([b"{}", b"[]", b"{invalid", b"\xff", b"{}" + b" " * 65536]):
        fix = fixture(directory, f"invalid-document-{index}", "csv-to-json", [column("h")], b"h\nx\n")
        fix.settings_path.write_bytes(data)
        reject(app, fix)
    return len(changes) + 16


def check_paths(app: Application, directory: Path) -> int:
    for kind in ["input-symlink", "input-fifo", "output-file", "output-directory", "output-symlink", "permission"]:
        fix = fixture(directory, kind, "csv-to-json", [column("h")], b"h\nx\n")
        if kind == "input-symlink":
            fix.input.rename(fix.work / "original")
            fix.input.symlink_to("original")
        elif kind == "input-fifo":
            fix.input.unlink()
            os.mkfifo(fix.input)
        elif kind == "output-file":
            fix.output.write_bytes(b"existing")
        elif kind == "output-directory":
            fix.output.mkdir()
            (fix.output / "keep").write_bytes(b"existing")
        elif kind == "output-symlink":
            fix.output.symlink_to("missing")
        else:
            assert os.getuid() != 0
            fix.work.chmod(0o500)
        try:
            result = app.run(fix.work, fix.settings(), timeout=10)
            assert result.returncode != 0
            assert not list(fix.work.glob(".csv-json-*"))
            if kind == "output-file":
                assert fix.output.read_bytes() == b"existing"
            if kind == "output-directory":
                assert (fix.output / "keep").read_bytes() == b"existing"
        finally:
            fix.work.chmod(0o700)
    return 6


def check_limits(app: Application, directory: Path) -> dict:
    limited = Application(["/usr/bin/prlimit", "--as=134217728", "--", *app.command], app.engine)
    for direction in ["json-to-csv", "csv-to-json"]:
        records = [{"h": "😀" * 16384}, {"h": '"' * 65536}, {"h": ""}]
        raw = (
            json.dumps(records, ensure_ascii=False).encode()
            if direction == "json-to-csv"
            else csv_text([["h"], *[[r["h"]] for r in records]]).encode()
        )
        fix = fixture(directory, "field-limit-" + direction, direction, [column("h")], raw, max_rows=3)
        run(limited, fix, records, timeout=90)
    rows = [{"h": f"row {i} 世界," + '"' * 4 + "\r\n"} for i in range(10000)]
    raw = csv_text([["h"], *[[r["h"]] for r in rows]]).encode()
    fix = fixture(directory, "row-limit", "csv-to-json", [column("h")], raw)
    run(limited, fix, rows, timeout=120)
    for name, raw, changes in [
        ("rows-over", b"h\na\nb\n", {"max_rows": 1}),
        ("field-over", b"h\n" + b"x" * 65537 + b"\n", {}),
        ("columns-over", b"h\n" + b"," * 64 + b"\n", {}),
        ("bytes-over", b"h\nx\n", {"max_input_bytes": 3}),
    ]:
        reject(limited, fixture(directory, name, "csv-to-json", [column("h")], raw, **changes))
    columns = [column(f"h{i}") for i in range(64)]
    record = {c["name"]: str(i) for i, c in enumerate(columns)}
    fix = fixture(directory, "column-limit", "json-to-csv", columns, json.dumps([record]).encode())
    run(limited, fix, [record])
    count, remainder = divmod(4194304 - 2, 65537)
    records = [{"h": "x" * 65536} for _ in range(count)] + [{"h": "y" * (remainder - 1)}]
    source = ("h\n" + "".join(row["h"] + "\n" for row in records)).encode()
    assert len(source) == 4194304
    exact = fixture(directory, "byte-limit", "csv-to-json", [column("h")], source)
    run(limited, exact, records, timeout=120)
    reject(limited, fixture(directory, "above-byte-limit", "csv-to-json", [column("h")], source + b"\n"), "byte limit")
    long_columns = [column(f"{i:02d}" + "h" * 254) for i in range(64)]
    source = csv_text([[c["name"] for c in long_columns], *[["x"] * 64 for _ in range(600)]]).encode()
    reject(
        limited, fixture(directory, "output-limit", "csv-to-json", long_columns, source), "converted data exceeds 8 MiB"
    )
    invalid_columns = [{**item, "type": "integer"} for item in long_columns]
    source = csv_text([[c["name"] for c in invalid_columns], *[["bad"] * 64 for _ in range(1000)]]).encode()
    reject(
        limited, fixture(directory, "report-limit", "csv-to-json", invalid_columns, source), "rejection report exceeds"
    )
    return {"memory_limit": 134217728, "rows": 10000, "columns": 64, "field_bytes": 65536, "input_bytes": 4194304}


def pause(app: Application, fix: Fixture, point: str) -> subprocess.Popen:
    process = subprocess.Popen(
        app.command,
        cwd=fix.work,
        env=app.environment(fix.settings(CONVERT_PAUSE=point, CONVERT_CONTINUE=str(fix.work / "continue"))),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            assert selector.select(15), "converter did not pause"
        assert process.stdout.readline().rstrip() == "PAUSED " + point
        return process
    except BaseException:
        process.kill()
        process.communicate()
        raise


def resume(process: subprocess.Popen, fix: Fixture) -> subprocess.CompletedProcess:
    (fix.work / "continue").touch()
    output, error = process.communicate(timeout=20)
    return subprocess.CompletedProcess(process.args, process.returncode, output, error)


def bundle(fix: Fixture) -> dict:
    report = json.loads((fix.output / "report.json").read_bytes())
    assert {p.name for p in fix.output.iterdir()} == {"report.json", report["data_file"]}
    assert report["data_sha256"] == hashlib.sha256((fix.output / report["data_file"]).read_bytes()).hexdigest()
    return report


def check_publication(app: Application, directory: Path) -> int:
    points = ["validated", "stage", "data", "report", "ready", "published"]
    for index, point in enumerate(points):
        fix = fixture(directory, f"failure-{index}", "csv-to-json", [column("h")], b"h\nx\n")
        result = app.run(fix.work, fix.settings(CONVERT_FAIL=point))
        assert result.returncode != 0 and "injected failure: " + point in result.stderr, result.stderr
        assert not list(fix.work.glob(".csv-json-*"))
        if point == "published":
            assert bundle(fix)["accepted"] == 1
        else:
            assert not fix.output.exists()
            run(app, fix, [{"h": "x"}])
    for point in ["stage", "data", "ready", "published"]:
        fix = fixture(directory, "killed-" + point, "csv-to-json", [column("h")], b"h\nx\n")
        process = pause(app, fix, point)
        process.kill()
        process.communicate(timeout=10)
        assert process.returncode == -9
        if point == "published":
            assert bundle(fix)["accepted"] == 1
        else:
            assert not fix.output.exists()
            stages = list(fix.work.glob(".csv-json-*"))
            assert len(stages) == 1
            # Killed writers leave private staging directories. Inspect/remove
            # them as the test operator; the application does not claim recovery.
            shutil.rmtree(stages[0])
            run(app, fix, [{"h": "x"}])
    for changed in ["input", "configuration", "output"]:
        fix = fixture(directory, "changed-" + changed, "csv-to-json", [column("h")], b"h\nx\n")
        process = pause(app, fix, "ready" if changed == "output" else "validated")
        try:
            if changed == "input":
                fix.input.write_bytes(b"h\ny\n")
            elif changed == "configuration":
                fix.settings_path.write_bytes(fix.settings_path.read_bytes() + b" ")
            else:
                fix.output.mkdir()
                (fix.output / "keep").write_bytes(b"untouched")
            result = resume(process, fix)
            assert result.returncode != 0, result.stdout
            assert not list(fix.work.glob(".csv-json-*"))
            if changed == "output":
                assert {p.name for p in fix.output.iterdir()} == {"keep"}
                assert (fix.output / "keep").read_bytes() == b"untouched"
            else:
                assert not fix.output.exists() and "input changed" in result.stderr
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()
    fix = fixture(directory, "staging-permission", "csv-to-json", [column("h")], b"h\nx\n")
    process = pause(app, fix, "stage")
    staging = next(fix.work.glob(".csv-json-*"))
    try:
        staging.chmod(0o500)
        result = resume(process, fix)
        assert result.returncode != 0 and "Permission denied" in result.stderr, result.stderr
        assert not fix.output.exists() and not staging.exists()
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate()
        if staging.exists():
            staging.chmod(0o700)
    (fix.work / "continue").unlink()
    run(app, fix, [{"h": "x"}])
    return len(points) + 8


def check(app: Application, directory: Path) -> dict:
    roundtrips = check_roundtrips(app, directory)
    dialects = check_dialects(app, directory)
    invalid_rows = check_types(app, directory)
    invalid_documents = check_invalid(app, directory)
    paths = check_paths(app, directory)
    publication = check_publication(app, directory)
    limits = check_limits(app, directory)
    return {
        "roundtrips": roundtrips,
        "dialect_cases": dialects,
        "invalid_rows": invalid_rows,
        "invalid_documents": invalid_documents,
        "path_and_permission_cases": paths,
        "publication_boundaries": publication,
        "limits": limits,
    }
