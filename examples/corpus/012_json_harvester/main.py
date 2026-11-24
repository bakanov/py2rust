"""Fetch a bounded number of pages and resume from the last committed checkpoint."""

import sys

from model import accept_page, configuration, setting
from storage import load, save, state_path, validate_paths

from py2rust.stdlib import (
    Json,
    WebResponse,
    env_get,
    json_array,
    json_dumps,
    json_int,
    json_is_null,
    json_loads,
    json_string,
    path_exists,
    pretty,
    web_request,
    write_text_atomic,
)


def fetch(url: str, policy: Json) -> Json:
    try:
        response: WebResponse = web_request(
            "GET",
            url,
            b"",
            {"Accept": "application/json"},
            json_int(policy["timeout_ms"]),
            json_int(policy["max_body"]),
        )
        if response.status != 200:
            return {"error": "http", "status": response.status}
        return {"error": "", "status": 200, "text": response.body.decode()}
    except Exception:  # noqa: BLE001 - the compiled profile uses recoverable Exception
        return {"error": "transport", "status": 0}


def run_pages(state: Json, steps: int) -> Json:
    error: Json = None
    fetched: int = 0
    for index in range(steps):
        if json_is_null(state["next"]):
            break
        current: str = json_string(state["next"])
        if len(json_array(state["pages"])) >= json_int(state["policy"]["max_pages"]):
            error = {"kind": "page_budget", "url": current, "status": 0}
            break
        response: Json = fetch(current, state["policy"])
        fetched = fetched + 1
        if json_string(response["error"]) != "":
            error = {"kind": response["error"], "url": current, "status": response["status"]}
            break
        updated: Json = None
        try:
            updated = accept_page(state, json_loads(json_string(response["text"])))
        except Exception:  # noqa: BLE001 - the compiled profile uses recoverable Exception
            error = {"kind": "page", "url": current, "status": 200}
            break
        if env_get("HARVEST_STOP", "") == "before_checkpoint":
            sys.exit(75)
        save(updated)
        state = updated
        if env_get("HARVEST_STOP", "") == "after_checkpoint":
            sys.exit(75)
    return {"state": state, "error": error, "fetched": fetched}


def report(result: Json) -> Json:
    state: Json = result["state"]
    records: list[Json] = json_array(state["records"])
    pages: list[Json] = json_array(state["pages"])
    received: int = 0
    for receipt in pages:
        received = received + json_int(receipt["received"])
    return {
        "complete": json_is_null(state["next"]),
        "next": state["next"],
        "error": result["error"],
        "pages": len(pages),
        "records": records,
        "count": len(records),
        "duplicates": received - len(records),
        "fetched_this_run": result["fetched"],
    }


def main() -> None:
    validate_paths()
    mode: str = env_get("HARVEST_MODE", "run")
    assert mode in ["run", "inspect"], "invalid mode"
    steps: int = setting("HARVEST_STEPS", 10)
    assert steps >= 1 and steps <= 100, "invalid step budget"
    assert env_get("HARVEST_STOP", "") in ["", "before_checkpoint", "after_checkpoint"], "invalid interruption point"
    policy: Json = configuration()
    state: Json = load(policy)
    result: Json = {"state": state, "error": None, "fetched": 0}
    if mode == "run":
        if not path_exists(state_path()):
            save(state)
        result = run_pages(state, steps)
    output: Json = report(result)
    validate_paths()
    write_text_atomic(state_path() + ".report.json", pretty(output))
    print(json_dumps({"complete": output["complete"], "pages": output["pages"], "count": output["count"]}))
    if not json_is_null(output["error"]):
        sys.exit(1)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


if __name__ == "__main__":
    main()
