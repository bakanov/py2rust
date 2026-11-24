"""Parse an ASCII warehouse and a complete, bounded sequence of typed commands."""

# ruff: noqa: PLR1711 - explicit returns
from dataclasses import dataclass
from enum import Enum

from py2rust.stdlib import (
    Json,
    json_array,
    json_int,
    json_keys,
    json_kind,
    json_string,
    unicode_normalize,
)


class Command(Enum):
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"
    UNDO = "undo"


@dataclass
class Program:
    title: str
    grid: list[list[str]]
    robot_row: int
    robot_column: int
    commands: list[Command]


def text(value: Json) -> str:
    assert json_kind(value) == "string", "expected text"
    return json_string(value)


def exact(value: Json, fields: list[str]) -> None:
    assert json_kind(value) == "object", "expected object"
    assert sorted(json_keys(value)) == sorted(fields), "unexpected fields"
    return


def array(value: Json, maximum: int) -> list[Json]:
    assert json_kind(value) == "array", "expected array"
    values: list[Json] = json_array(value)
    assert len(values) <= maximum, "array count limit"
    return values


def display(value: str) -> str:
    return " ".join(unicode_normalize("NFKC", value).split())


def parse(source: Json) -> Program:
    exact(source, ["version", "title", "grid", "commands"])
    assert json_int(source["version"]) == 1, "unsupported source version"
    title: str = text(source["title"])
    shown: str = display(title)
    assert 1 <= len(title) <= 100 and 1 <= len(shown) <= 100, "title character limit"
    for character in shown:
        assert ord(character) >= 32 and not 127 <= ord(character) <= 159, "control character in title"
    rows: list[Json] = array(source["grid"], 32)
    assert len(rows) > 0, "empty grid"
    grid: list[list[str]] = []
    width: int = len(text(rows[0]))
    assert 1 <= width <= 32, "grid width limit"
    robots: int = 0
    boxes: int = 0
    robot_row: int = 0
    robot_column: int = 0
    for row in range(len(rows)):
        line: str = text(rows[row])
        assert len(line) == width, "ragged grid"
        cells: list[str] = []
        for column in range(width):
            cell: str = line[column]
            assert cell in ["#", ".", "@", "$"], "unknown grid cell"
            if cell == "@":
                robots = robots + 1
                robot_row = row
                robot_column = column
            elif cell == "$":
                boxes = boxes + 1
            cells.append(cell)
        grid.append(cells)
    assert robots == 1, "grid requires exactly one robot"
    assert boxes <= 64, "box count limit"
    names: dict[str, Command] = {
        "up": Command.UP,
        "down": Command.DOWN,
        "left": Command.LEFT,
        "right": Command.RIGHT,
        "undo": Command.UNDO,
    }
    commands: list[Command] = []
    for value in array(source["commands"], 2048):
        name: str = text(value)
        assert name in names, "unknown command"
        commands.append(names[name])
    return Program(title, grid, robot_row, robot_column, commands)
