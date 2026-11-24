"""Resource lifetime, incremental file I/O and independently known SHA-256 vectors."""

from pathlib import Path

import pytest
from py2rust.compiler.service import ServiceCompiler, ServiceError

from .test_services import parity


def test_file_scopes_and_hash_snapshots(tmp_path: Path) -> None:
    assert (
        parity(
            tmp_path,
            """
from py2rust.stdlib import (
    FileHandle, Sha256, file_open, file_read, file_write, file_seek, file_size, file_truncate,
    file_sync, file_close, sha256_new, sha256_update, sha256_digest, read_bytes,
    link_file, path_same, path_parent, path_name, path_is_symlink, sync_directory, remove_file,
)
def size_and_close(source: FileHandle) -> int:
    with source as handle:
        return file_size(handle)
def run() -> None:
    first: Sha256 = sha256_new()
    second: Sha256 = sha256_update(first, b"abc")
    assert sha256_digest(first) == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert sha256_digest(second) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    branch: Sha256 = sha256_update(sha256_update(first, b"a"), b"bc")
    assert sha256_digest(branch) == sha256_digest(second)
    with file_open("data.bin", "x+b") as output:
        file_write(output, b"abcdef")
        assert file_size(output) == 6
        assert file_seek(output, -3, 2) == 3
        assert file_read(output, 20) == b"def"
        assert file_read(output, 1) == b""
        assert file_seek(output, -2, 1) == 4
        file_write(output, b"XY")
        file_truncate(output, 5)
        assert file_size(output) == 5
        assert file_seek(output, 0, 0) == 0
        assert file_read(output, 10) == b"abcdX"
        file_sync(output)
    saved: FileHandle = file_open("data.bin", "rb")
    assert size_and_close(saved) == 5
    caught: int = 0
    try:
        file_read(saved, 1)
    except Exception:
        caught = caught + 1
    file_close(saved)
    failed: FileHandle = file_open("data.bin", "rb")
    try:
        with failed as resource:
            assert False, "scope failure"
    except Exception:
        caught = caught + 1
    try:
        file_read(failed, 1)
    except Exception:
        caught = caught + 1
    for index in range(3):
        with file_open("data.bin", "rb") as resource:
            if index == 0:
                continue
            break
    assert caught == 3
    link_file("data.bin", "linked.bin")
    assert path_same("data.bin", "linked.bin")
    assert path_parent("data.bin") == "." and path_name("a/data.bin") == "data.bin"
    assert path_parent("/") == "/" and path_parent("") == "."
    assert not path_is_symlink("linked.bin") and not path_is_symlink("absent")
    sync_directory(".")
    try:
        link_file("data.bin", "linked.bin")
    except Exception:
        caught = caught + 1
    assert caught == 4 and read_bytes("linked.bin") == b"abcdX"
    remove_file("linked.bin")
    remove_file("data.bin")
    print("scoped resources passed")
    return
if __name__ == "__main__":
    run()
""",
        )
        == "scoped resources passed\n"
    )


def test_file_validation_and_closed_aliases(tmp_path: Path) -> None:
    (tmp_path / "link").symlink_to("missing")
    assert (
        parity(
            tmp_path,
            """
from py2rust.stdlib import FileHandle, file_open, file_read, file_write, file_seek, file_truncate, file_close, path_is_symlink
def run() -> None:
    assert path_is_symlink("link")
    with file_open("data", "w+b") as output:
        file_write(output, b"abc")
    errors: int = 0
    for mode in ["x+b", "unknown"]:
        try:
            file_open("data", mode)
        except Exception:
            errors = errors + 1
    with file_open("data", "rb") as source:
        try:
            file_write(source, b"x")
        except Exception:
            errors = errors + 1
        for count in [0, -1, 33554433]:
            try:
                file_read(source, count)
            except Exception:
                errors = errors + 1
        for whence in [-1, 3]:
            try:
                file_seek(source, 0, whence)
            except Exception:
                errors = errors + 1
        try:
            file_seek(source, -1, 0)
        except Exception:
            errors = errors + 1
    with file_open("data", "r+b") as writable:
        try:
            file_truncate(writable, -1)
        except Exception:
            errors = errors + 1
    handle: FileHandle = file_open("data", "rb")
    alias: FileHandle = handle
    file_close(alias)
    try:
        with handle as closed:
            print("unreachable")
    except Exception:
        errors = errors + 1
    assert errors == 11
    print("validation passed")
    return
if __name__ == "__main__":
    run()
""",
        )
        == "validation passed\n"
    )


def test_with_rejects_unsupported_context() -> None:
    with pytest.raises(ServiceError, match="with supports .* resources"):
        ServiceCompiler().compile("""
def run() -> None:
    with "not a resource" as value:
        print(value)
    return
if __name__ == "__main__":
    run()
""")
    return  # noqa: PLR1711 - explicit return required by repository guidelines
