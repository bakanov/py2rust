"""An append-only receipt identity and atomic pending/done transitions."""

import sys

from config import state_path, validate_paths

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_dumps,
    json_int,
    json_keys,
    json_loads,
    json_string,
    path_exists,
    pretty,
    read_text,
    regex_fullmatch,
    write_text_atomic,
)


def identifier(value: Json) -> str:
    name: str = json_string(value)
    assert regex_fullmatch("[A-Za-z0-9_-]{1,40}", name), "invalid job ID"
    return name


def payload_valid(value: Json, policy: Json) -> None:
    assert len(json_dumps(value).encode()) <= json_int(policy["max_payload"]), "job payload exceeds limit"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def retained_policy(policy: Json) -> Json:
    return {"max_jobs": policy["max_jobs"], "max_payload": policy["max_payload"]}


def validate(state: Json, policy: Json) -> None:
    assert json_keys(state) == ["format", "jobs", "next_sequence", "policy"], "invalid snapshot fields"
    assert json_int(state["format"]) == 1, "unsupported snapshot format"
    saved: Json = state["policy"]
    assert json_keys(saved) == ["max_jobs", "max_payload"], "invalid stored policy"
    assert json_int(saved["max_jobs"]) == json_int(policy["max_jobs"]), "retained capacity changed"
    assert json_int(saved["max_payload"]) == json_int(policy["max_payload"]), "payload policy changed"
    jobs: list[Json] = json_array(state["jobs"])
    assert len(jobs) <= json_int(policy["max_jobs"]), "snapshot exceeds retained capacity"
    assert json_int(state["next_sequence"]) == len(jobs) + 1, "invalid next sequence"
    ids: set[str] = set()
    for index in range(len(jobs)):
        job: Json = jobs[index]
        assert json_keys(job) == ["id", "payload", "sequence", "state"], "invalid job fields"
        name: str = identifier(job["id"])
        assert name not in ids, "duplicate stored ID"
        ids.add(name)
        assert json_int(job["sequence"]) == index + 1, "noncontiguous receipt sequence"
        assert json_string(job["state"]) in ["pending", "done"], "invalid job state"
        payload_valid(job["payload"], policy)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def load(policy: Json) -> Json:
    validate_paths()
    if not path_exists(state_path()):
        return {"format": 1, "policy": retained_policy(policy), "next_sequence": 1, "jobs": []}
    text: str = read_text(state_path())
    assert len(text.encode()) <= 8388608, "snapshot exceeds 8 MiB"
    state: Json = json_loads(text)
    validate(state, policy)
    return state


def fault(boundary: str) -> None:
    if env_get("BROKER_STOP", "") == boundary:
        sys.exit(75)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def save(state: Json, policy: Json) -> None:
    validate(state, policy)
    text: str = pretty(state)
    assert len(text.encode()) <= 8388608, "snapshot exceeds 8 MiB"
    validate_paths()
    fault("before_checkpoint")
    write_text_atomic(state_path(), text)
    fault("after_checkpoint")
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def find(state: Json, name: str) -> int:
    jobs: list[Json] = json_array(state["jobs"])
    for index in range(len(jobs)):
        if json_string(jobs[index]["id"]) == name:
            return index
    return -1
