"""Independent mutable-tree oracle, exact-value round trips and guarded publication checks."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import random
import re
import selectors
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .common import Application
from .csv_json import canonical


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def pointer(parts: tuple[str, ...]) -> str:
    return "".join("/" + token.replace("~", "~0").replace("/", "~1") for token in parts)


def count(value: object) -> int:
    pending = [value]
    result = 0
    while pending:
        item = pending.pop()
        result += 1
        if isinstance(item, dict):
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
    return result


def difference(before: object, after: object) -> dict:
    changes = []
    pending = [((), before, after, "compare")]
    while pending:
        parts, old, new, operation = pending.pop()
        if operation != "compare":
            changes.append({"op": operation, "path": pointer(parts), "before": old, "after": new})
            continue
        if canonical(old) == canonical(new):
            continue
        work = []
        if isinstance(old, dict) and isinstance(new, dict):
            for key in sorted(old.keys() | new.keys()):
                kind = "add" if key not in old else "remove" if key not in new else "compare"
                work.append(((*parts, key), old.get(key), new.get(key), kind))
        elif isinstance(old, list) and isinstance(new, list):
            work.extend(((*parts, str(i)), old[i], new[i], "compare") for i in range(min(len(old), len(new))))
            work.extend(((*parts, str(i)), old[i], None, "remove") for i in reversed(range(len(new), len(old))))
            work.extend(((*parts, str(i)), None, new[i], "add") for i in range(len(old), len(new)))
        else:
            work.append((parts, old, new, "replace"))
        pending.extend(reversed(work))
    return envelope(before, after, changes)


def envelope(before: object, after: object, changes: list[dict]) -> dict:
    return {"version": 1, "base_sha256": digest(before), "target_sha256": digest(after), "changes": changes}


def apply(before: object, patch: dict) -> object:
    assert digest(before) == patch["base_sha256"]
    result = copy.deepcopy(before)
    for change in patch["changes"]:
        path, operation = change["path"], change["op"]
        assert path == "" or path.startswith("/")
        assert re.fullmatch(r"([^~]|~[01])*", path)
        parts = [token.replace("~1", "/").replace("~0", "~") for token in path[1:].split("/")] if path else []
        if not parts:
            assert operation == "replace" and canonical(result) == canonical(change["before"])
            result = copy.deepcopy(change["after"])
            continue
        parent = result
        for token in parts[:-1]:
            parent = parent[int(token)] if isinstance(parent, list) else parent[token]
        key = int(parts[-1]) if isinstance(parent, list) else parts[-1]
        if operation != "add":
            assert canonical(parent[key]) == canonical(change["before"])
        if operation == "remove":
            del parent[key]
        elif operation == "replace":
            parent[key] = copy.deepcopy(change["after"])
        elif isinstance(parent, list):
            assert 0 <= key <= len(parent)
            parent.insert(key, copy.deepcopy(change["after"]))
        else:
            assert key not in parent
            parent[key] = copy.deepcopy(change["after"])
    assert digest(result) == patch["target_sha256"]
    return result


def undo(patch: dict) -> dict:
    return {
        "version": 1,
        "base_sha256": patch["target_sha256"],
        "target_sha256": patch["base_sha256"],
        "changes": [
            {
                "op": {"add": "remove", "remove": "add", "replace": "replace"}[row["op"]],
                "path": row["path"],
                "before": row["after"],
                "after": row["before"],
            }
            for row in reversed(patch["changes"])
        ],
    }


@dataclass
class Fixture:
    work: Path
    config: dict
    base: object
    incoming: object

    @property
    def output(self) -> Path:
        return self.work / "output"

    @property
    def path(self) -> Path:
        return self.work / "patch-job.json"

    def save(self) -> None:
        self.path.write_text(json.dumps(self.config, ensure_ascii=False))
        return  # noqa: PLR1711

    def settings(self, mode: str = "write", **extra: str) -> dict[str, str]:
        return {"PATCH_CONFIG": str(self.path), "PATCH_MODE": mode, **extra}


def fixture(
    directory: Path, name: str, base: object, incoming: object, action: str = "diff", **changes: object
) -> Fixture:
    work = directory / name
    work.mkdir(parents=True)
    config = {
        "action": action,
        "base": "base.json",
        "target" if action == "diff" else "patch": "incoming.json",
        "output": "output",
        "max_nodes": 20000,
        "max_changes": 2000,
    }
    config.update(changes)
    fix = Fixture(work, config, copy.deepcopy(base), copy.deepcopy(incoming))
    fix.save()
    (work / "base.json").write_text(json.dumps(base, ensure_ascii=False, indent=2) + "\n")
    (work / "incoming.json").write_text(json.dumps(incoming, ensure_ascii=False, indent=2) + "\n")
    return fix


def expected(fix: Fixture) -> tuple[dict, dict[str, bytes]]:
    patch = difference(fix.base, fix.incoming) if fix.config["action"] == "diff" else fix.incoming
    target = apply(fix.base, patch)
    inverse = undo(patch)
    assert canonical(apply(target, inverse)) == canonical(fix.base)
    report = {
        "action": fix.config["action"],
        "base_sha256": digest(fix.base),
        "target_sha256": digest(target),
        "base_nodes": count(fix.base),
        "target_nodes": count(target),
        "changes": len(patch["changes"]),
        "operations": {
            name: sum(row["op"] == name for row in patch["changes"]) for name in ["add", "remove", "replace"]
        },
    }
    files = {"patch.json": patch} if fix.config["action"] == "diff" else {"result.json": target, "undo.json": inverse}
    return report, {
        name: (canonical(value) + ("" if name == "result.json" else "\n")).encode() for name, value in files.items()
    }


def bundle(fix: Fixture, report: dict, files: dict[str, bytes]) -> None:
    assert {p.name for p in fix.output.iterdir()} == {"report.json", *files}
    assert json.loads((fix.output / "report.json").read_bytes()) == report
    for name, data in files.items():
        assert (fix.output / name).read_bytes() == data, name
    return  # noqa: PLR1711


def run(app: Application, fix: Fixture, timeout: int = 30) -> dict:
    report, files = expected(fix)
    before = {p.name: p.read_bytes() for p in fix.work.iterdir() if p.is_file()}
    for mode in ["preview", "write"]:
        result = app.run(fix.work, fix.settings(mode), timeout=timeout)
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout) == report
        if mode == "preview":
            assert not fix.output.exists()
        else:
            bundle(fix, report, files)
    assert all((fix.work / name).read_bytes() == data for name, data in before.items())
    assert not list(fix.work.glob(".json-patch-*"))
    result = app.run(fix.work, fix.settings())
    assert result.returncode != 0 and "already exists" in result.stderr
    bundle(fix, report, files)
    return report


def reject(app: Application, fix: Fixture, message: str = "", **settings: str) -> None:
    before = {p.name: p.read_bytes() for p in fix.work.iterdir() if p.is_file() and not p.is_symlink()}
    result = app.run(fix.work, fix.settings(**settings), timeout=60)
    assert result.returncode != 0 and message in result.stderr, result.stderr
    assert not fix.output.exists() and not list(fix.work.glob(".json-patch-*"))
    assert all((fix.work / name).read_bytes() == data for name, data in before.items())
    return  # noqa: PLR1711


def roundtrip(app: Application, directory: Path, name: str, before: object, after: object) -> str:
    generated = fixture(directory, name + "-diff", before, after)
    run(app, generated)
    patch = json.loads((generated.output / "patch.json").read_bytes())
    assert patch == difference(before, after)
    applied = fixture(directory, name + "-apply", before, patch, "apply")
    run(app, applied)
    target = json.loads((applied.output / "result.json").read_bytes())
    assert canonical(target) == canonical(after)
    reverted = fixture(
        directory, name + "-undo", target, json.loads((applied.output / "undo.json").read_bytes()), "apply"
    )
    run(app, reverted)
    assert canonical(json.loads((reverted.output / "result.json").read_bytes())) == canonical(before)
    return digest(patch)


def check_roundtrips(app: Application, directory: Path) -> dict:
    cases = []
    kinds = [None, True, 7, "世界", [1, None], {"a": 2}]
    for old in kinds:
        for new in kinds:
            cases.append((old, new))
    numbers = [
        (1, 1.0),
        (0.0, -0.0),
        (True, 1),
        (False, 0),
        (2**53 + 1, float(2**53)),
        (-(2**63), -(2**63) + 1),
        (2**63 - 1, 1.25),
        (5e-324, 1e-300),
        (1e308, -1e308),
    ]
    cases.extend(({"value": old}, {"value": new}) for old, new in numbers)
    cases += [
        (
            {"a/b": {"~1": [1, 2, 3]}, "": {"\0\n": "x"}, "gone": None},
            {"a/b": {"~1": [4]}, "": {"\0\n": "y"}, "new": None},
        ),
        ([0, 1, 2, 3], [0]),
        ([0], [0, None, [], {}]),
        ({"01": 1, "-": 2, "~01": 3}, {"01": 2, "-": 3, "~01": 4}),
    ]
    rng = random.Random(450045)
    pool = [None, False, True, 0, -9, 1.0, -0.0, "", "é", "é", "😀", "\0"]
    names = ["", "a", "a/b", "~", "~1", "世界", "00", "line\n", "\0"]

    def tree(depth: int) -> object:
        choice = rng.randrange(5 if depth < 4 else 3)
        if choice < 3:
            return rng.choice(pool)
        if choice == 3:
            return [tree(depth + 1) for _ in range(rng.randrange(5))]
        return {name: tree(depth + 1) for name in rng.sample(names, rng.randrange(5))}

    cases.extend((tree(0), tree(0)) for _ in range(45))
    hashes = [roundtrip(app, directory, f"round-{i}", old, new) for i, (old, new) in enumerate(cases)]
    return {"cases": len(cases), "patches_sha256": hashlib.sha256("".join(hashes).encode()).hexdigest()}


def change(operation: str, path: str, before: object, after: object) -> dict:
    return {"op": operation, "path": path, "before": before, "after": after}


def check_manual(app: Application, directory: Path) -> int:
    before = {"items": [0, 2], "x": None, "object": {"a": 1}}
    changes = [
        change("add", "/items/1", None, 1),
        change("replace", "/items/0", 0, -1),
        change("remove", "/items/2", 2, None),
        change("add", "/items/2", None, {"n": 3}),
        change("replace", "/items/2/n", 3, 4),
        change("remove", "/x", None, None),
        change("add", "/x", None, [9]),
        change("replace", "/object", {"a": 1}, {"b": 2}),
        change("add", "/object/c", None, True),
    ]
    after = {"items": [-1, 1, {"n": 4}], "x": [9], "object": {"b": 2, "c": True}}
    patch = envelope(before, after, changes)
    fix = fixture(directory, "manual", before, patch, "apply")
    run(app, fix)
    run(app, fixture(directory, "manual-undo", after, undo(patch), "apply"))
    # Object member order and whitespace do not make the source stale.
    fix = fixture(directory, "reformatted", before, patch, "apply")
    (fix.work / "base.json").write_text(
        json.dumps({key: before[key] for key in reversed(before)}, separators=(",", ":"))
    )
    run(app, fix)
    return 3


def check_rejections(app: Application, directory: Path) -> int:
    before = {"a": 1, "items": [0, 1], "null": None}
    after = {"a": 2, "items": [0, 1], "null": None}
    good = difference(before, after)
    bad = []
    for name, value in [
        ("version", 2),
        ("version", True),
        ("version", 1.0),
        ("base_sha256", "x"),
        ("base_sha256", "0" * 64),
        ("target_sha256", "f" * 64),
        ("changes", {}),
        ("extra", 1),
    ]:
        document = copy.deepcopy(good)
        document[name] = value
        bad.append(document)
    for row in [
        change("move", "/a", 1, 2),
        change("add", "", None, 2),
        change("remove", "", before, None),
        change("add", "/a", None, 3),
        change("remove", "/missing", None, None),
        change("replace", "/a/x", 1, 2),
        change("replace", "/missing/x", 1, 2),
        change("replace", "/a", True, 2),
        change("replace", "/a", 1.0, 2),
        change("remove", "/a", 1, 2),
        change("add", "/new", 3, 4),
        {"op": "replace", "path": "/a", "after": 2},
        {**good["changes"][0], "extra": 1},
    ]:
        bad.append(envelope(before, after, [row]))
    for path in [
        "a",
        "/~",
        "/~2",
        "/a~x",
        "/items/00",
        "/items/-1",
        "/items/+1",
        "/items/ 1",
        "/items/١",
        "/items/-",
        "/items/2",
        "/items/9223372036854775808",
        "/" + "x" * 4096,
        "/x" * 25,
    ]:
        bad.append(envelope(before, after, [change("replace", path, 1, 2)]))
    for path in ["/items/-", "/items/3", "/items/01", "/items/1/x"]:
        bad.append(envelope(before, after, [change("add", path, None, 2)]))
    # A valid first change followed by a stale/malformed guard must leave every source byte intact.
    for second in [
        change("replace", "/items/1", 99, 2),
        change("remove", "/missing", None, None),
        change("add", "/a", None, 3),
        change("replace", "/a/x", None, 2),
    ]:
        bad.append(envelope(before, after, [good["changes"][0], second]))
    for index, patch in enumerate(bad):
        reject(app, fixture(directory, f"invalid-patch-{index}", before, patch, "apply"))
    stale_values = [
        {**before, "a": 8},
        {**before, "a": 1.0},
        {**before, "new": True},
        {**before, "items": [1, 0]},
        {"a": 1, "items": [0, 1]},
    ]
    for i, value in enumerate(stale_values):
        reject(app, fixture(directory, f"stale-{i}", value, good, "apply"), "stale base")
    configs = [
        {"action": "merge"},
        {"max_nodes": 0},
        {"max_nodes": True},
        {"max_nodes": 20001},
        {"max_changes": 0},
        {"max_changes": True},
        {"max_changes": 2001},
        {"extra": 1},
        {"base": "missing"},
        {"target": "missing"},
        {"output": "base.json"},
        {"output": "missing/child"},
        {"base": ""},
        {"target": "\0"},
    ]
    for i, update in enumerate(configs):
        fix = fixture(directory, f"config-{i}", before, after)
        fix.config.update(update)
        fix.save()
        reject(app, fix)
    count_bad = len(bad) + len(stale_values) + len(configs)
    for filename in ["base.json", "incoming.json", "patch-job.json"]:
        for i, raw in enumerate([b"{", b"[NaN]", b"9223372036854775808", b'"\\ud800"', b"\xff", b"{bad}"]):
            fix = fixture(directory, f"invalid-json-{filename}-{i}", before, after)
            (fix.work / filename).write_bytes(raw)
            reject(app, fix)
            count_bad += 1
    reject(app, fixture(directory, "bad-mode", before, after), PATCH_MODE="apply")
    return count_bad + 1


def pause(app: Application, fix: Fixture, point: str) -> subprocess.Popen:
    process = subprocess.Popen(
        app.command,
        cwd=fix.work,
        env=app.environment(fix.settings(PATCH_PAUSE=point, PATCH_CONTINUE=str(fix.work / "continue"))),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            assert selector.select(20), "patch application did not pause"
        assert process.stdout.readline().rstrip() == "PAUSED " + point
        return process
    except BaseException:
        process.kill()
        process.communicate()
        raise


def resume(process: subprocess.Popen, fix: Fixture) -> subprocess.CompletedProcess:
    (fix.work / "continue").touch()
    out, error = process.communicate(timeout=30)
    return subprocess.CompletedProcess(process.args, process.returncode, out, error)


def check_publication(app: Application, directory: Path) -> int:
    before, after = {"a": [1, 2]}, {"a": [3]}
    count_cases = 0
    for action in ["diff", "apply"]:
        incoming = after if action == "diff" else difference(before, after)
        points = ["validated", "stage", "report.json", "ready", "published"] + (
            ["patch.json"] if action == "diff" else ["result.json", "undo.json"]
        )
        for point in points:
            for killed in [False, True]:
                fix = fixture(directory, f"fault-{action}-{point}-{killed}", before, incoming, action)
                report, files = expected(fix)
                if killed:
                    process = pause(app, fix, point)
                    process.kill()
                    process.communicate(timeout=10)
                    assert process.returncode == -9
                else:
                    result = app.run(fix.work, fix.settings(PATCH_FAIL=point))
                    assert result.returncode != 0 and "injected failure: " + point in result.stderr
                if point == "published":
                    bundle(fix, report, files)
                else:
                    assert not fix.output.exists()
                stages = list(fix.work.glob(".json-patch-*"))
                assert len(stages) == int(killed and point not in ["validated", "published"])
                for stage in stages:
                    shutil.rmtree(stage)  # Operator cleanup of a test-owned unpublished stage.
                if point != "published":
                    run(app, fix)
                count_cases += 1
    for point in ["validated", "ready"]:
        for changed in ["base.json", "incoming.json", "patch-job.json", "output"]:
            fix = fixture(directory, f"changed-{point}-{changed}", before, difference(before, after), "apply")
            process = pause(app, fix, point)
            try:
                if changed == "output":
                    fix.output.mkdir()
                    (fix.output / "keep").write_bytes(b"untouched")
                else:
                    path = fix.work / changed
                    path.write_bytes(path.read_bytes() + b" ")
                result = resume(process, fix)
                assert result.returncode != 0
                assert not list(fix.work.glob(".json-patch-*"))
                if changed == "output":
                    assert {p.name for p in fix.output.iterdir()} == {"keep"}
                    assert (fix.output / "keep").read_bytes() == b"untouched"
                else:
                    assert not fix.output.exists() and "input changed" in result.stderr
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate()
            count_cases += 1
    for point in ["stage", "result.json"]:
        fix = fixture(directory, "permission-" + point, before, difference(before, after), "apply")
        process = pause(app, fix, point)
        stage = next(fix.work.glob(".json-patch-*"))
        try:
            assert os.getuid() != 0
            stage.chmod(0o500)
            result = resume(process, fix)
            assert result.returncode != 0 and "Permission denied" in result.stderr
            assert not fix.output.exists()
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()
            if stage.exists():
                stage.chmod(0o700)
                shutil.rmtree(stage)
        (fix.work / "continue").unlink()
        run(app, fix)
        count_cases += 1
    return count_cases


def check_paths(app: Application, directory: Path) -> int:
    for kind in ["symlink", "fifo", "directory", "output-file", "output-directory", "output-symlink", "permission"]:
        fix = fixture(directory, "paths-" + kind, {"a": 1}, {"a": 2})
        source = fix.work / "base.json"
        if kind == "symlink":
            source.rename(fix.work / "original")
            source.symlink_to("original")
        elif kind == "fifo":
            source.unlink()
            os.mkfifo(source)
        elif kind == "directory":
            source.unlink()
            source.mkdir()
        elif kind == "output-file":
            fix.output.write_bytes(b"keep")
        elif kind == "output-directory":
            fix.output.mkdir()
            (fix.output / "keep").write_bytes(b"keep")
        elif kind == "output-symlink":
            fix.output.symlink_to("missing")
        else:
            fix.work.chmod(0o500)
        try:
            result = app.run(fix.work, fix.settings(), timeout=10)
            assert result.returncode != 0
            assert not list(fix.work.glob(".json-patch-*"))
            if kind == "output-file":
                assert fix.output.read_bytes() == b"keep"
            if kind == "output-directory":
                assert (fix.output / "keep").read_bytes() == b"keep"
            if kind == "output-symlink":
                assert fix.output.is_symlink() and os.readlink(fix.output) == "missing"
        finally:
            fix.work.chmod(0o700)
    return 7


def compact_inputs(fix: Fixture) -> None:
    (fix.work / "base.json").write_bytes(canonical(fix.base).encode())
    (fix.work / "incoming.json").write_bytes(canonical(fix.incoming).encode())
    return  # noqa: PLR1711


def check_limits(app: Application, directory: Path) -> dict:
    limited = Application(["/usr/bin/prlimit", "--as=268435456", "--", *app.command], app.engine)
    deep: object = "leaf"
    for _ in range(24):
        deep = {"x": deep}
    run(limited, fixture(directory, "depth-exact", deep, deep))
    reject(limited, fixture(directory, "depth-above", {"x": deep}, None), "nesting/path")
    wide = {str(i): i for i in range(19999)}
    changed = {**wide, "0": -1}
    run(limited, fixture(directory, "nodes-exact", wide, changed), timeout=120)
    reject(limited, fixture(directory, "nodes-above", {**wide, "last": 1}, None), "node limit")
    changes = [change("replace", "/value", i, i + 1) for i in range(2000)]
    patch = envelope({"value": 0}, {"value": 2000}, changes)
    run(limited, fixture(directory, "changes-exact", {"value": 0}, patch, "apply"), timeout=120)
    reject(
        limited,
        fixture(directory, "changes-above", {"value": 0}, {**patch, "changes": changes + changes[:1]}, "apply"),
        "change limit",
    )
    reject(limited, fixture(directory, "diff-changes-above", list(range(2001)), [-1] * 2001), "change limit")
    # Even a transient oversized result is rejected before publication, regardless of the final hash.
    temporary = envelope({"x": 1}, {"x": 1}, [change("add", "/y", None, 2), change("remove", "/y", 2, None)])
    reject(limited, fixture(directory, "intermediate-limit", {"x": 1}, temporary, "apply", max_nodes=2), "node limit")
    value = "x" * (4194304 - 2)
    exact = fixture(directory, "bytes-exact", value, value)
    compact_inputs(exact)
    run(limited, exact, timeout=120)
    identity = envelope(value, value, [])
    boundary = fixture(directory, "result-boundary", value, identity, "apply")
    compact_inputs(boundary)
    run(limited, boundary, timeout=120)
    assert (boundary.output / "result.json").stat().st_size == 4194304
    reused = fixture(directory, "result-reused", value, undo(identity), "apply")
    compact_inputs(reused)
    reused.config["base"] = str(boundary.output / "result.json")
    reused.config["patch"] = str(boundary.output / "undo.json")
    reused.save()
    run(limited, reused, timeout=120)
    above = fixture(directory, "bytes-above", value + "x", None)
    compact_inputs(above)
    reject(limited, above, "byte limit")
    root_patch = envelope(value, None, [change("replace", "", value, None)])
    large_apply = fixture(directory, "large-apply", value, root_patch, "apply")
    compact_inputs(large_apply)
    run(limited, large_apply, timeout=120)
    padded = fixture(directory, "patch-bytes-exact", {"a": 1}, difference({"a": 1}, {"a": 2}), "apply")
    raw = canonical(padded.incoming).encode()
    (padded.work / "incoming.json").write_bytes(raw + b" " * (16777216 - len(raw)))
    run(limited, padded, timeout=120)
    prefix = "\0" * 2048
    expanded_before = {prefix: {str(i): 1 for i in range(2000)}}
    expanded_after = {prefix: {str(i): 2 for i in range(2000)}}
    reject(
        limited, fixture(directory, "expanded-patch-overflow", expanded_before, expanded_after), "patch exceeds 16 MiB"
    )
    too_large_patch = fixture(directory, "patch-bytes-above", None, {}, "apply")
    (too_large_patch.work / "incoming.json").write_bytes(b" " * 16777217)
    reject(limited, too_large_patch, "byte limit")
    path_key = "x" * 4095
    run(limited, fixture(directory, "path-exact", {path_key: 1}, {path_key: 2}))
    reject(limited, fixture(directory, "path-above", {path_key + "x": 1}, None), "nesting/path")
    escaped = "~" * 2048
    reject(limited, fixture(directory, "escaped-path-above", {escaped: 1}, None), "nesting/path")
    return {
        "memory_limit": 268435456,
        "nodes": 20000,
        "changes": 2000,
        "depth": 24,
        "document_bytes": 4194304,
        "path_bytes": 4096,
        "patch_byte_limit": 16777216,
    }


def check(app: Application, directory: Path) -> dict:
    return {
        "roundtrips": check_roundtrips(app, directory),
        "manual_cases": check_manual(app, directory),
        "rejected_cases": check_rejections(app, directory),
        "publication_cases": check_publication(app, directory),
        "path_cases": check_paths(app, directory),
        "limits": check_limits(app, directory),
    }
