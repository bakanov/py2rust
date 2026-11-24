"""Consecutive failures open a circuit; bounded successful probes close it again."""

from enum import Enum

from py2rust.stdlib import Json, json_array, json_float, json_int, json_string


class Phase(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


def fresh(identifier: str) -> Json:
    return {
        "id": identifier,
        "phase": Phase.CLOSED.value,
        "failures": 0,
        "successes": 0,
        "retry_at": 0.0,
        "calls": 0,
        "failed_calls": 0,
        "rejected": 0,
        "inflight": False,
        "last_status": 0,
        "last_error": "",
        "last_at": 0.0,
        "sequence": 0,
        "history": [],
    }


def transition(record: Json, phase: Phase, now: float, reason: str) -> Json:
    previous: str = json_string(record["phase"])
    if previous == phase.value:
        return record
    sequence: int = json_int(record["sequence"]) + 1
    history: list[Json] = json_array(record["history"])
    history.append({"sequence": sequence, "at": now, "before": previous, "after": phase.value, "reason": reason})
    retained: list[Json] = []
    for index in range(max(0, len(history) - 20), len(history)):
        retained.append(history[index])
    record["phase"] = phase.value
    record["sequence"] = sequence
    record["history"] = retained
    return record


def claim(record: Json, now: float) -> Json:
    if json_string(record["phase"]) == Phase.OPEN.value:
        assert now >= json_float(record["retry_at"]), "circuit cooldown has not expired"
        record = transition(record, Phase.HALF_OPEN, now, "probe")
        record["retry_at"] = 0.0
        record["successes"] = 0
    record["inflight"] = True
    record["calls"] = json_int(record["calls"]) + 1
    record["last_at"] = now
    return record


def finish(record: Json, status: int, error: str, now: float, policy: Json) -> Json:
    record["inflight"] = False
    record["last_status"] = status
    record["last_error"] = error
    record["last_at"] = now
    if error != "":
        record["failed_calls"] = json_int(record["failed_calls"]) + 1
        record["failures"] = min(json_int(policy["threshold"]), json_int(record["failures"]) + 1)
        record["successes"] = 0
        if json_string(record["phase"]) == Phase.HALF_OPEN.value or json_int(record["failures"]) >= json_int(
            policy["threshold"]
        ):
            record["retry_at"] = now + json_float(policy["cooldown"])
            record = transition(record, Phase.OPEN, now, error)
    else:
        record["failures"] = 0
        if json_string(record["phase"]) == Phase.HALF_OPEN.value:
            record["successes"] = json_int(record["successes"]) + 1
            if json_int(record["successes"]) >= json_int(policy["probes"]):
                record["successes"] = 0
                record = transition(record, Phase.CLOSED, now, "recovered")
    return record
