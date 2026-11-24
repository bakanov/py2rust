"""Consistent A* with stable heap priorities, stale-entry checks and ASCII route overlays."""

import heapq

from model import Grid, cell

from py2rust.stdlib import Json, json_array, json_canonical, json_int, json_string


def estimate(position: int, destination: int, width: int, minimum: int) -> int:
    row: int = position // width
    column: int = position % width
    target_row: int = destination // width
    target_column: int = destination % width
    distance: int = (
        max(row, target_row) - min(row, target_row) + max(column, target_column) - min(column, target_column)
    )
    return distance * minimum


def neighbors(position: int, width: int, height: int) -> list[int]:
    result: list[int] = []
    directions: list[tuple[int, int]] = [(-1, 0), (0, -1), (0, 1), (1, 0)]
    for direction in directions:
        row: int = position // width + direction[0]
        column: int = position % width + direction[1]
        if 0 <= row < height and 0 <= column < width:
            result.append(row * width + column)
    return result


def solve(grid: Grid, request: Json) -> Json:
    start: int = cell(grid, request["start"])
    destination: int = cell(grid, request["goal"])
    blocked: list[str] = []
    if grid.cells[start] < 0:
        blocked.append("start")
    if grid.cells[destination] < 0:
        blocked.append("goal")
    response: Json = {
        "id": request["id"],
        "start": request["start"],
        "goal": request["goal"],
        "status": "blocked",
        "blocked": blocked,
        "cost": None,
        "steps": 0,
        "path": [],
        "stats": {
            "pushed": 0,
            "popped": 0,
            "expanded": 0,
            "stale": 0,
            "discovered": 0,
            "frontier_peak": 0,
            "frontier_remaining": 0,
        },
    }
    if len(blocked) > 0:
        return response
    distances: list[int] = []
    parents: list[int] = []
    for value in grid.cells:
        distances.append(-1)
        parents.append(-1)
    distances[start] = 0
    heap: list[tuple[int, int, int]] = []
    heapq.heappush(heap, (estimate(start, destination, grid.width, grid.minimum), 0, start))
    closed: set[int] = set()
    pushed: int = 1
    popped: int = 0
    stale: int = 0
    discovered: int = 1
    peak: int = 1
    while len(heap) > 0:
        ticket: tuple[int, int, int] = heapq.heappop(heap)
        popped = popped + 1
        position: int = ticket[2]
        if position in closed or ticket[1] != distances[position]:
            stale = stale + 1
            continue
        closed.add(position)
        if position == destination:
            break
        for following in neighbors(position, grid.width, len(grid.rows)):
            if grid.cells[following] < 0 or following in closed:
                continue
            cost: int = ticket[1] + grid.cells[following]
            if distances[following] < 0 or cost < distances[following]:
                if distances[following] < 0:
                    discovered = discovered + 1
                distances[following] = cost
                parents[following] = position
                heapq.heappush(
                    heap, (cost + estimate(following, destination, grid.width, grid.minimum), cost, following)
                )
                pushed = pushed + 1
                peak = max(peak, len(heap))
    response["stats"] = {
        "pushed": pushed,
        "popped": popped,
        "expanded": len(closed),
        "stale": stale,
        "discovered": discovered,
        "frontier_peak": peak,
        "frontier_remaining": len(heap),
    }
    response["status"] = "unreachable"
    if destination in closed:
        reverse: list[int] = [destination]
        current: int = destination
        while current != start:
            current = parents[current]
            assert current >= 0 and len(reverse) < len(grid.cells), "invalid route predecessor chain"
            reverse.append(current)
        reverse.reverse()
        path: list[Json] = []
        for position in reverse:
            path.append([position // grid.width, position % grid.width])
        response["status"] = "found"
        response["cost"] = distances[destination]
        response["steps"] = len(path) - 1
        response["path"] = path
    return response


def render(grid: Grid, result: Json) -> str:
    marked: set[int] = set()
    for point in json_array(result["path"]):
        marked.add(json_int(point[0]) * grid.width + json_int(point[1]))
    start: int = cell(grid, result["start"])
    destination: int = cell(grid, result["goal"])
    lines: list[str] = [
        "Route "
        + json_canonical(result["id"])
        + ": "
        + json_string(result["status"])
        + " cost="
        + json_canonical(result["cost"])
    ]
    for row in range(len(grid.rows)):
        symbols: list[str] = []
        for column in range(grid.width):
            position: int = row * grid.width + column
            symbol: str = "*" if position in marked else grid.rows[row][column]
            if position == start or position == destination:
                symbol = (
                    "X"
                    if grid.cells[position] < 0
                    else "@" if start == destination else "S" if position == start else "G"
                )
            symbols.append(symbol)
        lines.append("".join(symbols))
    return "\n".join(lines) + "\n"
