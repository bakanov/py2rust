"""Independent Unicode conformance, cell widths and real stdout/PTY terminal operations."""

import hashlib
import json
import os
import select
import struct
import subprocess
import time
from pathlib import Path

import pytest
from uniseg.graphemecluster import grapheme_clusters
from wcwidth import table_vs16, table_wide, table_zero, wcswidth, wcwidth

from .test_services import program

SOURCE = """from py2rust.stdlib import (
    Json, Sha256, env_get, json_array, json_canonical, json_loads_unique, json_string,
    read_text, write_text, sha256_new, sha256_update, sha256_digest, sleep,
    terminal_cells, terminal_info, terminal_write,
)
def run() -> None:
    mode: str = env_get("TERMINAL_TEST", "batch")
    if mode == "batch":
        for row in json_array(json_loads_unique(read_text("cases.json"))):
            try:
                print(json_canonical(terminal_cells(json_string(row))))
            except Exception:
                print("null")
    elif mode == "scalar":
        state: Sha256 = sha256_new()
        count: int = 0
        for character in read_text("scalars"):
            cells: list[tuple[str, int]] = terminal_cells(character)
            assert len(cells) == 1
            state = sha256_update(state, str(cells[0][1]).encode())
            count = count + 1
        print(str(count) + " " + sha256_digest(state))
    elif mode == "info":
        terminal_write(json_canonical(terminal_info()) + "\\n")
    elif mode == "resize":
        terminal_write(json_canonical(terminal_info()) + "\\nready")
        sleep(0.5)
        terminal_write("\\n" + json_canonical(terminal_info()) + "\\n")
    elif mode == "write":
        try:
            terminal_write(read_text("payload"))
        except Exception:
            write_text("caught", "yes")
    elif mode == "closed":
        terminal_write("ready")
        sleep(0.5)
        try:
            terminal_write("after close")
        except Exception:
            write_text("caught", "yes")
    return
if __name__ == "__main__":
    run()
"""


@pytest.fixture(scope="module")
def applications(tmp_path_factory: pytest.TempPathFactory) -> dict:
    root = tmp_path_factory.mktemp("terminal-build")
    return {engine: program(root, SOURCE, engine, "terminal_" + engine) for engine in ["python", "rust"]}


def forbidden(code: int) -> bool:
    return (
        code < 32
        or 127 <= code <= 159
        or 55296 <= code <= 57343
        or code in {0x061C, 0x200E, 0x200F, 0x2028, 0x2029}
        or 0x202A <= code <= 0x202E
        or 0x2066 <= code <= 0x2069
    )


def expected(cluster: str) -> list:
    width = wcswidth(cluster, unicode_version="16.0.0")
    return [cluster if width else "◌" + cluster, max(1, width)]


