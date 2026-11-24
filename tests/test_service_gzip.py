"""Streaming gzip interoperability, budgets, corruption and shared resource lifetimes."""

# ruff: noqa: PLR1711 - explicit returns required by repository guidelines
import gzip
import hashlib
import json
import os
import random
import subprocess
import zlib
from pathlib import Path

import pytest
from py2rust.compiler.service import ServiceCompiler, ServiceError

from .test_project import run_project, sources
from .test_services import parity, program

READ = """from py2rust.stdlib import (
    Json, Sha256, gzip_open, gzip_read, json_array, json_bool, json_int, json_string,
    json_loads_unique, read_text, sha256_new, sha256_update, sha256_digest,
)
def run() -> None:
    checked: int = 0
    for row in json_array(json_loads_unique(read_text("cases.json"))):
        valid: bool = json_bool(row["valid"])
        succeeded: bool = False
        try:
            total: int = 0
            digest: Sha256 = sha256_new()
            with gzip_open(json_string(row["path"]), json_int(row["compressed"]), json_int(row["expanded"])) as source:
                while True:
                    part: bytes = gzip_read(source, json_int(row["chunk"]))
                    if len(part) == 0:
                        break
                    total = total + len(part)
                    digest = sha256_update(digest, part)
                assert gzip_read(source, 1) == b""
            assert total == json_int(row["length"])
            assert sha256_digest(digest) == json_string(row["sha256"])
            succeeded = True
        except Exception:
            assert not valid
        assert succeeded == valid
        checked = checked + 1
    print(checked)
    return
if __name__ == "__main__":
    run()
"""

WRITE = """from py2rust.stdlib import (
    file_open, file_read, gzip_create, gzip_write, gzip_finish, json_array, json_int,
    json_string, json_loads_unique, read_text,
)
def run() -> None:
    for row in json_array(json_loads_unique(read_text("write.json"))):
        with gzip_create(json_string(row["output"]), json_int(row["level"]), 10000000, 10000000) as target:
            with file_open(json_string(row["path"]), "rb") as source:
                while True:
                    part: bytes = file_read(source, json_int(row["chunk"]))
                    if len(part) == 0:
                        break
                    gzip_write(target, part)
            gzip_write(target, b"")
            sizes: tuple[int, int] = gzip_finish(target)
            assert sizes[0] >= 20 and sizes[1] == json_int(row["length"])
    print("compressed")
    return
if __name__ == "__main__":
    run()
"""


def member(data: bytes, flags: int = 0, name: bytes = b"name", comment: bytes = b"comment") -> bytes:
    header = b"\x1f\x8b\x08" + bytes([flags]) + b"\x00\x00\x00\x00\x00\xff"
    if flags & 4:
        extra = b"AB\x02\x00xy"
        header += len(extra).to_bytes(2, "little") + extra
    if flags & 8:
        header += name + b"\0"
    if flags & 16:
        header += comment + b"\0"
    if flags & 2:
        header += (zlib.crc32(header) & 65535).to_bytes(2, "little")
    codec = zlib.compressobj(6, zlib.DEFLATED, -15)
    return (
        header
        + codec.compress(data)
        + codec.flush()
        + zlib.crc32(data).to_bytes(4, "little")
        + len(data).to_bytes(4, "little")
    )


def write_cases(root: Path, cases: list[tuple[bytes, int, int, int, bytes | None]]) -> int:
    rows = []
    for index, (data, compressed, expanded, chunk, expected) in enumerate(cases):
        name = f"{index}.gz"
        (root / name).write_bytes(data)
        rows.append(
            {
                "path": name,
                "compressed": compressed,
                "expanded": expanded,
                "chunk": chunk,
                "valid": expected is not None,
                "length": len(expected) if expected is not None else 0,
                "sha256": hashlib.sha256(expected).hexdigest() if expected is not None else "",
            }
        )
    (root / "cases.json").write_text(json.dumps(rows))
    return len(rows)


