"""Strict ASCII terrain grids, integer traversal costs and bounded routing requests."""

# ruff: noqa: PLR1711 - explicit subset returns

from dataclasses import dataclass

from py2rust.stdlib import Json, json_array, json_int, json_keys, json_string


@dataclass
class Grid:
    rows: list[str]
    cells: list[int]
    width: int
    minimum: int
    passable: int


def exact(value: Json, fields: list[str]) -> None:
    assert json_keys(value) == sorted(fields), "unexpected object fields"
    return


def terrain(value: Json) -> dict[str, int]:
    exact(value, ["version", "costs"])
    assert json_int(value["version"]) == 1, "unsupported terrain version"
    keys: list[str] = json_keys(value["costs"])
    assert len(keys) <= 16, "terrain count exceeds 16"
    costs: dict[str, int] = {}
    for symbol in keys:
        assert len(symbol) == 1 and " " <= symbol <= "~" and symbol not in "#SG*@X", "invalid terrain symbol"
        cost: int = json_int(value["costs"][symbol])
        assert 0 <= cost <= 1000000000, "terrain cost outside bounds"
        costs[symbol] = cost
    return costs


def load(text: str, costs: dict[str, int]) -> Grid:
    normalized: str = text.replace("\r\n", "\n")
    assert "\r" not in normalized, "bare carriage return in grid"
    rows: list[str] = normalized.split("\n")
    if rows[-1] == "":
        rows.pop()
    assert 1 <= len(rows) <= 64, "grid height must be 1..64"
    width: int = len(rows[0])
    assert 1 <= width <= 64, "grid width must be 1..64"
    cells: list[int] = []
    minimum: int = 1000000000
    passable: int = 0
    for row in rows:
        assert len(row) == width, "grid is not rectangular"
        for column in range(width):
            symbol: str = row[column]
            cost: int = -1
            if symbol != "#":
                assert symbol in costs, "unknown grid terrain"
                cost = costs[symbol]
                minimum = min(minimum, cost)
                passable = passable + 1
            cells.append(cost)
    return Grid(rows, cells, width, minimum if passable > 0 else 0, passable)


def cell(grid: Grid, value: Json) -> int:
    coordinates: list[Json] = json_array(value)
    assert len(coordinates) == 2, "coordinates must be [row, column]"
    row: int = json_int(coordinates[0])
    column: int = json_int(coordinates[1])
    assert 0 <= row < len(grid.rows) and 0 <= column < grid.width, "coordinate outside grid"
    return row * grid.width + column


def requests(grid: Grid, value: Json) -> list[Json]:
    rows: list[Json] = json_array(value)
    assert len(rows) <= 64, "query count exceeds 64"
    seen: set[str] = set()
    for row in rows:
        exact(row, ["id", "start", "goal"])
        name: str = json_string(row["id"])
        assert 1 <= len(name) <= 64 and len(name.encode()) <= 256 and "\x00" not in name, "invalid query id"
        assert name not in seen, "duplicate query id"
        seen.add(name)
        cell(grid, row["start"])
        cell(grid, row["goal"])
    return rows
