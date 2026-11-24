"""Durable queue snapshots and a monotone clock for lease expiry."""

from model import clear_lease, clock, normalize_job, setting, valid_name, valid_token

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_equal,
    json_float,
    json_int,
    json_loads,
    json_string,
    path_exists,
    pretty,
    read_text,
    write_text_atomic,
)


def state_path() -> str:
    return env_get("QUEUE_STATE", "queue-state.json")


def load() -> Json:
    content: str = read_text(state_path())
    assert len(content.encode()) <= 8388608, "snapshot exceeds byte limit"
    state: Json = json_loads(content)
    assert json_int(state["version"]) == 1, "unsupported snapshot version"
    return state


def save(state: Json) -> None:
    content: str = pretty(state)
    assert len(content.encode()) <= 8388608, "snapshot exceeds byte limit"
    assert len(json_array(state["jobs"])) <= setting("QUEUE_LIMIT", 1000), "job limit exceeded"
    write_text_atomic(state_path(), content)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def find(jobs: list[Json], identifier: str) -> int:
    for index in range(len(jobs)):
        if json_string(jobs[index]["job"]["id"]) == identifier:
            return index
    return -1


def initialize() -> None:
    if not path_exists(state_path()):
        save({"version": 1, "clock": clock(), "jobs": []})
    state: Json = load()
    observed: float = json_float(state["clock"])
    assert observed >= 0.0 and observed <= 253402214400.0, "invalid stored clock"
    jobs: list[Json] = json_array(state["jobs"])
    assert len(jobs) <= setting("QUEUE_LIMIT", 1000), "stored queue exceeds job limit"
    identifiers: set[str] = set()
    tokens: set[str] = set()
    for record in jobs:
        assert json_equal(normalize_job(record["job"]), record["job"]), "invalid stored job"
        identifier: str = json_string(record["job"]["id"])
        assert identifier not in identifiers, "duplicate stored job ID"
        identifiers.add(identifier)
        created: float = json_float(record["created"])
        assert created >= 0.0 and created <= observed, "invalid job creation time"
        assert json_float(record["available_at"]) >= created, "invalid availability time"
        attempts: int = json_int(record["attempts"])
        assert attempts >= 0, "invalid attempt count"
        status: str = json_string(record["state"])
        worker: str = json_string(record["worker"])
        token: str = json_string(record["token"])
        if status == "pending":
            assert token == "" and worker == "" and json_float(record["lease_until"]) == 0.0, "pending job has a lease"
            assert json_float(record["completed_at"]) == 0.0, "pending job is marked complete"
        else:
            assert attempts > 0 and valid_name(worker) and valid_token(token), "invalid lease receipt"
            assert token not in tokens, "duplicate lease token"
            tokens.add(token)
            if status == "leased":
                assert json_float(record["lease_until"]) > created, "invalid lease deadline"
                assert json_float(record["completed_at"]) == 0.0, "leased job is marked complete"
            else:
                assert status == "done" and json_float(record["lease_until"]) == 0.0, "invalid completed state"
                completed: float = json_float(record["completed_at"])
                assert completed >= created and completed <= observed, "invalid completion time"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def refresh() -> Json:
    state: Json = load()
    now: float = max(clock(), json_float(state["clock"]))
    jobs: list[Json] = []
    for record in json_array(state["jobs"]):
        if json_string(record["state"]) == "leased" and json_float(record["lease_until"]) <= now:
            jobs.append(clear_lease(record, now))
        else:
            jobs.append(record)
    updated: Json = {"version": 1, "clock": now, "jobs": jobs}
    if not json_equal(state, updated):
        save(updated)
    return updated
