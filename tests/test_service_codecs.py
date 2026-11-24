"""Canonical base64, SHA-1 protocol vectors and repeating-key byte masks."""

from pathlib import Path

from .test_services import parity


def test_standard_vectors_and_byte_masks(tmp_path: Path) -> None:
    (tmp_path / "binary").write_bytes(bytes(range(256)) * 100)
    parity(
        tmp_path,
        """
from py2rust.stdlib import base64_encode, base64_decode, sha1_digest, bytes_xor, read_bytes

def check() -> None:
    vectors: list[tuple[bytes, str]] = [(b"", ""), (b"f", "Zg=="), (b"fo", "Zm8="), (b"foo", "Zm9v"), (b"foob", "Zm9vYg=="), (b"fooba", "Zm9vYmE="), (b"foobar", "Zm9vYmFy"), (b"\\x00\\xff", "AP8=")]
    for pair in vectors:
        assert base64_encode(pair[0]) == pair[1]
        assert base64_decode(pair[1]) == pair[0]
    assert sha1_digest(b"").hex() == "da39a3ee5e6b4b0d3255bfef95601890afd80709"
    assert sha1_digest(b"abc").hex() == "a9993e364706816aba3e25717850c26c9cd0d89d"
    assert base64_encode(sha1_digest(b"dGhlIHNhbXBsZSBub25jZQ==258EAFA5-E914-47DA-95CA-C5AB0DC85B11")) == "s3pPLMBiTxaQ9kYGzzhZRbK+xOo="
    assert bytes_xor(b"Hello", bytes.fromhex("37fa213d")).hex() == "7f9f4d5158"
    data: bytes = read_bytes("binary")
    assert base64_decode(base64_encode(data)) == data
    assert bytes_xor(bytes_xor(data, b"abc"), b"abc") == data
    assert bytes_xor(b"", b"x") == b""
    print("codec vectors passed")
    return
if __name__ == "__main__":
    check()
""",
    )
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def test_noncanonical_base64_is_rejected(tmp_path: Path) -> None:
    parity(
        tmp_path,
        """
from py2rust.stdlib import base64_decode, bytes_xor

def check() -> None:
    errors: int = 0
    for value in ["Zg", "Zg=", "Zg===", "Zg==\\n", " Zg==", "Zh==", "Zm9=", "====", "-_8=", "é", "Zg==Zg==", "Zm9v===="]:
        try:
            base64_decode(value)
        except Exception as error:
            assert str(error) == "expected canonical padded base64"
            errors = errors + 1
    try:
        bytes_xor(b"x", b"")
    except Exception:
        errors = errors + 1
    assert errors == 13
    print("codec rejections passed")
    return
if __name__ == "__main__":
    check()
""",
    )
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def test_codec_buffer_bounds(tmp_path: Path) -> None:
    (tmp_path / "limit").write_bytes(b"a" * 1048576)
    (tmp_path / "above").write_bytes(b"a" * 1048577)
    (tmp_path / "key").write_bytes(b"k" * 4097)
    # Exactly the encoded character bound, but three output bytes over a multiple of three.
    (tmp_path / "encoded").write_text("YWFh" * 349526)
    parity(
        tmp_path,
        """
from py2rust.stdlib import base64_encode, base64_decode, sha1_digest, bytes_xor, read_bytes, read_text

def check() -> None:
    data: bytes = read_bytes("limit")
    assert len(base64_encode(data)) == 1398104
    assert base64_decode(base64_encode(data)) == data
    assert len(sha1_digest(data)) == 20 and len(bytes_xor(data, b"x")) == 1048576
    oversized: bytes = read_bytes("above")
    errors: int = 0
    try:
        base64_encode(oversized)
    except Exception:
        errors = errors + 1
    try:
        sha1_digest(oversized)
    except Exception:
        errors = errors + 1
    try:
        bytes_xor(oversized, b"x")
    except Exception:
        errors = errors + 1
    try:
        bytes_xor(b"", read_bytes("key"))
    except Exception:
        errors = errors + 1
    try:
        base64_decode(read_text("encoded"))
    except Exception:
        errors = errors + 1
    try:
        base64_decode(read_text("encoded") + "YWFh")
    except Exception:
        errors = errors + 1
    assert errors == 6
    print("codec bounds passed")
    return
if __name__ == "__main__":
    check()
""",
    )
    return  # noqa: PLR1711 - explicit return required by repository guidelines
