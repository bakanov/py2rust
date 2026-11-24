"""Validate ordered telemetry and normalize RFC3339 timestamps without float timestamp conversion."""

# ruff: noqa: BLE001, PLR1711 - normalized input diagnostics and explicit returns
from dataclasses import dataclass

from py2rust.stdlib import (
    DateTime,
    Json,
    datetime_iso,
    datetime_parse,
    datetime_unix_microseconds,
    json_array,
    json_float,
    json_int,
    json_keys,
    json_kind,
    json_string,
    regex_fullmatch,
)


@dataclass
class Parameters:
    window: int
    warmup: int
    gap_us: int
    sigma: float


@dataclass
class Sample:
    timestamp: int
    utc: str
    value: float


def text(value: Json) -> str:
    assert json_kind(value) == "string", "expected text"
    return json_string(value)


def exact(value: Json, names: list[str]) -> None:
    assert json_kind(value) == "object", "expected object"
    assert sorted(json_keys(value)) == sorted(names), "unexpected fields"
    return


def number(value: Json) -> float:
    parsed: float = 0.0
    try:
        if json_kind(value) == "number":
            parsed = json_float(value)
        else:
            spelling: str = text(value)
            assert 1 <= len(spelling) <= 64 and regex_fullmatch("[-+0-9_eE.]+", spelling), "decimal spelling"
            parsed = float(spelling)
            mantissa: str = spelling.lower().split("e")[0].replace("_", "").strip("+-0.")
            assert parsed != 0.0 or mantissa == "", "decimal underflow"
        assert abs(parsed) <= 1e100 and (parsed == 0.0 or abs(parsed) >= 1e-100), "value range"
        return 0.0 if parsed == 0.0 else parsed
    except Exception:
        assert False, "expected zero or finite numeric value with magnitude 1e-100..1e100"
    return 0.0


def parameters(value: Json) -> Parameters:
    exact(value, ["window", "warmup", "gap_us", "sigma"])
    result: Parameters = Parameters(
        json_int(value["window"]), json_int(value["warmup"]), json_int(value["gap_us"]), number(value["sigma"])
    )
    assert 2 <= result.window <= 256 and 2 <= result.warmup <= result.window, "window or warmup limit"
    assert 1 <= result.gap_us <= 86400000000, "gap threshold limit"
    assert 0.1 <= result.sigma <= 20.0, "sigma threshold limit"
    return result


def series(document: Json) -> list[Json]:
    exact(document, ["version", "settings", "series"])
    assert json_int(document["version"]) == 1, "unsupported source version"
    assert json_kind(document["series"]) == "array", "expected series array"
    rows: list[Json] = json_array(document["series"])
    assert len(rows) <= 8, "series count limit"
    seen: list[str] = []
    count: int = 0
    for row in rows:
        exact(row, ["id", "samples"])
        name: str = text(row["id"])
        assert regex_fullmatch("[A-Za-z][A-Za-z0-9_-]{0,31}", name), "invalid series identifier"
        assert name not in seen, "duplicate series identifier"
        seen.append(name)
        if json_kind(row["samples"]) == "array":
            count = count + len(json_array(row["samples"]))
    assert count <= 4096, "total sample limit"
    return rows


def timestamp(value: Json, index: int) -> tuple[int, str]:
    try:
        spelling: str = text(value)
        assert len(spelling) <= 40, "timestamp spelling limit"
        date: DateTime = datetime_parse(spelling)
        return (datetime_unix_microseconds(date), datetime_iso(date))
    except Exception:
        assert False, "invalid timestamp at sample " + str(index)
    return (0, "")


def samples(value: Json) -> list[Sample]:
    assert json_kind(value) == "array", "expected sample array"
    rows: list[Json] = json_array(value)
    result: list[Sample] = []
    previous: int = 0
    for index in range(len(rows)):
        row: Json = rows[index]
        exact(row, ["at", "value"])
        time: tuple[int, str] = timestamp(row["at"], index)
        assert index == 0 or time[0] > previous, "timestamps must be strictly increasing at sample " + str(index)
        result.append(Sample(time[0], time[1], number(row["value"])))
        previous = time[0]
    return result
