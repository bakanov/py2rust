"""Plan filtered JSONL appends and rotate before a record would exceed its segment."""

# ruff: noqa: I001 - compact grouped runtime imports within 120 columns
from config import severity
from files import hashed, read

from py2rust.stdlib import (
    Json, json_array, json_canonical, json_int, json_keys, json_string, path_join
)


def route(config: Json, state: Json, rows: list[Json]) -> tuple[Json, Json]:
    files: Json = state["files"]
    segments: Json = state["segments"]
    additions: Json = {}
    buffers: dict[str, bytes] = {}
    for row in rows:
        matched: bool = False
        data: bytes = (json_canonical(row) + "\n").encode()
        assert len(data) <= json_int(config["segment_bytes"]), "encoded record exceeds segment size"
        for rule in json_array(config["routes"]):
            if row["source"] not in json_array(rule["sources"]):
                continue
            if severity(json_string(row["level"])) < severity(json_string(rule["minimum"])):
                continue
            if json_string(rule["contains"]) not in json_string(row["message"]):
                continue
            matched = True
            key: str = json_string(rule["id"])
            index: int = json_int(segments[key])
            name: str = key + "." + str(index) + ".jsonl"
            if name not in buffers:
                buffers[name] = (
                    read(path_join(json_string(config["output"]), name), 16384) if name in json_keys(files) else b""
                )
            if len(buffers[name]) + len(data) > json_int(config["segment_bytes"]):
                index = index + 1
                assert index < json_int(
                    config["segments"]
                ), "output capacity reached; input positions were not committed"
                segments[key] = index
                name = key + "." + str(index) + ".jsonl"
                buffers[name] = b""
            buffers[name] = buffers[name] + data
            previous: str = json_string(additions[name]) if name in json_keys(additions) else ""
            additions[name] = previous + data.decode()
            count: int = json_int(files[name]["records"]) if name in json_keys(files) else 0
            files[name] = {"bytes": len(buffers[name]), "sha256": hashed(buffers[name]), "records": count + 1}
        if not matched:
            state["filtered"] = json_int(state["filtered"]) + 1
    state["files"] = files
    state["segments"] = segments
    return (state, additions)
