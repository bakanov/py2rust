"""Bounded run generation, checksum-verified readers and heap-based multiway merging."""

# ruff: noqa: PLR1711, BLE001 - explicit returns and error propagation

import heapq

from model import Cursor, Job, Row, Run, Writer, decode, encode, parse, rank
from storage import checkpoint, stamp

from py2rust.stdlib import (
    Json,
    file_open,
    file_sync,
    file_write,
    json_equal,
    json_int,
    line_close,
    line_open,
    line_read,
    path_join,
    sha256_digest,
    sha256_new,
    sha256_update,
)


def write(writer: Writer, row: Row, plain: bool) -> Writer:
    assert writer.count == 0 or writer.previous <= rank(row), "output is out of order"
    writer.previous = rank(row)
    data: bytes = (row.data + "\n").encode() if plain else encode(row)
    file_write(writer.handle, data)
    writer.count = writer.count + 1
    writer.size = writer.size + len(data)
    writer.digest = sha256_update(writer.digest, data)
    return writer


def finish(writer: Writer, path: str) -> Run:
    file_sync(writer.handle)
    return Run(path, writer.count, writer.size, sha256_digest(writer.digest))


def run_path(job: Job, identifier: int) -> str:
    return path_join(job.workspace, "run-" + str(identifier) + ".jsonl")


def write_run(job: Job, identifier: int, rows: list[Row]) -> Run:
    path: str = run_path(job, identifier)
    with file_open(path, "x+b") as handle:
        writer: Writer = Writer(handle, 0, 0, sha256_new(), (0, "", 0))
        checkpoint("run-open")
        for row in sorted(rows, key=rank):
            writer = write(writer, row, False)
        checkpoint("run-written")
        return finish(writer, path)


def generate(job: Job, stamps: list[Json]) -> tuple[list[Run], Json]:
    runs: list[Run] = []
    batch: list[Row] = []
    batch_bytes: int = 0
    peak_bytes: int = 0
    total: int = 0
    sources: list[Json] = []
    for position in range(len(job.inputs)):
        path: str = job.inputs[position]
        lines: int = 0
        size: int = 0
        with line_open(path, 0) as reader:
            while True:
                if len(batch) > 0 and (batch_bytes + job.record_bytes > job.chunk_bytes or len(batch) == 4096):
                    assert len(runs) < 4096, "initial run count exceeds 4096"
                    runs.append(write_run(job, len(runs), batch))
                    batch.clear()
                    batch_bytes = 0
                part: tuple[bytes, bool] = line_read(reader, job.record_bytes + 2)
                if len(part[0]) == 0:
                    break
                lines = lines + 1
                try:
                    assert part[1], "physical record exceeds byte limit"
                    assert total < job.max_rows, "row limit exceeded"
                    row: Row = parse(part[0], total, job)
                    total = total + 1
                    batch.append(row)
                    batch_bytes = batch_bytes + len(row.data.encode())
                    peak_bytes = max(peak_bytes, batch_bytes)
                    size = size + len(part[0])
                    assert size <= json_int(stamps[position]["size"]), "input grew while reading"
                except Exception as error:
                    assert False, path + " line " + str(lines) + ": " + str(error)
        assert size == json_int(stamps[position]["size"]) and json_equal(
            stamps[position], stamp(path)
        ), "input changed while reading"
        sources.append({"input_index": position, "rows": lines, "bytes": size})
    if len(batch) > 0:
        assert len(runs) < 4096, "initial run count exceeds 4096"
        runs.append(write_run(job, len(runs), batch))
    return (runs, {"rows": total, "inputs": sources, "peak_batch_bytes": peak_bytes})


def open_cursor(run: Run) -> Cursor:
    assert json_int(stamp(run.path)["size"]) == run.size, "run file size changed"
    return Cursor(line_open(run.path, 0), run, 0, 0, sha256_new())


def advance(cursor: Cursor, job: Job) -> tuple[Cursor, bool, Row]:
    part: tuple[bytes, bool] = line_read(cursor.handle, job.record_bytes * 4 + 256)
    if len(part[0]) == 0:
        assert cursor.count == cursor.expected.count and cursor.size == cursor.expected.size, "run cardinality changed"
        assert sha256_digest(cursor.digest) == cursor.expected.digest, "run checksum mismatch"
        return (cursor, False, Row(0, "", 0, ""))
    assert part[1], "run record exceeds byte limit"
    row: Row = decode(part[0], job)
    cursor.count = cursor.count + 1
    cursor.size = cursor.size + len(part[0])
    assert cursor.count <= cursor.expected.count and cursor.size <= cursor.expected.size, "run grew while reading"
    cursor.digest = sha256_update(cursor.digest, part[0])
    return (cursor, True, row)


def close_all(cursors: list[Cursor]) -> None:
    for cursor in cursors:
        line_close(cursor.handle)
    return


def merge(job: Job, sources: list[Run], target: str, plain: bool) -> Run:
    cursors: list[Cursor] = []
    heads: dict[int, Row] = {}
    heap: list[tuple[int, str, int, int]] = []
    result: Run = Run(target, 0, 0, "")
    try:
        for position in range(len(sources)):
            cursors.append(open_cursor(sources[position]))
            item: tuple[Cursor, bool, Row] = advance(cursors[position], job)
            cursors[position] = item[0]
            if item[1]:
                heads[position] = item[2]
                key: tuple[int, str, int] = rank(item[2])
                heapq.heappush(heap, (key[0], key[1], key[2], position))
        with file_open(target, "x+b") as handle:
            writer: Writer = Writer(handle, 0, 0, sha256_new(), (0, "", 0))
            checkpoint("merge-open")
            while len(heap) > 0:
                position: int = heapq.heappop(heap)[3]
                writer = write(writer, heads[position], plain)
                item: tuple[Cursor, bool, Row] = advance(cursors[position], job)
                cursors[position] = item[0]
                if item[1]:
                    heads[position] = item[2]
                    key: tuple[int, str, int] = rank(item[2])
                    heapq.heappush(heap, (key[0], key[1], key[2], position))
                else:
                    del heads[position]
            checkpoint("merge-written")
            result = finish(writer, target)
    except Exception:
        close_all(cursors)
        raise
    close_all(cursors)
    return result
