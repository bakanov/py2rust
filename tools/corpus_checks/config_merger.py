"""Independent overlays, provenance, hostile inputs and publication interruption checks."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import random
import selectors
import struct
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .common import Application


def kind(value: object) -> str:
    return {
        type(None): "null",
        bool: "bool",
        int: "number",
        float: "number",
        str: "string",
        list: "array",
        dict: "object",
    }[type(value)]


def pointer(parts: tuple[str, ...]) -> str:
    return "".join("/" + part.replace("~", "~0").replace("/", "~1") for part in parts)


def flatten(value: object, parts: tuple[str, ...] = ()) -> dict[str, object]:
    pending = [(parts, value)]
    result = {}
    while pending:
        tokens, node = pending.pop()
        result[pointer(tokens)] = node
        if isinstance(node, dict):
            pending.extend(((*tokens, key), child) for key, child in node.items())
        elif isinstance(node, list):
            pending.extend(((*tokens, str(index)), child) for index, child in enumerate(node))
    return result


def signature(value: object) -> object:
    """Check float bits and integer/bool distinctions, not Python's loose == alone."""
    if isinstance(value, dict):
        return {key: signature(item) for key, item in value.items()}
    if isinstance(value, list):
        return [signature(item) for item in value]
    if isinstance(value, float):
        return ("float", struct.pack(">d", value).hex())
    return (type(value).__name__, value)


def equivalent(left: object, right: object) -> bool:
    flattened = [
        {path: (kind(item), None if isinstance(item, (dict, list)) else item) for path, item in flatten(value).items()}
        for value in [left, right]
    ]
    return flattened[0] == flattened[1]


def oracle(layers: list[tuple[str, dict | None]], permissions: list[str]) -> dict:
    """Iterative traversal mutates a copy; the application uses recursive result records."""
    value: dict = {}
    origins: dict[str, str] = {}
    events: list[dict] = []
    conflicts: list[dict] = []
    used: set[str] = set()
    for layer, document in layers:
        if document is None:
            continue
        pending = [((), document)]
        while pending:
            parts, incoming = pending.pop()
            path = pointer(parts)
            container = value
            for key in parts[:-1]:
                container = container[key]
            exists = not parts or parts[-1] in container
            before = (container[parts[-1]] if parts else value) if exists else None
            before_kind = kind(before) if exists else "missing"
            after_kind = kind(incoming)
            if not exists:
                action = "add"
            elif before_kind != after_kind:
                action = "type_change" if path in permissions else "conflict"
            elif isinstance(before, dict):
                action = "merge"
            elif equivalent(before, incoming):
                action = "unchanged"
            else:
                action = "replace"
            event = {
                "path": path,
                "layer": layer,
                "previous_layer": origins.get(path, ""),
                "action": action,
                "before": before_kind,
                "after": after_kind,
            }
            events.append(event)
            if action == "conflict":
                conflicts.append(event)
                continue
            if action == "merge":
                origins[path] = layer
                pending.extend(((*parts, key), incoming[key]) for key in sorted(incoming, reverse=True))
                continue
            for old in tuple(origins):
                if old == path or old.startswith(path + "/"):
                    del origins[old]
            origins.update(dict.fromkeys(flatten(incoming, parts), layer))
            container[parts[-1]] = copy.deepcopy(incoming)
            if action == "type_change":
                used.add(path)
    return {
        "status": "conflicted" if conflicts else "resolved",
        "resolved": None if conflicts else value,
        "provenance": {} if conflicts else origins,
        "events": events,
        "conflicts": conflicts,
        "unused_type_changes": sorted(set(permissions) - used),
    }


@dataclass
class Fixture:
    directory: Path
    config: dict
    layers: list[tuple[str, dict | None]]

    @property
    def path(self) -> Path:
        return self.directory / "merge.json"

    @property
    def output(self) -> Path:
        return self.directory / self.config["output"]

    def save(self) -> None:
        self.path.write_text(json.dumps(self.config, ensure_ascii=False))
        return  # noqa: PLR1711 - explicit return required by repository guidelines

    def settings(self, mode: str = "preview", **extra: str) -> dict[str, str]:
        return dict(MERGE_CONFIG=str(self.path), MERGE_MODE=mode, **extra)

    def inputs(self) -> dict[Path, bytes]:
        paths = [self.path, *(self.directory / item["path"] for item in self.config["layers"])]
        return {path: path.read_bytes() for path in paths if path.is_file()}


