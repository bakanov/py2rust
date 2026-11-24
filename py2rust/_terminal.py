"""Explicit terminal I/O and Unicode 16 grapheme/cell policy for the service profile."""

import os
import sys
from collections.abc import Iterator
from functools import lru_cache


def terminal_info() -> dict[str, object]:
    """Query stdout itself; ignore COLUMNS/LINES and use 80x24 when size is unavailable."""
    descriptor = sys.stdout.fileno()
    attached = os.isatty(descriptor)
    columns, rows = 80, 24
    if attached:
        try:
            size = os.get_terminal_size(descriptor)
            columns = size.columns or 80
            rows = size.lines or 24
        except OSError:
            pass
    return {
        "isatty": attached,
        "ansi": attached and os.environ.get("TERM", "") not in {"", "dumb", "unknown"},
        "columns": columns,
        "rows": rows,
    }


def terminal_write(text: str) -> None:
    """Write at most 1 MiB of UTF-8 to stdout, without a newline, and flush it."""
    if type(text) is not str:
        raise ValueError("terminal output requires text")
    data = text.encode("utf-8")
    if len(data) > 1048576:
        raise ValueError("terminal output byte limit")
    pending = memoryview(data)
    while pending:
        written = sys.stdout.buffer.write(pending)
        if written is None or written <= 0:
            raise BlockingIOError("terminal output made no progress")
        pending = pending[written:]
    sys.stdout.buffer.flush()
    return  # noqa: PLR1711 - explicit facade return


@lru_cache(maxsize=4096)
def _properties(character: str) -> tuple[str, str, bool]:
    from uniseg.derived import indic_conjunct_break
    from uniseg.emoji import extended_pictographic
    from uniseg.graphemecluster import grapheme_cluster_break

    return (
        grapheme_cluster_break(character).value,
        indic_conjunct_break(character).value,
        extended_pictographic(character),
    )


def _graphemes(text: str) -> Iterator[str]:
    """UAX29 GB3..GB13 in one pass; retain lookbehind state instead of rescanning long mark runs."""
    previous = ""
    regional = 0
    pictographic_run = False
    pictographic_zwj = False
    consonant_run = False
    linker_seen = False
    start = 0
    for index, character in enumerate(text):
        current, conjunct, pictographic = _properties(character)
        if previous == "CR" and current == "LF":
            joined = True
        elif previous in {"Control", "CR", "LF"} or current in {"Control", "CR", "LF"}:
            joined = False
        else:
            joined = (
                (previous == "L" and current in {"L", "V", "LV", "LVT"})
                or (previous in {"LV", "V"} and current in {"V", "T"})
                or (previous in {"LVT", "T"} and current == "T")
                or current in {"Extend", "ZWJ", "SpacingMark"}
                or previous == "Prepend"
                or (conjunct == "Consonant" and consonant_run and linker_seen)
                or (previous == "ZWJ" and pictographic_zwj and pictographic)
                or (previous == current == "Regional_Indicator" and regional % 2 == 1)
            )
        if index and not joined:
            yield text[start:index]
            start = index
        pictographic_zwj = current == "ZWJ" and pictographic_run
        pictographic_run = pictographic or (current == "Extend" and pictographic_run)
        regional = regional + 1 if current == "Regional_Indicator" else 0
        if conjunct == "Consonant":
            consonant_run, linker_seen = True, False
        elif conjunct == "Linker":
            linker_seen = consonant_run
        elif conjunct != "Extend":
            consonant_run, linker_seen = False, False
        previous = current
    if text:
        yield text[start:]
    return


def terminal_cells(text: str) -> list[tuple[str, int]]:
    """Return intact graphemes and narrow-ambiguous cell widths; never accept control injection."""
    # Reference-only dependencies. Native applications use Rust segmentation and embedded width tables.
    from wcwidth import wcswidth

    if type(text) is not str or len(text.encode("utf-8")) > 65536:
        raise ValueError("terminal text requires at most 65536 UTF-8 bytes")
    for character in text:
        code = ord(character)
        if (
            code < 32
            or 127 <= code <= 159
            or code in {0x061C, 0x200E, 0x200F, 0x2028, 0x2029}
            or 0x202A <= code <= 0x202E
            or 0x2066 <= code <= 0x2069
        ):
            raise ValueError("terminal text contains control or bidi formatting")
    result = []
    for cluster in _graphemes(text):
        width = wcswidth(cluster, unicode_version="16.0.0")
        if width == 0:
            cluster = "◌" + cluster
            width = 1
        result.append((cluster, width))
    return result
