"""Compare native TZif resolution with ZoneInfo, including gap/fold boundaries."""

# ruff: noqa: PLR1711, DTZ001 - explicit returns and intentional naive local-time fixtures
import datetime as dt
import io
import json
import random
import struct
from pathlib import Path
from zoneinfo import ZoneInfo, available_timezones

import pytest

from .test_services import run

UTC = dt.timezone.utc
ZONES = [
    "UTC",
    "America/New_York",
    "Europe/Berlin",
    "Europe/Dublin",
    "Australia/Lord_Howe",
    "Pacific/Apia",
    "Asia/Kathmandu",
    "Africa/Casablanca",
    "Europe/Amsterdam",
    "Antarctica/Troll",
]


def view(zone: ZoneInfo, instant: dt.datetime) -> dict:
    local = instant.astimezone(zone)
    delta = local.utcoffset()
    return {
        "utc": instant.isoformat(timespec="microseconds"),
        "local": local.replace(tzinfo=None).isoformat(timespec="microseconds"),
        "offset_seconds": delta.days * 86400 + delta.seconds,
        "abbreviation": local.tzname(),
        "is_dst": local.dst() != dt.timedelta(0),
    }


def resolve(data: bytes, text: str) -> dict:
    zone = ZoneInfo.from_file(io.BytesIO(data))
    local = dt.datetime.fromisoformat(text)
    valid, shifted = {}, {}
    for fold in (0, 1):
        instant = local.replace(tzinfo=zone, fold=fold).astimezone(UTC)
        projection = view(zone, instant)
        shifted[instant] = projection
        if instant.astimezone(zone).replace(tzinfo=None) == local:
            valid[instant] = projection
    kind = "gap" if not valid else "unique" if len(valid) == 1 else "fold"
    return {
        "kind": kind,
        "local": local.isoformat(timespec="microseconds"),
        "candidates": [valid[key] for key in sorted(valid)],
        "projections": [shifted[key] for key in sorted(shifted)] if kind == "gap" else [],
    }


def write_zones(directory: Path) -> dict[str, bytes]:
    result = {}
    for index, name in enumerate(ZONES):
        data = Path("/usr/share/zoneinfo", name).read_bytes()
        (directory / f"zone-{index}.tzif").write_bytes(data)
        result[name] = data
    return result


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_tzif_local_and_utc_vectors(tmp_path: Path, engine: str) -> None:
    zones = write_zones(tmp_path)
    locals_, utc_values = [], []
    centers = [
        "2024-03-10T02:00:00",
        "2024-11-03T01:00:00",
        "2024-03-31T02:00:00",
        "2024-10-27T02:00:00",
        "2024-04-07T01:30:00",
        "2024-10-06T02:00:00",
        "2011-12-30T00:00:00",
        "2011-12-31T00:00:00",
    ]
    rng = random.Random(8601)
    for name in ZONES:
        index = ZONES.index(name)
        texts = [
            "0001-01-02T12:00:00",
            "1890-01-01T00:00:00.123456",
            "1900-01-01T00:00:00",
            "2038-01-19T03:14:08",
            "2050-03-27T02:30:00",
            "2050-10-30T02:30:00",
            "2400-02-29T12:00:00",
            "9999-12-30T00:00:00",
        ]
        for center in centers:
            value = dt.datetime.fromisoformat(center)
            texts += [
                (value + dt.timedelta(microseconds=shift)).isoformat(timespec="microseconds")
                for shift in [-1, 0, 1, 1799999999, 1800000000, 3599999999, 3600000000, 3600000001]
            ]
        texts += [
            (
                dt.datetime(1800, 1, 1)
                + dt.timedelta(days=rng.randrange(150000), microseconds=rng.randrange(86400000000))
            ).isoformat(timespec="microseconds")
            for _ in range(30)
        ]
        for text in texts:
            locals_.append({"zone": index, "text": text})
            utc_values.append({"zone": index, "text": text + "Z"})
    source = """
from py2rust.stdlib import Json, json_array, json_int, json_string, json_loads, json_canonical, read_bytes, timezone_local, timezone_project, datetime_parse
def evaluate() -> None:
    for case in json_array(json_loads(LOCAL)):
        data: bytes = read_bytes("zone-" + str(json_int(case["zone"])) + ".tzif")
        print(json_canonical(timezone_local(data, json_string(case["text"]))))
    for case in json_array(json_loads(UTC)):
        data: bytes = read_bytes("zone-" + str(json_int(case["zone"])) + ".tzif")
        print(json_canonical(timezone_project(data, datetime_parse(json_string(case["text"])))))
    return
if __name__ == "__main__":
    evaluate()
""".replace("LOCAL", repr(json.dumps(locals_))).replace("UTC", repr(json.dumps(utc_values)))
    result = run(tmp_path, source, engine)
    assert result.returncode == 0, result.stderr
    actual = [json.loads(line) for line in result.stdout.splitlines()]
    expected = [resolve(zones[ZONES[row["zone"]]], row["text"]) for row in locals_]
    expected += [
        view(
            ZoneInfo.from_file(io.BytesIO(zones[ZONES[row["zone"]]])),
            dt.datetime.fromisoformat(row["text"].replace("Z", "+00:00")),
        )
        for row in utc_values
    ]
    assert len(actual) == len(expected)
    for index, (left, right) in enumerate(zip(actual, expected, strict=True)):
        assert left == right, (index, (locals_ + utc_values)[index], left, right)
    assert {row["kind"] for row in actual[: len(locals_)]} == {"unique", "gap", "fold"}
    return


