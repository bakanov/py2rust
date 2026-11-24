"""Validate complete experiments before integrating any parameter set."""

# ruff: noqa: PLR1711 - explicit returns
from dataclasses import dataclass

from py2rust.stdlib import (
    Json,
    json_array,
    json_float,
    json_int,
    json_keys,
    json_kind,
    json_string,
    regex_fullmatch,
    unicode_normalize,
)


@dataclass
class Parameters:
    identifier: str
    name: str
    model: str
    initial: float
    rate: float
    capacity: float


@dataclass
class Experiment:
    title: str
    timestep: float
    steps: int
    cases: list[Parameters]


def exact(value: Json, fields: list[str]) -> None:
    assert json_kind(value) == "object", "expected object"
    assert sorted(json_keys(value)) == sorted(fields), "unexpected fields"
    return


def text(value: Json) -> str:
    assert json_kind(value) == "string", "expected text"
    return json_string(value)


def display(value: str) -> str:
    return " ".join(unicode_normalize("NFKC", value).split())


def label(value: Json, limit: int) -> str:
    original: str = text(value)
    shown: str = display(original)
    assert 1 <= len(original) <= limit and 1 <= len(shown) <= limit, "label character limit"
    for character in shown:
        assert ord(character) >= 32 and not 127 <= ord(character) <= 159, "control character in label"
        assert ord(character) != 65534 and ord(character) != 65535, "character not allowed in XML"
    return original


def number(value: Json, low: float, high: float) -> float:
    assert json_kind(value) == "number", "expected JSON number"
    result: float = json_float(value)
    assert low <= result <= high, "number range"
    return 0.0 if result == 0.0 else result


def parse(source: Json) -> Experiment:
    exact(source, ["version", "title", "timestep", "steps", "cases"])
    assert json_int(source["version"]) == 1, "unsupported source version"
    title: str = label(source["title"], 100)
    timestep: float = number(source["timestep"], 1e-9, 1e6)
    steps: int = json_int(source["steps"])
    assert 0 <= steps <= 2048, "step count limit"
    assert json_kind(source["cases"]) == "array", "expected cases array"
    rows: list[Json] = json_array(source["cases"])
    assert 1 <= len(rows) <= 16, "case count limit"
    seen: list[str] = []
    cases: list[Parameters] = []
    for row in rows:
        exact(row, ["id", "name", "model", "initial", "rate", "capacity"])
        identifier: str = text(row["id"])
        assert regex_fullmatch("[A-Za-z][A-Za-z0-9_-]{0,31}", identifier), "invalid identifier"
        assert identifier not in seen, "duplicate identifier"
        seen.append(identifier)
        name: str = label(row["name"], 60)
        model: str = text(row["model"])
        assert model in ["exponential", "logistic"], "unknown growth model"
        initial: float = number(row["initial"], 0.0, 1e12)
        assert initial == 0.0 or initial >= 1e-9, "initial population range"
        rate: float = number(row["rate"], -1000.0, 1000.0)
        assert rate == 0.0 or abs(rate) >= 1e-12, "rate range"
        capacity: float = 0.0
        if model == "logistic":
            capacity = number(row["capacity"], 1e-9, 1e12)
        else:
            assert json_kind(row["capacity"]) == "null", "exponential capacity must be null"
        cases.append(Parameters(identifier, name, model, initial, rate, capacity))
    return Experiment(title, timestep, steps, cases)
