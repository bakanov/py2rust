"""Poll endpoints independently, checkpoint observations, and render health reports."""

import logging
import sys

from model import clock, configuration, observe, setting, status
from storage import load, save, state_path, validate_paths

from py2rust.stdlib import (
    Json,
    WebResponse,
    env_get,
    json_array,
    json_dumps,
    json_float,
    json_int,
    json_is_null,
    json_string,
    log,
    log_configure,
    monotonic,
    pretty,
    sleep,
    web_request,
    write_text_atomic,
)


def measure(endpoint: Json, policy: Json, now: float) -> Json:
    began: float = monotonic()
    code: int = 0
    kind: str = "transport"
    try:
        response: WebResponse = web_request(
            "GET", json_string(endpoint["url"]), b"", {}, json_int(policy["timeout_ms"]), json_int(policy["max_body"])
        )
        code = response.status
        kind = "http"
    except Exception:  # noqa: BLE001 - the compiled profile uses recoverable Exception
        code = 0
    elapsed: float = max(0.0, (monotonic() - began) * 1000.0)
    ok: bool = False
    for accepted in json_array(endpoint["statuses"]):
        if code == json_int(accepted):
            ok = True
    return {"at": now, "status": code, "kind": kind, "ok": ok, "latency_ms": elapsed}


def poll_round(state: Json) -> Json:
    policy: Json = state["policy"]
    records: list[Json] = json_array(state["records"])
    endpoints: list[Json] = json_array(policy["endpoints"])
    for index in range(len(endpoints)):
        now: float = max(clock(), json_float(state["clock"]))
        before: str = status(records[index])
        records[index] = observe(records[index], measure(endpoints[index], policy, now), policy)
        state["records"] = records
        state["clock"] = now
        save(state)
        after: str = status(records[index])
        if before != after:
            log(logging.INFO, json_string(endpoints[index]["id"]) + ": " + before + " -> " + after)
        if env_get("HEALTH_STOP", "") == json_string(endpoints[index]["id"]):
            sys.exit(75)
    return state


def report(state: Json) -> Json:
    records: list[Json] = json_array(state["records"])
    endpoints: list[Json] = json_array(state["policy"]["endpoints"])
    results: list[Json] = []
    healthy: int = 0
    for index in range(len(records)):
        record: Json = records[index]
        current: str = status(record)
        if current == "up":
            healthy = healthy + 1
        down: float = json_float(record["down_seconds"])
        if not json_is_null(record["opened"]):
            down = down + (json_float(state["clock"]) - json_float(record["opened"]))
        results.append(
            {
                "id": endpoints[index]["id"],
                "state": current,
                "checks": record["checks"],
                "failures": record["failures"],
                "down_seconds": down,
                "opened": record["opened"],
                "samples": record["samples"],
                "outages": record["outages"],
            }
        )
    return {"at": state["clock"], "healthy": healthy, "unhealthy": len(results) - healthy, "endpoints": results}


def render_text(result: Json) -> str:
    lines: list[str] = ["Service health at " + str(json_float(result["at"]))]
    for endpoint in json_array(result["endpoints"]):
        line: str = json_string(endpoint["id"]) + ": " + json_string(endpoint["state"])
        line = (
            line + " | checks=" + str(json_int(endpoint["checks"])) + " failures=" + str(json_int(endpoint["failures"]))
        )
        samples: list[Json] = json_array(endpoint["samples"])
        if len(samples) > 0:
            line = line + " last_status=" + str(json_int(samples[-1]["status"]))
            line = line + " latency_ms=" + str(json_float(samples[-1]["latency_ms"]))
        lines.append(line)
    return "\n".join(lines) + "\n"


def main() -> None:
    validate_paths()
    assert env_get("HEALTH_MODE", "run") in ["run", "inspect"], "invalid mode"
    rounds: int = setting("HEALTH_ROUNDS", 1)
    interval: int = setting("HEALTH_INTERVAL", 0)
    assert rounds >= 1 and rounds <= 50 and interval >= 0 and interval <= 60, "invalid polling schedule"
    assert clock() >= 0.0 and clock() <= 253402214400.0, "invalid clock"
    policy: Json = configuration()
    state: Json = load(policy)
    log_configure(logging.INFO)
    if env_get("HEALTH_MODE", "run") == "run":
        for index in range(rounds):
            if index > 0:
                sleep(interval)
            state = poll_round(state)
    result: Json = report(state)
    validate_paths()
    write_text_atomic(state_path() + ".report.json", pretty(result))
    write_text_atomic(state_path() + ".report.txt", render_text(result))
    print(json_dumps({"healthy": result["healthy"], "unhealthy": result["unhealthy"]}))
    if json_int(result["unhealthy"]) > 0:
        sys.exit(1)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


if __name__ == "__main__":
    main()
