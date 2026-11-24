"""Content freshness, staged commands and successful output/cache publication."""

# ruff: noqa: I001, BLE001 - compact imports and per-step recovery boundary
from configuration import environment
from files import absolute, checkpoint, discard, present, regular, scan, unchanged
from storage import save, signature
from py2rust.stdlib import (
    Json, base64_encode, file_open, file_sync, json_array, json_equal, json_int, json_keys, json_string, path_join,
    path_parent, process_run, replace_file, sync_directory,
)


def current(config: Json, row: Json, entries: Json) -> tuple[Json, Json, dict[str, str]]:
    inputs: Json = {}
    dependencies: Json = {}
    guards: Json = {}
    for path in json_keys(config["guards"]):
        guards[path] = config["guards"][path]
    replacements: dict[str, str] = {"{output}": path_join(json_string(config["state"]), "artifact.tmp")}
    for key in json_keys(row["input_paths"]):
        path: str = json_string(row["input_paths"][key])
        observed: Json = scan(path)
        inputs[key] = observed["value"]
        guards[path] = observed["stamp"]
        replacements["{input:" + key + "}"] = path
    for dependency in json_array(row["dependencies"]):
        dep: str = json_string(dependency)
        path: str = json_string(config["targets"][dep]["output_path"])
        observed: Json = scan(path)
        assert json_equal(observed["value"], entries[dep]["output"]), "dependency changed during build"
        guards[path] = observed["stamp"]
        dependencies[dep] = {"signature": entries[dep]["signature"], "output": observed["value"]}
        replacements["{dependency:" + dep + "}"] = path
    entry: Json = {"recipe": row["recipe"], "inputs": inputs, "dependencies": dependencies}
    entry["signature"] = signature(entry)
    return (entry, guards, replacements)


def reason(row: Json, entry: Json, entries: Json) -> str:
    name: str = json_string(row["id"])
    if name not in json_keys(entries):
        return "no_cache"
    previous: Json = entries[name]
    for key in ["recipe", "inputs", "dependencies"]:
        if not json_equal(entry[key], previous[key]):
            return "changed_" + key
    path: str = json_string(row["output_path"])
    if not present(path):
        return "missing_output"
    observed: Json = scan(path)
    return "cached" if json_equal(observed["value"], previous["output"]) else "changed_output"


def build(config: Json, row: Json, entries: Json) -> tuple[Json, Json]:
    name: str = json_string(row["id"])
    record: Json = {
        "id": name,
        "status": "failed",
        "reason": "input_error",
        "outcome": None,
        "stdout_base64": "",
        "stderr_base64": "",
        "error": "",
        "interrupt_signal": 0,
    }
    stage: str = path_join(json_string(config["state"]), "artifact.tmp")
    try:
        observed: tuple[Json, Json, dict[str, str]] = current(config, row, entries)
        entry: Json = observed[0]
        why: str = reason(row, entry, entries)
        record["reason"] = why
        if why == "cached":
            record["status"] = "cached"
            return (entries, record)
        if name in json_keys(entries):
            del entries[name]
        save(config, entries, "invalidate:" + name)
        discard(stage)
        arguments: list[str] = []
        for argument in json_array(row["argv"]):
            text: str = json_string(argument)
            arguments.append(observed[2].get(text, text))
        arguments[0] = absolute(arguments[0], json_string(config["root"]))
        result: tuple[Json, bytes, bytes] = process_run(
            arguments,
            environment(row["environment"]),
            json_string(config["root"]),
            b"",
            json_int(row["timeout_ms"]),
            json_int(row["max_output"]),
        )
        record["outcome"] = result[0]
        record["stdout_base64"] = base64_encode(result[1])
        record["stderr_base64"] = base64_encode(result[2])
        record["interrupt_signal"] = result[0]["interrupt_signal"]
        assert json_string(result[0]["kind"]) == "exited" and json_int(result[0]["returncode"]) == 0, "command failed"
        produced: Json = scan(stage)
        with file_open(stage, "r+b") as handle:
            file_sync(handle)
        checkpoint("produced:" + name)
        unchanged(observed[1])
        assert json_equal(produced["stamp"], regular(stage)), "staged output changed"
        output: str = json_string(row["output_path"])
        if present(output):
            regular(output)
        replace_file(stage, output)
        sync_directory(path_parent(output))
        checkpoint("published:" + name)
        unchanged(observed[1])
        entry["output"] = produced["value"]
        entries[name] = entry
        save(config, entries, "success:" + name)
        record["status"] = "rebuilt"
    except Exception as error:
        if name in json_keys(entries):
            del entries[name]
        record["error"] = str(error)
    discard(stage)
    return (entries, record)
