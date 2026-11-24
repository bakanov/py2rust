"""Checksummed snapshots validate interval arithmetic and retained delivery receipts before reuse."""

# ruff: noqa: PLR1711 - explicit subset returns
from documents import present, read, stamp
from model import MAX_CLOCK, Policy, Reminder, empty, exact, integer, policy_json, utc

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_canonical,
    json_equal,
    json_int,
    json_loads,
    json_string,
    sha256_digest,
    sha256_new,
    sha256_update,
    sleep,
    write_text_atomic,
)


def digest(value: Json) -> str:
    return sha256_digest(sha256_update(sha256_new(), json_canonical(value).encode()))


def validate(state: Json, reminders: list[Reminder]) -> None:
    exact(state, ["version", "policy", "clock", "ticks", "sequence", "records", "history"])
    assert json_int(state["version"]) == 1, "unsupported state version"
    assert json_equal(state["policy"], policy_json(reminders)), "reminder configuration changed"
    clock: int = integer(state["clock"], -1, MAX_CLOCK)
    ticks: int = integer(state["ticks"], 0, 1000000000000)
    assert (ticks == 0) == (clock == -1), "inconsistent clock and tick count"
    records: list[Json] = json_array(state["records"])
    assert len(records) == len(reminders), "inconsistent reminder count"
    total: int = 0
    emitted_by_id: dict[str, int] = {}
    next_by_id: dict[str, int] = {}
    definitions_by_id: dict[str, Reminder] = {}
    for index in range(len(records)):
        reminder: Reminder = reminders[index]
        row: Json = records[index]
        exact(row, ["id", "next", "emitted", "skipped"])
        assert json_string(row["id"]) == reminder.identifier, "inconsistent reminder order"
        emitted: int = integer(row["emitted"], 0, MAX_CLOCK + 1)
        skipped: int = integer(row["skipped"], 0, MAX_CLOCK + 1)
        consumed: int = emitted + skipped
        due: int = 0 if clock < reminder.start else (clock - reminder.start) // reminder.every + 1
        assert consumed <= due, "progress exceeds clock"
        if reminder.policy == Policy.ALL:
            assert skipped == 0 and emitted <= ticks * 16, "invalid catch-up progress"
        else:
            assert consumed == due and emitted <= ticks, "invalid missed-run progress"
        deadline: int = json_int(row["next"])
        assert deadline == reminder.start + consumed * reminder.every, "inconsistent next deadline"
        total = total + emitted
        emitted_by_id[reminder.identifier] = emitted
        next_by_id[reminder.identifier] = deadline
        definitions_by_id[reminder.identifier] = reminder
    assert json_int(state["sequence"]) == total, "inconsistent event count"
    history: list[Json] = json_array(state["history"])
    assert len(history) == min(total, 256), "inconsistent retained history length"
    previous_observed: int = -1
    previous_scheduled: dict[str, int] = {}
    retained: dict[str, int] = {}
    for index in range(len(history)):
        event: Json = history[index]
        exact(
            event,
            ["sequence", "id", "message", "scheduled", "scheduled_utc", "observed", "observed_utc", "late_seconds"],
        )
        assert json_int(event["sequence"]) == total - len(history) + index + 1, "history sequence gap"
        identifier: str = json_string(event["id"])
        assert identifier in definitions_by_id, "unknown history reminder"
        reminder: Reminder = definitions_by_id[identifier]
        scheduled: int = integer(event["scheduled"], reminder.start, clock)
        observed: int = integer(event["observed"], scheduled, clock)
        assert (scheduled - reminder.start) % reminder.every == 0, "off-schedule history event"
        if reminder.policy == Policy.LATEST:
            assert scheduled + reminder.every > observed, "history violates latest policy"
        elif reminder.policy == Policy.SKIP:
            assert scheduled == observed, "history violates skip policy"
        assert scheduled < next_by_id[identifier] and scheduled > previous_scheduled.get(
            identifier, -1
        ), "history order"
        assert observed >= previous_observed, "history clock moved backward"
        assert json_int(event["late_seconds"]) == observed - scheduled, "inconsistent lateness"
        assert json_string(event["message"]) == reminder.message, "inconsistent history message"
        assert json_string(event["scheduled_utc"]) == utc(scheduled), "inconsistent scheduled UTC"
        assert json_string(event["observed_utc"]) == utc(observed), "inconsistent observed UTC"
        retained[identifier] = retained.get(identifier, 0) + 1
        assert retained[identifier] <= emitted_by_id[identifier], "history exceeds emitted count"
        previous_scheduled[identifier] = scheduled
        previous_observed = observed
    return


def load(path: str, reminders: list[Reminder]) -> Json:
    if not present(path):
        return empty(reminders)
    envelope: Json = json_loads(read(path, 1048576).data.decode())
    exact(envelope, ["state", "sha256"])
    state: Json = envelope["state"]
    assert json_string(envelope["sha256"]) == digest(state), "state checksum mismatch"
    validate(state, reminders)
    return state


def checkpoint(label: str) -> None:
    assert env_get("REMINDER_FAULT", "") != label, "injected failure: " + label
    if env_get("REMINDER_PAUSE", "") == label:
        print("PAUSED " + label)
        for attempt in range(3000):
            sleep(0.01)
        assert False, "pause timed out"
    return


def save(path: str, state: Json) -> None:
    text: str = json_canonical({"state": state, "sha256": digest(state)}) + "\n"
    assert len(text.encode()) <= 1048576, "snapshot exceeds 1 MiB"
    if present(path):
        stamp(path)
    checkpoint("before_commit")
    write_text_atomic(path, text)
    checkpoint("after_commit")
    return
