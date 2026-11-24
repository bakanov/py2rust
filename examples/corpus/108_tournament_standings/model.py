"""Validate team registrations and single-round-robin fixtures before calculating any standings."""

# ruff: noqa: PLR1711 - explicit returns
from dataclasses import dataclass

from py2rust.stdlib import (
    Json,
    json_array,
    json_int,
    json_keys,
    json_kind,
    json_string,
    regex_fullmatch,
    unicode_normalize,
)


@dataclass
class Team:
    identifier: str
    name: str


@dataclass
class Fixture:
    identifier: str
    home: str
    away: str
    played: bool
    home_score: int
    away_score: int


@dataclass
class Tournament:
    title: str
    teams: dict[str, Team]
    fixtures: list[Fixture]


def text(value: Json) -> str:
    assert json_kind(value) == "string", "expected text"
    return json_string(value)


def exact(value: Json, fields: list[str]) -> None:
    assert json_kind(value) == "object", "expected object"
    assert sorted(json_keys(value)) == sorted(fields), "unexpected fields"
    return


def array(value: Json, maximum: int) -> list[Json]:
    assert json_kind(value) == "array", "expected array"
    values: list[Json] = json_array(value)
    assert len(values) <= maximum, "array count limit"
    return values


def display(value: str) -> str:
    return " ".join(unicode_normalize("NFKC", value).split())


def label(value: Json) -> str:
    raw: str = text(value)
    shown: str = display(raw)
    assert 1 <= len(raw) <= 100 and 1 <= len(shown) <= 100, "label character limit"
    for character in shown:
        assert ord(character) >= 32 and not 127 <= ord(character) <= 159, "control character in label"
    return raw


def identifier(value: Json) -> str:
    name: str = text(value)
    assert regex_fullmatch("[A-Za-z][A-Za-z0-9_-]{0,31}", name), "invalid identifier"
    return name


def score(value: Json) -> int:
    result: int = json_int(value)
    assert 0 <= result <= 10000, "score limit"
    return result


def parse(source: Json) -> Tournament:
    exact(source, ["version", "title", "teams", "fixtures"])
    assert json_int(source["version"]) == 1, "unsupported source version"
    title: str = label(source["title"])
    teams: dict[str, Team] = {}
    for row in array(source["teams"], 32):
        exact(row, ["id", "name"])
        name: str = identifier(row["id"])
        assert name not in teams, "duplicate team identifier"
        teams[name] = Team(name, label(row["name"]))
    fixtures: list[Fixture] = []
    fixture_ids: set[str] = set()
    pairs: set[str] = set()
    for row in array(source["fixtures"], 496):
        exact(row, ["id", "home", "away", "home_score", "away_score"])
        name: str = identifier(row["id"])
        home: str = identifier(row["home"])
        away: str = identifier(row["away"])
        assert name not in fixture_ids, "duplicate fixture identifier"
        assert home in teams and away in teams and home != away, "invalid fixture teams"
        pair: str = home + ":" + away if home < away else away + ":" + home
        assert pair not in pairs, "duplicate team pairing"
        played: bool = json_kind(row["home_score"]) != "null"
        assert played == (json_kind(row["away_score"]) != "null"), "both scores must be null or integers"
        home_score: int = 0
        away_score: int = 0
        if played:
            home_score = score(row["home_score"])
            away_score = score(row["away_score"])
        fixtures.append(Fixture(name, home, away, played, home_score, away_score))
        fixture_ids.add(name)
        pairs.add(pair)
    return Tournament(title, teams, fixtures)
