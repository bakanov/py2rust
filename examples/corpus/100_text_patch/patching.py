"""Reject stale, malformed and noncanonical hunks before returning corrected bytes."""

from alignment import create
from text_model import exact, identity, integer, lines, metadata

from py2rust.stdlib import Json, json_array, json_equal, json_int, json_string


def apply(before: bytes, patch: Json) -> bytes:
    exact(patch, ["version", "format", "context", "before", "after", "hunks"])
    assert json_int(patch["version"]) == 1 and json_string(patch["format"]) == "line-lcs", "unsupported patch format"
    context: int = integer(patch["context"], 0, 16)
    metadata(patch["before"])
    metadata(patch["after"])
    assert json_equal(identity(before), patch["before"]), "base identity mismatch"
    original: list[str] = lines(before)
    result: list[str] = []
    cursor: int = 0
    operation_count: int = 0
    rows: list[Json] = json_array(patch["hunks"])
    assert len(rows) <= 1024, "hunk count limit"
    for number in range(len(rows)):
        hunk: Json = rows[number]
        exact(hunk, ["old_start", "old_count", "new_start", "new_count", "ops"])
        start: int = integer(hunk["old_start"], 0, len(original))
        old_count: int = integer(hunk["old_count"], 0, 1024)
        new_start: int = integer(hunk["new_start"], 0, 1024)
        new_count: int = integer(hunk["new_count"], 0, 1024)
        assert start >= cursor, "overlapping or unordered hunk"
        result.extend(original[cursor:start])
        assert len(result) == new_start, "new hunk position mismatch"
        cursor = start
        used: int = 0
        added: int = 0
        local_changes: int = 0
        operations: list[Json] = json_array(hunk["ops"])
        operation_count = operation_count + len(operations)
        assert 1 <= len(operations) and operation_count <= 2048, "operation count limit"
        for operation in operations:
            exact(operation, ["op", "text"])
            kind: str = json_string(operation["op"])
            text: str = json_string(operation["text"])
            assert kind in [" ", "-", "+"] and lines(text.encode()) == [text], "invalid line operation"
            if kind != "+":
                assert cursor < len(original) and original[cursor] == text, "hunk context or deletion mismatch"
                cursor = cursor + 1
                used = used + 1
            if kind != "-":
                result.append(text)
                added = added + 1
            if kind != " ":
                local_changes = local_changes + 1
            assert len(result) <= 1024, "result line limit exceeded"
        assert used == old_count and added == new_count, "hunk count mismatch"
        assert local_changes > 0, "hunk contains no change"
    result.extend(original[cursor:])
    after: bytes = "".join(result).encode()
    assert lines(after) == result, "noncanonical line boundaries"
    assert json_equal(identity(after), patch["after"]), "result identity mismatch"
    assert json_equal(create(before, after, context), patch), "noncanonical LCS or context hunks"
    return after
