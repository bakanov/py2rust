"""Hand-labeled logs, independent delimiter parsing and count/ranking oracles for application 071."""

# ruff: noqa: PLR1711 - explicit repository returns

from __future__ import annotations

import datetime as dt
import hashlib
import itertools
import json
import random
import selectors
import string
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from .common import Application
from .csv_json import canonical

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
TOKEN = set(string.ascii_letters + string.digits + "-!#$%&'*+.^_`|~")
MAXIMUM = 9223372036854775807


def line(
    timestamp: str = "12/Oct/2026:10:00:00 +0000",
    host: str = "host",
    ident: str = "-",
    user: str = "-",
    method: str = "GET",
    target: str = "/notes",
    protocol: str = "HTTP/1.1",
    status: str = "200",
    size: str = "12",
) -> bytes:
    return f'{host} {ident} {user} [{timestamp}] "{method} {target} {protocol}" {status} {size}'.encode()


def sample() -> dict[str, bytes]:
    return {
        "front": b'127.0.0.1 - ada [12/Oct/2026:15:00:00 +0500] "GET /notes?q=rust HTTP/1.1" 200 120\r\n'
        b'127.0.0.1 - ada [12/Oct/2026:10:30:00 +0000] "GET /notes?q=python HTTP/1.1" 304 -\n'
        b'host - - [12/Oct/2026:11:00:00 +0000] "GET /outside HTTP/1.0" 200 100\n'
        b"malformed sample\n",
        "api": (
            '::1 - bob [12/Oct/2026:10:45:00 +0000] "POST /api/items HTTP/2.0" 503 42\n'
            '::1 - - [12/Oct/2026:10:59:59 +0000] "GET /世界 HTTP/1.1" 404 8'
        ).encode(),
    }


def instant(value: str | None) -> str | None:
    if value is None:
        return None
    return (
        dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        .astimezone(dt.timezone.utc)
        .isoformat(timespec="microseconds")
    )


def framed(raw: bytes) -> list[bytes]:
    parts = raw.split(b"\n")
    result = [part.removesuffix(b"\r") for part in parts[:-1]]
    if parts[-1]:
        result.append(parts[-1])
    return result


def digits(value: str, width: int = 0) -> bool:
    return bool(value) and (not width or len(value) == width) and all("0" <= char <= "9" for char in value)


def parse_line(raw: bytes) -> tuple[dict | None, str]:
    try:
        text = raw.decode()
    except UnicodeError:
        return None, "utf8"
    if any(number < 32 or number == 127 for number in raw):
        return None, "control"
    fields = text.split(" ", 3)
    if len(fields) != 4 or any(not value or '"' in value for value in fields[:3]) or not fields[3].startswith("["):
        return None, "format"
    timestamp, separator, following = fields[3][1:].partition('] "')
    if not separator:
        return None, "format"
    request, separator, suffix = following.partition('" ')
    parts = request.split(" ")
    tail = suffix.split(" ")
    if not separator or len(parts) != 3 or len(tail) != 2:
        return None, "format"
    method, target, protocol = parts
    status, size = tail
    if not method or not set(method) <= TOKEN or not target or '"' in target:
        return None, "format"
    if (
        len(protocol) != 8
        or protocol[:5] != "HTTP/"
        or protocol[6] != "."
        or not digits(protocol[5])
        or not digits(protocol[7])
    ):
        return None, "format"
    if not digits(status, 3) or not (size == "-" or digits(size)):
        return None, "format"
    if (
        len(timestamp) != 26
        or [timestamp[n] for n in [2, 6, 11, 14, 17, 20]] != ["/", "/", ":", ":", ":", " "]
        or timestamp[21] not in "+-"
    ):
        return None, "format"
    if not all(
        digits(timestamp[left:right], right - left)
        for left, right in [(0, 2), (7, 11), (12, 14), (15, 17), (18, 20), (22, 26)]
    ):
        return None, "format"
    if not all(char in string.ascii_letters for char in timestamp[3:6]):
        return None, "format"
    try:
        month = MONTHS.index(timestamp[3:6]) + 1
        hours, minutes = int(timestamp[22:24]), int(timestamp[24:26])
        if hours > 23 or minutes > 59:
            return None, "timestamp"
        offset = dt.timedelta(minutes=(60 * hours + minutes) * (1 if timestamp[21] == "+" else -1))
        value = dt.datetime(
            int(timestamp[7:11]),
            month,
            int(timestamp[:2]),
            int(timestamp[12:14]),
            int(timestamp[15:17]),
            int(timestamp[18:20]),
            tzinfo=dt.timezone(offset),
        )
        normalized = value.astimezone(dt.timezone.utc).isoformat(timespec="microseconds")
    except (ValueError, OverflowError):
        return None, "timestamp"
    code = int(status)
    if not 100 <= code <= 599:
        return None, "status"
    if len(size) > 4096 or (size != "-" and int(size) > MAXIMUM):
        return None, "bytes"
    return {
        "host": fields[0],
        "ident": fields[1],
        "user": fields[2],
        "timestamp": normalized,
        "method": method,
        "target": target,
        "path": target.partition("?")[0],
        "protocol": protocol,
        "status": code,
        "bytes": 0 if size == "-" else int(size),
    }, ""


