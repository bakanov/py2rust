"""Bounded binary line chunks, exact positions, shared cursors and scoped closure."""

import hashlib
import io
import json
import os
import subprocess
from pathlib import Path

from .test_services import parity, program


def test_line_chunks_match_independent_byte_oracle(tmp_path: Path) -> None:
    content = b"A\r\nB\rC\n\xff\xf0\x9f\x98\x80\0" + b"x" * 65530 + b"\r\nlast"
    (tmp_path / "input").write_bytes(content)
    cases = []
    for limit in [1, 2, 7, 65536, 1048576]:
        for start in [0, 1, 8, 65535, len(content)]:
            reader = io.BytesIO(content)
            reader.seek(start)
            rows = []
            while True:
                data = reader.readline(limit)
                rows.append(
                    {
                        "hex": data.hex(),
                        "complete": data.endswith(b"\n") or reader.tell() == len(content),
                        "position": reader.tell(),
                    }
                )
                if not data:
                    break
            cases.append({"limit": limit, "start": start, "rows": rows})
    (tmp_path / "oracle.json").write_text(json.dumps(cases))
    parity(
        tmp_path,
        """
from py2rust.stdlib import Json, json_array, json_bool, json_int, json_loads, json_string, line_open, line_position, line_read, read_text

def run() -> None:
    cases: list[Json] = json_array(json_loads(read_text("oracle.json")))
    for case in cases:
        with line_open("input", json_int(case["start"])) as reader:
            assert line_position(reader) == json_int(case["start"])
            for row in json_array(case["rows"]):
                chunk: tuple[bytes, bool] = line_read(reader, json_int(case["limit"]))
                assert chunk[0].hex() == json_string(row["hex"])
                assert chunk[1] == json_bool(row["complete"])
                assert line_position(reader) == json_int(row["position"])
            assert line_read(reader, 1) == (b"", True)
    print("line chunks and byte positions agree")
    return

if __name__ == "__main__":
    run()
""",
    )
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def test_line_reader_aliases_cleanup_and_invalid_bounds(tmp_path: Path) -> None:
    (tmp_path / "input").write_bytes(b"first\nsecond")
    (tmp_path / "empty").write_bytes(b"")
    (tmp_path / "directory").mkdir()
    os.mkfifo(tmp_path / "pipe")
    parity(
        tmp_path,
        """
from py2rust.stdlib import LineReader, line_open, line_read, line_position, line_close

def read_alias(reader: LineReader) -> bytes:
    return line_read(reader, 2)[0]

def close_early(reader: LineReader) -> None:
    with reader as scoped:
        assert line_read(scoped, 1)[0] == b"r"
        return

def run() -> None:
    errors: int = 0
    reader: LineReader = line_open("input", 0)
    alias: LineReader = reader
    assert read_alias(alias) == b"fi" and line_position(reader) == 2
    close_early(reader)
    for attempt in range(3):
        try:
            if attempt == 0:
                line_read(alias, 1)
            elif attempt == 1:
                line_position(reader)
            else:
                with reader as reopened:
                    pass
        except Exception as error:
            assert str(error) == "line reader is closed"
            errors = errors + 1
    line_close(reader)
    line_close(alias)
    for offset in [-1, 13]:
        try:
            line_open("input", offset)
        except Exception:
            errors = errors + 1
    for path in ["directory", "pipe", "missing"]:
        try:
            line_open(path, 0)
        except Exception:
            errors = errors + 1
    with line_open("empty", 0) as empty:
        assert line_read(empty, 1048576) == (b"", True) and line_position(empty) == 0
        for limit in [0, -1, 1048577]:
            try:
                line_read(empty, limit)
            except Exception:
                errors = errors + 1
    reader = line_open("input", 6)
    try:
        with reader as scoped:
            assert line_read(scoped, 6) == (b"second", True)
            assert False, "close on failure"
    except Exception:
        pass
    try:
        line_position(reader)
    except Exception:
        errors = errors + 1
    assert errors == 12
    print("line resource lifetime and bounds agree")
    return

if __name__ == "__main__":
    run()
""",
    )
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def test_oversized_line_is_streamed_under_memory_limit(tmp_path: Path) -> None:
    content = b"\xff\0" * 524288
    digest = hashlib.sha256()
    with (tmp_path / "large").open("wb") as output:
        for _ in range(64):
            output.write(content)
            digest.update(content)
        output.write(b"last\r\n")
        digest.update(b"last\r\n")
    source = """
from py2rust.stdlib import Sha256, line_open, line_read, line_position, sha256_new, sha256_update, sha256_digest

def run() -> None:
    state: Sha256 = sha256_new()
    count: int = 0
    with line_open("large", 0) as reader:
        while True:
            chunk: tuple[bytes, bool] = line_read(reader, 65536)
            if len(chunk[0]) == 0:
                assert chunk[1]
                break
            count = count + len(chunk[0])
            assert len(chunk[0]) <= 65536 and line_position(reader) == count
            assert chunk[1] == (count == 67108870)
            state = sha256_update(state, chunk[0])
    assert count == 67108870
    assert sha256_digest(state) == "DIGEST"
    print("64 MiB logical line streamed within 128 MiB")
    return

if __name__ == "__main__":
    run()
""".replace("DIGEST", digest.hexdigest())
    for engine in ["python", "rust"]:
        command = program(tmp_path, source, engine)
        result = subprocess.run(
            ["/usr/bin/prlimit", "--as=134217728", "--", *command],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=40,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "64 MiB logical line streamed within 128 MiB"
    return  # noqa: PLR1711 - explicit return required by repository guidelines
