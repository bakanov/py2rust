"""Two-phase staging, exact recovery states and a separately resumable reverse pass."""

import sys
import time

from checks import digest, document, parents, present, signature
from planning import keys, names

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_bool,
    json_equal,
    json_int,
    json_string,
    path_join,
    path_parent,
    pretty,
    rename_no_replace,
    sync_directory,
    write_text_atomic,
)


def checkpoint(label: str, step: int) -> None:
    if env_get("RENAME_PAUSE", "") == label + ":" + str(step):
        print("PAUSED", label, step)
        time.sleep(60.0)
    if env_get("RENAME_STOP", "") == label + ":" + str(step):
        print("INTERRUPTED", label, step)
        sys.exit(75)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def operations(envelope: Json, reverse: bool) -> list[Json]:
    plan: Json = envelope["plan"]
    first: list[Json] = []
    second: list[Json] = []
    index: int = 0
    for row in json_array(plan["rows"]):
        source: str = json_string(row["source"])
        target: str = json_string(row["target"])
        if source != target:
            temporary: str = ".py2rust-rename-" + json_string(envelope["id"]) + "-" + str(index)
            if path_parent(source) != ".":
                temporary = path_join(path_parent(source), temporary)
            first.append({"source": target if reverse else source, "target": temporary, "signature": row["signature"]})
            second.append({"source": temporary, "target": source if reverse else target, "signature": row["signature"]})
        index = index + 1
    first.extend(second)
    return first


def state(envelope: Json, reverse: bool, step: int) -> dict[str, Json]:
    expected: dict[str, Json] = {}
    for row in json_array(envelope["plan"]["rows"]):
        name: str = json_string(row["target"] if reverse else row["source"])
        expected[name] = row["signature"]
    index: int = 0
    for operation in operations(envelope, reverse):
        if index < step:
            del expected[json_string(operation["source"])]
            expected[json_string(operation["target"])] = operation["signature"]
        index = index + 1
    return expected


def matches(envelope: Json, reverse: bool, step: int) -> bool:
    plan: Json = envelope["plan"]
    root: str = json_string(plan["root"])
    expected: dict[str, Json] = state(envelope, reverse, step)
    touched: set[str] = set(names(plan))
    for operation in operations(envelope, reverse):
        touched.add(json_string(operation["target"]))
    for name in touched:
        path: str = path_join(root, name)
        if name in expected:
            if not present(path) or not json_equal(signature(path, json_int(plan["max_bytes"])), expected[name]):
                return False
        elif present(path):
            return False
    return True


def save(path: str, receipt: Json) -> None:
    write_text_atomic(path, pretty({"checksum": digest(receipt), "receipt": receipt}))
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def execute(envelope: Json, journal_path: str, reverse: bool) -> Json:
    plan: Json = envelope["plan"]
    root: str = json_string(plan["root"])
    identifier: str = json_string(envelope["id"])
    steps: list[Json] = operations(envelope, reverse)
    receipt: Json = {"version": 1, "id": identifier, "reverse": reverse, "step": 0, "complete": False}
    if present(journal_path):
        saved: Json = document(journal_path, 4096)
        keys(saved, ["checksum", "receipt"])
        receipt = saved["receipt"]
        keys(receipt, ["version", "id", "reverse", "step", "complete"])
        assert json_string(saved["checksum"]) == digest(receipt), "journal checksum mismatch"
        assert (
            json_int(receipt["version"]) == 1 and json_string(receipt["id"]) == identifier
        ), "journal belongs to another plan"
        if json_bool(receipt["reverse"]) != reverse:
            assert reverse and json_bool(
                receipt["complete"]
            ), "finish forward recovery before reversing; reversed plans cannot reapply"
            assert json_int(receipt["step"]) == len(steps), "incomplete forward journal"
            assert matches(envelope, True, 0), "reverse conflict: entries changed"
            receipt = {"version": 1, "id": identifier, "reverse": True, "step": 0, "complete": False}
            save(journal_path, receipt)
    else:
        assert not reverse, "reverse requires an applied journal"
        assert matches(envelope, False, 0), "preflight conflict: entries or destinations changed"
        save(journal_path, receipt)
    step: int = json_int(receipt["step"])
    assert step >= 0 and step <= len(steps), "invalid journal progress"
    assert not json_bool(receipt["complete"]) or step == len(steps), "invalid completed journal"
    checkpoint("journal", step)
    if not matches(envelope, reverse, step):
        assert not json_bool(receipt["complete"]) and step < len(steps), "completed tree changed"
        assert matches(
            envelope, reverse, step + 1
        ), "recovery conflict: tree matches neither recorded nor pending state"
        operation: Json = steps[step]
        sync_directory(path_join(root, path_parent(json_string(operation["source"]))))
        sync_directory(path_join(root, path_parent(json_string(operation["target"]))))
        step = step + 1
        receipt["step"] = step
        save(journal_path, receipt)
    while step < len(steps):
        assert json_equal(parents(root, names(plan)), plan["parents"]), "parent identity changed"
        operation: Json = steps[step]
        source: str = path_join(root, json_string(operation["source"]))
        target: str = path_join(root, json_string(operation["target"]))
        assert json_equal(signature(source, json_int(plan["max_bytes"])), operation["signature"]), "source changed"
        checkpoint("before", step)
        rename_no_replace(source, target)
        checkpoint("renamed", step)
        sync_directory(path_parent(source))
        sync_directory(path_parent(target))
        checkpoint("synced", step)
        step = step + 1
        receipt["step"] = step
        save(journal_path, receipt)
        checkpoint("saved", step)
    assert matches(envelope, reverse, step), "final tree changed"
    receipt["complete"] = True
    save(journal_path, receipt)
    return {"id": identifier, "action": "reversed" if reverse else "applied", "moves": len(steps) // 2}
