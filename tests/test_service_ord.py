"""Unicode scalar and binary ord semantics, recoverable length errors and single evaluation."""

from pathlib import Path

import pytest
from py2rust.compiler.service import ServiceCompiler, ServiceError

from .test_services import parity, run


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_ord_all_unicode_scalars(tmp_path: Path, engine: str) -> None:
    points = [n for n in range(0x110000) if not 0xD800 <= n <= 0xDFFF]
    (tmp_path / "scalars.txt").write_text("".join(chr(n) for n in points), encoding="utf-8")
    checksum = 0
    for point in points:
        checksum = (checksum * 65599 + point) % 1000000007
    result = run(
        tmp_path,
        """
from py2rust.stdlib import read_text
def check() -> None:
    checksum: int = 0
    count: int = 0
    for character in read_text("scalars.txt"):
        checksum = (checksum * 65599 + ord(character)) % 1000000007
        count = count + 1
    print(count)
    print(checksum)
    return
if __name__ == "__main__":
    check()
""",
        engine,
    )
    assert result.returncode == 0 and not result.stderr, result.stderr
    assert result.stdout.splitlines() == [str(len(points)), str(checksum)]
    return  # noqa: PLR1711


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_ord_all_bytes_and_recoverable_lengths(tmp_path: Path, engine: str) -> None:
    (tmp_path / "bytes.bin").write_bytes(bytes(range(256)))
    result = run(
        tmp_path,
        """
from py2rust.stdlib import read_bytes
def check() -> None:
    data: bytes = read_bytes("bytes.bin")
    mutable: bytearray = bytearray(data)
    for index in range(256):
        assert ord(data[index:index + 1]) == index
        assert ord(mutable[index:index + 1]) == index
    for text in ["", "ab", "éx", "é", "😀😀"]:
        try:
            ord(text)
        except Exception:
            print("text length")
    for raw in [b"", b"ab"]:
        try:
            ord(raw)
        except Exception:
            print("byte length")
        try:
            ord(bytearray(raw))
        except Exception:
            print("array length")
    print("continued")
    return
if __name__ == "__main__":
    check()
""",
        engine,
    )
    assert result.returncode == 0 and not result.stderr, result.stderr
    assert result.stdout.splitlines() == [
        *["text length"] * 5,
        "byte length",
        "array length",
        "byte length",
        "array length",
        "continued",
    ]
    return  # noqa: PLR1711


def test_ord_single_evaluation(tmp_path: Path) -> None:
    output = parity(
        tmp_path,
        """
def observed() -> str:
    print("called")
    return "😀"
def check() -> None:
    print(ord(observed()))
    return
if __name__ == "__main__":
    check()
""",
    )
    assert output.splitlines() == ["called", "128512"]
    return  # noqa: PLR1711


@pytest.mark.parametrize(
    "expression",
    ["ord()", 'ord("a", "b")', "ord(1)", "ord(1.0)", "ord(True)", "ord([1])", 'ord(value="x")', 'ord({"a":1})'],
)
def test_ord_rejects_unsupported_calls(expression: str) -> None:
    with pytest.raises(ServiceError):
        ServiceCompiler().compile("def check() -> None:\n    " + expression + "\n    return\n")
    return  # noqa: PLR1711
