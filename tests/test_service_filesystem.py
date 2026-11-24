"""Filesystem observations checked against independent os/stat metadata."""

import json
import os
import socket
import stat
import tempfile
from pathlib import Path

import pytest

from .test_services import parity, run


def observed(path: Path, follow: bool) -> dict:
    value = os.stat(path, follow_symlinks=follow)
    kinds = [
        ("file", stat.S_ISREG),
        ("directory", stat.S_ISDIR),
        ("symlink", stat.S_ISLNK),
        ("fifo", stat.S_ISFIFO),
        ("socket", stat.S_ISSOCK),
        ("char", stat.S_ISCHR),
    ]
    kind = next((name for name, check in kinds if check(value.st_mode)), "other")
    return {
        "kind": kind,
        "size": value.st_size,
        "mode": stat.S_IMODE(value.st_mode),
        "device": value.st_dev,
        "inode": value.st_ino,
        "links": value.st_nlink,
        "mtime_ns": value.st_mtime_ns,
        "atime_ns": value.st_atime_ns,
        "ctime_ns": value.st_ctime_ns,
    }


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_filesystem_metadata_matches_os(tmp_path: Path, engine: str) -> None:
    with tempfile.TemporaryDirectory(prefix="p2r-stat-") as short, socket.socket(socket.AF_UNIX) as listener:
        root = Path(short)
        data = root / "世界.bin"
        data.write_bytes(b"\x00abc\xff")
        data.chmod(0o640)
        os.utime(data, ns=(1666666666987654321, -1))
        hard = root / "hard"
        hard.hardlink_to(data)
        link = root / "link"
        link.symlink_to(data.name)
        broken = root / "broken"
        broken.symlink_to("missing target")
        fifo = root / "pipe"
        os.mkfifo(fifo)
        listener.bind(str(root / "socket"))
        rows = [
            (data, False),
            (hard, False),
            (link, False),
            (link, True),
            (broken, False),
            (fifo, False),
            (root / "socket", False),
            (root, False),
        ]
        expected = [observed(path, follow) for path, follow in rows]
        queries = json.dumps([[str(path), follow] for path, follow in rows], ensure_ascii=False)
        source = f"""
from py2rust.stdlib import Json, json_array, json_loads, json_string, json_bool, path_stat, read_link, pretty

def check() -> None:
    result: list[Json] = []
    for row in json_array(json_loads({queries!r})):
        result.append(path_stat(json_string(row[0]), json_bool(row[1])))
    assert read_link({str(link)!r}) == "世界.bin"
    assert read_link({str(broken)!r}) == "missing target"
    assert json_string(path_stat("/dev/null", False)["kind"]) == "char"
    print(pretty(result))
    return
if __name__ == "__main__":
    check()
"""
        result = run(tmp_path, source, engine)
        assert result.returncode == 0, result.stderr
        actual = json.loads(result.stdout)
        assert len(actual) == len(expected)
        for (path, _follow), before, reported in zip(rows, expected, actual):
            if before["kind"] == "symlink":
                # Following the link in a later query (or read_link) can update
                # its atime. Bracket that observation instead of requiring the
                # pre-follow value; all other fields and file times stay exact.
                after = path.lstat().st_atime_ns
                assert before["atime_ns"] <= reported["atime_ns"] <= after
                before["atime_ns"] = reported["atime_ns"]
            assert reported == before
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def test_bounded_directory_listing_and_failures(tmp_path: Path) -> None:
    root = tmp_path / "tree"
    root.mkdir()
    for name in ["z", "世界", "a", "😀", ".hidden"]:
        (root / name).write_bytes(b"")
    (tmp_path / "empty").mkdir()
    (tmp_path / "link").symlink_to("tree", target_is_directory=True)
    (tmp_path / "bad-target").symlink_to("absent")
    bad = tmp_path / "invalid"
    bad.mkdir()
    fd = os.open(os.fsencode(bad) + b"/bad\xff", os.O_CREAT | os.O_WRONLY, 0o600)
    os.close(fd)
    os.symlink(b"bad\xff", os.fsencode(tmp_path / "raw-link"))
    future = tmp_path / "future"
    future.write_bytes(b"")
    os.utime(future, ns=(2**63 + 100, 2**63 + 100))
    assert future.stat().st_mtime_ns > 2**63 - 1, "fixture filesystem cannot represent an out-of-range timestamp"
    parity(
        tmp_path,
        """
from py2rust.stdlib import directory_names, path_stat, read_link, json_string

def check() -> None:
    assert directory_names("tree", 5) == [".hidden", "a", "z", "世界", "😀"]
    assert len(directory_names("empty", 1)) == 0
    assert json_string(path_stat("link/.", False)["kind"]) == "symlink"
    assert json_string(path_stat("link/", True)["kind"]) == "directory"
    count: int = 0
    for limit in [0, -1, 100001, 4]:
        try:
            directory_names("tree", limit)
        except Exception:
            count = count + 1
    for path in ["link", "link/", "tree/a", "missing", "invalid", ""]:
        try:
            directory_names(path, 10)
        except Exception:
            count = count + 1
    for path in ["missing", "", "future"]:
        try:
            path_stat(path, False)
        except Exception:
            count = count + 1
    try:
        path_stat("bad-target", True)
    except Exception:
        count = count + 1
    for path in ["raw-link", "tree/a", "missing", ""]:
        try:
            read_link(path)
        except Exception:
            count = count + 1
    assert count == 18
    print("bounded listing and metadata failures passed")
    return
if __name__ == "__main__":
    check()
""",
    )
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def test_metadata_keeps_unreadable_entries_and_listing_fails(tmp_path: Path) -> None:
    assert os.geteuid() != 0, "this permission oracle must run without root privileges"
    locked = tmp_path / "locked"
    locked.mkdir()
    (locked / "secret").write_bytes(b"not read")
    locked.chmod(0)
    try:
        parity(
            tmp_path,
            """
from py2rust.stdlib import path_stat, directory_names, json_int, json_string

def check() -> None:
    assert json_string(path_stat("locked", False)["kind"]) == "directory"
    assert json_int(path_stat("locked", False)["mode"]) == 0
    failed: bool = False
    try:
        directory_names("locked", 10)
    except Exception:
        failed = True
    assert failed
    failed = False
    try:
        path_stat("locked/secret", False)
    except Exception:
        failed = True
    assert failed
    print("unreadable directory isolated")
    return
if __name__ == "__main__":
    check()
""",
        )
    finally:
        locked.chmod(0o700)
    return  # noqa: PLR1711 - explicit return required by repository guidelines