def test_gzip_independent_streams_and_optional_headers(tmp_path: Path) -> None:
    rng = random.Random(119)
    cases = []
    for level in range(10):
        for size in [0, 1, 257, 65535, 65536, 65537, 1048577]:
            data = rng.randbytes(min(size, 1024)) + b"x" * max(0, size - 1024)
            encoded = gzip.compress(data, compresslevel=level, mtime=0)
            cases.append((encoded, len(encoded), len(data), 257, data))
    for flags in range(32):
        raw = member(b"network\0\xff" * 40, flags)
        assert gzip.decompress(raw) == b"network\0\xff" * 40
        cases.append((raw, len(raw), 360, 1, b"network\0\xff" * 40))
    for name, comment in [(b"n" * 65535, b"c" * 65535), (b"n" * 65536, b""), (b"", b"c" * 65536)]:
        raw = member(b"", 26, name, comment)
        cases.append((raw, len(raw), 0, 1048576, b"" if max(len(name), len(comment)) <= 65535 else None))
    count = write_cases(tmp_path, cases)
    assert parity(tmp_path, READ) == str(count) + "\n"
    return


def test_gzip_corruption_prefixes_and_exact_limits(tmp_path: Path) -> None:
    data = b"hello\0\xff" * 100
    raw = member(data, 31)
    cases = [(raw, len(raw), len(data), 1048576, data), (raw, len(raw) - 1, len(data), 1, None)]
    cases += [(raw, len(raw), len(data) - 1, 257, None), (raw, len(raw), 0, 1, None)]
    cases += [(raw[:index], len(raw), len(data), 257, None) for index in range(len(raw))]
    for offset in [0, 1, 2, 3, 10, 12, 31, -1, -5, -8]:
        corrupted = bytearray(raw)
        corrupted[offset] ^= 0xFF
        cases.append((bytes(corrupted), len(raw), len(data), 257, None))
    for trailing in [b"\0", b"x", member(b""), member(b"second")]:
        cases.append((raw + trailing, len(raw + trailing), 10000, 257, None))
    cases += [(raw, -1, len(data), 1, None), (raw, len(raw), -1, 1, None)]
    cases += [(raw, len(raw), len(data), count, None) for count in [-1, 0, 1048577]]
    count = write_cases(tmp_path, cases)
    assert parity(tmp_path, READ) == str(count) + "\n"
    return


def test_gzip_writer_interoperates_at_all_levels_and_chunks(tmp_path: Path) -> None:
    data = random.Random(119).randbytes(65537) + b"readable network log\n" * 3000
    for engine in ["python", "rust"]:
        home = tmp_path / engine
        home.mkdir()
        (home / "input").write_bytes(data)
        (home / "empty").write_bytes(b"")
        rows = []
        for level in range(10):
            for chunk in [1, 65535, 65536, 1048576]:
                rows.append(
                    {
                        "path": "input",
                        "output": f"out-{level}-{chunk}.gz",
                        "length": len(data),
                        "level": level,
                        "chunk": chunk,
                    }
                )
        rows.append({"path": "empty", "output": "empty.gz", "length": 0, "level": 6, "chunk": 1})
        (home / "write.json").write_text(json.dumps(rows))
        result = subprocess.run(
            program(home, WRITE, engine), cwd=home, capture_output=True, text=True, timeout=180, check=False
        )
        assert result.returncode == 0 and result.stdout == "compressed\n" and not result.stderr, result
        for row in rows:
            compressed = (home / row["output"]).read_bytes()
            assert gzip.decompress(compressed) == (home / row["path"]).read_bytes()
            assert compressed[:8] == b"\x1f\x8b\x08\0\0\0\0\0" and compressed[9] == 255
            assert compressed[8] == (2 if row["level"] == 9 else 4 if row["level"] <= 1 else 0)
    return