def fixture(
    root: Path, name: str, layers: list[tuple[str, dict | None]], permissions: list[str] | None = None
) -> Fixture:
    directory = root / name
    directory.mkdir()
    config = {"layers": [], "type_changes": permissions or [], "output": "resolved.json", "max_nodes": 20000}
    for index, (label, value) in enumerate(layers):
        path = f"layer-{index}.json"
        config["layers"].append({"name": label, "path": path, "required": value is not None})
        if value is not None:
            data = json.dumps(value, ensure_ascii=False, indent=2).replace("\n", "\r\n") + "\r\n"
            (directory / path).write_bytes(data.encode())
    result = Fixture(directory, config, copy.deepcopy(layers))
    result.save()
    return result


def expected(fix: Fixture, mode: str) -> dict:
    report = oracle(fix.layers, fix.config["type_changes"])
    report["mode"] = mode
    report["layers"] = []
    for index, (label, value) in enumerate(fix.layers):
        path = fix.directory / fix.config["layers"][index]["path"]
        data = path.read_bytes() if value is not None else b""
        report["layers"].append(
            {
                "name": label,
                "present": value is not None,
                "sha256": hashlib.sha256(data).hexdigest() if value is not None else "",
                "bytes": len(data),
                "nodes": len(flatten(value)) if value is not None else 0,
            }
        )
    return report


def verify(app: Application, fix: Fixture, mode: str = "preview") -> dict:
    inputs = fix.inputs()
    original = fix.output.read_bytes() if fix.output.exists() else None
    result = app.run(fix.directory.parent, fix.settings(mode), timeout=40)
    report = expected(fix, mode)
    assert result.returncode == (2 if report["conflicts"] else 0), result.stderr
    observed = json.loads(result.stdout)
    assert signature(observed) == signature(report), (observed, report)
    assert fix.inputs() == inputs, "a configuration input changed"
    if mode == "apply" and not report["conflicts"]:
        assert signature(json.loads(fix.output.read_bytes())) == signature(report["resolved"])
    else:
        assert (fix.output.read_bytes() if fix.output.exists() else None) == original
    return observed


