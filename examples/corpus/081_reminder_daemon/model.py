"""Fixed UTC intervals, explicit missed-run policies and bounded durable reminder history."""

# ruff: noqa: PLR1711 - explicit subset returns
from dataclasses import dataclass
from enum import Enum

from py2rust.stdlib import (
    Json,
    datetime_format,
    datetime_from_unix,
    json_array,
    json_int,
    json_keys,
    json_string,
    regex_fullmatch,
    regex_search,
)

MAX_CLOCK: int = 4102444799


class Policy(Enum):
    ALL = "all"
    LATEST = "latest"
    SKIP = "skip"


@dataclass
class Reminder:
    identifier: str
    message: str
    start: int
    every: int
    policy: Policy


def exact(value: Json, keys: list[str]) -> None:
    assert sorted(json_keys(value)) == sorted(keys), "unexpected fields"
    return


def integer(value: Json, low: int, high: int) -> int:
    result: int = json_int(value)
    assert low <= result <= high, "integer outside allowed range"
    return result


def utc(seconds: int) -> str:
    return datetime_format(datetime_from_unix(seconds), "%Y-%m-%dT%H:%M:%SZ")


def definitions(value: Json) -> list[Reminder]:
    entries: list[Json] = json_array(value)
    assert 1 <= len(entries) <= 32, "expected 1..32 reminders"
    result: list[Reminder] = []
    identifiers: set[str] = set()
    for entry in entries:
        exact(entry, ["id", "message", "start", "every", "policy"])
        identifier: str = json_string(entry["id"])
        assert regex_fullmatch("[A-Za-z][A-Za-z0-9_-]{0,31}", identifier), "invalid reminder ID"
        assert identifier not in identifiers, "duplicate reminder ID"
        identifiers.add(identifier)
        message: str = json_string(entry["message"])
        assert 1 <= len(message.encode()) <= 256, "invalid reminder message length"
        assert not regex_search("[\\x00-\\x1f\\x7f]", message), "message contains controls"
        policy: str = json_string(entry["policy"])
        assert policy in ["all", "latest", "skip"], "invalid missed-run policy"
        selected: Policy = Policy.ALL
        if policy == "latest":
            selected = Policy.LATEST
        elif policy == "skip":
            selected = Policy.SKIP
        result.append(
            Reminder(
                identifier,
                message,
                integer(entry["start"], 0, MAX_CLOCK),
                integer(entry["every"], 1, 31536000),
                selected,
            )
        )
    return result


def policy_json(reminders: list[Reminder]) -> Json:
    entries: list[Json] = []
    for reminder in reminders:
        entries.append(
            {
                "id": reminder.identifier,
                "message": reminder.message,
                "start": reminder.start,
                "every": reminder.every,
                "policy": reminder.policy.value,
            }
        )
    return entries


def empty(reminders: list[Reminder]) -> Json:
    records: list[Json] = []
    for reminder in reminders:
        records.append({"id": reminder.identifier, "next": reminder.start, "emitted": 0, "skipped": 0})
    return {
        "version": 1,
        "policy": policy_json(reminders),
        "clock": -1,
        "ticks": 0,
        "sequence": 0,
        "records": records,
        "history": [],
    }


def advance(state: Json, reminders: list[Reminder], observed: int) -> tuple[Json, list[Json]]:
    now: int = max(integer(observed, 0, MAX_CLOCK), json_int(state["clock"]))
    records: list[Json] = json_array(state["records"])
    events: list[Json] = []
    sequence: int = json_int(state["sequence"])
    for index in range(len(reminders)):
        reminder: Reminder = reminders[index]
        record: Json = records[index]
        deadline: int = json_int(record["next"])
        if deadline <= now:
            due: int = (now - deadline) // reminder.every + 1
            emit: int = min(due, 16)
            consumed: int = emit
            first: int = deadline
            if reminder.policy != Policy.ALL:
                first = deadline + (due - 1) * reminder.every
                emit = 1 if reminder.policy == Policy.LATEST or first == now else 0
                consumed = due
            for offset in range(emit):
                scheduled: int = first + offset * reminder.every
                sequence = sequence + 1
                events.append(
                    {
                        "sequence": sequence,
                        "id": reminder.identifier,
                        "message": reminder.message,
                        "scheduled": scheduled,
                        "scheduled_utc": utc(scheduled),
                        "observed": now,
                        "observed_utc": utc(now),
                        "late_seconds": now - scheduled,
                    }
                )
            record["next"] = deadline + consumed * reminder.every
            record["emitted"] = json_int(record["emitted"]) + emit
            record["skipped"] = json_int(record["skipped"]) + consumed - emit
            records[index] = record
    history: list[Json] = json_array(state["history"]) + events
    state["history"] = history[-256:]
    state["records"] = records
    state["sequence"] = sequence
    state["clock"] = now
    state["ticks"] = json_int(state["ticks"]) + 1
    assert json_int(state["ticks"]) <= 1000000000000, "tick limit reached"
    return (state, events)


def report(state: Json) -> Json:
    rows: list[Json] = []
    for record in json_array(state["records"]):
        row: Json = {
            "id": record["id"],
            "next": record["next"],
            "next_utc": utc(json_int(record["next"])),
            "emitted": record["emitted"],
            "skipped": record["skipped"],
        }
        rows.append(row)
    return {
        "clock": state["clock"],
        "ticks": state["ticks"],
        "sequence": state["sequence"],
        "records": rows,
        "history": state["history"],
    }
