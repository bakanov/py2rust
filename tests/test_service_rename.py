"""No-overwrite moves and advisory locks checked against independent OS operations."""

import fcntl
import os
import subprocess
import time
from pathlib import Path

import pytest

from .test_services import program, run


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_rename_never_replaces_entries(tmp_path: Path, engine: str) -> None:
    (tmp_path / "source").write_bytes(b"\x00original\xff")
    (tmp_path / "existing").write_bytes(b"preserve me")
    (tmp_path / "dangling").symlink_to("absent")
    (tmp_path / "hard").hardlink_to(tmp_path / "source")
    (tmp_path / "directory").mkdir()
    (tmp_path / "directory/child").write_text("contained")
    (tmp_path / "other-directory").mkdir()
    inode = (tmp_path / "source").stat().st_ino
    result = run(
        tmp_path,
        """
from py2rust.stdlib import rename_no_replace, read_bytes, read_link, path_exists, path_stat, json_string

def check() -> None:
    failed: int = 0
    for target in ["existing", "dangling", "hard", "source", "directory"]:
        try:
            rename_no_replace("source", target)
        except Exception:
            failed = failed + 1
    for target in ["other-directory", "existing", "dangling"]:
        try:
            rename_no_replace("directory", target)
        except Exception:
            failed = failed + 1
    for source in ["missing", "", "nul\\x00path"]:
        try:
            rename_no_replace(source, "new")
        except Exception:
            failed = failed + 1
    assert failed == 11
    rename_no_replace("source", "世界😀")
    rename_no_replace("directory/", "moved-directory/.")
    rename_no_replace("dangling", "moved-link")
    assert read_bytes("世界😀") == b"\\x00original\\xff"
    assert read_bytes("existing") == b"preserve me"
    assert read_bytes("moved-directory/child") == b"contained"
    assert read_link("moved-link") == "absent"
    assert not path_exists("source")
    assert json_string(path_stat("moved-link", False)["kind"]) == "symlink"
    return
if __name__ == "__main__":
    check()
""",
        engine,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "世界😀").stat().st_ino == inode == (tmp_path / "hard").stat().st_ino
    assert (tmp_path / "moved-link").is_symlink() and os.readlink(tmp_path / "moved-link") == "absent"
    assert (tmp_path / "other-directory").is_dir()
    return  # noqa: PLR1711 - explicit return required by repository guidelines


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_scoped_lock_lifetime_contention_and_process_death(tmp_path: Path, engine: str) -> None:
    lock = tmp_path / "lock"
    lock.write_bytes(b"retained lock file content")
    (tmp_path / "link").symlink_to(lock)
    (tmp_path / "directory").mkdir()
    os.mkfifo(tmp_path / "pipe")
    source = """
import time
from py2rust.stdlib import FileHandle, env_get, file_lock, file_close, write_text

def check() -> None:
    if env_get("HOLD", "") == "1":
        with file_lock("lock") as held:
            write_text("ready", "ready")
            time.sleep(60.0)
        return
    failed: int = 0
    for path in ["lock", "link", "link/.", "directory", "pipe", "", "nul\\x00path"]:
        try:
            with file_lock(path) as unexpected:
                print("unexpected lock")
        except Exception:
            failed = failed + 1
    assert failed == 7
    with file_lock("scoped") as scoped:
        alias: FileHandle = scoped
        file_close(alias)
        with file_lock("scoped") as reacquired:
            print("reacquired")
    try:
        with file_lock("exception") as error_scope:
            assert False, "leave scope"
    except Exception:
        print("unwound")
    with file_lock("exception") as after_error:
        print("released")
    return
if __name__ == "__main__":
    check()
"""
    command = program(tmp_path, source, engine, "locking")
    with lock.open("rb") as parent:
        fcntl.flock(parent, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, timeout=5, check=False)
        assert result.returncode == 0 and result.stdout == "reacquired\nunwound\nreleased\n", result.stderr
    assert lock.read_bytes() == b"retained lock file content"
    child = subprocess.Popen(
        command, cwd=tmp_path, env=dict(os.environ, HOLD="1"), stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    try:
        deadline = time.monotonic() + 5
        while not (tmp_path / "ready").exists() and time.monotonic() < deadline:
            assert child.poll() is None, child.communicate()
            time.sleep(0.01)
        assert (tmp_path / "ready").exists()
        with lock.open("rb") as parent, pytest.raises(BlockingIOError):
            fcntl.flock(parent, fcntl.LOCK_EX | fcntl.LOCK_NB)
        child.kill()
        child.wait(timeout=5)
        with lock.open("rb") as parent:
            fcntl.flock(parent, fcntl.LOCK_EX | fcntl.LOCK_NB)
    finally:
        if child.poll() is None:
            child.kill()
        child.communicate(timeout=5)
    assert lock.read_bytes() == b"retained lock file content"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_competing_rename_has_one_winner(tmp_path: Path, engine: str) -> None:
    for name in ["left", "right"]:
        (tmp_path / name).write_text(name)
    source = """
import time
from py2rust.stdlib import env_get, path_exists, rename_no_replace, write_text

def check() -> None:
    source: str = env_get("SOURCE", "")
    write_text(source + ".ready", "ready")
    while not path_exists("go"):
        time.sleep(0.001)
    try:
        rename_no_replace(source, "destination")
        print("winner", source)
    except Exception:
        print("loser", source)
    return
if __name__ == "__main__":
    check()
"""
    command = program(tmp_path, source, engine, "race")
    children = [
        subprocess.Popen(
            command,
            cwd=tmp_path,
            env=dict(os.environ, SOURCE=name),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for name in ["left", "right"]
    ]
    try:
        deadline = time.monotonic() + 5
        while not all((tmp_path / (name + ".ready")).exists() for name in ["left", "right"]):
            assert time.monotonic() < deadline and all(child.poll() is None for child in children)
            time.sleep(0.01)
        (tmp_path / "go").touch()
        outputs = [child.communicate(timeout=5) for child in children]
        assert all(child.returncode == 0 for child in children), outputs
        winner = (tmp_path / "destination").read_text()
        loser = "right" if winner == "left" else "left"
        assert not (tmp_path / winner).exists() and (tmp_path / loser).read_text() == loser
        assert {out.strip() for out, err in outputs} == {"winner " + winner, "loser " + loser}
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
            child.communicate(timeout=5)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_regular_file_replacement_is_atomic_and_rejects_aliases(tmp_path: Path, engine: str) -> None:
    (tmp_path / "source").write_bytes(b"replacement\x00\xff")
    (tmp_path / "old").write_bytes(b"old contents")
    (tmp_path / "old-alias").hardlink_to(tmp_path / "old")
    (tmp_path / "source-alias").hardlink_to(tmp_path / "source")
    (tmp_path / "dangling").symlink_to("absent")
    (tmp_path / "link").symlink_to("source")
    (tmp_path / "directory").mkdir()
    os.mkfifo(tmp_path / "pipe")
    incoming_inode = (tmp_path / "source").stat().st_ino
    old_inode = (tmp_path / "old").stat().st_ino
    with (tmp_path / "old").open("rb") as old_reader:
        result = run(
            tmp_path,
            """
from py2rust.stdlib import replace_file, read_bytes, path_exists

def check() -> None:
    failed: int = 0
    for target in ["source", "source-alias", "dangling", "link", "directory", "pipe", "missing/child"]:
        try:
            replace_file("source", target)
        except Exception:
            failed = failed + 1
    for source in ["dangling", "link", "directory", "pipe", "missing", "", "null\\x00path"]:
        try:
            replace_file(source, "old")
        except Exception:
            failed = failed + 1
    assert failed == 14
    assert read_bytes("old") == b"old contents"
    replace_file("source", "old")
    assert not path_exists("source")
    assert read_bytes("old") == b"replacement\\x00\\xff"
    replace_file("old", "new")
    assert not path_exists("old")
    return
if __name__ == "__main__":
    check()
""",
            engine,
        )
        assert result.returncode == 0, result.stderr
        assert old_reader.read() == b"old contents"
    assert (tmp_path / "new").stat().st_ino == incoming_inode
    assert (tmp_path / "source-alias").read_bytes() == b"replacement\x00\xff"
    assert (tmp_path / "old-alias").stat().st_ino == old_inode
    assert (tmp_path / "old-alias").read_bytes() == b"old contents"
    assert (tmp_path / "dangling").is_symlink()
    return  # noqa: PLR1711 - explicit return required by repository guidelines
