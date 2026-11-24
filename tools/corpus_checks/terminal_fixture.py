"""Independent task-state oracle, grapheme widths and exact terminal export inspection."""

from __future__ import annotations

import itertools
import json
from pathlib import Path

from uniseg.graphemecluster import grapheme_clusters
from wcwidth import wcswidth

from .population_fixture import canonical, digest

__all__ = ["canonical", "digest", "files_at", "fit", "inspect", "lines", "observe", "save", "snapshot", "task", "width"]


def save(path: Path, value: object) -> None:
    path.write_bytes(canonical(value))
    return  # noqa: PLR1711


def files_at(path: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in path.iterdir() if p.is_file()}


def task(identifier: str, state: str = "running", done: int = 5, total: int = 10, label: str = "") -> dict:
    return {"id": identifier, "label": label or identifier, "state": state, "done": done, "total": total}


def snapshot(tasks: list | None = None, sequence: int = 1, title: str = "Network tasks") -> dict:
    return {
        "version": 1,
        "sequence": sequence,
        "title": title,
        "tasks": (
            tasks
            if tasks is not None
            else [
                task("upload", label="Upload 東京 screenshots"),
                task("search", "done", 20, 20, "Index saved notes"),
                task("queue", "queued", 0, 100, "Wait for 👩🏽‍💻 review"),
                task("retry", "failed", 3, 9, "Retry transfer"),
                task("watch", "running", 0, 0, "Watch évents 🇯🇵"),
            ]
        ),
    }


def parts(text: str) -> list[tuple[str, int]]:
    result = []
    for cluster in grapheme_clusters(text):
        cells = wcswidth(cluster, unicode_version="16.0.0")
        assert cells >= 0
        result.append((cluster if cells else "◌" + cluster, max(1, cells)))
    return result


def width(text: str) -> int:
    return sum(cells for _, cells in parts(text))


def fit(text: str, columns: int) -> str:
    segments = parts(text)
    sums = [0, *itertools.accumulate(cells for _, cells in segments)]
    clipped = sums[-1] > columns
    budget = max(0, columns - int(clipped))
    index = max(i for i, used in enumerate(sums) if used <= budget)
    content = "".join(cluster for cluster, _ in segments[:index]) + ("~" if clipped and columns else "")
    return content + " " * (columns - sums[index] - int(clipped and bool(columns)))