def reject(app: Application, fix: Fixture, needle: str = "") -> None:
    before = fix.output.read_bytes() if fix.output.is_file() else None
    result = app.run(fix.directory.parent, fix.settings("apply"), timeout=10)
    assert result.returncode != 0, result.stdout
    assert needle in result.stderr, result.stderr
    assert (fix.output.read_bytes() if fix.output.is_file() else None) == before
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def pause(app: Application, fix: Fixture, label: str) -> subprocess.Popen:
    process = subprocess.Popen(
        app.command,
        cwd=fix.directory.parent,
        env=app.environment(fix.settings("apply", MERGE_PAUSE=label, MERGE_CONTINUE=str(fix.directory / "continue"))),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    with selectors.DefaultSelector() as ready:
        ready.register(process.stdout, selectors.EVENT_READ)
        assert ready.select(10), "process did not reach pause"
    assert process.stdout.readline().rstrip() == "PAUSED " + label
    return process


def finish(process: subprocess.Popen, fix: Fixture, success: bool) -> None:
    try:
        (fix.directory / "continue").touch()
        output, error = process.communicate(timeout=10)
        assert (process.returncode == 0) == success, output + error
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate()
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def random_value(rng: random.Random, depth: int = 0) -> object:
    choice = rng.randrange(6 if depth < 3 else 4)
    if choice == 0:
        return None
    if choice == 1:
        return bool(rng.randrange(2))
    if choice == 2:
        return rng.choice([-7, 0, 1, 23, 0.1, -0.0])
    if choice == 3:
        return rng.choice(["", "hello", "世界", "x/y~z", "line\nfeed"])
    if choice == 4:
        return [random_value(rng, depth + 1) for _ in range(rng.randrange(4))]
    keys = ["a", "b", "", "x/y", "~", "é"]
    return {key: random_value(rng, depth + 1) for key in rng.sample(keys, rng.randrange(4))}


def check(app: Application, directory: Path) -> dict:
    base = {
        "server": {"host": "127.0.0.1", "port": 8080, "tls": False},
        "empty": {},
        "array": [{"old": True}, 2, 3],
        "null": None,
        "a/b": {"c~d": {"": "original"}},
        "": {"": 1},
        "é": "composed",
        "é": "decomposed",
        "numeric": 1,
        "zero": -0.0,
        "literal": "${HOME}",
        "unchanged": "same",
    }
    site = {
        "server": {"port": 9000},
        "array": [{"new": "世界"}],
        "empty": {},
        "numeric": 1.0,
        "a/b": {"c~d": {"": "site"}},
        "unchanged": "same",
    }
    user = {"server": {"tls": True}, "new": {"nullable": None}, "": {"": 2}, "array": []}
    good = fixture(directory, "nested", [("base", base), ("site", site), ("missing", None), ("user", user)])
    preview = verify(app, good)
    assert preview["provenance"]["/server/host"] == "base"
    assert preview["provenance"]["/server"] == "user"
    assert preview["provenance"]["/a~1b/c~0d/"] == "site" and "/array/0" not in preview["provenance"]
    assert preview["provenance"]["/unchanged"] == "site" and preview["provenance"]["//"] == "user"
    verify(app, good, "apply")
    old_handle = good.output.open("rb")
    old_bytes = old_handle.read()
    good.layers[-1][1]["revision"] = 2
    (good.directory / "layer-3.json").write_text(json.dumps(good.layers[-1][1], ensure_ascii=False))
    verify(app, good, "apply")
    assert good.output.read_bytes() != old_bytes
    old_handle.seek(0)
    assert old_handle.read() == old_bytes
    old_handle.close()

    # Every JSON-kind transition, with exact paths and explicit overrides.
    values = [None, False, 1, "text", [1, {"x": True}], {"x": 1}]
    first = {f"case-{i}-{j}": left for i, left in enumerate(values) for j in range(len(values))}
    second = {f"case-{i}-{j}": right for i in range(len(values)) for j, right in enumerate(values)}
    transitions = fixture(directory, "transitions", [("base", first), ("site", second)])
    transitions.output.write_bytes(b"old output\r\n")
    blocked = verify(app, transitions, "apply")
    assert len(blocked["conflicts"]) == 30
    transitions.config["type_changes"] = [item["path"] for item in blocked["conflicts"]] + ["/unused"]
    transitions.save()
    allowed = verify(app, transitions, "apply")
    assert allowed["unused_type_changes"] == ["/unused"]
    repaired = fixture(directory, "later-repair", [("base", {"x": 1}), ("bad", {"x": "wrong"}), ("later", {"x": 2})])
    assert verify(app, repaired, "apply")["status"] == "conflicted"

    rng = random.Random(381207)
    for index in range(60):
        layers = [(f"layer-{number}", {key: random_value(rng) for key in ["a", "b", "x/y", ""]}) for number in range(4)]
        permissions = []
        if index % 3:
            all_paths = set().union(*(set(flatten(value)) for _, value in layers))
            permissions = sorted(path for path in all_paths if rng.randrange(3))
        item = fixture(directory, f"random-{index}", layers, permissions)
        verify(app, item, "apply")

    invalid = []
    for index, change in enumerate(
        [
            {"max_nodes": 0},
            {"max_nodes": 20001},
            {"max_nodes": True},
            {"max_nodes": 1.0},
            {"layers": []},
            {"layers": "base"},
            {"type_changes": ["relative"]},
            {"type_changes": ["/bad~2"]},
            {"type_changes": ["/x", "/x"]},
            {"type_changes": [1]},
            {"type_changes": ["/" + "x" * 4096]},
            {"type_changes": [f"/{i}" for i in range(129)]},
            {"extra": True},
            {"output": ""},
            {"output": "bad\0path"},
        ]
    ):
        item = fixture(directory, f"bad-config-{index}", [("base", {"x": 1})])
        item.config.update(change)
        item.save()
        reject(app, item)
        invalid.append("config")
    for index, change in enumerate(
        [
            {"name": "same name"},
            {"name": "世界"},
            {"name": ""},
            {"name": "n" * 65},
            {"required": 1},
            {"path": ""},
            {"extra": None},
            {"required": False, "path": "missing-parent/a.json"},
        ]
    ):
        item = fixture(directory, f"bad-layer-{index}", [("base", {"x": 1})])
        item.config["layers"][0].update(change)
        item.save()
        reject(app, item)
        invalid.append("layer")
    for index, contents in enumerate(
        [
            b"[]",
            b"null",
            b"{broken",
            b'{"bad":NaN}',
            b'{"bad":1e999}',
            b'{"bad":9223372036854775808}',
            b'{"bad":"\\ud800"}',
            b'{"bad":"\xff"}',
            b"\xff",
            b'{"bad":-9223372036854775809}',
        ]
    ):
        item = fixture(directory, f"bad-json-{index}", [("base", {})])
        (item.directory / "layer-0.json").write_bytes(contents)
        reject(app, item)
        invalid.append("json")

    empty = fixture(directory, "empty", [("base", {})])
    empty.config["max_nodes"] = 1
    empty.save()
    verify(app, empty, "apply")
    missing = fixture(directory, "all-missing", [("base", None)])
    reject(app, missing, "all layers are missing")
    missing.config["layers"][0]["required"] = True
    missing.save()
    reject(app, missing, "required layer is missing")
    deep: dict = {}
    for _ in range(24):
        deep = {"a": deep}
    depth = fixture(directory, "depth", [("base", deep)])
    verify(app, depth)
    (depth.directory / "layer-0.json").write_text(json.dumps({"a": deep}))
    reject(app, depth, "24 nesting levels")
    long_key = fixture(directory, "long-key", [("base", {"x" * 4095: True})])
    verify(app, long_key)
    (long_key.directory / "layer-0.json").write_text(json.dumps({"x" * 4096: True}))
    reject(app, long_key, "invalid JSON Pointer")
    sized = fixture(directory, "size", [("base", {})])
    (sized.directory / "layer-0.json").write_bytes(b"{}" + b" " * (1048576 - 2))
    verify(app, sized)
    (sized.directory / "layer-0.json").write_bytes(b"{}" + b" " * (1048576 - 1))
    reject(app, sized, "exceeds 1 MiB")
    maximum_layers = fixture(directory, "sixteen", [(f"layer-{i}", {"value": i}) for i in range(16)])
    verify(app, maximum_layers)
    maximum_layers.config["layers"].append({"name": "extra", "path": "absent.json", "required": False})
    maximum_layers.save()
    reject(app, maximum_layers, "1..16 layers")

    # Aliases and special paths cannot turn an output or optional input into an overwrite or a blocking read.
    for case in [
        "same-output",
        "hardlink-output",
        "symlink-output",
        "dangling-output",
        "directory-output",
        "fifo-output",
        "same-input",
        "hardlink-input",
        "symlink-input",
        "dangling-input",
        "fifo-input",
        "directory-input",
        "config-output",
        "duplicate-name",
    ]:
        item = fixture(directory, case, [("base", {"x": 1}), ("site", {"x": 2})])
        first_path, second_path = item.directory / "layer-0.json", item.directory / "layer-1.json"
        if case == "same-output":
            item.config["output"] = "layer-0.json"
        elif case == "config-output":
            item.config["output"] = "merge.json"
        elif case == "hardlink-output":
            os.link(first_path, item.output)
        elif case in {"symlink-output", "dangling-output"}:
            item.output.symlink_to(first_path if case == "symlink-output" else "absent.json")
        elif case == "directory-output":
            item.output.mkdir()
        elif case == "fifo-output":
            os.mkfifo(item.output)
        elif case == "same-input":
            item.config["layers"][1]["path"] = "layer-0.json"
        elif case == "duplicate-name":
            item.config["layers"][1]["name"] = "base"
        else:
            second_path.unlink()
            item.config["layers"][1]["required"] = False
            if case == "hardlink-input":
                os.link(first_path, second_path)
            elif case in {"symlink-input", "dangling-input"}:
                second_path.symlink_to(first_path if case == "symlink-input" else "absent.json")
            elif case == "fifo-input":
                os.mkfifo(second_path)
            elif case == "directory-input":
                second_path.mkdir()
        item.save()
        original = first_path.read_bytes()
        reject(app, item)
        assert first_path.read_bytes() == original
        invalid.append(case)

    for index, target in enumerate(["input", "config", "optional", "output", "removed"]):
        item = fixture(directory, f"changing-{index}", [("base", {"x": 1}), ("optional", None)])
        item.output.write_bytes(b"previous output")
        process = pause(app, item, "before_publish")
        try:
            if target == "input":
                path = item.directory / "layer-0.json"
                metadata = path.stat()
                path.write_text('{"x":2}')
                os.utime(path, ns=(metadata.st_atime_ns, metadata.st_mtime_ns))
            elif target == "config":
                item.path.write_text(item.path.read_text() + " ")
            elif target == "optional":
                (item.directory / "layer-1.json").write_text('{"x":3}')
            elif target == "output":
                item.output.write_bytes(b"another writer")
            else:
                (item.directory / "layer-0.json").unlink()
            finish(process, item, False)
            assert item.output.read_bytes() == (b"another writer" if target == "output" else b"previous output")
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()

    for label in ["loaded", "resolved", "before_publish", "after_publish"]:
        item = fixture(directory, "failure-" + label, [("base", {"x": 1})])
        item.output.write_bytes(b"original")
        result = app.run(directory, item.settings("apply", MERGE_FAIL=label))
        assert result.returncode != 0
        assert item.output.read_bytes() == (b'{\n  "x": 1\n}\n' if label == "after_publish" else b"original")
        verify(app, item, "apply")
    for label in ["before_publish", "after_publish"]:
        item = fixture(directory, "killed-" + label, [("base", {"x": 1})])
        item.output.write_bytes(b"original")
        process = pause(app, item, label)
        process.kill()
        process.communicate(timeout=10)
        assert process.returncode < 0
        assert item.output.read_bytes() == (b'{\n  "x": 1\n}\n' if label == "after_publish" else b"original")
        verify(app, item, "apply")

    denied = fixture(directory, "denied", [("base", {"x": 1})])
    denied.output.write_bytes(b"original")
    denied.directory.chmod(0o500)
    try:
        reject(app, denied)
    finally:
        denied.directory.chmod(0o700)
    unreadable = fixture(directory, "unreadable", [("base", {"x": 1})])
    source = unreadable.directory / "layer-0.json"
    source.chmod(0)
    try:
        reject(app, unreadable)
    finally:
        source.chmod(0o600)

    wide = fixture(
        directory,
        "wide",
        [
            ("base", {f"k-{i:04}": "x" * 64 for i in range(4000)}),
            ("site", {f"k-{i:04}": "changed" for i in range(0, 4000, 2)}),
        ],
    )
    wide.config["max_nodes"] = 6002
    wide.save()
    limited = Application(["/usr/bin/prlimit", "--as=134217728", "--", *app.command], app.engine)
    verify(limited, wide, "apply")
    wide.config["max_nodes"] = 6001
    wide.save()
    reject(app, wide, "total input node budget exceeded")
    return {
        "json_kind_transitions": 36,
        "reported_type_conflicts": 30,
        "generated_overlays": 60,
        "precise_provenance": True,
        "unchanged_inputs": True,
        "invalid_requests": len(invalid),
        "changed_snapshots": 5,
        "failure_boundaries": 4,
        "killed_publishers": 2,
        "filesystem_failures": 2,
        "wide_keys": 4000,
        "address_space_bytes": 134217728,
    }
