"""Restore primitives checked through OS metadata, including symlink non-following."""

import os
import stat
from pathlib import Path

import pytest

from .test_services import run


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_restore_metadata_and_exclusive_creation(tmp_path: Path, engine: str) -> None:
    original = tmp_path / "original"
    original.write_bytes(b"retained")
    os.utime(original, ns=(123456789000, 987654321000))
    before = original.stat()
    (tmp_path / "directory").mkdir()
    os.mkfifo(tmp_path / "pipe")
    result = run(
        tmp_path,
        """
from py2rust.stdlib import mkdir_new, create_symlink, path_set_metadata, write_bytes, read_link

def check() -> None:
    mkdir_new("private")
    write_bytes("private/file", b"binary\\x00\\xff")
    create_symlink("../original", "private/link")
    create_symlink("missing/../世界", "dangling")
    assert read_link("dangling") == "missing/../世界"
    path_set_metadata("private/file", 416, 1700000000123456789)
    path_set_metadata("private/link", 511, -1)
    path_set_metadata("dangling", 511, 1700000000987654321)
    path_set_metadata("private", 360, 1700000000555555555)
    failed: int = 0
    for path in ["private", "dangling", "original", "directory", "pipe", "", "null\\x00path"]:
        try:
            mkdir_new(path)
        except Exception:
            failed = failed + 1
    for path in ["dangling", "original", "private", "pipe", "missing/child", ""]:
        try:
            create_symlink("target", path)
        except Exception:
            failed = failed + 1
    for target in ["", "bad\\x00target"]:
        try:
            create_symlink(target, "bad-link")
        except Exception:
            failed = failed + 1
    for path in ["pipe", "missing", "", "bad\\x00path"]:
        try:
            path_set_metadata(path, 384, 1)
        except Exception:
            failed = failed + 1
    for mode in [-1, 512, 4095]:
        try:
            path_set_metadata("original", mode, 1)
        except Exception:
            failed = failed + 1
    try:
        path_set_metadata("dangling", 384, 1)
    except Exception:
        failed = failed + 1
    assert failed == 23
    return
if __name__ == "__main__":
    check()
""",
        engine,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "private/file").read_bytes() == b"binary\x00\xff"
    assert stat.S_IMODE((tmp_path / "private").stat().st_mode) == 0o550
    assert stat.S_IMODE((tmp_path / "private/file").stat().st_mode) == 0o640
    assert (tmp_path / "private").stat().st_mtime_ns == 1700000000555555555
    assert (tmp_path / "private/file").stat().st_mtime_ns == 1700000000123456789
    assert (tmp_path / "private/link").lstat().st_mtime_ns == -1
    assert (tmp_path / "dangling").lstat().st_mtime_ns == 1700000000987654321
    after = original.stat()
    assert (after.st_mode, after.st_mtime_ns, after.st_atime_ns) == (
        before.st_mode,
        before.st_mtime_ns,
        before.st_atime_ns,
    )
    assert not (tmp_path / "bad-link").is_symlink()
    return  # noqa: PLR1711 - explicit return required by repository guidelines