def lines(state: dict | None, columns: int, rows: int, index: int, count: int, status: str) -> list[str]:
    source = snapshot([], 0, "Waiting for tasks") if state is None else state
    tasks = source["tasks"]
    output = [fit(source["title"], columns)]
    if rows == 1:
        return output
    counts = {name: sum(t["state"] == name for t in tasks) for name in ["running", "done", "failed"]}
    output.append(
        fit(
            f'{len(tasks)} tasks | {counts["running"]} running | {counts["done"]} done | {counts["failed"]} failed',
            columns,
        )
    )
    if rows == 2:
        return output
    if columns >= 50 and rows >= 5:
        output.append(fit("ID       STATE   DONE  PROGRESS / TASK", columns))
    shown = tasks[: max(0, rows - len(output) - 1)]
    for item in shown:
        symbol = {"queued": ".", "running": ">", "done": "+", "failed": "!"}[item["state"]]
        percentage = 100 if item["state"] == "done" else item["done"] * 100 // item["total"] if item["total"] else -1
        percent = " --%" if percentage == -1 else fit(str(percentage) + "%", 4)
        if columns == 1:
            output.append(symbol)
        elif columns < 24:
            output.append(fit(symbol + " " + item["label"], columns))
        elif columns < 50:
            output.append(symbol + " " + percent + " " + fit(item["label"], columns - 7))
        else:
            length = min(20, columns // 6)
            filled = max(0, percentage) * length // 100
            bar = "#" * filled + ("?" if percentage == -1 else "-") * (length - filled)
            output.append(
                fit(item["id"], 8)
                + " "
                + fit(item["state"], 7)
                + " "
                + percent
                + " ["
                + bar
                + "] "
                + fit(item["label"], columns - length - 25)
            )
    output.append(fit(f"{len(tasks) - len(shown)} hidden | frame {index}/{count} | {status}", columns))
    assert len(output) <= rows and all(width(line) == columns for line in output)
    return output


def unique_object(pairs: list) -> dict:
    result = {}
    for key, value in pairs:
        assert key not in result
        result[key] = value
    return result


def valid_label(text: object, maximum: int) -> bool:
    if type(text) is not str or not text.strip() or len(text) > maximum:
        return False
    bad = set(range(32)) | set(range(127, 160)) | {0x061C, 0x200E, 0x200F, 0x2028, 0x2029}
    bad |= set(range(0x202A, 0x202F)) | set(range(0x2066, 0x206A))
    return all(ord(c) not in bad and not 0xD800 <= ord(c) <= 0xDFFF for c in text)


def observe(previous: dict | None, raw: bytes, readable: bool) -> tuple[dict | None, str]:
    if not readable:
        return previous, "unreadable"
    try:
        value = json.loads(raw.decode(), object_pairs_hook=unique_object)
        assert type(value) is dict and value.keys() == {"version", "sequence", "title", "tasks"}
        assert type(value["version"]) is int and value["version"] == 1
        assert type(value["sequence"]) is int and 0 <= value["sequence"] < 2**63
        assert valid_label(value["title"], 120)
        assert type(value["tasks"]) is list and len(value["tasks"]) <= 128
        seen = set()
        for item in value["tasks"]:
            assert type(item) is dict and item.keys() == {"id", "label", "state", "done", "total"}
            assert valid_label(item["id"], 32) and valid_label(item["label"], 120)
            assert item["id"] not in seen
            seen.add(item["id"])
            assert item["state"] in ["queued", "running", "done", "failed"]
            assert (
                type(item["done"]) is int and type(item["total"]) is int and 0 <= item["done"] <= item["total"] <= 10**9
            )
            assert item["state"] != "queued" or item["done"] == 0
            assert item["state"] != "done" or item["done"] == item["total"]
        if previous is not None:
            if value["sequence"] < previous["sequence"]:
                return previous, "older sequence"
            if value["sequence"] == previous["sequence"]:
                return previous, "unchanged" if value == previous else "conflicting sequence"
        return value, "updated"
    except (ValueError, AssertionError, KeyError, TypeError, UnicodeError):
        return previous, "invalid snapshot"


def inspect(directory: Path) -> dict:
    exported = files_at(directory)
    assert set(exported) == {
        "archive.json",
        "snapshot.json",
        "watch.json",
        "replay.json",
        "report.json",
        "transcript.txt",
        "manifest.json",
    }
    archive = json.loads(exported["archive.json"])
    assert archive.keys() == {"version", "settings", "events", "signal"} and archive["version"] == 1
    options = archive["settings"]
    assert options.keys() == {"columns", "refreshes", "interval_ms"}
    assert all(type(v) is int for v in options.values())
    assert 1 <= options["columns"] <= 200 and 1 <= options["refreshes"] <= 64 and 20 <= options["interval_ms"] <= 60000
    assert options["refreshes"] * options["interval_ms"] <= 3600000
    assert type(archive["signal"]) is int and archive["signal"] in [0, 2, 15]
    assert len(archive["events"]) <= options["refreshes"]
    assert len(archive["events"]) == options["refreshes"] or archive["signal"]
    state, transcript, errors = None, [], 0
    for index, record in enumerate(archive["events"], 1):
        assert record.keys() == {"source_hex", "readable", "status", "columns", "rows", "lines"}
        assert type(record["readable"]) is bool
        raw = bytes.fromhex(record["source_hex"])
        assert len(raw) <= 65536 and raw.hex() == record["source_hex"] and (record["readable"] or not raw)
        state, status = observe(state, raw, record["readable"])
        assert status == record["status"]
        errors += status not in ["updated", "unchanged"]
        assert type(record["columns"]) is int and type(record["rows"]) is int
        assert 1 <= record["columns"] <= options["columns"] and 1 <= record["rows"] <= 132
        assert record["lines"] == lines(state, record["columns"], record["rows"], index, options["refreshes"], status)
        transcript.append("\n".join(record["lines"]) + "\n\n")
    assert exported["transcript.txt"] == "".join(transcript).encode()
    report = {
        "version": 1,
        "frames": len(archive["events"]),
        "errors": errors,
        "signal": archive["signal"],
        "last": state,
    }
    assert canonical(json.loads(exported["report.json"])) == canonical(report)
    assert exported["snapshot.json"] == canonical(snapshot([], 0, "Waiting for tasks") if state is None else state)
    assert exported["watch.json"] == canonical(
        {"version": 1, "mode": "watch", "input": "snapshot.json", "output": "watched", **options}
    )
    assert exported["replay.json"] == canonical(
        {"version": 1, "mode": "replay", "input": "archive.json", "output": "replayed"}
    )
    assert exported["archive.json"] == canonical(archive)
    assert exported["manifest.json"] == canonical(
        {name: {"bytes": len(raw), "sha256": digest(raw)} for name, raw in exported.items() if name != "manifest.json"}
    )
    return archive
