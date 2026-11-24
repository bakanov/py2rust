"""Literal Latin-1, ASCII and UTF-8 byte decoding, strict failures and receiver evaluation."""

from pathlib import Path

import pytest
from py2rust.compiler.service import ServiceCompiler, ServiceError

from .test_project import run_project, sources
from .test_services import parity


def test_decode_all_latin1_bytes_and_utf8_aliases(tmp_path: Path) -> None:
    (tmp_path / "latin.bin").write_bytes(bytes(range(256)))
    (tmp_path / "expected.txt").write_text(bytes(range(256)).decode("latin-1"), encoding="utf-8")
    output = parity(
        tmp_path,
        """
from py2rust.stdlib import read_bytes, read_text

def receiver() -> bytearray:
    print("receiver once")
    return bytearray(b"\\xff\\x80")

def check() -> None:
    raw: bytes = read_bytes("latin.bin")
    expected: str = read_text("expected.txt")
    assert raw.decode("latin-1") == expected
    assert raw.decode("LATIN_1") == expected
    assert raw.decode("latin1") == expected
    assert raw.decode("iso-8859-1") == expected
    assert bytearray(raw).decode("iso8859_1") == expected
    assert receiver().decode("latin-1") == "ÿ\\x80"
    unicode_data: bytes = "Aé世界😀".encode()
    assert unicode_data.decode("UTF_8") == "Aé世界😀"
    assert bytearray(unicode_data).decode("utf8") == unicode_data.decode()
    assert b"".decode("latin-1") == "" and bytearray().decode("ascii") == ""
    return
if __name__ == "__main__":
    check()
""",
    )
    assert output == "receiver once\n"
    return  # noqa: PLR1711


def test_decode_ascii_and_malformed_utf8(tmp_path: Path) -> None:
    (tmp_path / "ascii.bin").write_bytes(bytes(range(128)))
    parity(
        tmp_path,
        """
from py2rust.stdlib import read_bytes

def check() -> None:
    raw: bytes = read_bytes("ascii.bin")
    assert raw.decode("ascii") == raw.decode()
    assert bytearray(raw).decode("ASCII") == raw.decode()
    failures: int = 0
    invalid: list[bytes] = [b"\\x80", b"\\xff", b"A\\x80", b"\\xc0\\x80", b"\\xed\\xa0\\x80", b"\\xf4\\x90\\x80\\x80", b"\\xe2\\x82"]
    for data in invalid:
        try:
            data.decode("ascii")
        except Exception:
            failures = failures + 1
        try:
            bytearray(data).decode("utf-8")
        except Exception:
            failures = failures + 1
        assert len(data.decode("latin-1")) == len(data)
    assert failures == 14
    print("strict decoding passed")
    return
if __name__ == "__main__":
    check()
""",
    )
    return  # noqa: PLR1711


def test_decode_whole_project(tmp_path: Path) -> None:
    root = sources(
        tmp_path,
        {
            "main.py": """from labels import label

def main() -> None:
    assert label(b"caf\\xe9") == "café"
    print(label(b"caf\\xe9"))
    return
if __name__ == "__main__":
    main()
""",
            "labels.py": 'def label(data: bytes) -> str:\n    return data.decode("latin-1")\n',
        },
    )
    result = run_project(root, tmp_path / "rust")
    assert result.returncode == 0 and result.stdout == "café\n" and not result.stderr
    return  # noqa: PLR1711


@pytest.mark.parametrize(
    "expression",
    [
        'b"".decode("utf-16")',
        'b"".decode("unknown")',
        'b"".decode("ascii", "ignore")',
        'b"".decode(1)',
        'b"".decode(True)',
        'b"".decode(b"ascii")',
        'b"".decode(encoding)',
        'b"".decode(encoding="ascii")',
    ],
)
def test_decode_rejects_unsupported_encoding_calls(expression: str) -> None:
    with pytest.raises(ServiceError):
        ServiceCompiler().compile(
            'def main() -> None:\n    encoding: str = "ascii"\n    ' + expression + "\n    return\n"
        )
    return  # noqa: PLR1711
