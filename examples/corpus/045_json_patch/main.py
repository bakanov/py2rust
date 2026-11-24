"""Generate or apply guarded JSON patches, with preview and atomic publication modes."""

from differences import difference
from documents import Document, absolute, checkpoint, present, publish, read, unchanged
from model import digest, fields, same, validate
from patching import apply, reverse

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_canonical,
    json_int,
    json_loads,
    json_string,
    path_parent,
    path_resolve,
    pretty,
)


def main() -> None:
    mode: str = env_get("PATCH_MODE", "preview")
    assert mode in ["preview", "write"], "invalid patch mode"
    path: str = absolute(env_get("PATCH_CONFIG", "patch-job.json"), path_resolve("."))
    configuration: Document = read(path, 65536)
    config: Json = json_loads(configuration.data.decode())
    action: str = json_string(config["action"])
    assert action in ["diff", "apply"], "invalid patch action"
    input_name: str = "target" if action == "diff" else "patch"
    fields(config, ["action", "base", input_name, "output", "max_nodes", "max_changes"])
    node_limit: int = json_int(config["max_nodes"])
    change_limit: int = json_int(config["max_changes"])
    assert 1 <= node_limit <= 20000 and 1 <= change_limit <= 2000, "invalid patch limits"
    parent: str = path_parent(path)
    output: str = absolute(json_string(config["output"]), parent)
    assert not present(output), "output directory already exists"
    original: Document = read(absolute(json_string(config["base"]), parent), 4194304)
    incoming: Document = read(
        absolute(json_string(config[input_name]), parent), 4194304 if action == "diff" else 16777216
    )
    base: Json = json_loads(original.data.decode())
    other: Json = json_loads(incoming.data.decode())
    before_nodes: int = validate(base, node_limit)
    patch: Json = other
    target: Json = None
    if action == "diff":
        validate(other, node_limit)
        patch = difference(base, other, change_limit)
    patch_text: str = json_canonical(patch) + "\n"
    assert len(patch_text.encode()) <= 16777216, "patch exceeds 16 MiB"
    target = apply(base, patch, node_limit, change_limit)
    if action == "diff":
        assert same(target, other), "generated patch did not reconstruct target"
    undo: Json = reverse(patch)
    assert same(apply(target, undo, node_limit, change_limit), base), "undo did not reconstruct base"
    counts: dict[str, int] = {"add": 0, "remove": 0, "replace": 0}
    for change in json_array(patch["changes"]):
        operation: str = json_string(change["op"])
        counts[operation] = counts[operation] + 1
    report: Json = {
        "action": action,
        "base_sha256": digest(base),
        "target_sha256": digest(target),
        "base_nodes": before_nodes,
        "target_nodes": validate(target, node_limit),
        "changes": len(json_array(patch["changes"])),
        "operations": counts,
    }
    files: dict[str, str] = {"report.json": pretty(report) + "\n"}
    if action == "diff":
        files["patch.json"] = patch_text
    else:
        files["result.json"] = json_canonical(target)
        files["undo.json"] = json_canonical(undo) + "\n"
    for name in files:  # noqa: PLC0206 - subset key iteration
        assert len(files[name].encode()) <= 16777216, "output bundle file exceeds 16 MiB"
    documents: list[Document] = [configuration, original, incoming]
    checkpoint("validated")
    unchanged(documents)
    if mode == "write":
        publish(output, files, documents)
    print(pretty(report))
    return  # noqa: PLR1711


if __name__ == "__main__":
    main()
