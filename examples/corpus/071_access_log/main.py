"""Analyze immutable log inputs, retain malformed bytes and publish a reusable report bundle."""

# ruff: noqa: PLR1711, BLE001, LOG015, PLC0206 - explicit returns and subset operations

import logging

from aggregate import summarize
from documents import Document, absolute, checkpoint, present, publish, read, unchanged
from parser import lines, parse

from py2rust.stdlib import (
    Json,
    datetime_iso,
    datetime_parse,
    env_get,
    json_array,
    json_bool,
    json_canonical,
    json_int,
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


def digest(data: bytes) -> str:
    return sha256_digest(sha256_update(sha256_new(), data))


def exact(value: Json, fields: list[str]) -> None:
    assert json_keys(value) == sorted(fields), "unexpected object fields"
    return


def boundary(value: Json) -> Json:
    if value is None:
        return None
    return datetime_iso(datetime_parse(json_string(value)))


def run() -> int:
    mode: str = env_get("ACCESS_MODE", "preview")
    assert mode in ["preview", "write"], "invalid access-log mode"
    path: str = absolute(env_get("ACCESS_CONFIG", "access-job.json"), path_resolve("."))
    configuration: Document = read(path, 65536)
    config: Json = json_loads(configuration.data.decode())
    exact(config, ["sources", "start", "end", "top", "output"])
    start: Json = boundary(config["start"])
    end: Json = boundary(config["end"])
    assert start is None or end is None or json_string(start) <= json_string(end), "reversed time window"
    top: int = json_int(config["top"])
    assert 0 <= top <= 100, "top outside 0..100"
    base: str = path_parent(path)
    output: str = absolute(json_string(config["output"]), base)
    assert not present(output), "output directory already exists"
    manifest: Document = read(absolute(json_string(config["sources"]), base), 65536)
    source_config: Json = json_loads(manifest.data.decode())
    exact(source_config, ["version", "files"])
    assert json_int(source_config["version"]) == 1, "unsupported source version"
    sources: list[Json] = json_array(source_config["files"])
    assert len(sources) <= 8, "source count exceeds 8"
    documents: list[Document] = [configuration, manifest]
    names: set[str] = set()
    paths: set[str] = set()
    files: dict[str, bytes] = {}
    hashes: Json = {}
    exported: list[Json] = []
    records: list[Json] = []
    valid_lines: list[str] = []
    invalid_lines: list[str] = []
    count: int = 0
    input_bytes: int = 0
    record_bytes: int = 0
    for source in sources:
        exact(source, ["name", "path"])
        name: str = json_string(source["name"])
        assert 1 <= len(name) <= 128 and len(name.encode()) <= 512 and "\x00" not in name, "invalid source name"
        assert name not in names, "duplicate source name"
        names.add(name)
        source_path: str = absolute(json_string(source["path"]), path_parent(manifest.path))
        assert source_path not in paths, "duplicate source path"
        paths.add(source_path)
        source_document: Document = read(source_path, 1048576)
        input_bytes = input_bytes + len(source_document.data)
        assert input_bytes <= 4194304, "combined logs exceed 4 MiB"
        documents.append(source_document)
        filename: str = "source-" + str(len(exported)) + ".log"
        files[filename] = source_document.data
        exported.append({"name": name, "path": filename})
        hashes[name] = digest(source_document.data)
        number: int = 0
        for raw in lines(source_document.data):
            number = number + 1
            count = count + 1
            assert count <= 10000, "log line count exceeds 10000"
            result: Json = parse(raw)
            row: Json = {"source": name, "line": number}
            if json_bool(result["ok"]):
                row = result["record"]
                row["source"] = name
                row["line"] = number
                timestamp: str = json_string(row["timestamp"])
                row["selected"] = (start is None or timestamp >= json_string(start)) and (
                    end is None or timestamp < json_string(end)
                )
            else:
                row["reason"] = result["reason"]
                row["raw_hex"] = raw.hex()
            encoded: str = json_canonical(row) + "\n"
            record_bytes = record_bytes + len(encoded.encode())
            assert record_bytes <= 16777216, "record exports exceed 16 MiB"
            if json_bool(result["ok"]):
                records.append(row)
                valid_lines.append(encoded)
            else:
                invalid_lines.append(encoded)
    summary: Json = summarize(records, top)
    selected: int = json_int(summary["requests"])
    report: Json = {
        "version": 1,
        "window": {"start": start, "end": end},
        "top": top,
        "input_sha256": hashes,
        "counts": {
            "lines": count,
            "valid": len(records),
            "malformed": len(invalid_lines),
            "selected": selected,
            "filtered": len(records) - selected,
        },
        "summary": summary,
    }
    files["sources.json"] = (json_canonical({"version": 1, "files": exported}) + "\n").encode()
    files["report.json"] = (json_canonical(report) + "\n").encode()
    files["records.jsonl"] = "".join(valid_lines).encode()
    files["invalid.jsonl"] = "".join(invalid_lines).encode()
    files["summary.txt"] = ("Access-log analysis\n" + pretty(report) + "\n").encode()
    checksums: Json = {}
    for name in files:
        assert len(files[name]) <= 33554432, "output file exceeds 32 MiB"
        checksums[name] = {"bytes": len(files[name]), "sha256": digest(files[name])}
    files["manifest.json"] = (pretty({"version": 1, "files": checksums}) + "\n").encode()
    checkpoint("validated")
    unchanged(documents)
    if mode == "write":
        publish(output, files, documents)
    print(json_canonical(report))
    return 0 if len(invalid_lines) == 0 else 1


def main() -> None:
    try:
        status: int = run()
        if status != 0:
            process_exit(status)
    except Exception as error:
        logging.error(str(error))
        process_exit(2)
    return


if __name__ == "__main__":
    main()
