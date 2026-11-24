"""Literal portability must preserve emitted source and generated-program output."""

import subprocess
from pathlib import Path

import pytest

from py2rust.compiler.rust_text import quote


def test_literal_renderer_preserves_existing_escaping() -> None:
    text = "".join(chr(number) for number in range(256)) + '世界😀"\\'
    expected = '"'
    for char in text:
        number = ord(char)
        expected += {'"': '\\"', "\\": "\\\\", "\n": "\\n", "\r": "\\r", "\t": "\\t"}.get(
            char, f"\\u{{{number:x}}}" if number < 32 else char
        )
    assert quote(text) == expected + '"'
    for surrogate in ["\ud800", "\udfff"]:
        with pytest.raises(ValueError, match="surrogate"):
            quote(surrogate)
    return


def test_emitted_literals_execute_with_original_utf8(tmp_path: Path) -> None:
    text = "".join(chr(number) for number in range(128)) + "Заметка 世界 😀"
    source = tmp_path / "literal.rs"
    source.write_text('fn main() { print!("{}", ' + quote(text) + "); }\n")
    binary = tmp_path / "literal"
    subprocess.run(["rustc", "--edition=2021", str(source), "-o", str(binary)], check=True, capture_output=True)
    result = subprocess.run([str(binary)], check=True, capture_output=True)
    assert result.stdout == text.encode("utf-8")
    return
