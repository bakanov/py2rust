"""Replay moves with compact undo records and immutable snapshots of every resulting state."""

from dataclasses import dataclass

from model import Command, Program

from py2rust.stdlib import Json


@dataclass
class Move:
    command: Command
    old_row: int
    old_column: int
    new_row: int
    new_column: int
    pushed: bool
    box_row: int
    box_column: int


def direction(command: Command) -> tuple[int, int]:
    if command == Command.UP:
        return (-1, 0)
    if command == Command.DOWN:
        return (1, 0)
    if command == Command.LEFT:
        return (0, -1)
    assert command == Command.RIGHT, "expected movement command"
    return (0, 1)


def inside(grid: list[list[str]], row: int, column: int) -> bool:
    return 0 <= row < len(grid) and 0 <= column < len(grid[0])


def blocked(grid: list[list[str]], row: int, column: int, dr: int, dc: int) -> str:
    if not inside(grid, row, column):
        return "boundary"
    if grid[row][column] == "#":
        return "wall"
    if grid[row][column] == "$":
        if not inside(grid, row + dr, column + dc):
            return "box_boundary"
        target: str = grid[row + dr][column + dc]
        if target == "#":
            return "box_wall"
        if target == "$":
            return "box_chain"
    return ""


def state(grid: list[list[str]], robot_row: int, robot_column: int, depth: int) -> Json:
    rows: list[str] = []
    boxes: list[list[int]] = []
    for row in range(len(grid)):
        rows.append("".join(grid[row]))
        for column in range(len(grid[row])):
            if grid[row][column] == "$":
                boxes.append([row, column])
    return {"grid": rows, "robot": [robot_row, robot_column], "boxes": boxes, "history_depth": depth}


def simulate(program: Program) -> Json:
    grid: list[list[str]] = []
    for row_cells in program.grid:
        grid.append(row_cells.copy())
    row: int = program.robot_row
    column: int = program.robot_column
    initial: Json = state(grid, row, column, 0)
    history: list[Move] = []
    trace: list[Json] = []
    walks: int = 0
    pushes: int = 0
    undos: int = 0
    blocked_count: int = 0
    for index in range(len(program.commands)):
        command: Command = program.commands[index]
        action: str = "blocked"
        reason: str = ""
        if command == Command.UNDO:
            if len(history) == 0:
                reason = "empty_history"
            else:
                previous: Move = history.pop()
                grid[previous.new_row][previous.new_column] = "."
                if previous.pushed:
                    grid[previous.box_row][previous.box_column] = "."
                    grid[previous.new_row][previous.new_column] = "$"
                row = previous.old_row
                column = previous.old_column
                grid[row][column] = "@"
                action = "undo_push" if previous.pushed else "undo_move"
                undos = undos + 1
        else:
            offset: tuple[int, int] = direction(command)
            nr: int = row + offset[0]
            nc: int = column + offset[1]
            reason = blocked(grid, nr, nc, offset[0], offset[1])
            if reason == "":
                assert len(history) < 1024, "undo history limit"
                pushed: bool = grid[nr][nc] == "$"
                history.append(Move(command, row, column, nr, nc, pushed, nr + offset[0], nc + offset[1]))
                grid[row][column] = "."
                grid[nr][nc] = "@"
                if pushed:
                    grid[nr + offset[0]][nc + offset[1]] = "$"
                    pushes = pushes + 1
                else:
                    walks = walks + 1
                row = nr
                column = nc
                action = "push" if pushed else "move"
        if action == "blocked":
            blocked_count = blocked_count + 1
        trace.append(
            {
                "index": index,
                "command": command.value,
                "action": action,
                "reason": reason,
                "state": state(grid, row, column, len(history)),
            }
        )
    active: list[str] = []
    for entry in history:
        active.append(entry.command.value)
    counts: Json = {
        "commands": len(program.commands),
        "walks": walks,
        "pushes": pushes,
        "undos": undos,
        "blocked": blocked_count,
        "history_depth": len(history),
    }
    return {
        "title": program.title,
        "initial": initial,
        "final": state(grid, row, column, len(history)),
        "summary": counts,
        "active_commands": active,
        "trace": trace,
    }
