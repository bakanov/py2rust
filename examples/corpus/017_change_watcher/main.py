"""Poll bounded snapshots, commit each observation and regenerate readable reports."""

import sys
import time

from changes import difference, hidden, mask, nodes, pointer
from model import clock, configuration, ignored_paths, setting
from storage import load, save, state_path, validate_paths

from py2rust.stdlib import (
    Json,
    WebResponse,
    env_get,
    json_array,
    json_bool,
    json_dumps,
    json_float,
    json_int,
    json_is_null,
    json_loads,
    json_string,
    pretty,
    web_request,
    write_text_atomic,
)


def observe(state: Json, policy: Json, now: str) -> Json:
    result: Json = {
        "version": 1,
        "policy": policy,
        "ready": state["ready"],
        "snapshot": state["snapshot"],
        "checks": json_int(state["checks"]) + 1,
        "last_at": now,
        "next_id": state["next_id"],
        "history": state["history"],
        "error": {"kind": "transport", "status": 0},
    }
    try:
        headers: dict[str, str] = {"Accept": "application/json", "Accept-Encoding": "identity"}
        response: WebResponse = web_request(
            "GET",
            json_string(policy["url"]),
            b"",
            headers,
            json_int(policy["timeout_ms"]),
            json_int(policy["max_body"]),
        )
        result["error"] = {"kind": "http", "status": response.status}
        assert response.status == 200, "expected status 200"
        result["error"] = {"kind": "json", "status": response.status}
        assert response.headers.get("content-encoding", "identity").lower() == "identity", "encoded JSON rejected"
        current: Json = json_loads(response.body.decode())
        nodes(current, 0)
        current = mask(current, "", ignored_paths(policy))
        changes: list[Json] = []
        if json_bool(state["ready"]):
            for change in difference(state["snapshot"], current, ""):
                path: str = pointer(json_string(change["path"]))
                if not hidden(path, ignored_paths(policy)):
                    changes.append(change)
        result["error"] = {"kind": "change_budget", "status": response.status}
        assert len(changes) <= json_int(policy["max_changes"]), "change budget exceeded"
        retained: list[Json] = json_array(state["history"]).copy()
        if len(changes) > 0:
            retained.append({"id": state["next_id"], "at": now, "changes": changes})
            result["next_id"] = json_int(state["next_id"]) + 1
        history: list[Json] = []
        for index in range(max(0, len(retained) - json_int(policy["retain"])), len(retained)):
            history.append(retained[index])
        result["history"] = history
        result["ready"] = True
        result["snapshot"] = current
        result["error"] = None
    except Exception:  # noqa: BLE001 - rejected observations preserve the accepted snapshot
        return result
    return result


def render(state: Json) -> str:
    text: str = "JSON change watcher\nURL: " + json_string(state["policy"]["url"]) + "\n"
    text = (
        text
        + "Checks: "
        + str(json_int(state["checks"]))
        + "\nLast observation: "
        + json_string(state["last_at"])
        + "\n"
    )
    text = text + "Last failure: " + json_dumps(state["error"]) + "\n"
    for event in json_array(state["history"]):
        text = text + "\nEvent " + str(json_int(event["id"])) + " at " + json_string(event["at"]) + "\n"
        for change in json_array(event["changes"]):
            text = text + json_string(change["op"]) + " " + json_dumps(change["path"]) + "\n"
            text = (
                text + "  before: " + json_dumps(change["before"]) + "\n  after:  " + json_dumps(change["after"]) + "\n"
            )
    return text


def main() -> None:
    mode: str = env_get("WATCH_MODE", "run")
    rounds: int = setting("WATCH_ROUNDS", 1)
    assert mode in ["run", "inspect"] and rounds >= 1 and rounds <= 100, "invalid execution settings"
    assert env_get("WATCH_STOP", "") in ["", "before_checkpoint", "after_checkpoint"], "invalid interruption point"
    policy: Json = configuration()
    validate_paths()
    state: Json = load(policy)
    failed: bool = False
    if mode == "run":
        for index in range(rounds):
            now: str = clock()
            assert now >= json_string(state["last_at"]), "observation clock moved backward"
            assert json_int(state["checks"]) < 1000000000, "observation counter exhausted"
            updated: Json = observe(state, policy, now)
            save(updated)
            state = updated
            if not json_is_null(state["error"]):
                failed = True
            if index + 1 < rounds:
                time.sleep(json_float(policy["interval_ms"]) * 0.001)
    write_text_atomic(state_path() + ".report.json", pretty(state))
    write_text_atomic(state_path() + ".report.txt", render(state))
    print(
        json_dumps(
            {
                "checks": state["checks"],
                "ready": state["ready"],
                "events": json_int(state["next_id"]) - 1,
                "retained": len(json_array(state["history"])),
                "error": state["error"],
            }
        )
    )
    if failed:
        sys.exit(1)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


if __name__ == "__main__":
    main()
