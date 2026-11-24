"""Typed records, bounded JSONL encoding and stable ordering by key then input position."""

from dataclasses import dataclass

from py2rust.stdlib import (
    FileHandle,
    Json,
    LineReader,
    Sha256,
    json_array,
    json_canonical,
    json_int,
    json_keys,
    json_loads,
    json_string,
)


@dataclass
class Job:
    inputs: list[str]
    field: str
    kind: str
    chunk_bytes: int
    record_bytes: int
    fan_in: int
    max_rows: int
    memory_bytes: int
    output: str
    workspace: str
    config_path: str
    config_stamp: Json


@dataclass
class Row:
    number: int
    text: str
    sequence: int
    data: str


@dataclass
class Run:
    path: str
    count: int
    size: int
    digest: str


@dataclass
class Cursor:
    handle: LineReader
    expected: Run
    count: int
    size: int
    digest: Sha256


@dataclass
class Writer:
    handle: FileHandle
    count: int
    size: int
    digest: Sha256
    previous: tuple[int, str, int]


def rank(row: Row) -> tuple[int, str, int]:
    return (row.number, row.text, row.sequence)


def parse(raw: bytes, sequence: int, job: Job) -> Row:
    if raw.endswith(b"\n"):
        raw = raw[:-1]
        if raw.endswith(b"\r"):
            raw = raw[:-1]
    assert len(raw) <= job.record_bytes, "physical record exceeds byte limit"
    value: Json = json_loads(raw.decode())
    assert job.field in json_keys(value), "record is missing its sort key"
    encoded: str = json_canonical(value)
    assert len(encoded.encode()) <= job.record_bytes, "canonical record exceeds byte limit"
    number: int = 0
    text: str = ""
    if job.kind == "integer":
        number = json_int(value[job.field])
    else:
        text = json_string(value[job.field])
    return Row(number, text, sequence, encoded)


def encode(row: Row) -> bytes:
    return (json_canonical([row.number, row.text, row.sequence, row.data]) + "\n").encode()


def decode(raw: bytes, job: Job) -> Row:
    value: list[Json] = json_array(json_loads(raw.decode()))
    assert len(value) == 4, "invalid run record"
    row: Row = Row(json_int(value[0]), json_string(value[1]), json_int(value[2]), json_string(value[3]))
    assert 0 <= row.sequence < job.max_rows, "invalid saved input position"
    assert (
        len(row.data.encode()) <= job.record_bytes and len(row.text.encode()) <= job.record_bytes
    ), "run record exceeds limit"
    return row
