"""Create a reviewable plan whose digest approves exact paths and file contents."""

from checks import digest, document, identity, parents, present, relative, signature

from py2rust.stdlib import (
    Json,
    json_array,
    json_equal,
    json_get,
    json_int,
    json_keys,
    json_string,
    path_join,
    path_name,
    path_parent,
    path_resolve,
    regex_replace,
)


def keys(value: Json, expected: list[str]) -> None:
    assert json_keys(value) == sorted(expected), "unexpected document fields"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def names(plan: Json) -> list[str]:
    result: list[str] = []
    for row in json_array(plan["rows"]):
        result.append(json_string(row["source"]))
        result.append(json_string(row["target"]))
    return result


def validate(plan: Json) -> None:
    keys(plan, ["version", "root", "max_bytes", "parents", "rows"])
    assert json_int(plan["version"]) == 1, "unsupported plan version"
    root: str = json_string(plan["root"])
    assert root != "/" and path_resolve(root) == root, "root must be canonical"
    limit: int = json_int(plan["max_bytes"])
    assert limit >= 0 and limit <= 67108864, "max_bytes must be 0..67108864"
    rows: list[Json] = json_array(plan["rows"])
    assert len(rows) > 0 and len(rows) <= 128, "select 1..128 entries"
    sources: set[str] = set()
    targets: set[str] = set()
    directories: list[str] = []
    for row in rows:
        keys(row, ["source", "target", "signature"])
        source: str = relative(json_string(row["source"]))
        target: str = relative(json_string(row["target"]))
        assert source not in sources, "duplicate source: " + source
        assert target not in targets, "duplicate destination: " + target
        sources.add(source)
        targets.add(target)
        info: Json = row["signature"]
        kind: str = json_string(info["kind"])
        assert kind in ["file", "directory", "symlink"], "invalid entry kind"
        if kind == "directory":
            directories.append(source)
            directories.append(target)
    for directory in directories:
        for name in names(plan):
            assert not name.startswith(directory + "/"), "overlapping directory selection: " + directory
    assert json_equal(plan["parents"], parents(root, names(plan))), "parent identity changed"
    for row in rows:
        device: int = json_int(row["signature"]["device"])
        for name in [json_string(row["source"]), json_string(row["target"])]:
            assert device == json_int(plan["parents"][path_parent(name)]["device"]), "cross-device rename"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def preview(raw: Json) -> Json:
    for key in json_keys(raw):
        assert key in ["root", "paths", "rules", "overrides", "max_bytes"], "unknown configuration field"
    root: str = path_resolve(json_string(raw["root"]))
    identity(root)
    limit: int = json_int(json_get(raw, "max_bytes", 8388608))
    assert limit >= 0 and limit <= 67108864, "invalid hash limit"
    selected: list[Json] = json_array(raw["paths"])
    assert len(selected) > 0 and len(selected) <= 128, "select 1..128 entries"
    rules: list[Json] = json_array(json_get(raw, "rules", []))
    assert len(rules) <= 32, "too many naming rules"
    for rule in rules:
        keys(rule, ["pattern", "replace"])
        assert len(json_string(rule["pattern"]).encode()) <= 1024, "pattern too large"
        assert len(json_string(rule["replace"]).encode()) <= 255, "replacement too large"
        regex_replace(json_string(rule["pattern"]), json_string(rule["replace"]), "validation")
    overrides: Json = json_get(raw, "overrides", {})
    rows: list[Json] = []
    sources: list[str] = []
    for value in selected:
        source: str = relative(json_string(value))
        sources.append(source)
        target: str = path_name(source)
        for rule in rules:
            target = regex_replace(json_string(rule["pattern"]), json_string(rule["replace"]), target)
        if path_parent(source) != ".":
            target = path_join(path_parent(source), target)
        target = relative(json_string(json_get(overrides, source, target)))
        parents(root, [source, target])
        rows.append({"source": source, "target": target, "signature": signature(path_join(root, source), limit)})
    for key in json_keys(overrides):
        assert key in sources, "override requires a selected source"
    plan: Json = {"version": 1, "root": root, "max_bytes": limit, "rows": rows, "parents": {}}
    plan["parents"] = parents(root, names(plan))
    validate(plan)
    for row in rows:
        target: str = json_string(row["target"])
        assert target in sources or not present(path_join(root, target)), "destination exists: " + target
    return {"id": digest(plan), "plan": plan}


def load(path: str) -> Json:
    envelope: Json = document(path, 2097152)
    keys(envelope, ["id", "plan"])
    assert json_string(envelope["id"]) == digest(envelope["plan"]), "plan digest mismatch"
    validate(envelope["plan"])
    return envelope
