"""Deterministic classification, collision resolution and reviewable move plans."""

from configuration import classify
from guards import digest, fields, parents, present, relative, signature

from py2rust.stdlib import (
    Json,
    datetime_format,
    datetime_from_unix,
    directory_names,
    json_array,
    json_bool,
    json_equal,
    json_int,
    json_keys,
    json_string,
    path_join,
    path_parent,
    path_resolve,
    path_stat,
)


def destination(root: str, folder: str, name: str, suffix: str, reserved: set[str]) -> str:
    stem: str = name[: -len(suffix)] if suffix != "" else name
    for number in range(10001):
        label: str = "" if number == 0 else " (" + str(number) + ")"
        shortened: str = stem
        while len((shortened + label + suffix).encode()) > 255:
            assert len(shortened) > 0, "collision suffix cannot fit filename"
            shortened = shortened[:-1]
        target: str = relative(folder + "/" + shortened + label + suffix)
        if target not in reserved and not present(path_join(root, target)):
            return target
    assert False, "more than 10000 filename collisions"
    return ""


def preview(config: Json) -> Json:
    root: str = json_string(config["root"])
    rows: list[Json] = []
    skipped: list[Json] = []
    targets: list[str] = []
    reserved: set[str] = set()
    total: int = 0
    for name in directory_names(root, json_int(config["max_entries"])):
        reason: str = ""
        if name.startswith(".py2rust-organize"):
            reason = "reserved"
        elif name.startswith(".") and not json_bool(config["include_hidden"]):
            reason = "hidden"
        else:
            for suffix in json_array(config["skip_suffixes"]):
                if name.lower().endswith(json_string(suffix)):
                    reason = "temporary"
            kind: str = json_string(path_stat(path_join(root, name), False)["kind"])
            if kind != "file":
                reason = kind
        if reason != "":
            skipped.append({"source": name, "reason": reason})
            continue
        relative(name)
        assert len(rows) < json_int(config["max_files"]), "file count budget exceeded"
        info: Json = signature(path_join(root, name), json_int(config["max_bytes"]) - total)
        total = total + json_int(info["size"])
        classified: tuple[str, str] = classify(name, config["categories"])
        date: str = relative(
            datetime_format(
                datetime_from_unix(json_int(info["mtime_ns"]) // 1000000000), json_string(config["date_format"])
            )
        )
        folder: str = classified[0] + "/" + date
        # Validate existing ancestors before testing candidate names beneath them.
        parents(root, [folder + "/" + name])
        target: str = destination(root, folder, name, classified[1], reserved)
        reserved.add(target)
        targets.append(target)
        rows.append({"source": name, "target": target, "signature": info, "category": classified[0], "date": date})
    plan: Json = {
        "version": 1,
        "root": root,
        "max_bytes": config["max_bytes"],
        "bytes": total,
        "rows": rows,
        "skipped": skipped,
        "parents": parents(root, targets),
    }
    return {"id": digest(plan), "plan": plan}


def validate(envelope: Json) -> None:
    fields(envelope, ["id", "plan"])
    plan: Json = envelope["plan"]
    fields(plan, ["version", "root", "max_bytes", "bytes", "rows", "skipped", "parents"])
    assert (
        json_string(envelope["id"]) == digest(plan) and json_int(plan["version"]) == 1
    ), "invalid plan digest or version"
    root: str = json_string(plan["root"])
    assert root != "/" and path_resolve(root) == root, "invalid root"
    assert 1 <= json_int(plan["max_bytes"]) <= 1099511627776, "invalid hash budget"
    rows: list[Json] = json_array(plan["rows"])
    assert len(rows) <= 1000, "too many moves"
    sources: set[str] = set()
    targets: list[str] = []
    total: int = 0
    for row in rows:
        fields(row, ["source", "target", "signature", "category", "date"])
        source: str = relative(json_string(row["source"]))
        target: str = relative(json_string(row["target"]))
        assert "/" not in source and source not in sources, "invalid or repeated source"
        assert "/" in target and target not in targets, "invalid or repeated target"
        assert path_parent(target) == relative(
            json_string(row["category"]) + "/" + json_string(row["date"])
        ), "target folder differs"
        sources.add(source)
        targets.append(target)
        total = total + json_int(row["signature"]["size"])
        assert 0 <= total <= json_int(plan["max_bytes"]), "invalid planned size"
    assert total == json_int(plan["bytes"]), "planned byte count differs"
    current: Json = parents(root, targets)
    assert json_keys(current) == json_keys(plan["parents"]), "parent inventory differs"
    for parent in json_keys(current):
        saved: Json = plan["parents"][parent]
        if saved is not None:
            assert json_equal(saved, current[parent]), "parent identity changed"
            assert json_equal(saved["device"], plan["parents"]["."]["device"]), "cross-device move"
    return  # noqa: PLR1711 - explicit return required by repository guidelines
