"""Independent UTF-8 tokenization, shortest-edit and context-hunk oracles."""

from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache
from itertools import groupby


def canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def lines(data: bytes) -> list[str]:
    return re.findall(r"[^\r\n]*(?:\r\n|\r|\n)|[^\r\n]+\Z", data.decode())


def identity(data: bytes) -> dict:
    ending = next(
        (name for suffix, name in [(b"\r\n", "crlf"), (b"\n", "lf"), (b"\r", "cr")] if data.endswith(suffix)), "none"
    )
    return {"bytes": len(data), "lines": len(lines(data)), "sha256": digest(data), "ending": ending}


def shortest(before: list[str], after: list[str]) -> list[tuple[str, str]]:
    """Choose the cheapest edit path; ordered alternatives resolve equal costs locally."""

    @lru_cache(None)
    def visit(left: int, right: int) -> tuple[int, tuple[tuple[str, str], ...]]:
        if left == len(before) and right == len(after):
            return 0, ()
        alternatives = []
        if left < len(before) and right < len(after) and before[left] == after[right]:
            cost, rest = visit(left + 1, right + 1)
            alternatives.append((cost, ((" ", before[left]), *rest)))
        if left < len(before):
            cost, rest = visit(left + 1, right)
            alternatives.append((cost + 1, (("-", before[left]), *rest)))
        if right < len(after):
            cost, rest = visit(left, right + 1)
            alternatives.append((cost + 1, (("+", after[right]), *rest)))
        return min(alternatives, key=lambda row: row[0])

    return list(visit(0, 0)[1])


def lcs_length(before: list[str], after: list[str]) -> int:
    """A forward two-row recurrence independent of the application's suffix table."""
    previous = [0] * (len(after) + 1)
    for left in before:
        current = [0]
        for index, right in enumerate(after, 1):
            current.append(previous[index - 1] + 1 if left == right else max(previous[index], current[-1]))
        previous = current
    return previous[-1]


def grouped(edits: list[tuple[str, str]], context: int) -> list[dict]:
    covered = set()
    for index, (kind, _) in enumerate(edits):
        if kind != " ":
            covered.update(range(max(0, index - context), min(len(edits), index + context + 1)))
    groups = []
    for _, entries in groupby(enumerate(sorted(covered)), key=lambda row: row[1] - row[0]):
        positions = [row[1] for row in entries]
        start, end = positions[0], positions[-1] + 1
        preceding, selected = edits[:start], edits[start:end]
        groups.append(
            {
                "old_start": sum(kind != "+" for kind, _ in preceding),
                "new_start": sum(kind != "-" for kind, _ in preceding),
                "old_count": sum(kind != "+" for kind, _ in selected),
                "new_count": sum(kind != "-" for kind, _ in selected),
                "ops": [{"op": kind, "text": text} for kind, text in selected],
            }
        )
    return groups


def inspect_patch(patch: dict, before: bytes, after: bytes, context: int) -> dict:
    assert set(patch) == {"version", "format", "context", "before", "after", "hunks"}
    assert patch["version"] == 1 and patch["format"] == "line-lcs" and patch["context"] == context
    assert patch["before"] == identity(before) and patch["after"] == identity(after)
    old, new = lines(before), lines(after)
    operations, result = [], []
    cursor = 0
    for row in patch["hunks"]:
        assert set(row) == {"old_start", "old_count", "new_start", "new_count", "ops"}
        assert cursor <= row["old_start"] <= len(old)
        unchanged = old[cursor : row["old_start"]]
        operations.extend((" ", token) for token in unchanged)
        result.extend(unchanged)
        assert len(result) == row["new_start"]
        cursor = row["old_start"]
        removed, added = 0, 0
        for item in row["ops"]:
            assert set(item) == {"op", "text"} and item["op"] in [" ", "-", "+"]
            kind, token = item["op"], item["text"]
            assert lines(token.encode()) == [token]
            operations.append((kind, token))
            if kind != "+":
                assert cursor < len(old) and old[cursor] == token
                cursor += 1
                removed += 1
            if kind != "-":
                result.append(token)
                added += 1
        assert (removed, added) == (row["old_count"], row["new_count"])
    result.extend(old[cursor:])
    operations.extend((" ", token) for token in old[cursor:])
    assert result == new and "".join(result).encode() == after
    assert patch["hunks"] == grouped(operations, context)
    common = lcs_length(old, new)
    assert sum(kind == " " for kind, _ in operations) == common
    if len(old) + len(new) <= 24:
        assert operations == shortest(old, new), (old, new, operations, shortest(old, new))
    return {
        "removed": len(old) - common,
        "added": len(new) - common,
        "common": common,
        "hunks": len(patch["hunks"]),
        "cells": (len(old) + 1) * (len(new) + 1),
    }


def fixtures() -> dict[str, tuple[bytes, bytes]]:
    return {
        "empty": (b"", b""),
        "insert": (b"", "Hello 世界\n".encode()),
        "delete": (b"one\ntwo\n", b""),
        "unchanged": (b"one\ntwo", b"one\ntwo"),
        "newline-add": (b"one", b"one\n"),
        "newline-remove": (b"one\n", b"one"),
        "empty-lines": (b"\n\n\r\n", b"\n\r\n\n"),
        "tie": (b"A\nB\n", b"B\nA\n"),
        "repeated": (b"x\ny\nx\nz\n", b"x\nx\ny\nz\n"),
        "mixed": (b"one\r\ntwo\rthree\nlast", b"one\r\nTWO\rthree\nlast\r"),
        "unicode": ("A\u0301\n世界\r😀\u2028x\n".encode(), "Á\n世界\r😀\u2028y\n".encode()),
        "bom": (b"\xef\xbb\xbfhello\n", b"\xef\xbb\xbfworld\n"),
        "nul-controls": (b"zero\x00one\n\t\x01", b"zero\x00two\r\n\t\x02"),
        "unicode-separators": ("a\u0085b\u2028c\u2029d".encode(), "a\u0085b\u2028c\u2029e".encode()),
        "crlf-boundary": (b"a\rb\n", b"a\r\nb\n"),
        "crlf-remove-cr": (b"a\r\nb\n", b"a\nb\n"),
    }
