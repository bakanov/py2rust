"""Validate exploration bounds separately from per-expression syntax diagnostics."""

from dataclasses import dataclass

from documents import Document, absolute, present

from py2rust.stdlib import (
    DateTime,
    Json,
    datetime_add_seconds,
    datetime_iso,
    datetime_parse,
    json_array,
    json_int,
    json_keys,
    json_loads,
    json_string,
    path_parent,
    regex_fullmatch,
)


@dataclass
class Job:
    start: DateTime
    end: DateTime
    days: int
    limit: int
    schedules: list[Json]
    output: str


def load(document: Document) -> Job:
    value: Json = json_loads(document.data.decode())
    assert sorted(json_keys(value)) == [
        "days",
        "limit",
        "output",
        "schedules",
        "start",
        "version",
    ], "invalid job fields"
    assert json_int(value["version"]) == 1, "unsupported job version"
    days: int = json_int(value["days"])
    limit: int = json_int(value["limit"])
    assert 1 <= days <= 3660 and 1 <= limit <= 1000, "days or limit outside bounds"
    start: DateTime = datetime_parse(json_string(value["start"]))
    end: DateTime = datetime_add_seconds(start, days * 86400)
    output: str = absolute(json_string(value["output"]), path_parent(document.path))
    assert not present(output), "output already exists"
    schedules: list[Json] = json_array(value["schedules"])
    assert 1 <= len(schedules) <= 16, "expected 1..16 schedules"
    identifiers: set[str] = set()
    for entry in schedules:
        assert sorted(json_keys(entry)) == ["expression", "id"], "invalid schedule fields"
        identifier: str = json_string(entry["id"])
        assert regex_fullmatch("[A-Za-z][A-Za-z0-9_-]{0,31}", identifier), "invalid schedule ID"
        assert identifier not in identifiers, "duplicate schedule ID"
        identifiers.add(identifier)
        expression: str = json_string(entry["expression"])
        assert len(expression.encode()) <= 256, "expression exceeds 256 UTF-8 bytes"
    return Job(start, end, days, limit, schedules, output)


def replay(job: Job) -> Json:
    return {
        "version": 1,
        "start": datetime_iso(job.start),
        "days": job.days,
        "limit": job.limit,
        "schedules": job.schedules,
        "output": "rebuilt",
    }
