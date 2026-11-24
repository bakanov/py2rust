"""Atomic queue/receipt/quota checkpoints; a durable claim exposes uncertain requests."""

from model import new_entry, normalize_job, result_nodes

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_dumps,
    json_equal,
    json_float,
    json_int,
    json_is_null,
    json_keys,
    json_loads,
    json_string,
    path_exists,
    path_is_symlink,
    path_join,
    path_name,
    path_parent,
    path_resolve,
    path_same,
    read_text,
    write_text_atomic,
)


def state_path() -> str:
    return env_get("BATCH_STATE", "batch-state.json")


def validate_paths() -> None:
    paths: list[str] = [state_path(), state_path() + ".report.json", env_get("BATCH_CONFIG", "batch.json")]
    for name in ["BATCH_IMPORT", "BATCH_CA"]:
        value: str = env_get(name, "")
        if value != "":
            paths.append(value)
    canonical: list[str] = []
    for index in range(len(paths)):
        path: str = paths[index]
        if index < 2:
            assert not path_is_symlink(path), "outputs must not be symlinks"
        normalized: str = path_join(path_resolve(path_parent(path)), path_name(path))
        assert normalized not in canonical, "input and output paths overlap"
        canonical.append(normalized)
        for previous in range(index):
            if path_exists(path) and path_exists(paths[previous]):
                assert not path_same(path, paths[previous]), "input and output paths alias"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def save(state: Json) -> None:
    text: str = json_dumps(state)
    assert len(text.encode()) <= 16777216, "state exceeds 16 MiB"
    validate_paths()
    write_text_atomic(state_path(), text)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def validate_entry(entry: Json, policy: Json, last: float) -> None:
    assert json_keys(entry) == [
        "attempts",
        "error",
        "job",
        "last_at",
        "next_at",
        "result",
        "state",
        "status",
    ], "invalid receipt fields"
    assert json_equal(normalize_job(entry["job"], policy), entry["job"]), "noncanonical stored request"
    state: str = json_string(entry["state"])
    attempts: int = json_int(entry["attempts"])
    status: int = json_int(entry["status"])
    error: str = json_string(entry["error"])
    next_at: float = json_float(entry["next_at"])
    at: float = json_float(entry["last_at"])
    assert attempts >= 0 and attempts <= json_int(policy["attempts"]), "invalid attempt count"
    assert at >= 0.0 and at <= last and next_at >= 0.0 and next_at <= 253402300799.0, "invalid receipt times"
    assert status == 0 or (status >= 100 and status <= 599), "invalid HTTP status"
    assert state in ["pending", "inflight", "complete", "failed"], "invalid receipt state"
    assert error in ["", "transport", "http", "invalid JSON result", "uncertain request"], "invalid receipt error"
    if state == "complete":
        assert status >= 200 and status < 300 and attempts > 0 and error == "", "invalid completed receipt"
        result_nodes(entry["result"], 0)
        assert len(json_dumps(entry["result"]).encode()) <= 131072, "stored result exceeds limit"
        assert status != 204 or json_is_null(entry["result"]), "204 receipt has a result"
    else:
        assert json_is_null(entry["result"]), "unfinished receipt has a result"
    if state == "pending":
        assert attempts < json_int(policy["attempts"]), "exhausted pending request"
        if attempts > 0:
            assert next_at > at and error != "", "retry lacks deadline or error"
            assert error != "invalid JSON result", "invalid JSON is a terminal failure"
            if error == "http":
                assert status == 408 or status == 429 or status >= 500, "permanent HTTP failure queued for retry"
    elif state != "inflight":
        assert next_at == 0.0 and attempts > 0, "terminal receipt has a deadline"
    if state == "failed":
        assert error != "", "failed receipt lacks error"
    if state == "inflight":
        assert attempts > 0, "unclaimed inflight request"
    if attempts == 0:
        assert json_equal(entry, new_entry(entry["job"])), "invalid unattempted receipt"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def load(policy: Json) -> Json:
    if not path_exists(state_path()):
        return {"version": 1, "policy": policy, "last_at": 0.0, "quota": {"not_before": 0.0, "blocked": ""}, "jobs": []}
    text: str = read_text(state_path())
    assert len(text.encode()) <= 16777216, "state exceeds 16 MiB"
    state: Json = json_loads(text)
    assert json_keys(state) == ["jobs", "last_at", "policy", "quota", "version"], "invalid state fields"
    assert json_int(state["version"]) == 1 and json_equal(state["policy"], policy), "state policy mismatch"
    last: float = json_float(state["last_at"])
    assert last >= 0.0 and last <= 253402200000.0, "invalid queue clock"
    quota: Json = state["quota"]
    assert json_keys(quota) == ["blocked", "not_before"], "invalid quota fields"
    gate: float = json_float(quota["not_before"])
    assert gate >= 0.0 and gate <= 253402300799.0, "invalid quota deadline"
    assert json_string(quota["blocked"]) in ["", "invalid quota headers"], "invalid blocked reason"
    entries: list[Json] = json_array(state["jobs"])
    assert len(entries) <= 100, "queue exceeds 100 requests"
    seen: set[str] = set()
    inflight: int = 0
    for entry in entries:
        validate_entry(entry, policy, last)
        identifier: str = json_string(entry["job"]["id"])
        assert identifier not in seen, "duplicate stored ID"
        seen.add(identifier)
        if json_string(entry["state"]) == "inflight":
            inflight = inflight + 1
    assert inflight <= 1, "multiple inflight requests"
    return state


def import_jobs(state: Json) -> Json:
    source: str = env_get("BATCH_IMPORT", "")
    if source == "":
        return state
    text: str = read_text(source)
    assert len(text.encode()) <= 1048576, "import exceeds 1 MiB"
    incoming: list[Json] = json_array(json_loads(text))
    assert len(incoming) <= 100, "import exceeds 100 requests"
    entries: list[Json] = json_array(state["jobs"])
    for raw in incoming:
        job: Json = normalize_job(raw, state["policy"])
        found: bool = False
        for entry in entries:
            if json_string(entry["job"]["id"]) == json_string(job["id"]):
                assert json_equal(entry["job"], job), "conflicting request ID"
                found = True
        if not found:
            entries.append(new_entry(job))
    assert len(entries) <= 100, "queue is full"
    state["jobs"] = entries
    return state
