"""Static map rules shared by movement, visibility, and the economy."""

MAP_ROWS: tuple[str, ...] = (
    "ggpgg",
    "gppfg",
    "ggghg",
    "ggggg",
)
YIELDS: dict[str, tuple[int, int, int]] = {
    "g": (2, 1, 1),
    "p": (3, 1, 1),
    "f": (1, 2, 0),
    "h": (1, 3, 0),
}
DIRECTIONS: tuple[tuple[int, int], ...] = ((0, -1), (1, 0), (0, 1), (-1, 0))


def inside(point: tuple[int, int]) -> bool:
    return 0 <= point[1] < len(MAP_ROWS) and 0 <= point[0] < len(MAP_ROWS[0])


def terrain(point: tuple[int, int]) -> str:
    assert inside(point), "point outside campaign map"
    return MAP_ROWS[point[1]][point[0]]


def sight(center: tuple[int, int]) -> set[tuple[int, int]]:
    result: set[tuple[int, int]] = {center}
    for direction in DIRECTIONS:
        point: tuple[int, int] = center[0] + direction[0], center[1] + direction[1]
        if inside(point):
            result.add(point)
    return result


def step_toward(origin: tuple[int, int], destination: tuple[int, int]) -> tuple[int, int]:
    x: int = origin[0]
    y: int = origin[1]
    if x < destination[0]:
        x += 1
    elif x > destination[0]:
        x -= 1
    elif y < destination[1]:
        y += 1
    elif y > destination[1]:
        y -= 1
    return x, y