def tzif(types: list[tuple[int, int, bytes]], transitions: list[tuple[int, int]]) -> bytes:
    names, table = b"", b""
    for offset, dst, label in types:
        table += struct.pack(">iBB", offset, dst, len(names))
        names += label + b"\0"
    header = b"TZif\0" + b"\0" * 15 + struct.pack(">6I", 0, 0, 0, len(transitions), len(types), len(names))
    return (
        header
        + b"".join(struct.pack(">i", stamp) for stamp, _ in transitions)
        + bytes(index for _, index in transitions)
        + table
        + names
    )


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_tzif_v1_defaults_and_historical_seconds(tmp_path: Path, engine: str) -> None:
    tables = [
        tzif([(1234, 0, b"HIS")], []),
        tzif([(3600, 1, b"DST"), (0, 0, b"STD")], [(0, 0), (86400, 1)]),
        tzif([(3600, 0, b"ONE"), (7200, 0, b"TWO")], []),
    ]
    expected = []
    for index, data in enumerate(tables):
        (tmp_path / f"zone-{index}.tzif").write_bytes(data)
        zone = ZoneInfo.from_file(io.BytesIO(data))
        for text in [
            "1900-01-01T12:34:56.123456",
            "1970-01-01T00:00:00",
            "1970-01-01T01:30:00",
            "1970-01-02T00:30:00",
            "2050-01-01T00:00:00",
        ]:
            expected += [resolve(data, text), view(zone, dt.datetime.fromisoformat(text).replace(tzinfo=UTC))]
    # With a first DST type, ZoneInfo's local fold shortcut omits one side of
    # this first gap. The UTC projections give the independently known pair.
    zone = ZoneInfo.from_file(io.BytesIO(tables[1]))
    expected[12]["projections"] = [
        view(zone, dt.datetime(1969, 12, 31, 23, tzinfo=UTC)),
        view(zone, dt.datetime(1970, 1, 1, tzinfo=UTC)),
    ]
    source = """
from py2rust.stdlib import read_bytes, timezone_local, timezone_project, datetime_parse, json_canonical
def evaluate() -> None:
    for index in range(3):
        data: bytes = read_bytes("zone-" + str(index) + ".tzif")
        for text in ["1900-01-01T12:34:56.123456", "1970-01-01T00:00:00", "1970-01-01T01:30:00", "1970-01-02T00:30:00", "2050-01-01T00:00:00"]:
            print(json_canonical(timezone_local(data, text)))
            print(json_canonical(timezone_project(data, datetime_parse(text + "Z"))))
    return
if __name__ == "__main__":
    evaluate()
"""
    result = run(tmp_path, source, engine)
    assert result.returncode == 0, result.stderr
    actual = [json.loads(line) for line in result.stdout.splitlines()]
    assert actual == expected
    return


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_tzif_invalid_inputs_are_recoverable(tmp_path: Path, engine: str) -> None:
    valid = tzif([(0, 0, b"UTC")], [])
    values = [
        b"",
        b"TZif",
        b"x" * 44,
        b"x" * 1048577,
        valid[:-1],
        valid + b"garbage",
        valid[:4] + b"4" + valid[5:],
        tzif([(86400, 0, b"BAD")], []),
        tzif([(-86400, 0, b"BAD")], []),
        tzif([(0, 2, b"BAD")], []),
        tzif([(0, 0, b"TOO_LONG")], []),
        tzif([(0, 0, b"UT")], []),
        tzif([(0, 0, b"B!D")], []),
        tzif([(0, 0, b"UTC")], [(1, 0), (0, 0)]),
        tzif([(0, 0, b"UTC")], [(0, 0), (0, 0)]),
        valid[:20] + struct.pack(">II", 1, 0) + valid[28:] + b"\x01",
        valid[:20] + struct.pack(">II", 0, 1) + valid[28:] + b"\x02",
        valid[:20] + struct.pack(">II", 1, 1) + valid[28:] + b"\x00\x01",
    ]
    for position, count in [(20, 2), (24, 2), (28, 1), (32, 20001), (36, 0), (36, 257), (40, 4097)]:
        value = bytearray(valid)
        value[position : position + 4] = struct.pack(">I", count)
        values.append(bytes(value))
    for index, data in enumerate(values):
        (tmp_path / f"invalid-{index}").write_bytes(data)
    (tmp_path / "utc.tzif").write_bytes(valid)
    invalid = [
        "",
        "2024-01-01",
        "2024-01-01 00:00:00",
        "2024-01-01t00:00:00",
        "2024-01-01T00:00:00Z",
        "2024-01-01T00:00:00+05:00",
        "2024-01-01T00:00:00.1234567",
        "2024-01-01T00:00:00\n",
        "0000-01-01T00:00:00",
        "2024-02-30T00:00:00",
        "2024-01-01T24:00:00",
        "2016-12-31T23:59:60",
        "２０２４-01-01T00:00:00",
    ]
    source = """
from py2rust.stdlib import read_bytes, timezone_local, timezone_project, datetime_parse, Json
def evaluate() -> None:
    errors: int = 0
    for index in range(COUNT):
        data: bytes = read_bytes("invalid-" + str(index))
        try:
            value: Json = timezone_local(data, "2024-01-01T00:00:00")
        except Exception:
            errors = errors + 1
        try:
            value: Json = timezone_project(data, datetime_parse("2024-01-01T00:00:00Z"))
        except Exception:
            errors = errors + 1
    for text in INVALID:
        try:
            value: Json = timezone_local(read_bytes("utc.tzif"), text)
        except Exception:
            errors = errors + 1
    print(errors)
    return
if __name__ == "__main__":
    evaluate()
""".replace("COUNT", str(len(values))).replace("INVALID", repr(invalid))
    result = run(tmp_path, source, engine)
    assert result.returncode == 0 and result.stdout == f"{2 * len(values) + len(invalid)}\n", (
        result.stderr + result.stdout
    )
    return


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_tzif_every_installed_zone_round_trips(tmp_path: Path, engine: str) -> None:
    names = sorted(name for name in available_timezones() if Path("/usr/share/zoneinfo", name).is_file())
    assert len(names) > 400
    stamps = ["1920-01-01T12:34:56.123456Z", "2024-11-03T06:30:00.123456Z", "2050-07-01T12:00:00Z"]
    expected, labels = [], []
    for index, name in enumerate(names):
        data = Path("/usr/share/zoneinfo", name).read_bytes()
        (tmp_path / f"zone-{index}").write_bytes(data)
        zone = ZoneInfo.from_file(io.BytesIO(data))
        for text in stamps:
            projection = view(zone, dt.datetime.fromisoformat(text.replace("Z", "+00:00")))
            expected += [projection, resolve(data, projection["local"])]
            labels += [(name, text)] * 2
    source = """
from py2rust.stdlib import Json, read_bytes, timezone_local, timezone_project, datetime_parse, json_string, json_canonical
def evaluate() -> None:
    for index in range(COUNT):
        data: bytes = read_bytes("zone-" + str(index))
        for text in STAMPS:
            projected: Json = timezone_project(data, datetime_parse(text))
            print(json_canonical(projected))
            print(json_canonical(timezone_local(data, json_string(projected["local"]))))
    return
if __name__ == "__main__":
    evaluate()
""".replace("COUNT", str(len(names))).replace("STAMPS", repr(stamps))
    result = run(tmp_path, source, engine)
    assert result.returncode == 0, result.stderr
    actual = [json.loads(line) for line in result.stdout.splitlines()]
    assert len(actual) == len(expected)
    for label, left, right in zip(labels, actual, expected, strict=True):
        assert left == right, (label, left, right)
    return


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_tzif_fold_overflow_does_not_silently_remove_an_interpretation(tmp_path: Path, engine: str) -> None:
    def block(width: int, times: list[int], offsets: tuple[int, int]) -> bytes:
        header = b"TZif2" + b"\0" * 15 + struct.pack(">6I", 0, 0, 0, len(times), 2, 8)
        entries = b"".join(struct.pack(">i" if width == 4 else ">q", value) for value in times)
        entries += b"\1" * len(times)
        entries += struct.pack(">iBB", offsets[0], 0, 0) + struct.pack(">iBB", offsets[1], 0, 4)
        return header + entries + b"ONE\0TWO\0"

    for name, stamp, offsets in [("lower", -62135596800, (3600, 0)), ("upper", 253402300800, (0, -3600))]:
        data = block(4, [], offsets) + block(8, [stamp], offsets) + b"\n\n"
        (tmp_path / name).write_bytes(data)
    source = """
from py2rust.stdlib import Json, read_bytes, timezone_local, json_string
def evaluate() -> None:
    errors: int = 0
    for text in ["0001-01-01T00:00:00", "0001-01-01T00:59:59.999999"]:
        try:
            value: Json = timezone_local(read_bytes("lower"), text)
        except Exception:
            errors = errors + 1
    for text in ["9999-12-31T23:00:00", "9999-12-31T23:59:59.999999"]:
        try:
            value: Json = timezone_local(read_bytes("upper"), text)
        except Exception:
            errors = errors + 1
    print(errors)
    print(json_string(timezone_local(read_bytes("lower"), "0001-01-01T01:00:00")["kind"]))
    print(json_string(timezone_local(read_bytes("upper"), "9999-12-31T22:59:59.999999")["kind"]))
    return
if __name__ == "__main__":
    evaluate()
"""
    result = run(tmp_path, source, engine)
    assert result.returncode == 0 and result.stdout == "4\nunique\nunique\n", (result.stdout, result.stderr)
    return
