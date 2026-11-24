"""Deterministic depth-first Sudoku search with a counted node budget and two witnesses."""

from dataclasses import dataclass

from model import Board, diagnostics, grid

from py2rust.stdlib import Json


@dataclass
class State:
    cells: list[int]
    depth: int


def options(cells: list[int], base: int, position: int) -> list[int]:
    side: int = base * base
    row: int = position // side
    column: int = position % side
    used: set[int] = set()
    for offset in range(side):
        used.add(cells[row * side + offset])
        used.add(cells[offset * side + column])
        other_row: int = (row // base) * base + offset // base
        other_column: int = (column // base) * base + offset % base
        used.add(cells[other_row * side + other_column])
    result: list[int] = []
    for value in range(1, side + 1):
        if value not in used:
            result.append(value)
    return result


def solve(board: Board) -> Json:
    errors: list[Json] = diagnostics(board)
    pending: list[State] = []
    if len(errors) == 0:
        pending.append(State(board.cells.copy(), 0))
    solutions: list[Json] = []
    visited: int = 0
    expanded: int = 0
    dead_ends: int = 0
    max_depth: int = 0
    while len(pending) > 0 and visited < board.budget and len(solutions) < 2:
        current: State = pending.pop()
        visited = visited + 1
        max_depth = max(max_depth, current.depth)
        target: int = -1
        candidates: list[int] = []
        for position in range(len(current.cells)):
            if current.cells[position] == 0:
                available: list[int] = options(current.cells, board.box_size, position)
                if target < 0 or len(available) < len(candidates):
                    target = position
                    candidates = available
                if len(candidates) == 0:
                    break
        if target < 0:
            solutions.append(grid(current.cells, board.box_size * board.box_size))
        elif len(candidates) == 0:
            dead_ends = dead_ends + 1
        else:
            expanded = expanded + 1
            for index in range(len(candidates) - 1, -1, -1):
                following: list[int] = current.cells.copy()
                following[target] = candidates[index]
                pending.append(State(following, current.depth + 1))
    status: str = (
        "invalid"
        if len(errors) > 0
        else (
            "multiple"
            if len(solutions) == 2
            else "search_limit" if len(pending) > 0 else "unique" if len(solutions) == 1 else "unsatisfiable"
        )
    )
    return {
        "id": board.identifier,
        "box_size": board.box_size,
        "status": status,
        "budget": board.budget,
        "complete_search": len(errors) == 0 and len(pending) == 0,
        "solutions_found": len(solutions),
        "solutions": solutions,
        "diagnostics": errors,
        "stats": {
            "visited": visited,
            "expanded": expanded,
            "dead_ends": dead_ends,
            "max_depth": max_depth,
            "remaining_frontier": len(pending),
        },
    }
