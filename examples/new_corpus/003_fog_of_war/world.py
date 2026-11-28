"""A bounded square map with coordinate-based tile identity."""

from dataclasses import dataclass

Point = tuple[int, int]
DIRECTIONS: tuple[Point, ...] = ((0, -1), (1, 0), (0, 1), (-1, 0))


@dataclass
class Tile:
    x: int
    y: int
    terrain: str
    ruin: bool = False

    @property
    def point(self) -> Point:
        return self.x, self.y


@dataclass
class World:
    width: int
    height: int
    tiles: list[Tile]

    def tile_at(self, x: int, y: int) -> Tile | None:
        if not (0 <= x < self.width and 0 <= y < self.height):
            return None
        return self.tiles[y * self.width + x]

    def neighbors(self, tile: Tile) -> list[Tile]:
        result: list[Tile] = []
        for direction in DIRECTIONS:
            neighbor: Tile | None = self.tile_at(tile.x + direction[0], tile.y + direction[1])
            if neighbor is not None:
                result.append(neighbor)
        return result


def tiny_world() -> World:
    tiles: list[Tile] = []
    for y in range(5):
        for x in range(5):
            terrain: str = "hills" if (x + y) % 4 == 0 else "grassland"
            tiles.append(Tile(x, y, terrain, (x, y) == (2, 1)))
    return World(5, 5, tiles)