def test_gzip_explicit_finish_abort_and_alias_lifetimes(tmp_path: Path) -> None:
    assert (
        parity(
            tmp_path,
            """from py2rust.stdlib import (
    GzipWriter, GzipReader, gzip_create, gzip_write, gzip_finish, gzip_writer_close,
    gzip_open, gzip_read, gzip_reader_close, read_bytes, remove_file,
)
def abandon(writer: GzipWriter) -> int:
    with writer as held:
        gzip_write(held, b"partial")
        return 7
def run() -> None:
    writer: GzipWriter = gzip_create("ok.gz", 6, 1000, 3)
    alias: GzipWriter = writer
    with writer as held:
        gzip_write(held, b"abc")
        sizes: tuple[int, int] = gzip_finish(alias)
        assert sizes[0] == len(read_bytes("ok.gz")) and sizes[1] == 3
    errors: int = 0
    try:
        gzip_finish(writer)
    except Exception:
        errors = errors + 1
    try:
        gzip_write(alias, b"")
    except Exception:
        errors = errors + 1
    gzip_writer_close(alias)
    failed: GzipWriter = gzip_create("partial.gz", 6, 1000, 100)
    assert abandon(failed) == 7
    try:
        gzip_finish(failed)
    except Exception:
        errors = errors + 1
    try:
        with gzip_open("partial.gz", 1000, 100) as unfinished:
            gzip_read(unfinished, 100)
    except Exception:
        errors = errors + 1
    for index in range(2):
        iteration: GzipWriter = gzip_create("loop.gz", 6, 1000, 100)
        with iteration as scoped:
            gzip_write(scoped, b"not finalized")
            if index == 0:
                continue
            break
        assert False
    print(errors)
    return
if __name__ == "__main__":
    run()
""".replace('"loop.gz"', '"loop-" + str(index) + ".gz"').replace(
                "    print(errors)",
                """    reader: GzipReader = gzip_open("ok.gz", 1000, 3)
    other: GzipReader = reader
    with reader as input:
        assert gzip_read(input, 1) == b"a"
    try:
        gzip_read(other, 1)
    except Exception:
        errors = errors + 1
    gzip_reader_close(reader)
    try:
        with other as closed:
            assert False
    except Exception:
        errors = errors + 1
    for name in ["ok.gz", "partial.gz", "loop-0.gz", "loop-1.gz"]:
        remove_file(name)
    assert errors == 6
    print(errors)""",
            ),
        )
        == "6\n"
    )
    return


def test_gzip_writer_limits_failure_poisoning_and_paths(tmp_path: Path) -> None:
    (tmp_path / "link").symlink_to("missing")
    os.mkfifo(tmp_path / "pipe")
    assert (
        parity(
            tmp_path,
            """from py2rust.stdlib import (
    GzipWriter, gzip_create, gzip_write, gzip_finish, gzip_open, gzip_read,
    gzip_writer_close, path_exists, read_bytes, remove_file,
)
def run() -> None:
    errors: int = 0
    for bound in [-1, 0, 9]:
        try:
            gzip_create("never", 6, bound, 100)
        except Exception:
            errors = errors + 1
    assert not path_exists("never")
    for level in [-1, 10]:
        try:
            gzip_create("never", level, 1000, 100)
        except Exception:
            errors = errors + 1
    for path in ["link", "pipe", "."]:
        try:
            gzip_create(path, 6, 1000, 100)
        except Exception:
            errors = errors + 1
        try:
            gzip_open(path, 1000, 100)
        except Exception:
            errors = errors + 1
    limited: GzipWriter = gzip_create("limited", 6, 1000, 1)
    try:
        gzip_write(limited, b"xx")
    except Exception:
        errors = errors + 1
    try:
        gzip_finish(limited)
    except Exception:
        errors = errors + 1
    gzip_writer_close(limited)
    for bound in [10, 11, 19, 20]:
        succeeded: bool = False
        try:
            with gzip_create("bound-" + str(bound), 6, bound, 0) as output:
                result: tuple[int, int] = gzip_finish(output)
                assert result == (20, 0)
                succeeded = True
        except Exception:
            assert bound < 20
        assert succeeded == (bound == 20)
        assert len(read_bytes("bound-" + str(bound))) <= bound
        remove_file("bound-" + str(bound))
    assert errors == 13
    remove_file("limited")
    print("limits passed")
    return
if __name__ == "__main__":
    run()
""",
        )
        == "limits passed\n"
    )
    return


