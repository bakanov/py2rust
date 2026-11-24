"""Append bounded records, synchronize batches, and resume from verified offsets."""

from storage import fault, guard, names, present, save
from transform import Row, classify

from py2rust.stdlib import (
    FileHandle,
    Json,
    LineReader,
    Sha256,
    env_get,
    file_seek,
    file_size,
    file_sync,
    file_truncate,
    file_write,
    json_canonical,
    json_int,
    json_string,
    line_position,
    line_read,
    sha256_digest,
    sha256_new,
    sha256_update,
)


def cancelled() -> bool:
    marker: str = env_get("JSONL_CANCEL", "")
    return marker != "" and present(marker)


def append(handle: FileHandle, data: bytes, hashed: Sha256) -> Sha256:
    file_write(handle, data)
    return sha256_update(hashed, data)


def commit(config: Json, state: Json, outputs: list[FileHandle], hashes: list[Sha256], start: int, phase: str) -> Json:
    guard(config, state)
    batch: int = json_int(state["batches"]) + (1 if json_int(state["lines"]) > start else 0)
    fault("before_sync", batch)
    paths: list[str] = names()
    entries: Json = state["outputs"]
    for index in range(3):
        position: int = file_seek(outputs[index], 0, 1)
        assert position == file_size(outputs[index]), "output size changed during processing"
        file_sync(outputs[index])
        entry: Json = entries[paths[index]]
        entry["size"] = position
        entry["sha256"] = sha256_digest(hashes[index + 1])
        entries[paths[index]] = entry
    state["outputs"] = entries
    state["source_sha256"] = sha256_digest(hashes[0])
    state["phase"] = phase
    state["batches"] = batch
    fault("after_sync", batch)
    save(json_string(config["output"]), state)
    fault("checkpoint", batch)
    return state


def run(config: Json, state: Json, reader: LineReader, outputs: list[FileHandle], hashes: list[Sha256]) -> Json:
    if json_string(state["phase"]) == "complete":
        return state
    start: int = json_int(state["lines"])
    batch_offset: int = json_int(state["offset"])
    raw_start: int = file_seek(outputs[1], 0, 1)
    length: int = 0
    buffer: bytes = b""
    spilled: bool = False
    line_hash: Sha256 = sha256_new()
    source_hash: Sha256 = hashes[0]
    raw_hash: Sha256 = hashes[2]
    while True:
        if cancelled():
            file_truncate(outputs[1], raw_start)
            file_seek(outputs[1], raw_start, 0)
            return commit(config, state, outputs, hashes, start, "paused")
        chunk: tuple[bytes, bool] = line_read(reader, json_int(config["chunk_bytes"]))
        if len(chunk[0]) == 0:
            assert length == 0 and json_int(state["offset"]) == json_int(
                state["input"]["size"]
            ), "source ended unexpectedly"
            return commit(config, state, outputs, hashes, start, "complete")
        length = length + len(chunk[0])
        line_hash = sha256_update(line_hash, chunk[0])
        source_hash = sha256_update(source_hash, chunk[0])
        if spilled:
            raw_hash = append(outputs[1], chunk[0], raw_hash)
        elif length > json_int(config["max_line_bytes"]):
            raw_hash = append(outputs[1], buffer, raw_hash)
            raw_hash = append(outputs[1], chunk[0], raw_hash)
            buffer = b""
            spilled = True
            fault("spill", json_int(state["lines"]) + 1)
        else:
            buffer = buffer + chunk[0]
        if chunk[1]:
            row: Row = Row("rejected", b"", "line exceeds byte limit") if spilled else classify(buffer, config)
            number: int = json_int(state["lines"]) + 1
            if row.kind == "accepted":
                hashes[1] = append(outputs[0], row.data, hashes[1])
            elif row.kind == "rejected":
                if not spilled:
                    raw_hash = append(outputs[1], buffer, raw_hash)
                entry: Json = {
                    "line": number,
                    "offset": state["offset"],
                    "length": length,
                    "raw_offset": raw_start,
                    "sha256": sha256_digest(line_hash),
                    "reason": row.reason,
                }
                hashes[3] = append(outputs[2], (json_canonical(entry) + "\n").encode(), hashes[3])
            state[row.kind] = json_int(state[row.kind]) + 1
            state["lines"] = number
            state["offset"] = line_position(reader)
            hashes[0] = source_hash
            hashes[2] = raw_hash
            raw_start = file_seek(outputs[1], 0, 1)
            length = 0
            buffer = b""
            spilled = False
            line_hash = sha256_new()
            fault("row", number)
            if number - start >= json_int(config["batch_rows"]) or json_int(state["offset"]) - batch_offset >= json_int(
                config["batch_bytes"]
            ):
                phase: str = "complete" if json_int(state["offset"]) == json_int(state["input"]["size"]) else "running"
                state = commit(config, state, outputs, hashes, start, phase)
                start = number
                batch_offset = json_int(state["offset"])
                if phase == "complete":
                    return state
    return state
