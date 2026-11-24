"""Independent minute-grid calendar oracle and exact grammar/source diagnostic fixtures."""

import copy
import csv
import datetime as dt
import hashlib
import io
import json
import random
from dataclasses import dataclass
from pathlib import Path

from .common import Application

BOUNDS = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 7)]
NAMES = ["minute", "hour", "day_of_month", "month", "day_of_week"]


@dataclass
class Spec:
    expression: str
    values: list[set[int]]
    starred: list[bool]
    error: tuple[str, int, int] | None = None


@dataclass
class Fixture:
    directory: Path
    config: dict
    specs: list[Spec]
    filename: str = "job.json"

    @property
    def output(self) -> Path:
        return self.directory / self.config["output"]


def stamp(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(dt.timezone.utc)


def iso(value: dt.datetime) -> str:
    return value.isoformat(timespec="microseconds")


def spec(
    expression: str,
    minute: set[int] | None = None,
    hour: set[int] | None = None,
    date: set[int] | None = None,
    month: set[int] | None = None,
    weekday: set[int] | None = None,
) -> Spec:
    values = [minute, hour, date, month, weekday]
    normalized = [
        set(range(low, high + 1)) if value is None else value for value, (low, high) in zip(values, BOUNDS, strict=True)
    ]
    normalized[4] = {day % 7 for day in normalized[4]}
    return Spec(expression, normalized, [token.startswith("*") for token in expression.split()])


def examples() -> list[Spec]:
    return [
        spec("* * * * *"),
        spec("*/15 9-17/2 * * 1-5", {0, 15, 30, 45}, {9, 11, 13, 15, 17}, weekday={1, 2, 3, 4, 5}),
        spec("0 0 29 2 *", {0}, {0}, {29}, {2}),
        spec("0 0 31 2 *", {0}, {0}, {31}, {2}),
        spec("0 12 1 * 1", {0}, {12}, {1}, weekday={1}),
        spec("0 12 */2 * 1", {0}, {12}, set(range(1, 32, 2)), weekday={1}),
        spec("0 12 1-31 * 1", {0}, {12}, set(range(1, 32)), weekday={1}),
        spec("0 0 * * 7", {0}, {0}, weekday={0}),
        spec("00,00,30 0 * * 0,7", {0, 30}, {0}, weekday={0}),
        spec("5-59/17 23 * * 5-7", {5, 22, 39, 56}, {23}, weekday={5, 6, 0}),
        spec("  0\t0  *  *\t*  ", {0}, {0}),
        spec("0 0 1 1 *", {0}, {0}, {1}, {1}),
        spec("59 23 31 12 *", {59}, {23}, {31}, {12}),
        spec("0 0 1-31/4 */3 */2", {0}, {0}, set(range(1, 32, 4)), {1, 4, 7, 10}, {0, 2, 4, 6}),
        spec("*/60 */24 */31 */12 */8", {0}, {0}, {1}, {1}, {0}),
        spec("1-1/1 2-2 3-3 4-4 5-5", {1}, {2}, {3}, {4}, {5}),
    ]


def invalid_expressions() -> list[Spec]:
    cases = [
        ("", "expected five fields; found 0", 1, 1),
        ("* * * *", "expected five fields; found 4", 5, 8),
        ("* * * * * extra", "expected five fields; found 6", 6, 11),
        ("60 * * * *", "minute: value must be in 0..59", 1, 1),
        ("0 24 * * *", "hour: value must be in 0..23", 2, 3),
        ("0 0 0 * *", "day_of_month: value must be in 1..31", 3, 5),
        ("0 0 * 13 *", "month: value must be in 1..12", 4, 7),
        ("0 0 * * 8", "day_of_week: value must be in 0..7", 5, 9),
        ("*/0 * * * *", "minute: value must be in 1..60", 1, 1),
        ("*/61 * * * *", "minute: value must be in 1..60", 1, 1),
        ("1/2 * * * *", "minute: steps require a wildcard or range", 1, 1),
        ("5-3 * * * *", "minute: range is descending", 1, 1),
        ("1-2-3 * * * *", "minute: expected a value or ascending range", 1, 1),
        ("*/1/2 * * * *", "minute: expected at most one step separator", 1, 1),
        ("1,,3 * * * *", "minute: expected one or two ASCII digits", 1, 3),
        ("1, * * * *", "minute: expected one or two ASCII digits", 1, 3),
        ("*,1 * * * *", "wildcards cannot be combined with a list", 1, 1),
        ("1,* * * * *", "wildcards cannot be combined with a list", 1, 1),
        ("000 * * * *", "minute: expected one or two ASCII digits", 1, 1),
        ("+1 * * * *", "minute: expected one or two ASCII digits", 1, 1),
        ("-1 * * * *", "minute: expected one or two ASCII digits", 1, 1),
        ("１ * * * *", "minute: expected one or two ASCII digits", 1, 1),
        ("0 0 * * MON", "day_of_week: expected one or two ASCII digits", 5, 9),
        ("0 0 L * *", "day_of_month: expected one or two ASCII digits", 3, 5),
        ("0 0 * * 1#2", "day_of_week: expected one or two ASCII digits", 5, 9),
        ("0 0 ? * *", "day_of_month: expected one or two ASCII digits", 3, 5),
        ("0\n 0 * * *", "minute: expected one or two ASCII digits", 1, 1),
        ("0\0 0 * * *", "minute: expected one or two ASCII digits", 1, 1),
        ("*/ * * * *", "minute: expected one or two ASCII digits", 1, 1),
        ("0 0 1,32 * *", "day_of_month: value must be in 1..31", 3, 7),
    ]
    return [Spec(text, [], [], (error, field, column)) for text, error, field, column in cases]


def fixture(
    directory: Path,
    specs: list[Spec] | None = None,
    start: str = "2024-02-28T23:59:59Z",
    days: int = 5,
    limit: int = 100,
) -> Fixture:
    directory.mkdir(parents=True)
    specs = examples() if specs is None else specs
    value = {
        "version": 1,
        "start": start,
        "days": days,
        "limit": limit,
        "output": "output",
        "schedules": [{"id": "schedule" + str(i), "expression": item.expression} for i, item in enumerate(specs)],
    }
    (directory / "job.json").write_text(json.dumps(value))
    return Fixture(directory, value, specs)


def expected_runs(item: Spec, start: dt.datetime, days: int, limit: int) -> tuple[list[dict], bool, str]:
    """Scan real datetime minutes independently of the application's day-selection algorithm."""
    end = start + dt.timedelta(days=days)
    candidate = start.replace(second=0, microsecond=0)
    if candidate < start:
        candidate += dt.timedelta(minutes=1)
    found = []
    while candidate < end:
        minute, hour, date, month, weekday = (
            candidate.minute,
            candidate.hour,
            candidate.day,
            candidate.month,
            candidate.isoweekday() % 7,
        )
        date_ok, weekday_ok = date in item.values[2], weekday in item.values[4]
        allowed_day = (date_ok and weekday_ok) if (item.starred[2] or item.starred[4]) else (date_ok or weekday_ok)
        if minute in item.values[0] and hour in item.values[1] and month in item.values[3] and allowed_day:
            if len(found) == limit:
                return found, True, iso(candidate)
            found.append({"utc": iso(candidate), "weekday": weekday})
        if end - candidate <= dt.timedelta(minutes=1):
            break
        candidate += dt.timedelta(minutes=1)
    return found, False, ""


def verify(case: Fixture, explicit: dict[int, list[str]] | None = None) -> tuple[dict, dict[str, bytes]]:
    files = {path.name: path.read_bytes() for path in case.output.iterdir()}
    assert set(files) == {"report.json", "report.txt", "schedule.csv", "cron-job.json", "manifest.json"}
    report = json.loads(files["report.json"])
    manifest = json.loads(files["manifest.json"])
    assert manifest["version"] == report["version"] == 1
    assert set(manifest["files"]) == set(files) - {"manifest.json"}
    for name, value in manifest["files"].items():
        assert value == {"bytes": len(files[name]), "sha256": hashlib.sha256(files[name]).hexdigest()}
    start = stamp(case.config["start"])
    end = start + dt.timedelta(days=case.config["days"])
    assert report["start"] == iso(start) and report["end"] == iso(end)
    assert report["days"] == case.config["days"] and report["limit"] == case.config["limit"]
    assert len(report["schedules"]) == len(case.specs)
    csv_rows = []
    for index, (row, item) in enumerate(zip(report["schedules"], case.specs, strict=True)):
        assert row["id"] == case.config["schedules"][index]["id"] and row["expression"] == item.expression
        explanation = row["explanation"]
        if item.error is not None:
            assert (explanation["error"], explanation["error_field"], explanation["error_column"]) == item.error
            assert row["status"] == "invalid" and row["runs"] == [] and row["inspected_days"] == 0
            assert explanation["fields"] == [] and explanation["day_rule"] == ""
            assert not row["more"] and row["next_omitted"] == ""
            assert item.error[0].encode() in files["report.txt"]
            continue
        assert explanation["error"] == "" and explanation["error_field"] == explanation["error_column"] == 0
        assert explanation["fields"] == [
            {"name": name, "values": sorted(values), "starred": starred}
            for name, values, starred in zip(NAMES, item.values, item.starred, strict=True)
        ]
        assert explanation["day_rule"] == ("and" if item.starred[2] or item.starred[4] else "or")
        if explicit is None:
            runs, more, omitted = expected_runs(item, start, case.config["days"], case.config["limit"])
        else:
            all_runs = explicit[index]
            runs = [
                {"utc": iso(stamp(value)), "weekday": stamp(value).isoweekday() % 7}
                for value in all_runs[: case.config["limit"]]
            ]
            more = len(all_runs) > case.config["limit"]
            omitted = iso(stamp(all_runs[case.config["limit"]])) if more else ""
        assert row["status"] == "valid" and row["runs"] == runs, (item.expression, row["runs"], runs)
        assert row["more"] == more and row["next_omitted"] == omitted
        last_day = stamp(omitted).date() if more else (end - dt.timedelta(microseconds=1)).date()
        assert row["inspected_days"] == (last_day - start.date()).days + 1
        for occurrence in runs:
            csv_rows.append({"id": row["id"], "utc": occurrence["utc"], "weekday": str(occurrence["weekday"])})
            assert occurrence["utc"].encode() in files["report.txt"]
    assert report["errors"] == sum(item.error is not None for item in case.specs)
    assert list(csv.DictReader(io.StringIO(files["schedule.csv"].decode()))) == csv_rows
    replay = json.loads(files["cron-job.json"])
    assert replay == dict(case.config, start=iso(start), output="rebuilt")
    return report, files


def run(app: Application, case: Fixture, explicit: dict[int, list[str]] | None = None) -> tuple[dict, dict[str, bytes]]:
    config = case.directory / case.filename
    before = config.read_bytes()
    result = app.run(case.directory, {"CRON_CONFIG": str(config)}, timeout=120)
    assert result.returncode == (1 if any(item.error for item in case.specs) else 0) and not result.stderr, result
    report, files = verify(case, explicit)
    assert json.loads(result.stdout) == report and config.read_bytes() == before
    assert not list(case.directory.glob(".cron-*"))
    return report, files


def generated() -> list[Spec]:
    rng = random.Random(82082)
    result = []
    for _ in range(80):
        tokens, values = [], []
        for low, high in BOUNDS:
            kind = rng.randrange(5)
            first, last = sorted([rng.randint(low, high), rng.randint(low, high)])
            step = rng.randint(1, high - low + 1)
            if kind == 0:
                token, selected = "*", set(range(low, high + 1))
            elif kind == 1:
                token, selected = str(first), {first}
            elif kind == 2:
                token, selected = f"{first},{last},{first}", {first, last}
            elif kind == 3:
                token, selected = f"{first}-{last}/{step}", set(range(first, last + 1, step))
            else:
                token, selected = f"*/{step}", set(range(low, high + 1, step))
            tokens.append(token)
            values.append(selected)
        values[4] = {day % 7 for day in values[4]}
        result.append(Spec(" ".join(tokens), values, [token.startswith("*") for token in tokens]))
    return result


def invalid_jobs(app: Application, directory: Path) -> int:
    case = fixture(directory, [spec("* * * * *")])
    base = case.config
    invalid = [
        dict(base, **change)
        for change in [
            {"version": True},
            {"version": 2},
            {"extra": 1},
            {"days": 0},
            {"days": 3661},
            {"days": True},
            {"limit": 0},
            {"limit": 1001},
            {"limit": 1.5},
            {"start": "2024-02-30T00:00:00Z"},
            {"start": "2024-01-01"},
            {"start": "2024-01-01T00:00:00"},
            {"start": "2024-01-01T00:00:00+24:00"},
            {"start": "9999-12-31T00:00:00Z"},
            {"schedules": []},
            {"schedules": base["schedules"] * 17},
            {"schedules": base["schedules"] * 2},
            {"output": ""},
            {"output": True},
            {"output": "missing/output"},
            {"output": "job.json"},
            {"output": "folder"},
            {"output": "link"},
            {"output": "dangling"},
        ]
    ]
    for key in base:
        changed = copy.deepcopy(base)
        del changed[key]
        invalid.append(changed)
    for change in [
        {"id": ""},
        {"id": "1a"},
        {"id": "x" * 33},
        {"id": "é"},
        {"expression": "x" * 257},
        {"expression": "😀" * 65},
        {"expression": True},
        {"extra": 1},
    ]:
        invalid.append(dict(base, schedules=[dict(base["schedules"][0], **change)]))
    (directory / "folder").mkdir()
    (directory / "folder/keep").write_text("unchanged")
    (directory / "link").symlink_to(directory / "folder")
    (directory / "dangling").symlink_to(directory / "absent")
    config = directory / "job.json"
    for value in invalid:
        config.write_text(json.dumps(value))
        before = {
            str(path.relative_to(directory)): (path.lstat().st_mode, path.lstat().st_mtime_ns)
            for path in directory.rglob("*")
        }
        result = app.run(directory, {"CRON_CONFIG": str(config)})
        assert result.returncode == 2 and not result.stdout and result.stderr, result
        after = {
            str(path.relative_to(directory)): (path.lstat().st_mode, path.lstat().st_mtime_ns)
            for path in directory.rglob("*")
        }
        assert before == after and (directory / "folder/keep").read_text() == "unchanged"
    for data in [b"\xff", b"{", b" " * 65537]:
        config.write_bytes(data)
        result = app.run(directory, {"CRON_CONFIG": str(config)})
        assert result.returncode == 2 and not result.stdout and config.read_bytes() == data
        assert not case.output.exists() and not list(directory.glob(".cron-*"))
    config.write_text(json.dumps(base))
    (directory / "config-link").symlink_to(config)
    result = app.run(directory, {"CRON_CONFIG": str(directory / "config-link")})
    assert result.returncode == 2 and not case.output.exists()
    return len(invalid) + 4


def check(app: Application, directory: Path) -> dict:
    bundles = []
    case = fixture(directory / "basic")
    report, files = run(app, case)
    assert report["schedules"][2]["runs"] == [{"utc": "2024-02-29T00:00:00.000000+00:00", "weekday": 4}]
    assert report["schedules"][3]["runs"] == []
    bundles.append(hashlib.sha256(b"".join(files[name] for name in sorted(files))).hexdigest())
    replay = Fixture(case.output, json.loads(files["cron-job.json"]), case.specs, "cron-job.json")
    replayed, rebuilt = run(app, replay)
    assert replayed == report and rebuilt == files
    invalid = invalid_expressions()
    for start in range(0, len(invalid), 15):
        mixed = [spec("0 0 * * *", {0}, {0}), *invalid[start : start + 15]]
        _report, files = run(app, fixture(directory / f"invalid-expression-{start}", mixed))
        bundles.append(hashlib.sha256(b"".join(files[name] for name in sorted(files))).hexdigest())
    randomized = generated()
    for start in range(0, len(randomized), 16):
        run(
            app,
            fixture(directory / f"generated-{start}", randomized[start : start + 16], "2025-12-30T00:00:00Z", 5, 50),
        )
    dates = [
        ("2000-02-28T00:00:00Z", 2),
        ("1900-02-28T00:00:00Z", 2),
        ("2100-02-28T00:00:00Z", 2),
        ("2024-12-31T23:59:59.999999Z", 2),
        ("2024-01-01T05:00:00+05:00", 2),
        ("2024-01-01T00:00:00.000001Z", 1),
        ("2024-01-01T00:00:00-03:30", 1),
        ("0001-01-01T00:00:00Z", 1),
        ("9999-12-30T23:59:59Z", 1),
    ]
    for index, (start, days) in enumerate(dates):
        run(app, fixture(directory / f"date-{index}", examples()[:10], start, days, 100))
    for limit in [1, 2, 3]:
        result, _files = run(
            app,
            fixture(
                directory / f"exact-limit-{limit}", [spec("0 0 * * *", {0}, {0})], "2024-01-01T00:00:00Z", 2, limit
            ),
        )
        assert result["schedules"][0]["more"] == (limit == 1)
    long_specs = [spec("0 0 29 2 *", {0}, {0}, {29}, {2}), spec("0 0 31 2 *", {0}, {0}, {31}, {2})]
    run(
        app,
        fixture(directory / "century", long_specs, "2096-03-01T00:00:00Z", 3660, 10),
        {0: ["2104-02-29T00:00:00Z"], 1: []},
    )
    capacity_app = Application(["/usr/bin/prlimit", "--as=268435456", "--", *app.command], app.engine)
    maximum = fixture(directory / "capacity", [spec("* * * * *".ljust(256))] * 16, "2024-01-01T00:00:00Z", 3660, 1000)
    for index, entry in enumerate(maximum.config["schedules"]):
        entry["id"] = "S" + str(index).zfill(31)
    source = json.dumps(maximum.config).encode()
    (maximum.directory / "job.json").write_bytes(source + b" " * (65536 - len(source)))
    result, _files = run(capacity_app, maximum)
    assert sum(len(row["runs"]) for row in result["schedules"]) == 16000
    no_write = invalid_jobs(app, directory / "invalid-jobs")
    return {
        "explicit_valid_expressions": 16,
        "generated_expression_oracles": 80,
        "exact_expression_diagnostics": len(invalid),
        "calendar_boundaries": len(dates),
        "inclusive_start_exclusive_end": True,
        "cron_day_rule_and_sunday_alias": True,
        "actual_extra_match_required_for_truncation": True,
        "century_and_impossible_date_search": True,
        "maximum_days": 3660,
        "maximum_exported_runs": 16000,
        "maximum_job_bytes": 65536,
        "maximum_expression_bytes": 256,
        "maximum_identifier_characters": 32,
        "memory_limit": 268435456,
        "invalid_jobs_without_writes": no_write,
        "manifest_and_csv_verified": True,
        "byte_identical_export_replay": True,
        "bundle_sha256": bundles,
    }
