"""Copy-on-write visibility updates preserve explored terrain and tile history."""

from dataclasses import dataclass, field

from world import DIRECTIONS, Point, Tile, World


@dataclass
class TileKnowledge:
    known: set[Point] = field(default_factory=set)
    visible: set[Point] = field(default_factory=set)
    frontier: set[Point] = field(default_factory=set)
    known_terrain: dict[Point, str] = field(default_factory=dict)
    known_ruins: set[Point] = field(default_factory=set)


def observe(original: TileKnowledge, world: World, visible: set[Point]) -> TileKnowledge:
    refreshed: TileKnowledge = TileKnowledge(
        original.known.copy(),
        visible.copy(),
        set(),
        original.known_terrain.copy(),
        original.known_ruins.copy(),
    )
    for point in visible:
        tile: Tile | None = world.tile_at(point[0], point[1])
        assert tile is not None, "cannot observe a point outside the world"
        refreshed.known.add(point)
        refreshed.known_terrain[point] = tile.terrain
        if tile.ruin:
            refreshed.known_ruins.add(point)
        else:
            refreshed.known_ruins.discard(point)
    for point in refreshed.known:
        for direction in DIRECTIONS:
            candidate: Point = point[0] + direction[0], point[1] + direction[1]
            if world.tile_at(candidate[0], candidate[1]) is not None and candidate not in refreshed.known:
                refreshed.frontier.add(candidate)
    return refreshed


def update_visibility(
    knowledge: dict[int, TileKnowledge], world: World, owner: int, visible: set[Point]
) -> dict[int, TileKnowledge]:
    assert owner in knowledge, "missing player knowledge"
    knowledge[owner] = observe(knowledge[owner], world, visible)
    return knowledge


def point_text(points: set[Point]) -> str:
    rows: list[str] = []
    for point in sorted(points):
        rows.append(str(point[0]) + "," + str(point[1]))
    return " ".join(rows)
