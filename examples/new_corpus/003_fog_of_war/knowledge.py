"""Copy-on-write visibility updates preserve explored terrain and tile history."""

from dataclasses import dataclass, field

from world import DIRECTIONS, Tile, World


@dataclass
class TileKnowledge:
    known: set[tuple[int, int]] = field(default_factory=set)
    visible: set[tuple[int, int]] = field(default_factory=set)
    frontier: set[tuple[int, int]] = field(default_factory=set)
    known_terrain: dict[tuple[int, int], str] = field(default_factory=dict)
    known_ruins: set[tuple[int, int]] = field(default_factory=set)


def observe(original: TileKnowledge, world: World, visible: set[tuple[int, int]]) -> TileKnowledge:
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
            candidate: tuple[int, int] = point[0] + direction[0], point[1] + direction[1]
            if world.tile_at(candidate[0], candidate[1]) is not None and candidate not in refreshed.known:
                refreshed.frontier.add(candidate)
    return refreshed


def update_visibility(
    knowledge: dict[int, TileKnowledge], world: World, owner: int, visible: set[tuple[int, int]]
) -> dict[int, TileKnowledge]:
    assert owner in knowledge, "missing player knowledge"
    knowledge[owner] = observe(knowledge[owner], world, visible)
    return knowledge


def point_text(points: set[tuple[int, int]]) -> str:
    rows: list[str] = []
    for point in sorted(points):
        rows.append(str(point[0]) + "," + str(point[1]))
    return " ".join(rows)