def reference(inputs: dict[str, bytes], start: str | None, end: str | None, top: int) -> tuple[dict, list, list]:
    beginning, ending = instant(start), instant(end)
    records, invalid = [], []
    for name, raw in inputs.items():
        for number, data in enumerate(framed(raw), 1):
            record, reason = parse_line(data)
            if record is None:
                invalid.append({"source": name, "line": number, "reason": reason, "raw_hex": data.hex()})
            else:
                record.update(
                    source=name,
                    line=number,
                    selected=(beginning is None or record["timestamp"] >= beginning)
                    and (ending is None or record["timestamp"] < ending),
                )
                records.append(record)
    selected = [row for row in records if row["selected"]]
    statuses = Counter(row["status"] for row in selected)
    methods = Counter(row["method"] for row in selected)
    hours = Counter(row["timestamp"][:13] + ":00:00.000000+00:00" for row in selected)
    paths = defaultdict(list)
    for row in selected:
        paths[row["path"]].append(row)
    ranked = sorted(paths, key=lambda name: (-len(paths[name]), name))[:top]
    summary = {
        "requests": len(selected),
        "bytes": sum(row["bytes"] for row in selected),
        "client_errors": sum(400 <= row["status"] < 500 for row in selected),
        "server_errors": sum(row["status"] >= 500 for row in selected),
        "unique_hosts": len({row["host"] for row in selected}),
        "first": min((row["timestamp"] for row in selected), default=None),
        "last": max((row["timestamp"] for row in selected), default=None),
        "statuses": [{"status": status, "requests": statuses[status]} for status in sorted(statuses)],
        "methods": [{"method": method, "requests": methods[method]} for method in sorted(methods)],
        "hours": [{"hour": hour, "requests": hours[hour]} for hour in sorted(hours)],
        "path_count": len(paths),
        "top_paths": [
            {
                "path": name,
                "requests": len(paths[name]),
                "bytes": sum(row["bytes"] for row in paths[name]),
                "errors": sum(row["status"] >= 400 for row in paths[name]),
            }
            for name in ranked
        ],
    }
    report = {
        "version": 1,
        "window": {"start": beginning, "end": ending},
        "top": top,
        "input_sha256": {name: hashlib.sha256(raw).hexdigest() for name, raw in inputs.items()},
        "counts": {
            "lines": len(records) + len(invalid),
            "valid": len(records),
            "malformed": len(invalid),
            "selected": len(selected),
            "filtered": len(records) - len(selected),
        },
        "summary": summary,
    }
    return report, records, invalid


@dataclass
class Fixture:
    work: Path
    config: dict

    @property
    def path(self) -> Path:
        return self.work / "access-job.json"

    @property
    def manifest(self) -> Path:
        return self.work / self.config["sources"]

    @property
    def output(self) -> Path:
        return self.work / self.config["output"]

    def save(self) -> None:
        self.path.write_text(json.dumps(self.config, ensure_ascii=False))
        return

    def settings(self, mode: str = "write", **extra: str) -> dict:
        return {
            "ACCESS_CONFIG": str(self.path),
            "ACCESS_MODE": mode,
            "ACCESS_FAIL": "",
            "ACCESS_PAUSE": "",
            "ACCESS_CONTINUE": "",
            **extra,
        }


def fixture(directory: Path, name: str, inputs: dict[str, bytes], **changes: object) -> Fixture:
    work = directory / name
    work.mkdir(parents=True)
    fix = Fixture(
        work,
        {
            "sources": "sources.json",
            "start": "2026-10-12T10:00:00Z",
            "end": "2026-10-12T11:00:00Z",
            "top": 5,
            "output": "access-report",
            **changes,
        },
    )
    rows = []
    for index, (label, data) in enumerate(inputs.items()):
        path = "input-" + str(index) + ".log"
        (work / path).write_bytes(data)
        rows.append({"name": label, "path": path})
    (work / "sources.json").write_text(json.dumps({"version": 1, "files": rows}, ensure_ascii=False))
    fix.save()
    return fix


