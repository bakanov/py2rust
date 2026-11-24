"""Edit, normalize and expand an INI document before atomically publishing a reusable bundle."""

# ruff: noqa: BLE001, LOG015, PLC0206, PLR1711 - explicit returns and supported subset operations
import logging

from documents import Document, absolute, checkpoint, present, publish, read, unchanged
from editing import apply
from expansion import expand
from syntax import Line, parse, values, write

from py2rust.stdlib import (
    Json,
    env_get,
    json_canonical,
    json_keys,
    json_loads,
    json_string,
    path_parent,
    path_resolve,
    pretty,
    process_exit,
    sha256_digest,
    sha256_new,
    sha256_update,
)


def run() -> None:
    mode: str = env_get("INI_MODE", "preview")
    assert mode in ["preview", "write"], "invalid INI mode"
    config: Document = read(absolute(env_get("INI_CONFIG", "ini-job.json"), path_resolve(".")), 65536)
    job: Json = json_loads(config.data.decode())
    assert json_keys(job) == ["edits", "output", "source"], "invalid INI job fields"
    output: str = absolute(json_string(job["output"]), path_parent(config.path))
    assert not present(output), "output directory already exists"
    source: Document = read(absolute(json_string(job["source"]), path_parent(config.path)), 1048576)
    edits: Document = read(absolute(json_string(job["edits"]), path_parent(config.path)), 65536)
    lines: list[Line] = apply(parse(source.data.decode()), json_loads(edits.data.decode()))
    normalized: str = write(lines)
    parsed: list[Line] = parse(normalized)
    raw: dict[str, str] = values(parsed)
    expanded: dict[str, str] = expand(raw)
    assert values(lines) == raw and write(parsed) == normalized, "INI round-trip mismatch"
    values_json: Json = {}
    raw_json: Json = {}
    for name in raw:
        raw_json[name] = raw[name]
        values_json[name] = expanded[name]
    report: Json = {"version": 1, "raw": raw_json, "expanded": values_json, "keys": len(raw)}
    files: dict[str, bytes] = {
        "settings.ini": normalized.encode(),
        "values.json": (json_canonical(values_json) + "\n").encode(),
        "report.json": (json_canonical(report) + "\n").encode(),
        "input.ini": source.data,
        "edits.json": edits.data,
    }
    checksums: Json = {}
    total: int = 0
    for name in files:
        total = total + len(files[name])
        assert total <= 8388608, "exports exceed 8 MiB"
        checksums[name] = {"bytes": len(files[name]), "sha256": sha256_digest(sha256_update(sha256_new(), files[name]))}
    files["manifest.json"] = (pretty({"version": 1, "files": checksums}) + "\n").encode()
    documents: list[Document] = [config, source, edits]
    checkpoint("validated")
    unchanged(documents)
    if mode == "write":
        publish(output, files, documents)
    print(json_canonical(report))
    return


def main() -> None:
    try:
        run()
    except Exception as error:
        logging.error(str(error))
        process_exit(2)
    return


if __name__ == "__main__":
    main()