def test_gzip_large_stream_under_memory_limit(tmp_path: Path) -> None:
    block = b"network log line\0" * 4096
    (tmp_path / "block").write_bytes(block)
    expected = hashlib.sha256()
    for _ in range(4096):
        expected.update(block)
    source = """from py2rust.stdlib import (
    Sha256, read_bytes, gzip_create, gzip_write, gzip_finish, gzip_open, gzip_read,
    sha256_new, sha256_update, sha256_digest, remove_file,
)
def run() -> None:
    block: bytes = read_bytes("block")
    with gzip_create("large.gz", 6, 10000000, 300000000) as target:
        for index in range(4096):
            gzip_write(target, block)
        gzip_finish(target)
    digest: Sha256 = sha256_new()
    size: int = 0
    with gzip_open("large.gz", 10000000, 300000000) as input:
        while True:
            part: bytes = gzip_read(input, 65536)
            if len(part) == 0:
                break
            size = size + len(part)
            digest = sha256_update(digest, part)
    print(size)
    print(sha256_digest(digest))
    remove_file("large.gz")
    return
if __name__ == "__main__":
    run()
"""
    for engine in ["python", "rust"]:
        command = program(tmp_path, source, engine, engine)
        result = subprocess.run(
            ["/usr/bin/prlimit", "--as=134217728", "--", *command],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        assert result.returncode == 0 and not result.stderr, result
        assert result.stdout == f"{len(block) * 4096}\n{expected.hexdigest()}\n"
    return


def test_gzip_whole_project_resource_imports(tmp_path: Path) -> None:
    root = sources(
        tmp_path,
        {
            "main.py": """from codec import write, check
def main() -> None:
    write()
    check()
    print("project gzip")
    return

if __name__ == "__main__":
    main()
""",
            "codec.py": """from py2rust.stdlib import GzipWriter, gzip_create, gzip_finish, gzip_write, gzip_open, gzip_read
def finish(writer: GzipWriter) -> None:
    gzip_finish(writer)
    return
def write() -> None:
    with gzip_create("project.gz", 6, 1000, 3) as output:
        gzip_write(output, b"abc")
        finish(output)
    return
def check() -> None:
    with gzip_open("project.gz", 1000, 3) as input:
        assert gzip_read(input, 10) == b"abc"
        assert gzip_read(input, 1) == b""
    return
""",
        },
    )
    result = run_project(root, tmp_path / "rust")
    assert result.returncode == 0 and result.stdout == "project gzip\n" and not result.stderr, result
    return


def test_gzip_failure_poisoning_and_exception_cleanup(tmp_path: Path) -> None:
    corrupted = bytearray(gzip.compress(b"broken trailer", mtime=0))
    corrupted[-8] ^= 1
    (tmp_path / "broken.gz").write_bytes(corrupted)
    assert (
        parity(
            tmp_path,
            """from py2rust.stdlib import (
    GzipWriter, GzipReader, gzip_create, gzip_write, gzip_finish, gzip_writer_close,
    gzip_open, gzip_read, gzip_reader_close, file_open, file_seek, file_write, remove_file,
)
def run() -> None:
    errors: int = 0
    writer: GzipWriter = gzip_create("aborted.gz", 6, 1000, 100)
    try:
        with writer as resource:
            gzip_write(resource, b"interrupted")
            assert False, "abort"
    except Exception:
        errors = errors + 1
    try:
        gzip_finish(writer)
    except Exception:
        errors = errors + 1
    gzip_writer_close(writer)
    reader: GzipReader = gzip_open("broken.gz", 1000, 100)
    alias: GzipReader = reader
    try:
        gzip_read(reader, 100)
    except Exception:
        errors = errors + 1
    try:
        gzip_read(alias, 1)
    except Exception:
        errors = errors + 1
    gzip_reader_close(reader)
    with gzip_create("growing.gz", 6, 100, 3) as output:
        gzip_write(output, b"abc")
        sizes: tuple[int, int] = gzip_finish(output)
        reader = gzip_open("growing.gz", sizes[0], 3)
    with file_open("growing.gz", "r+b") as changed:
        file_seek(changed, 0, 2)
        file_write(changed, b"x")
    try:
        gzip_read(reader, 100)
    except Exception:
        errors = errors + 1
    try:
        gzip_read(reader, 1)
    except Exception:
        errors = errors + 1
    try:
        gzip_create("growing.gz", 6, 100, 3)
    except Exception:
        errors = errors + 1
    assert errors == 7
    remove_file("aborted.gz")
    remove_file("growing.gz")
    print("poisoned and closed")
    return
if __name__ == "__main__":
    run()
""",
        )
        == "poisoned and closed\n"
    )
    return


@pytest.mark.parametrize(
    "expression",
    [
        'gzip_create("x", True, 100, 100)',
        'gzip_create("x", 6, 1.0, 100)',
        'gzip_open("x", 100)',
        'gzip_read("x", 1)',
        'gzip_finish("x")',
        'gzip_write(gzip_create("x", 6, 100, 100), "text")',
    ],
)
def test_gzip_rejects_wrong_types(expression: str) -> None:
    with pytest.raises(ServiceError):
        ServiceCompiler().compile(
            "from py2rust.stdlib import gzip_create, gzip_open, gzip_read, gzip_finish, gzip_write\ndef run() -> None:\n    "
            + expression
            + "\n    return\n"
        )
    return
