"""One atomic state file binds the latest accepted snapshot to its retained events."""

import sys

from changes import hidden, mask, nodes, pointer
from model import ignored_paths

from py2rust.stdlib import (
    Json,
    datetime_iso,
    datetime_parse,
    env_get,
    json_array,
    json_bool,
    json_equal,
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
    pretty,
    read_text,
    write_text_atomic,
)


def state_path() -> str:
    return env_get("WATCH_STATE", "watch-state.json")


def validate_paths() -> None:
    paths: list[str] = [
        env_get("WATCH_CONFIG", "watch.json"),
        state_path(),
        state_path() + ".report.json",
        state_path() + ".report.txt",
    ]
    canonical: list[str] = []
    for index in range(len(paths)):
        value: str = paths[index]
        if index > 0:
            assert not path_is_symlink(value), "state and reports must not be symlinks"
        normalized: str = path_join(path_resolve(path_parent(value)), path_name(value))
        assert normalized not in canonical, "state and report paths overlap"
        canonical.append(normalized)
        for previous in range(index):
            if path_exists(value) and path_exists(paths[previous]):
                assert not path_same(value, paths[previous]), "state and report paths alias"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def stop(point: str) -> None:
    if env_get("WATCH_STOP", "") == point:
        sys.exit(75)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def save(state: Json) -> None:
    text: str = pretty(state)
    assert len(text.encode()) <= 8388608, "state exceeds 8 MiB"
    stop("before_checkpoint")
    write_text_atomic(state_path(), text)
    stop("after_checkpoint")
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def load(policy: Json) -> Json:
    if not path_exists(state_path()):
        return {
            "version": 1,
            "policy": policy,
            "ready": False,
            "snapshot": None,
            "checks": 0,
            "last_at": "",
            "next_id": 1,
            "history": [],
            "error": None,
        }
    text: str = read_text(state_path())
    assert len(text.encode()) <= 8388608, "state exceeds 8 MiB"
    state: Json = json_loads(text)
    assert json_keys(state) == [
        "checks",
        "error",
        "history",
        "last_at",
        "next_id",
        "policy",
        "ready",
        "snapshot",
        "version",
    ], "invalid state fields"
    assert json_int(state["version"]) == 1 and json_equal(state["policy"], policy), "state policy mismatch"
    checks: int = json_int(state["checks"])
    next_id: int = json_int(state["next_id"])
    assert checks >= 0 and checks <= 1000000000 and next_id >= 1 and next_id <= checks + 1, "invalid counters"
    if json_bool(state["ready"]):
        assert checks >= 1 and next_id <= checks, "events exceed accepted observations"
    last: str = json_string(state["last_at"])
    assert (checks == 0 and last == "") or (
        checks > 0 and datetime_iso(datetime_parse(last)) == last
    ), "invalid observation time"
    paths: list[str] = ignored_paths(policy)
    nodes(state["snapshot"], 0)
    assert json_equal(mask(state["snapshot"], "", paths), state["snapshot"]), "snapshot contains ignored fields"
    history: list[Json] = json_array(state["history"])
    assert len(history) == min(next_id - 1, json_int(policy["retain"])), "invalid history length"
    expected: int = next_id - len(history)
    previous_at: str = ""
    for event in history:
        assert (
            json_keys(event) == ["at", "changes", "id"] and json_int(event["id"]) == expected
        ), "invalid event identity"
        at: str = json_string(event["at"])
        assert datetime_iso(datetime_parse(at)) == at and at >= previous_at and at <= last, "invalid event time"
        entries: list[Json] = json_array(event["changes"])
        assert len(entries) >= 1 and len(entries) <= json_int(policy["max_changes"]), "invalid change count"
        seen: set[str] = set()
        for change in entries:
            assert json_keys(change) == ["after", "before", "op", "path"], "invalid change fields"
            path: str = pointer(json_string(change["path"]))
            operation: str = json_string(change["op"])
            assert path not in seen and not hidden(path, paths), "duplicate or ignored change path"
            seen.add(path)
            assert operation in ["add", "remove", "replace"], "invalid change operation"
            if operation == "add":
                assert json_is_null(change["before"]), "addition has a previous value"
            elif operation == "remove":
                assert json_is_null(change["after"]), "removal has a following value"
            else:
                assert not json_equal(change["before"], change["after"]), "replacement has no change"
            for key in ["before", "after"]:
                nodes(change[key], 0)
                assert json_equal(mask(change[key], path, paths), change[key]), "event contains ignored fields"
        expected = expected + 1
        previous_at = at
    if not json_bool(state["ready"]):
        assert json_is_null(state["snapshot"]) and next_id == 1, "uninitialized state has data"
    if not json_is_null(state["error"]):
        assert json_keys(state["error"]) == ["kind", "status"], "invalid failure fields"
        assert json_string(state["error"]["kind"]) in [
            "transport",
            "http",
            "json",
            "change_budget",
        ], "invalid failure kind"
        status: int = json_int(state["error"]["status"])
        assert status == 0 or (status >= 100 and status <= 599), "invalid failure status"
        kind: str = json_string(state["error"]["kind"])
        assert (
            (kind == "transport" and status == 0)
            or (kind == "http" and status >= 100 and status != 200)
            or (kind in ["json", "change_budget"] and status == 200)
        ), "failure kind and status disagree"
    return state
