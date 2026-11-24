"""Inspect or replay a complete traffic fixture; emit one JSON report and exit 0 or 2."""

# ruff: noqa: BLE001, PLR1711 - structured command boundary and explicit return
from records import digest, parse, problem
from replay import run
from settings import load, snapshot

from py2rust.stdlib import (
    Json,
    env_get,
    json_canonical,
    json_int,
    json_is_null,
    json_string,
    process_exit,
)


def execute() -> Json:
    job: Json = load(env_get("TRAFFIC_CONFIG", "traffic-job.json"))
    mode: str = json_string(job["mode"])
    data: bytes = snapshot(json_string(job["fixture"]), json_int(job["limits"]["fixture_bytes"]))
    decoded: tuple[list[Json], Json] = parse(data, job["limits"])
    rows: list[Json] = decoded[0]
    error: Json = decoded[1]
    result: Json = {
        "version": 1,
        "mode": mode,
        "fixture": {"size": len(data), "sha256": digest(data)},
        "records": rows,
        "replay": None,
        "error": error,
    }
    if json_is_null(error) and mode == "replay":
        replay: Json = run(data, rows, job)
        result["replay"] = replay
        result["error"] = replay["error"]
    result["status"] = "passed" if json_is_null(result["error"]) else "failed"
    return result


def main() -> None:
    result: Json = None
    try:
        result = execute()
    except Exception:
        result = {"version": 1, "status": "failed", "error": problem("invalid_input", "load", -1, 0, "none")}
    print(json_canonical(result))
    if json_string(result["status"]) != "passed":
        process_exit(2)
    return


if __name__ == "__main__":
    main()
