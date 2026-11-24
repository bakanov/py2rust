"""Stable hash join, duplicate multiplicities, projection and unmatched-row accounting."""

from dataclasses import dataclass

from csvcodec import render
from settings import Table

from py2rust.stdlib import Json, json_int, json_string


@dataclass
class Joined:
    data: str
    report: Json


def key(row: list[str], columns: list[int]) -> tuple[str, ...]:
    values: list[str] = []
    for column in columns:
        values.append(row[column])
    return tuple(values)


def index_rows(table: Table) -> dict[tuple[str, ...], list[int]]:
    result: dict[tuple[str, ...], list[int]] = {}
    for number in range(len(table.rows)):
        value: tuple[str, ...] = key(table.rows[number], table.keys)
        if value not in result:
            result[value] = []
        result[value].append(number)
    return result


def duplicates(index: dict[tuple[str, ...], list[int]]) -> list[Json]:
    result: list[Json] = []
    for value in sorted(list(index)):  # noqa: C414 - typed key snapshot
        if len(index[value]) > 1:
            numbers: list[int] = []
            for number in index[value]:
                numbers.append(number + 1)
            result.append({"key": value, "rows": numbers})
    return result


def unmatched(table: Table, matched: set[int]) -> list[Json]:
    result: list[Json] = []
    for number in range(len(table.rows)):
        if number not in matched:
            result.append({"row": number + 1, "values": table.rows[number]})
    return result


def project(left: list[str], right: list[str], selected: list[tuple[str, int, str]]) -> list[str]:
    result: list[str] = []
    for column in selected:
        if column[0] == "left":
            result.append(left[column[1]])
        else:
            result.append(right[column[1]] if len(right) > 0 else "")
    return result


def join(left: Table, right: Table, selected: list[tuple[str, int, str]], config: Json) -> Joined:
    left_index: dict[tuple[str, ...], list[int]] = index_rows(left)
    right_index: dict[tuple[str, ...], list[int]] = index_rows(right)
    left_duplicates: list[Json] = duplicates(left_index)
    right_duplicates: list[Json] = duplicates(right_index)
    assert json_string(config["duplicates"]) == "all" or (
        len(left_duplicates) == 0 and len(right_duplicates) == 0
    ), "duplicate join key rejected by policy"
    outer: bool = json_string(config["kind"]) == "left"
    count: int = 0
    matched_pairs: int = 0
    matched_left: set[int] = set()
    matched_right: set[int] = set()
    # Check expansion before allocating any result rows, including zero selected right columns.
    for value in left_index:  # noqa: PLC0206 - subset key iteration
        matches: list[int] = right_index.get(value, [])
        pairs: int = len(left_index[value]) * len(matches)
        matched_pairs = matched_pairs + pairs
        count = count + (len(left_index[value]) if outer and len(matches) == 0 else pairs)
        assert count <= json_int(config["max_output_rows"]), "join output row limit exceeded"
        if len(matches) > 0:
            for number in left_index[value]:
                matched_left.add(number)
            for number in matches:
                matched_right.add(number)
    ordered: list[int] = []
    if json_string(config["order"]) == "key":
        for value in sorted(list(left_index)):  # noqa: C414 - typed key snapshot
            ordered.extend(left_index[value])
    else:
        for number in range(len(left.rows)):
            ordered.append(number)  # noqa: PERF402 - lazy range is not a list
    header: list[str] = []
    for column in selected:
        header.append(column[2])
    lines: list[str] = [render([header], json_string(config["delimiter"]), 65536)]
    size: int = len(lines[0].encode())
    for number in ordered:
        value: tuple[str, ...] = key(left.rows[number], left.keys)
        matches: list[int] = right_index.get(value, [])
        if len(matches) == 0 and outer:
            matches.append(-1)
        for position in matches:
            row: list[str] = right.rows[position] if position >= 0 else []
            projected: list[str] = project(left.rows[number], row, selected)
            line: str = render([projected], json_string(config["delimiter"]), 65536)
            size = size + len(line.encode())
            assert size <= 8388608, "join output exceeds 8 MiB"
            lines.append(line)
    report: Json = {
        "kind": json_string(config["kind"]),
        "order": json_string(config["order"]),
        "columns": header,
        "left_columns": left.header,
        "right_columns": right.header,
        "left_rows": len(left.rows),
        "right_rows": len(right.rows),
        "output_rows": count,
        "matched_pairs": matched_pairs,
        "matched_left": len(matched_left),
        "matched_right": len(matched_right),
        "unmatched_left": unmatched(left, matched_left),
        "unmatched_right": unmatched(right, matched_right),
        "duplicate_left": left_duplicates,
        "duplicate_right": right_duplicates,
    }
    return Joined("".join(lines), report)