def source_files(fix: Fixture) -> list[tuple[str, Path]]:
    return [(row["name"], fix.manifest.parent / row["path"]) for row in json.loads(fix.manifest.read_bytes())["files"]]


def outputs(fix: Fixture, report: dict, records: list | None = None, invalid: list | None = None) -> dict:
    sources = source_files(fix)
    if records is None or invalid is None:
        expected, records, invalid = reference(
            {name: path.read_bytes() for name, path in sources},
            fix.config["start"],
            fix.config["end"],
            fix.config["top"],
        )
        assert report == expected
    files = {"source-" + str(index) + ".log": path.read_bytes() for index, (_label, path) in enumerate(sources)}
    files["sources.json"] = (
        canonical(
            {
                "version": 1,
                "files": [
                    {"name": label, "path": "source-" + str(index) + ".log"}
                    for index, (label, _path) in enumerate(sources)
                ],
            }
        )
        + "\n"
    ).encode()
    files["report.json"] = (canonical(report) + "\n").encode()
    files["records.jsonl"] = "".join(canonical(row) + "\n" for row in records).encode()
    files["invalid.jsonl"] = "".join(canonical(row) + "\n" for row in invalid).encode()
    actual = {path.name: path.read_bytes() for path in fix.output.iterdir()}
    assert set(actual) == {*files, "summary.txt", "manifest.json"}
    assert all(actual[name] == data for name, data in files.items())
    assert (
        actual["summary.txt"].startswith(b"Access-log analysis\n")
        and json.loads(actual["summary.txt"].split(b"\n", 1)[1]) == report
    )
    manifest = json.loads(actual["manifest.json"])
    assert manifest == {
        "version": 1,
        "files": {
            name: {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
            for name, raw in actual.items()
            if name != "manifest.json"
        },
    }
    return actual


def success(app: Application, fix: Fixture, mode: str = "write") -> dict:
    sources = source_files(fix)
    paths = [fix.path, fix.manifest, *(path for _name, path in sources)]
    originals = [path.read_bytes() for path in paths]
    expected, records, invalid = reference(
        {name: path.read_bytes() for name, path in sources}, fix.config["start"], fix.config["end"], fix.config["top"]
    )
    result = app.run(fix.work, fix.settings(mode), timeout=180)
    assert result.returncode == int(bool(invalid)) and not result.stderr, (fix.work, result)
    report = json.loads(result.stdout)
    assert report == expected, (fix.work, report, expected)
    assert result.stdout == canonical(report) + "\n"
    assert originals == [path.read_bytes() for path in paths]
    if mode == "write":
        outputs(fix, report, records, invalid)
    else:
        assert not fix.output.exists()
    assert not list(fix.output.parent.glob(".access-*"))
    return report


def failure(app: Application, fix: Fixture, message: str = "", **extra: str) -> None:
    existed = fix.output.exists() or fix.output.is_symlink()
    before = fix.output.read_bytes() if fix.output.is_file() else None
    result = app.run(fix.work, fix.settings(**extra), timeout=180)
    assert result.returncode == 2 and result.stderr and message in result.stderr and not result.stdout, (
        fix.work,
        result,
        message,
    )
    assert (fix.output.exists() or fix.output.is_symlink()) == existed
    if before is not None:
        assert fix.output.read_bytes() == before
    assert not list(fix.output.parent.glob(".access-*"))
    return


def scenarios(app: Application, directory: Path) -> dict:
    digest = hashlib.sha256()
    fix = fixture(directory, "sample", sample())
    report = success(app, fix)
    assert report["counts"] == {"lines": 6, "valid": 5, "malformed": 1, "selected": 4, "filtered": 1}
    assert report["summary"]["bytes"] == 170 and report["summary"]["unique_hosts"] == 2
    assert report["summary"]["top_paths"] == [
        {"path": "/notes", "requests": 2, "bytes": 120, "errors": 0},
        {"path": "/api/items", "requests": 1, "bytes": 42, "errors": 1},
        {"path": "/世界", "requests": 1, "bytes": 8, "errors": 1},
    ]
    records = [json.loads(raw) for raw in (fix.output / "records.jsonl").read_bytes().splitlines()]
    assert records[0] == {
        "source": "front",
        "line": 1,
        "host": "127.0.0.1",
        "ident": "-",
        "user": "ada",
        "timestamp": "2026-10-12T10:00:00.000000+00:00",
        "method": "GET",
        "target": "/notes?q=rust",
        "path": "/notes",
        "protocol": "HTTP/1.1",
        "status": 200,
        "bytes": 120,
        "selected": True,
    }
    digest.update(canonical(report).encode())
    statuses = b"\n".join(line(status=str(status), size="-") for status in range(100, 600))
    report = success(app, fixture(directory, "all-statuses", {"status": statuses}))
    assert (
        report["counts"]["valid"] == 500
        and report["summary"]["client_errors"] == report["summary"]["server_errors"] == 100
    )
    assert len(report["summary"]["statuses"]) == 500
    digest.update(canonical(report).encode())
    methods = b"\n".join(line(method=token, size="0") for token in sorted(TOKEN))
    report = success(app, fixture(directory, "method-tokens", {"methods": methods}))
    assert report["counts"]["valid"] == len(TOKEN) and len(report["summary"]["methods"]) == len(TOKEN)
    digest.update(canonical(report).encode())
    byte_values = b"\n".join(line().replace(b"/notes", b"/a" + bytes([number]) + b"b") for number in range(256))
    report = success(app, fixture(directory, "byte-values", {"bytes": byte_values}))
    assert report["counts"]["lines"] == 257
    digest.update(canonical(report).encode())
    labeled = [
        (b"", "format"),
        (b"not a log", "format"),
        (b"\xff", "utf8"),
        (b"bad\x00line", "control"),
        (line() + b" ", "format"),
        (b" " + line(), "format"),
        (line().replace(b"host - -", b"host  - -"), "format"),
        (line().replace(b"GET ", b"GET\t"), "control"),
        (line(method="GÉT"), "format"),
        (line(protocol="HTTP/2"), "format"),
        (line(protocol="HTTP/10.0"), "format"),
        (line(target='/a"b'), "format"),
        (line(target="/a b"), "format"),
        (line(target=""), "format"),
        (line(status="099"), "status"),
        (line(status="600"), "status"),
        (line(status="999"), "status"),
        (line(status="20"), "format"),
        (line(status="２００"), "format"),
        (line(size="+1"), "format"),
        (line(size="-1"), "format"),
        (line(size="1.0"), "format"),
        (line(size="١"), "format"),
        (line(size=str(MAXIMUM + 1)), "bytes"),
        (line(size="0" * 4097), "bytes"),
    ]
    malformed_times = [
        ("29/Feb/1900:00:00:00 +0000", "timestamp"),
        ("29/Feb/2100:00:00:00 +0000", "timestamp"),
        ("31/Apr/2026:10:00:00 +0000", "timestamp"),
        ("00/Oct/2026:10:00:00 +0000", "timestamp"),
        ("12/oct/2026:10:00:00 +0000", "timestamp"),
        ("12/Foo/2026:10:00:00 +0000", "timestamp"),
        ("12/Oсt/2026:10:00:00 +0000", "format"),
        ("12/Oct/2026:24:00:00 +0000", "timestamp"),
        ("12/Oct/2026:10:60:00 +0000", "timestamp"),
        ("12/Oct/2026:10:00:60 +0000", "timestamp"),
        ("12/Oct/2026:10:00:00 +2400", "timestamp"),
        ("12/Oct/2026:10:00:00 +0060", "timestamp"),
        ("01/Jan/0001:00:00:00 +0001", "timestamp"),
        ("31/Dec/9999:23:59:59 -0001", "timestamp"),
        ("12/Oct/0000:10:00:00 +0000", "timestamp"),
        ("1/Oct/2026:10:00:00 +0000", "format"),
        ("12/Oct/26:10:00:00 +0000", "format"),
        ("12/Oct/2026:10:00:00 Z", "format"),
        ("12/Oct/2026:10:00:00 +00:00", "format"),
        ("12/Oct/2026:10:00:00.5 +0000", "format"),
    ]
    labeled += [(line(timestamp=timestamp), reason) for timestamp, reason in malformed_times]
    assert all(parse_line(raw)[1] == reason for raw, reason in labeled)
    fix = fixture(directory, "labeled-errors", {"bad": b"\n".join(raw for raw, _reason in labeled) + b"\n"})
    report = success(app, fix)
    assert report["counts"]["malformed"] == len(labeled)
    bad = [json.loads(raw) for raw in (fix.output / "invalid.jsonl").read_bytes().splitlines()]
    assert [row["reason"] for row in bad] == [reason for _raw, reason in labeled]
    digest.update(canonical(report).encode())
    dates = [f"01/{month}/2026:00:00:00 +0000" for month in MONTHS]
    dates += [
        "29/Feb/2000:23:59:59 +0000",
        "29/Feb/2024:00:00:00 +0000",
        "01/Jan/0001:00:00:00 +0000",
        "31/Dec/9999:23:59:59 +0000",
        "12/Oct/2026:00:00:00 +2359",
        "12/Oct/2026:23:59:59 -2359",
    ]
    report = success(
        app,
        fixture(
            directory, "calendar", {"dates": b"\n".join(line(timestamp=value) for value in dates)}, start=None, end=None
        ),
    )
    assert report["counts"]["valid"] == len(dates)
    digest.update(canonical(report).encode())
    endpoints = [
        None,
        "2026-10-12T09:59:59.999999Z",
        "2026-10-12T10:00:00Z",
        "2026-10-12T10:00:00.000001Z",
        "2026-10-12T10:30:00Z",
        "2026-10-12T10:59:59.999999Z",
        "2026-10-12T11:00:00Z",
        "2026-10-12T11:00:00.000001Z",
    ]
    windows = 0
    for beginning, ending in itertools.product(endpoints, repeat=2):
        if beginning is not None and ending is not None and instant(beginning) > instant(ending):
            continue
        report = success(app, fixture(directory, "window-" + str(windows), sample(), start=beginning, end=ending))
        digest.update(canonical(report).encode())
        windows += 1
    baseline = success(app, fixture(directory, "window-baseline", sample()))
    for index, (beginning, ending) in enumerate(
        itertools.product(
            ["2026-10-12T10:00:00Z", "2026-10-12T15:00:00+05:00", "2026-10-12T04:30:00-05:30"],
            ["2026-10-12T11:00:00Z", "2026-10-12T16:00:00+05:00", "2026-10-12T05:30:00-05:30"],
        )
    ):
        assert (
            success(app, fixture(directory, "equivalent-window-" + str(index), sample(), start=beginning, end=ending))
            == baseline
        )
    for index, data in enumerate(
        [
            b"",
            b"\n",
            b"\r\n",
            b"\r",
            line(),
            line() + b"\n",
            line() + b"\r\n",
            line() + b"\r",
            line() + b"\r\r\n",
            line() + b"\n\n",
            b"\n" + line(),
        ]
    ):
        digest.update(canonical(success(app, fixture(directory, "framing-" + str(index), {"file": data}))).encode())
    rng = random.Random(710071)
    for index in range(40):
        inputs = {}
        for source_index in range(1 + index % 4):
            rows = []
            for _ in range(rng.randrange(1, 90)):
                utc = dt.datetime(2026, 10, 12, 9, tzinfo=dt.timezone.utc) + dt.timedelta(seconds=rng.randrange(14400))
                offset = rng.choice([-720, -330, 0, 345, 840])
                local = utc.astimezone(dt.timezone(dt.timedelta(minutes=offset)))
                stamp = f'{local.day:02}/{MONTHS[local.month - 1]}/{local.year:04}:{local.hour:02}:{local.minute:02}:{local.second:02} {"+" if offset >= 0 else "-"}{abs(offset) // 60:02}{abs(offset) % 60:02}'
                rows.append(
                    line(
                        timestamp=stamp,
                        host=rng.choice(["127.0.0.1", "::1", "host", "世界"]),
                        user=rng.choice(["-", "ada", "é"]),
                        method=rng.choice(["GET", "POST", "HEAD", "OPTIONS", "CONNECT", "patch", "M-SEARCH"]),
                        target=rng.choice(
                            [
                                "/notes?a=1",
                                "/notes?a=2",
                                "/Case",
                                "/case",
                                "/%61",
                                "/a",
                                "/é",
                                "/é",
                                "/世界",
                                "https://example.test/p?q=x",
                                "*",
                                "host:443",
                                "?only",
                            ]
                        ),
                        protocol=rng.choice(["HTTP/1.0", "HTTP/1.1", "HTTP/2.0", "HTTP/3.0"]),
                        status=str(rng.choice([200, 201, 304, 400, 404, 418, 500, 503])),
                        size=rng.choice(["-", str(rng.randrange(10000))]),
                    )
                )
            if index % 3 == 0:
                rows.append(b"\x80")
            rng.shuffle(rows)
            inputs["source-" + str(source_index)] = b"\n".join(rows)
        report = success(app, fixture(directory, "generated-" + str(index), inputs, top=index % 13))
        digest.update(canonical(report).encode())
        permuted = {name: b"\n".join(reversed(framed(raw))) + b"\n" for name, raw in reversed(list(inputs.items()))}
        reordered = success(app, fixture(directory, "reordered-" + str(index), permuted, top=index % 13))
        assert reordered["summary"] == report["summary"] and reordered["counts"] == report["counts"]
    ties = {
        "ties": b"\n".join(
            line(target=path, size="0") for path in ["/z", "/é", "/é", "/世界", "/a", "/%61", "/A", "?q", "*"]
        )
    }
    for top in [0, 1, 3, 9, 100]:
        report = success(app, fixture(directory, "top-" + str(top), ties, top=top))
        assert report["summary"]["path_count"] == 9 and len(report["summary"]["top_paths"]) == min(top, 9)
        digest.update(canonical(report).encode())
    success(app, fixture(directory, "empty-sources", {}, start=None, end=None))
    duplicate = success(app, fixture(directory, "duplicate-events", {"one": line() + b"\n" + line(), "two": line()}))
    assert duplicate["summary"]["requests"] == 3 and duplicate["summary"]["bytes"] == 36
    exact_bytes = {"bytes": line(size=str(MAXIMUM - 2)) + b"\n" + line(size="2")}
    assert success(app, fixture(directory, "byte-total-exact", exact_bytes))["summary"]["bytes"] == MAXIMUM
    failure(
        app,
        fixture(directory, "byte-total-overflow", {"bytes": exact_bytes["bytes"] + b"\n" + line(size="1")}),
        "byte total",
    )
    excluded = {"bytes": line(size=str(MAXIMUM), timestamp="12/Oct/2026:11:00:00 +0000") + b"\n" + line(size="1")}
    assert success(app, fixture(directory, "excluded-byte-total", excluded))["summary"]["bytes"] == 1
    assert (
        success(app, fixture(directory, "zero-digits-exact", {"bytes": line(size="0" * 4096)}))["summary"]["bytes"] == 0
    )
    return {
        "status_codes": 500,
        "method_tokens": len(TOKEN),
        "byte_values": 256,
        "labeled_malformed_lines": len(labeled),
        "calendar_cases": len(dates),
        "window_cases": windows,
        "equivalent_windows": 9,
        "framing_cases": 11,
        "generated_batches": 40,
        "source_and_line_permutations": 40,
        "ranking_limits": 5,
        "reports_sha256": digest.hexdigest(),
    }


def invalid_inputs(app: Application, directory: Path) -> int:
    base = {"version": 1, "files": [{"name": "front", "path": "input-0.log"}]}
    variants = [None, [], {}, True, {**base, "extra": 1}]
    variants += [{key: value for key, value in base.items() if key != missing} for missing in base]
    variants += [{**base, "version": value} for value in [0, 2, True, 1.0, "1", None]]
    variants += [{**base, "files": value} for value in [None, {}, True, ""]]
    row = base["files"][0]
    malformed = [None, [], {}, True, {**row, "extra": 1}]
    malformed += [{key: value for key, value in row.items() if key != missing} for missing in row]
    for key, values in [
        ("name", ["", "x\x00", "x" * 129, "🙂" * 129, None, True, 1, [], {}]),
        ("path", ["", "\x00", None, True, 1, [], {}]),
    ]:
        malformed += [{**row, key: value} for value in values]
    variants += [{**base, "files": [value]} for value in malformed]
    variants += [{**base, "files": [row, row]}, {**base, "files": [row, {**row, "name": "other"}]}]
    for index, value in enumerate(variants):
        fix = fixture(directory, "sources-" + str(index), {"front": line()})
        fix.manifest.write_text(json.dumps(value))
        failure(app, fix)
    count = len(variants)
    for key in ["sources", "output"]:
        for index, value in enumerate(["", "\x00", None, True, 1, [], {}]):
            fix = fixture(directory, f"config-{key}-{index}", {})
            fix.path.write_text(json.dumps({**fix.config, key: value}))
            failure(app, fix)
            count += 1
    for key in ["sources", "output", "start", "end", "top"]:
        fix = fixture(directory, "missing-" + key, {})
        fix.path.write_text(json.dumps({k: v for k, v in fix.config.items() if k != key}))
        failure(app, fix)
        count += 1
    for index, value in enumerate([-1, 101, True, 1.0, "1", None, [], {}]):
        failure(app, fixture(directory, "top-" + str(index), {}, top=value))
        count += 1
    dates = [
        True,
        1,
        [],
        {},
        "",
        "2026-10-12",
        "2026-10-12T10:00:00",
        "2026-02-29T00:00:00Z",
        "2026-10-12T00:00:60Z",
        "2026-10-12T00:00:00+24:00",
        "2026-10-12T00:00:00.0000001Z",
    ]
    for key in ["start", "end"]:
        for index, value in enumerate(dates):
            failure(app, fixture(directory, f"date-{key}-{index}", {}, **{key: value}))
            count += 1
    failure(
        app,
        fixture(directory, "reversed", {}, start="2026-10-12T11:00:00Z", end="2026-10-12T10:00:00Z"),
        "reversed time window",
    )
    fix = fixture(directory, "extra-config", {})
    fix.path.write_text(json.dumps({**fix.config, "extra": 1}))
    failure(app, fix)
    failure(app, fixture(directory, "mode", {}), "invalid access-log mode", ACCESS_MODE="bad")
    count += 3
    for name in ["sources.json", "access-job.json"]:
        for index, raw in enumerate([b"\xff", b"{", b"[] trailing", b"[NaN]", b"[Infinity]", b'{"a":1,"a":2}']):
            fix = fixture(directory, f"raw-{name}-{index}", {})
            (fix.work / name).write_bytes(raw)
            failure(app, fix)
            count += 1
    fix = fixture(directory, "duplicate-canonical-path", {"one": line()})
    fix.manifest.write_text(
        json.dumps(
            {"version": 1, "files": [{"name": "one", "path": "input-0.log"}, {"name": "two", "path": "./input-0.log"}]}
        )
    )
    failure(app, fix, "duplicate source path")
    return count + 1


def limits(app: Application, directory: Path) -> dict:
    maximum = 1048576
    block = b"!" * 8192 + b"\n"
    content = block * (maximum // len(block)) + b"!" * (maximum % len(block))
    assert len(content) == maximum and max(map(len, framed(content))) == 8192
    report = success(app, fixture(directory, "combined-bytes", {str(index): content for index in range(4)}))
    assert report["counts"]["malformed"] == 512
    failure(
        app,
        fixture(
            directory,
            "combined-bytes-above",
            {**dict.fromkeys([str(index) for index in range(4)], content), "extra": b"\n"},
        ),
        "combined logs exceed",
    )
    failure(app, fixture(directory, "file-bytes-above", {"large": content + b"!"}), "input byte limit")
    success(app, fixture(directory, "sources-exact", dict.fromkeys([str(index) for index in range(8)], b"")))
    failure(
        app, fixture(directory, "sources-above", dict.fromkeys([str(index) for index in range(9)], b"")), "source count"
    )
    report = success(app, fixture(directory, "lines-exact", {"lines": (line(size="0") + b"\n") * 10000}))
    assert report["counts"]["valid"] == report["summary"]["requests"] == 10000
    failure(app, fixture(directory, "lines-above", {"lines": b"\n" * 10001}), "line count")
    failure(app, fixture(directory, "lines-across-files", {"one": b"\n" * 5001, "two": b"\n" * 5000}), "line count")
    for suffix in [b"", b"\n", b"\r\n"]:
        fix = fixture(directory, "line-exact-" + suffix.hex(), {"line": b"x" * 8192 + suffix})
        assert success(app, fix)["counts"]["malformed"] == 1
    failure(app, fixture(directory, "line-above", {"line": b"x" * 8193}), "line exceeds")
    failure(app, fixture(directory, "line-above-crlf", {"line": b"x" * 8193 + b"\r\n"}), "line exceeds")
    success(app, fixture(directory, "name-exact", {"🙂" * 128: line()}))
    for name in ["access-job.json", "sources.json"]:
        fix = fixture(directory, "json-bytes-" + name, sample())
        path = fix.work / name
        raw = path.read_bytes()
        path.write_bytes(raw + b" " * (65536 - len(raw)))
        success(app, fix, "preview")
        path.write_bytes(raw + b" " * (65537 - len(raw)))
        failure(app, fix, "input byte limit")
    large = line(target="/" + "\\" * 300) + b"\n"
    inputs = {str(index) + "\x01" * 127: large * 2500 for index in range(4)}
    assert all(len(raw) <= maximum for raw in inputs.values()) and sum(map(len, inputs.values())) <= 4194304
    failure(app, fixture(directory, "record-byte-budget", inputs), "record exports exceed")
    return {
        "sources": 8,
        "source_bytes": maximum,
        "total_source_bytes": 4194304,
        "lines": 10000,
        "line_bytes": 8192,
        "config_bytes": 65536,
        "source_manifest_bytes": 65536,
        "source_name_characters": 128,
        "source_name_bytes": 512,
        "record_export_bytes": 16777216,
        "top_paths": 100,
        "byte_sum": MAXIMUM,
    }


def paused(app: Application, fix: Fixture) -> subprocess.Popen:
    process = subprocess.Popen(
        app.command,
        cwd=fix.work,
        env=app.environment(fix.settings(ACCESS_PAUSE="ready", ACCESS_CONTINUE=str(fix.work / "continue"))),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    with selectors.DefaultSelector() as selector:
        selector.register(process.stdout, selectors.EVENT_READ)
        ready = bool(selector.select(20))
    if not ready or process.stdout.readline() != "PAUSED ready\n":
        process.kill()
        raise AssertionError(process.communicate(timeout=5))
    return process


def stop(process: subprocess.Popen) -> None:
    if process.poll() is None:
        process.kill()
    process.communicate(timeout=5)
    return


def publication(app: Application, directory: Path) -> int:
    points = [
        "validated",
        "stage",
        "source-0.log",
        "source-1.log",
        "sources.json",
        "report.json",
        "records.jsonl",
        "invalid.jsonl",
        "summary.txt",
        "manifest.json",
        "ready",
        "published",
    ]
    for point in points:
        fix = fixture(directory, "fault-" + point, sample())
        reference = success(app, fix, "preview")
        result = app.run(fix.work, fix.settings(ACCESS_FAIL=point))
        assert result.returncode == 2 and "injected failure: " + point in result.stderr and not result.stdout
        assert not list(fix.work.glob(".access-*"))
        if point == "published":
            outputs(fix, reference)
        else:
            assert not fix.output.exists()
            success(app, fix)
    for name in ["input-0.log", "input-1.log", "sources.json", "config", "destination"]:
        fix = fixture(directory, "changed-" + name, sample())
        process = paused(app, fix)
        try:
            if name == "destination":
                fix.output.mkdir()
                (fix.output / "keep").write_bytes(b"another writer")
            else:
                path = fix.path if name == "config" else fix.work / name
                with path.open("ab") as stream:
                    stream.write(b" ")
            (fix.work / "continue").touch()
            output, error = process.communicate(timeout=20)
            assert process.returncode == 2 and error and not output
            assert not list(fix.work.glob(".access-*"))
            if name == "destination":
                assert list(fix.output.iterdir()) == [fix.output / "keep"]
                assert (fix.output / "keep").read_bytes() == b"another writer"
            else:
                assert "input changed before publication" in error and not fix.output.exists()
        finally:
            stop(process)
    fix = fixture(directory, "killed", sample())
    reference = success(app, fix, "preview")
    process = paused(app, fix)
    stop(process)
    assert not fix.output.exists()
    abandoned = list(fix.work.glob(".access-*"))
    assert len(abandoned) == 1
    old = {path.name: path.read_bytes() for path in abandoned[0].iterdir()}
    result = app.run(fix.work, fix.settings())
    assert result.returncode == 1 and not result.stderr
    outputs(fix, reference)
    assert {path.name: path.read_bytes() for path in abandoned[0].iterdir()} == old
    return len(points) + 6


def paths(app: Application, directory: Path) -> int:
    names = ["input-0.log", "input-1.log", "sources.json", "access-job.json"]
    for name in ["file", "directory", "symlink", "dangling", *names]:
        fix = fixture(directory, "destination-" + name, sample())
        if name == "file":
            fix.output.write_bytes(b"preserve")
        elif name == "directory":
            fix.output.mkdir()
            (fix.output / "keep").write_bytes(b"preserve")
        elif name in ["symlink", "dangling"]:
            fix.output.symlink_to(fix.work / ("input-0.log" if name == "symlink" else "missing"))
        else:
            fix.config["output"] = name
            fix.save()
        failure(app, fix, "output directory already exists")
    for name in names:
        fix = fixture(directory, "symlink-" + name, sample())
        path = fix.work / name
        path.rename(fix.work / "original")
        path.symlink_to(fix.work / "original")
        original = (fix.work / "original").read_bytes()
        failure(app, fix, "regular file")
        assert path.is_symlink() and (fix.work / "original").read_bytes() == original
    fix = fixture(directory, "readonly", sample())
    parent = fix.work / "readonly"
    parent.mkdir()
    fix.config["output"] = "readonly/result"
    fix.save()
    parent.chmod(0o500)
    try:
        failure(app, fix)
        assert not list(parent.iterdir())
    finally:
        parent.chmod(0o700)
    fix = fixture(directory, "nested-manifest", sample())
    nested = fix.work / "nested"
    nested.mkdir()
    old = fix.manifest
    value = json.loads(old.read_bytes())
    for row in value["files"]:
        row["path"] = "../" + row["path"]
    old.unlink()
    fix.config["sources"] = "nested/sources.json"
    fix.manifest.write_text(json.dumps(value))
    fix.save()
    success(app, fix)
    return 14


def check(app: Application, directory: Path) -> dict:
    cases = scenarios(app, directory / "scenarios")
    print(app.engine + " access logs: independent fields, aggregates, windows and malformed lines passed", flush=True)
    invalid = invalid_inputs(app, directory / "invalid")
    bounds = limits(app, directory / "limits")
    faults = publication(app, directory / "publication")
    path_cases = paths(app, directory / "paths")
    print(app.engine + " access logs: validation, limits, publication and paths passed", flush=True)
    return {**cases, "invalid_inputs": invalid, "limits": bounds, "publication_cases": faults, "path_cases": path_cases}
