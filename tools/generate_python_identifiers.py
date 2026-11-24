"""Regenerate the native parser's Unicode 15.1 identifier tables using CPython 3.13."""

import unicodedata
from pathlib import Path


def generate() -> str:
    assert unicodedata.unidata_version == "15.1.0", "use the Python 3.13 reference environment"
    source = "// Unicode 15.1 XID ranges generated from CPython 3.13 isidentifier().\n"
    source += "// Regenerate with tools/generate_python_identifiers.py; do not use locale-dependent classes.\n"
    for name in ["START", "CONTINUE"]:
        ranges: list[list[int]] = []
        for codepoint in range(0x110000):
            text = chr(codepoint) if name == "START" else "a" + chr(codepoint)
            if text.isidentifier():
                if ranges and codepoint == ranges[-1][1] + 1:
                    ranges[-1][1] = codepoint
                else:
                    ranges.append([codepoint, codepoint])
        source += f"const {name}: &[(u32, u32)] = &[\n"
        source += "".join(f"    (0x{start:X}, 0x{end:X}),\n" for start, end in ranges) + "];\n"
    source += """fn contains(ranges: &[(u32, u32)], c: char) -> bool {
    let value = c as u32;
    let index = ranges.partition_point(|range| range.0 <= value);
    index > 0 && value <= ranges[index - 1].1
}
pub(crate) fn valid(name: &str) -> bool {
    let mut chars = name.chars();
    chars.next().is_some_and(|c| contains(START, c)) && chars.all(|c| contains(CONTINUE, c))
}
"""
    return source


if __name__ == "__main__":
    Path(__file__).resolve().parents[1].joinpath(
        "py2rust/compiler/service_runtime/src/python_identifiers.rs"
    ).write_text(generate())
