"""Strict interval-consumption and fictional tariff definitions; UTC seconds and exact decimals."""

# ruff: noqa: PLR1711 - explicit returns
from dataclasses import dataclass

from py2rust.stdlib import (
    Json,
    Rational,
    datetime_from_unix,
    datetime_iso,
    datetime_parse,
    datetime_unix_microseconds,
    json_array,
    json_int,
    json_keys,
    json_kind,
    json_string,
    rational_compare,
    rational_decimal,
    rational_denominator,
    rational_numerator,
    regex_fullmatch,
)


@dataclass
class Interval:
    start: int
    end: int
    energy: Rational


@dataclass
class Band:
    start: int
    rate: Rational


@dataclass
class Tier:
    limit: Rational
    rate: Rational
    unlimited: bool


@dataclass
class Tariff:
    name: str
    fee: Rational
    bands: list[Band]
    tiers: list[Tier]


@dataclass
class Usage:
    start: int
    end: int
    intervals: list[Interval]
    tariffs: list[Tariff]


def text(value: Json) -> str:
    assert json_kind(value) == "string", "expected text"
    return json_string(value)


def exact(value: Json, fields: list[str]) -> None:
    assert json_kind(value) == "object", "expected object"
    assert sorted(json_keys(value)) == sorted(fields), "unexpected fields"
    return


def array(value: Json, minimum: int, maximum: int) -> list[Json]:
    assert json_kind(value) == "array", "expected array"
    rows: list[Json] = json_array(value)
    assert minimum <= len(rows) <= maximum, "array count limit"
    return rows


def decimal(value: Json, maximum: str) -> Rational:
    spelling: str = text(value)
    assert regex_fullmatch(
        "(0|[1-9][0-9]{0,8})(\\.[0-9]{1,6})?", spelling
    ), "expected nonnegative decimal, at most six places"
    result: Rational = rational_decimal(spelling)
    assert rational_compare(result, rational_decimal(maximum)) <= 0, "decimal range limit"
    return result


def timestamp(value: Json) -> int:
    spelling: str = text(value)
    assert len(spelling) <= 40, "timestamp spelling limit"
    micros: int = datetime_unix_microseconds(datetime_parse(spelling))
    assert micros % 1000000 == 0, "timestamps must be whole seconds"
    return micros // 1000000


def utc(seconds: int) -> str:
    return datetime_iso(datetime_from_unix(seconds))


def fraction(value: Rational) -> Json:
    return {"numerator": rational_numerator(value), "denominator": rational_denominator(value)}


def tariff(value: Json) -> Tariff:
    exact(value, ["id", "fee", "bands", "tiers"])
    name: str = text(value["id"])
    assert regex_fullmatch("[A-Za-z][A-Za-z0-9_-]{0,31}", name), "invalid tariff identifier"
    bands: list[Band] = []
    previous: int = -1
    for row in array(value["bands"], 1, 16):
        exact(row, ["start_second", "rate"])
        start: int = json_int(row["start_second"])
        assert previous < start < 86400 and (previous != -1 or start == 0), "bands must increase from midnight"
        bands.append(Band(start, decimal(row["rate"], "1000")))
        previous = start
    tiers: list[Tier] = []
    rows: list[Json] = array(value["tiers"], 1, 8)
    previous_limit: Rational = rational_decimal("0")
    for index in range(len(rows)):
        row: Json = rows[index]
        exact(row, ["up_to_kwh", "surcharge"])
        unlimited: bool = json_kind(row["up_to_kwh"]) == "null"
        assert unlimited == (index == len(rows) - 1), "only the last tier must be unlimited"
        limit: Rational = previous_limit
        if not unlimited:
            limit = decimal(row["up_to_kwh"], "256000000")
            assert rational_compare(limit, previous_limit) > 0, "tier limits must increase from zero"
        tiers.append(Tier(limit, decimal(row["surcharge"], "1000"), unlimited))
        previous_limit = limit
    return Tariff(name, decimal(value["fee"], "1000000"), bands, tiers)


def parse(value: Json) -> Usage:
    exact(value, ["version", "period", "intervals", "tariffs"])
    assert json_int(value["version"]) == 1, "unsupported source version"
    exact(value["period"], ["start", "end"])
    start: int = timestamp(value["period"]["start"])
    end: int = timestamp(value["period"]["end"])
    assert 0 < end - start <= 2678400, "billing period must be positive and at most 31 days"
    intervals: list[Interval] = []
    previous: int = start
    for row in array(value["intervals"], 0, 256):
        exact(row, ["start", "end", "kwh"])
        left: int = timestamp(row["start"])
        right: int = timestamp(row["end"])
        assert previous <= left < right <= end, "intervals must be ordered, disjoint and inside the period"
        intervals.append(Interval(left, right, decimal(row["kwh"], "1000000")))
        previous = right
    tariffs: list[Tariff] = []
    names: list[str] = []
    for row in array(value["tariffs"], 1, 8):
        item: Tariff = tariff(row)
        assert item.name not in names, "duplicate tariff identifier"
        names.append(item.name)
        tariffs.append(item)
    return Usage(start, end, intervals, tariffs)
