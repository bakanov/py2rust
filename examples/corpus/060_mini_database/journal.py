"""Framed committed records, prefix recovery and snapshot-before-truncation compaction."""

# ruff: noqa: PLR1711 - explicit subset returns

import model
import storage as disk
from model import State

from py2rust.stdlib import FileHandle, Json, json_canonical, json_loads


def marker(sequence: int) -> bytes:
    return b"DONE060!" + sequence.to_bytes(8, "big")


def replay(state: State, handle: FileHandle) -> tuple[State, int, int]:
    size: int = disk.file_size(handle)
    assert size <= 16777216, "journal exceeds 16 MiB"
    disk.file_seek(handle, 0, 0)
    valid: int = 0
    previous: int = 0
    applied: int = 0
    while valid < size:
        header: bytes = disk.take(handle, 52)
        assert b"PYDB060!".startswith(header[:8]), "invalid journal magic"
        if len(header) >= 12:
            assert 1 <= int.from_bytes(header[8:12], "big") <= 8192, "invalid journal length"
        if len(header) >= 20:
            candidate: int = int.from_bytes(header[12:20], "big")
            assert 1 <= candidate <= 1000000000, "invalid journal sequence"
            assert (
                previous == 0 and candidate <= state.sequence + 1
            ) or candidate == previous + 1, "journal sequence gap"
        if len(header) < 52:
            break
        length: int = int.from_bytes(header[8:12], "big")
        sequence: int = int.from_bytes(header[12:20], "big")
        body: bytes = disk.take(handle, length)
        if len(body) < length:
            break
        assert model.digest(header[12:20] + body) == header[20:52], "journal checksum mismatch"
        record: Json = json_loads(body.decode())
        assert model.command(record) in ["SET", "DELETE"], "journal contains a nonmutating operation"
        commit: bytes = disk.take(handle, 16)
        assert marker(sequence).startswith(commit), "invalid commit marker"
        if len(commit) < 16:
            break
        if sequence > state.sequence:
            assert sequence == state.sequence + 1, "journal cannot continue snapshot"
            state = model.apply(state, record)
            applied = applied + 1
        previous = sequence
        valid = disk.file_seek(handle, 0, 1)
    if valid < size:
        disk.file_truncate(handle, valid)
        disk.checkpoint("recovery-truncated", state.sequence)
        disk.file_sync(handle)
        disk.checkpoint("recovery-synced", state.sequence)
    disk.file_seek(handle, 0, 2)
    return (state, size - valid, applied)


def append(state: State, handle: FileHandle, record: Json) -> State:
    updated: State = model.apply(state, record)
    body: bytes = json_canonical(record).encode()
    sequence: int = updated.sequence
    encoded_sequence: bytes = sequence.to_bytes(8, "big")
    header: bytes = (
        b"PYDB060!" + len(body).to_bytes(4, "big") + encoded_sequence + model.digest(encoded_sequence + body)
    )
    commit: bytes = marker(sequence)
    assert len(body) <= 8192, "record exceeds 8 KiB"
    assert disk.file_size(handle) + len(header) + len(body) + len(commit) <= 16777216, "journal full; compact first"
    disk.file_seek(handle, 0, 2)
    disk.file_write(handle, header[:20])
    disk.checkpoint("header-part", sequence)
    disk.file_write(handle, header[20:])
    disk.checkpoint("header-written", sequence)
    disk.file_write(handle, body[: len(body) // 2])
    disk.checkpoint("body-part", sequence)
    disk.file_write(handle, body[len(body) // 2 :])
    disk.checkpoint("body-written", sequence)
    disk.file_sync(handle)
    disk.checkpoint("body-synced", sequence)
    disk.file_write(handle, commit[:8])
    disk.checkpoint("commit-part", sequence)
    disk.file_write(handle, commit[8:])
    disk.checkpoint("commit-written", sequence)
    disk.file_sync(handle)
    disk.checkpoint("commit-synced", sequence)
    return updated


def compact(state: State, handle: FileHandle, directory: str) -> None:
    target: str = disk.path_join(directory, "state.json")
    pending: str = disk.path_join(directory, "snapshot.next")
    raw: bytes = model.snapshot(state)
    assert len(raw) <= 4194304, "snapshot exceeds 4 MiB"
    with disk.file_open(pending, "x+b") as output:
        disk.file_write(output, raw[: len(raw) // 2])
        disk.checkpoint("snapshot-part", state.sequence)
        disk.file_write(output, raw[len(raw) // 2 :])
        disk.checkpoint("snapshot-written", state.sequence)
        disk.file_sync(output)
        disk.checkpoint("snapshot-synced", state.sequence)
    disk.replace_file(pending, target)
    disk.checkpoint("snapshot-published", state.sequence)
    disk.sync_directory(directory)
    disk.checkpoint("snapshot-directory", state.sequence)
    disk.file_truncate(handle, 0)
    disk.checkpoint("journal-truncated", state.sequence)
    disk.file_sync(handle)
    disk.file_seek(handle, 0, 0)
    disk.checkpoint("journal-cleared", state.sequence)
    return
