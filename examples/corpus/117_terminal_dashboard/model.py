"""Strict task snapshots and bounded refresh settings."""

# ruff: noqa: PLR1711 - explicit subset returns
from py2rust.stdlib import (
    Json,
    json_array,
    json_int,
    json_keys,
    json_string,
    terminal_cells,
)


def exact(value: Json, fields: list[str]) -> None:
    assert sorted(json_keys(value)) == sorted(fields), "unexpected fields"
    return


def text(value: Json) -> str:
    return json_string(value)


def label(value: Json, limit: int) -> str:
    result: str = text(value)
    assert result.strip() != "" and len(result) <= limit, "label length or empty label"
    terminal_cells(result)
    return result


def settings(value: Json) -> Json:
    exact(value, ["columns", "refreshes", "interval_ms"])
    assert 1 <= json_int(value["columns"]) <= 200, "column limit"
    assert 1 <= json_int(value["refreshes"]) <= 64, "refresh limit"
    assert 20 <= json_int(value["interval_ms"]) <= 60000, "refresh interval limit"
    assert json_int(value["refreshes"]) * json_int(value["interval_ms"]) <= 3600000, "duration limit"
    return value


def snapshot(value: Json) -> Json:
    exact(value, ["version", "sequence", "title", "tasks"])
    assert json_int(value["version"]) == 1 and json_int(value["sequence"]) >= 0, "snapshot version or sequence"
    label(value["title"], 120)
    tasks: list[Json] = json_array(value["tasks"])
    assert len(tasks) <= 128, "task count limit"
    seen: set[str] = set()
    for task in tasks:
        exact(task, ["id", "label", "state", "done", "total"])
        identifier: str = label(task["id"], 32)
        assert identifier not in seen, "duplicate task id"
        seen.add(identifier)
        label(task["label"], 120)
        state: str = text(task["state"])
        assert state in ["queued", "running", "done", "failed"], "unknown task state"
        done: int = json_int(task["done"])
        total: int = json_int(task["total"])
        assert 0 <= done <= total <= 1000000000, "progress range"
        assert state != "queued" or done == 0, "queued task has progress"
        assert state != "done" or done == total, "completed task has remaining work"
    return value


def empty() -> Json:
    return {"version": 1, "sequence": 0, "title": "Waiting for tasks", "tasks": []}
