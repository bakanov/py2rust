"""Strict batch input and complete duplicate-given diagnostics for 4x4 and 9x9 Sudoku."""

# ruff: noqa: PLR1711 - explicit subset returns

from dataclasses import dataclass

from py2rust.stdlib import Json, json_array, json_int, json_keys, json_string


@dataclass
class Board:
    identifier: str
    box_size: int
    cells: list[int]
    budget: int


def exact(value: Json, fields: list[str]) -> None:
    assert json_keys(value) == sorted(fields), "unexpected object fields"
    return


def grid(cells: list[int], side: int) -> Json:
    rows: list[Json] = []
    for start in range(0, len(cells), side):
        row: list[Json] = []
        for column in range(side):
            row.append(cells[start + column])
        rows.append(row)
    return rows


def load(value: Json) -> list[Board]:
    exact(value, ["version", "boards"])
    assert json_int(value["version"]) == 1, "unsupported batch version"
    rows: list[Json] = json_array(value["boards"])
    assert len(rows) <= 64, "board count exceeds 64"
    result: list[Board] = []
    names: set[str] = set()
    total_budget: int = 0
    for row in rows:
        exact(row, ["id", "box_size", "rows", "budget"])
        identifier: str = json_string(row["id"])
        assert (
            1 <= len(identifier) <= 128 and len(identifier.encode()) <= 512 and "\x00" not in identifier
        ), "invalid board id"
        assert identifier not in names, "duplicate board id"
        names.add(identifier)
        base: int = json_int(row["box_size"])
        assert base in [2, 3], "box size must be 2 or 3"
        side: int = base * base
        source: list[Json] = json_array(row["rows"])
        assert len(source) == side, "incorrect row count"
        cells: list[int] = []
        for values in source:
            columns: list[Json] = json_array(values)
            assert len(columns) == side, "incorrect column count"
            for cell in columns:
                number: int = json_int(cell)
                assert 0 <= number <= side, "cell value outside bounds"
                cells.append(number)
        budget: int = json_int(row["budget"])
        assert 0 <= budget <= 100000, "board budget outside 0..100000"
        total_budget = total_budget + budget
        assert total_budget <= 1000000, "batch budget exceeds 1000000"
        result.append(Board(identifier, base, cells, budget))
    return result


def document(boards: list[Board]) -> Json:
    rows: list[Json] = []
    for board in boards:
        rows.append(
            {
                "id": board.identifier,
                "box_size": board.box_size,
                "rows": grid(board.cells, board.box_size * board.box_size),
                "budget": board.budget,
            }
        )
    return {"version": 1, "boards": rows}


def diagnostics(board: Board) -> list[Json]:
    side: int = board.box_size * board.box_size
    result: list[Json] = []
    for kind in ["row", "column", "box"]:
        for unit in range(side):
            for value in range(1, side + 1):
                positions: list[Json] = []
                for position in range(len(board.cells)):
                    row: int = position // side
                    column: int = position % side
                    group: int = (
                        row
                        if kind == "row"
                        else (
                            column
                            if kind == "column"
                            else (row // board.box_size) * board.box_size + column // board.box_size
                        )
                    )
                    if group == unit and board.cells[position] == value:
                        positions.append({"row": row, "column": column})
                if len(positions) > 1:
                    result.append({"kind": kind, "unit": unit, "value": value, "cells": positions})
    return result
