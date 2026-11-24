"""Full default Unicode case folding matches the pinned Python reference on every scalar."""

import unicodedata
from pathlib import Path

import pytest
from py2rust.compiler.service import ServiceCompiler, ServiceError

from .test_services import parity, run


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_casefold_every_unicode_scalar(tmp_path: Path, engine: str) -> None:
    assert unicodedata.unidata_version == "15.1.0"
    text = "".join(chr(value) for value in range(0x110000) if not 0xD800 <= value <= 0xDFFF)
    (tmp_path / "input.txt").write_bytes(text.encode())
    result = run(
        tmp_path,
        """
from py2rust.stdlib import read_text, write_text_atomic
def check() -> None:
    original: str = read_text("input.txt")
    folded: str = original.casefold()
    assert folded.casefold() == folded
    write_text_atomic("folded.txt", folded)
    return
if __name__ == "__main__":
    check()
""",
        engine,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "folded.txt").read_bytes() == text.casefold().encode()
    return  # noqa: PLR1711


def test_casefold_sequences_expansion_and_evaluation(tmp_path: Path) -> None:
    output = parity(
        tmp_path,
        """
def observed() -> str:
    print("once")
    return "Straße Σςσ İıI ﬃ ᾈ Ꮳꮳ"
def check() -> None:
    assert "Straße".casefold() == "strasse"
    assert "Σςσ".casefold() == "σσσ"
    assert "İIı".casefold() == "i̇iı"
    assert "ΟΣ".casefold() == "οσ"
    assert "".casefold() == ""
    result: str = observed().casefold()
    print(result)
    return
if __name__ == "__main__":
    check()
""",
    )
    assert output.count("once\n") == 1
    return  # noqa: PLR1711


def test_casefold_rejects_arguments() -> None:
    with pytest.raises(ServiceError):
        ServiceCompiler().compile(
            'def check() -> None:\n    "x".casefold(True)\n    return\nif __name__ == "__main__":\n    check()\n'
        )
    return  # noqa: PLR1711