def batch(applications: dict, engine: str, root: Path, values: list) -> list:
    (root / "cases.json").write_text(json.dumps(values, ensure_ascii=False))
    result = subprocess.run(applications[engine], cwd=root, capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0 and not result.stderr, result
    return [json.loads(line) for line in result.stdout.splitlines()]


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_grapheme_unicode_conformance(applications: dict, tmp_path: Path, engine: str) -> None:
    values, wanted = [], []
    path = Path(__file__).parent / "fixtures/terminal/GraphemeBreakTest-16.0.0.txt"
    for line in path.read_text().splitlines():
        pieces = line.split("#")[0].split()
        if not pieces:
            continue
        groups, current = [], ""
        for piece in pieces:
            if piece == "÷":
                if current:
                    groups.append(current)
                    current = ""
            elif piece != "×":
                current += chr(int(piece, 16))
        text = "".join(groups)
        values.append(text)
        wanted.append(None if any(forbidden(ord(c)) for c in text) else [expected(c) for c in groups])
    assert len(values) == 1093
    assert batch(applications, engine, tmp_path, values) == wanted
    return  # noqa: PLR1711


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_width_table_boundaries(applications: dict, tmp_path: Path, engine: str) -> None:
    points = {
        point + delta
        for ranges in [
            table_zero.ZERO_WIDTH["16.0.0"],
            table_wide.WIDE_EASTASIAN["16.0.0"],
            table_vs16.VS16_NARROW_TO_WIDE["9.0.0"],
        ]
        for bounds in ranges
        for point in bounds
        for delta in [-1, 0, 1]
    }
    values = ["A" + chr(code) + "\ufe0fB" for code in sorted(points) if 0 <= code <= 0x10FFFF and not forbidden(code)]
    values += ["é東京", "👩🏽‍💻", "🇷🇺🇯🇵🇺", "🏳️‍🌈", "1️⃣", "क्ष", "a‍b", "́", "\u200d", "\u200c"]
    assert len(values) > 2000
    assert batch(applications, engine, tmp_path, values) == [
        [expected(c) for c in grapheme_clusters(v)] for v in values
    ]
    return  # noqa: PLR1711


def test_every_unicode_scalar_width(applications: dict, tmp_path: Path) -> None:
    digest = hashlib.sha256()
    count = 0
    scalars = []
    for code in range(0x110000):
        if not forbidden(code):
            digest.update(str(max(1, wcwidth(chr(code), unicode_version="16.0.0"))).encode())
            count += 1
            scalars.append(chr(code))
    (tmp_path / "scalars").write_text("".join(scalars))
    result = subprocess.run(
        applications["rust"],
        cwd=tmp_path,
        env=dict(os.environ, TERMINAL_TEST="scalar"),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0 and not result.stderr, result
    assert result.stdout == f"{count} {digest.hexdigest()}\n"
    return  # noqa: PLR1711


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_cell_bounds_and_control_injection(applications: dict, tmp_path: Path, engine: str) -> None:
    valid = ["", "x" * 65536, "🐍" * 16384, "́" * 32768]
    bad = ["x" * 65537, "🐍" * 16385]
    bad += ["x‍" + chr(code) + "y" for code in range(0x2100) if forbidden(code)]
    found = batch(applications, engine, tmp_path, valid + bad)
    assert found[:4] == [[], [["x", 1]] * 65536, [["🐍", 2]] * 16384, [["◌" + valid[3], 1]]]
    assert found[4:] == [None] * len(bad)
    return  # noqa: PLR1711


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_redirected_size_and_utf8(applications: dict, tmp_path: Path, engine: str) -> None:
    env = dict(os.environ, TERMINAL_TEST="info", TERM="xterm-256color", COLUMNS="12", LINES="2", LC_ALL="C")
    result = subprocess.run(applications[engine], cwd=tmp_path, env=env, capture_output=True, timeout=10, check=False)
    assert result.returncode == 0 and not result.stderr
    assert json.loads(result.stdout) == {"isatty": False, "ansi": False, "columns": 80, "rows": 24}
    (tmp_path / "payload").write_text("東京🐍é\n")
    result = subprocess.run(
        applications[engine], cwd=tmp_path, env=dict(env, TERMINAL_TEST="write"), capture_output=True, check=False
    )
    assert result.returncode == 0 and not result.stderr and result.stdout == "東京🐍é\n".encode()
    return  # noqa: PLR1711


def resize(descriptor: int, columns: int, rows: int) -> None:
    import fcntl
    import termios

    fcntl.ioctl(descriptor, termios.TIOCSWINSZ, struct.pack("HHHH", rows, columns, 0, 0))
    return  # noqa: PLR1711


def read_until(descriptor: int, wanted: bytes, timeout: float = 5.0) -> bytes:
    received = b""
    deadline = time.monotonic() + timeout
    while wanted not in received:
        assert select.select([descriptor], [], [], max(0, deadline - time.monotonic()))[0], received
        received += os.read(descriptor, 65536)
    return received


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_terminal_resize_and_unterminated_flush(applications: dict, tmp_path: Path, engine: str) -> None:
    master, slave = os.openpty()
    resize(slave, 41, 9)
    process = subprocess.Popen(
        applications[engine],
        cwd=tmp_path,
        stdout=slave,
        stderr=subprocess.PIPE,
        env=dict(os.environ, TERMINAL_TEST="resize", TERM="xterm", COLUMNS="999", LINES="999"),
    )
    try:
        first = read_until(master, b"ready")
        assert json.loads(first.splitlines()[0]) == {"isatty": True, "ansi": True, "columns": 41, "rows": 9}
        assert process.poll() is None
        resize(slave, 13, 3)
        second = read_until(master, b"}\r\n")
        assert json.loads(second.strip()) == {"isatty": True, "ansi": True, "columns": 13, "rows": 3}
        _, stderr = process.communicate(timeout=5)
        assert process.returncode == 0 and not stderr
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=5)
        process.stderr.close()
        os.close(master)
        os.close(slave)
    return  # noqa: PLR1711


@pytest.mark.parametrize("engine", ["python", "rust"])
@pytest.mark.parametrize("term", ["", "dumb", "unknown", "xterm-256color"])
def test_terminal_capabilities_and_zero_size(applications: dict, tmp_path: Path, engine: str, term: str) -> None:
    master, slave = os.openpty()
    resize(slave, 0, 0)
    try:
        result = subprocess.run(
            applications[engine],
            cwd=tmp_path,
            stdout=slave,
            stderr=subprocess.PIPE,
            env=dict(os.environ, TERMINAL_TEST="info", TERM=term),
            timeout=5,
            check=False,
        )
        raw = read_until(master, b"}\r\n")
        assert result.returncode == 0 and not result.stderr
        assert json.loads(raw) == {"isatty": True, "ansi": term == "xterm-256color", "columns": 80, "rows": 24}
    finally:
        os.close(master)
        os.close(slave)
    return  # noqa: PLR1711


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_output_byte_bound_and_recovery(applications: dict, tmp_path: Path, engine: str) -> None:
    for over in [False, True]:
        raw = b"x" * (1048576 + int(over))
        (tmp_path / "payload").write_bytes(raw)
        result = subprocess.run(
            applications[engine],
            cwd=tmp_path,
            env=dict(os.environ, TERMINAL_TEST="write"),
            capture_output=True,
            timeout=10,
            check=False,
        )
        assert result.returncode == 0 and not result.stderr
        assert result.stdout == (b"" if over else raw)
        assert (tmp_path / "caught").exists() == over
    return  # noqa: PLR1711


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_terminal_disconnect_recoverable(applications: dict, tmp_path: Path, engine: str) -> None:
    master, slave = os.openpty()
    process = subprocess.Popen(
        applications[engine],
        cwd=tmp_path,
        stdout=slave,
        stderr=subprocess.PIPE,
        env=dict(os.environ, TERMINAL_TEST="closed"),
    )
    try:
        assert read_until(master, b"ready") == b"ready"
        os.close(master)
        master = -1
        _, stderr = process.communicate(timeout=5)
        assert process.returncode == 0 and not stderr
        assert (tmp_path / "caught").read_text() == "yes"
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=5)
        process.stderr.close()
        if master >= 0:
            os.close(master)
        os.close(slave)
    return  # noqa: PLR1711


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_nonblocking_stdout_reports_incomplete_write(applications: dict, tmp_path: Path, engine: str) -> None:
    reader, writer = os.pipe2(os.O_NONBLOCK)
    (tmp_path / "payload").write_bytes(b"x" * 1048576)
    try:
        result = subprocess.run(
            applications[engine],
            cwd=tmp_path,
            env=dict(os.environ, TERMINAL_TEST="write"),
            stdout=writer,
            stderr=subprocess.PIPE,
            timeout=10,
            check=False,
        )
        assert result.returncode == 0 and not result.stderr
        assert (tmp_path / "caught").read_text() == "yes"
        partial = os.read(reader, 1048576)
        assert 0 < len(partial) < 1048576 and partial == b"x" * len(partial)
    finally:
        os.close(reader)
        os.close(writer)
    return  # noqa: PLR1711
