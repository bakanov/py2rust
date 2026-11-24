"""Validate jobs and completion events, preserving exact normalized UTC timestamps."""

# ruff: noqa: BLE001, PLR1711 - field-specific input errors and explicit returns
from dataclasses import dataclass

from documents import Document, absolute, present, read

from py2rust.stdlib import (
    DateTime,
    Json,
    datetime_add_seconds,
    datetime_from_unix,
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
class Inspection:
    observed: DateTime
    jobs: list[Json]
    events: list[Json]
    inputs: list[Document]
    output: str


def exact(value: Json, keys: list[str], location: str) -> None:
    assert sorted(json_keys(value)) == sorted(keys), location + ": unexpected fields"
    return


def identifier(value: Json, location: str) -> str:
    text: str = json_string(value)
    assert regex_fullmatch("[A-Za-z][A-Za-z0-9_-]{0,31}", text), location + ": invalid identifier"
    return text


def instant(value: Json, location: str) -> DateTime:
    result: DateTime = datetime_from_unix(0)
    try:
        result = datetime_parse(json_string(value).replace("t", "T").replace("z", "Z"))
    except Exception:
        assert False, location + ": expected RFC3339 timestamp, years 0001..9999, at most 6 fractional digits"
    return result


def load(config: Document) -> Inspection:
    value: Json = json_loads(config.data.decode())
    exact(value, ["version", "observed_at", "jobs", "events", "output"], "configuration")
    assert json_int(value["version"]) == 1, "unsupported configuration version"
    observed: DateTime = instant(value["observed_at"], "observed_at")
    base: str = path_parent(config.path)
    jobs_file: Document = read(absolute(json_string(value["jobs"]), base), 262144)
    events_file: Document = read(absolute(json_string(value["events"]), base), 524288)
    assert jobs_file.path != events_file.path and config.path not in [
        jobs_file.path,
        events_file.path,
    ], "aliased inputs"
    output: str = absolute(json_string(value["output"]), base)
    assert not present(output), "output already exists"
    jobs: list[Json] = json_array(json_loads(jobs_file.data.decode()))
    events: list[Json] = json_array(json_loads(events_file.data.decode()))
    assert 1 <= len(jobs) <= 256 and len(events) <= 4096, "expected 1..256 jobs and at most 4096 events"
    known: set[str] = set()
    for index in range(len(jobs)):
        job: Json = jobs[index]
        location: str = "jobs[" + str(index) + "]"
        exact(job, ["id", "label", "deadline", "grace_seconds"], location)
        key: str = identifier(job["id"], location + ".id")
        assert key not in known, location + ": duplicate job identifier"
        known.add(key)
        label: str = json_string(job["label"])
        assert 1 <= len(label.encode()) <= 256 and "\x00" not in label, location + ": invalid label"
        deadline: DateTime = instant(job["deadline"], location + ".deadline")
        grace: int = json_int(job["grace_seconds"])
        assert 0 <= grace <= 604800, location + ": grace must be 0..604800 seconds"
        cutoff: DateTime = deadline
        try:
            cutoff = datetime_add_seconds(deadline, grace)
        except Exception:
            assert False, location + ": grace cutoff exceeds supported years"
        job["deadline"] = datetime_iso(deadline)
        job["cutoff"] = datetime_iso(cutoff)
        jobs[index] = job
    for index in range(len(events)):
        event: Json = events[index]
        location: str = "events[" + str(index) + "]"
        exact(event, ["job", "completed_at"], location)
        key: str = identifier(event["job"], location + ".job")
        assert key in known, location + ": unknown job"
        event["completed_at"] = datetime_iso(instant(event["completed_at"], location + ".completed_at"))
        events[index] = event
    return Inspection(observed, jobs, events, [config, jobs_file, events_file], output)
