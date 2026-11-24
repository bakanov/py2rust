"""Atomic checkpoints and all-or-nothing validated imports; one writer per queue."""

from model import new_entry, normalize_job

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_equal,
    json_float,
    json_int,
    json_kind,
    json_loads,
    json_string,
    path_exists,
    pretty,
    read_text,
    write_text_atomic,
)


def state_path() -> str:
    return env_get("OUTBOX_STATE", "outbox-state.json")


def save(entries: list[Json]) -> None:
    content: str = pretty({"format": 1, "jobs": entries})
    assert len(content.encode()) <= 8388608, "queue snapshot exceeds limit"
    write_text_atomic(state_path(), content)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def validate_entry(entry: Json) -> None:
    assert json_equal(normalize_job(entry["job"]), entry["job"]), "stored job is not normalized"
    status: str = json_string(entry["state"])
    assert status in ["pending", "delivered", "dead"], "invalid stored state"
    attempts: int = json_int(entry["attempts"])
    assert attempts >= 0 and attempts <= 20, "invalid stored attempt count"
    assert json_float(entry["last_attempt"]) >= 0.0, "invalid last attempt time"
    assert json_float(entry["next_attempt"]) >= 0.0, "invalid next attempt time"
    code: int = json_int(entry["last_status"])
    assert code == 0 or (code >= 100 and code <= 599), "invalid stored status code"
    error: str = json_string(entry["last_error"])
    assert len(error) <= 100, "invalid stored error"
    if status == "delivered":
        assert code >= 200 and code < 300 and attempts > 0 and error == "", "invalid delivered receipt"
    if status == "dead":
        assert attempts > 0 and error != "", "invalid dead-letter receipt"
    if attempts == 0:
        assert status == "pending" and code == 0 and error == "", "invalid unattempted entry"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def load() -> list[Json]:
    if not path_exists(state_path()):
        return []
    content: str = read_text(state_path())
    assert len(content.encode()) <= 8388608, "queue snapshot exceeds limit"
    value: Json = json_loads(content)
    assert json_int(value["format"]) == 1, "unsupported queue format"
    entries: list[Json] = json_array(value["jobs"])
    assert len(entries) <= 1000, "queue is too large"
    seen: set[str] = set()
    for entry in entries:
        validate_entry(entry)
        identifier: str = json_string(entry["job"]["id"])
        assert identifier not in seen, "duplicate stored delivery ID"
        seen.add(identifier)
    return entries


def find(entries: list[Json], identifier: str) -> Json:
    for entry in entries:
        if json_string(entry["job"]["id"]) == identifier:
            return entry
    return None


def import_jobs(entries: list[Json]) -> list[Json]:
    path: str = env_get("OUTBOX_IMPORT", "")
    if path == "":
        return entries
    content: str = read_text(path)
    assert len(content.encode()) <= 8388608, "import exceeds limit"
    incoming: list[Json] = json_array(json_loads(content))
    assert len(incoming) <= 1000, "too many imported jobs"
    proposed: list[Json] = entries.copy()
    for raw in incoming:
        job: Json = normalize_job(raw)
        previous: Json = find(proposed, json_string(job["id"]))
        if json_kind(previous) == "null":
            proposed.append(new_entry(job))
        else:
            assert json_equal(previous["job"], job), "conflicting delivery ID"
    assert len(proposed) <= 1000, "queue is full"
    if not json_equal(entries, proposed):
        save(proposed)
    return proposed
