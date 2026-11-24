"""Run a bounded pass of due GET requests, with recoverable checkpoints and results."""

import sys

from model import clock, configuration, delay
from quota import finish
from storage import import_jobs, load, save, state_path, validate_paths

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_dumps,
    json_float,
    json_int,
    json_loads,
    json_string,
    pretty,
    write_text_atomic,
)


def stop(point: str) -> None:
    if env_get("BATCH_STOP", "") == point:
        sys.exit(75)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def blocked(state: Json) -> str:
    for entry in json_array(state["jobs"]):
        if json_string(entry["state"]) == "inflight":
            return "unacknowledged request"
    return json_string(state["quota"]["blocked"])


def recover(state: Json) -> Json:
    now: float = clock()
    assert now >= json_float(state["last_at"]), "clock moved backwards"
    entries: list[Json] = json_array(state["jobs"])
    for index in range(len(entries)):
        entry: Json = entries[index]
        if json_string(entry["state"]) == "inflight":
            entry["state"] = "failed"
            entry["error"] = "uncertain request"
            entry["next_at"] = 0.0
            if json_int(entry["attempts"]) < json_int(state["policy"]["attempts"]):
                entry["state"] = "pending"
                entry["next_at"] = now + delay(state["policy"], json_int(entry["attempts"]))
            entries[index] = entry
    quota: Json = state["quota"]
    quota["blocked"] = ""
    state["quota"] = quota
    state["jobs"] = entries
    state["last_at"] = now
    save(state)
    return state


def execute(state: Json, limit: int) -> Json:
    entries: list[Json] = json_array(state["jobs"])
    count: int = 0
    for index in range(len(entries)):
        now: float = clock()
        assert now >= json_float(state["last_at"]), "clock moved backwards"
        if blocked(state) != "" or now < json_float(state["quota"]["not_before"]) or count == limit:
            break
        entry: Json = entries[index]
        if json_string(entry["state"]) != "pending" or now < json_float(entry["next_at"]):
            continue
        entry["state"] = "inflight"
        entry["attempts"] = json_int(entry["attempts"]) + 1
        entry["last_at"] = now
        entries[index] = entry
        state["jobs"] = entries
        state["last_at"] = now
        save(state)
        stop("after_claim")
        quota: Json = state["quota"]
        outcome: Json = finish(entry, state["policy"], quota)
        entries[index] = outcome["entry"]
        stop("after_response")
        state["quota"] = outcome["quota"]
        state["jobs"] = entries
        state["last_at"] = entries[index]["last_at"]
        save(state)
        stop("after_checkpoint")
        count = count + 1
    return state


def report(state: Json) -> Json:
    counts: dict[str, int] = {"pending": 0, "inflight": 0, "complete": 0, "failed": 0}
    for entry in json_array(state["jobs"]):
        name: str = json_string(entry["state"])
        counts[name] = counts[name] + 1
    return {
        "counts": counts,
        "blocked": blocked(state),
        "not_before": state["quota"]["not_before"],
        "jobs": state["jobs"],
    }


def main() -> None:
    validate_paths()
    mode: str = env_get("BATCH_MODE", "run")
    assert mode in ["run", "inspect", "recover"], "unknown mode"
    limit: int = json_int(json_loads(env_get("BATCH_LIMIT", "100")))
    assert limit >= 1 and limit <= 100, "invalid pass limit"
    state: Json = load(configuration())
    if mode == "run":
        assert clock() >= json_float(state["last_at"]), "clock moved backwards"
        state = import_jobs(state)
        save(state)
        state = execute(state, limit)
    elif mode == "recover":
        state = recover(state)
    result: Json = report(state)
    validate_paths()
    write_text_atomic(state_path() + ".report.json", pretty(result))
    print(json_dumps(result["counts"]))
    if json_string(result["blocked"]) != "" or json_int(result["counts"]["failed"]) > 0:
        sys.exit(1)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


if __name__ == "__main__":
    main()
