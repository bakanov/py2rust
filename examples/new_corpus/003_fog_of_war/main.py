"""Reveal two scout positions while retaining the first position's history."""

from knowledge import TileKnowledge, observe, point_text, update_visibility
from world import Point, Tile, World, tiny_world


def sight(world: World, x: int, y: int) -> set[Point]:
    center: Tile | None = world.tile_at(x, y)
    assert center is not None
    result: set[Point] = {center.point}
    for neighbor in world.neighbors(center):
        result.add(neighbor.point)
    return result


def main() -> None:
    world: World = tiny_world()
    knowledge: dict[int, TileKnowledge] = {0: TileKnowledge(), 1: TileKnowledge()}
    first: set[Point] = sight(world, 1, 1)
    knowledge = update_visibility(knowledge, world, 0, first)
    print("First known/visible/frontier: " + str(len(knowledge[0].known)) + "/" + str(len(first)) + "/" + str(len(knowledge[0].frontier)))
    second: set[Point] = sight(world, 2, 2)
    knowledge = update_visibility(knowledge, world, 0, second)
    print("Second known/visible/frontier: " + str(len(knowledge[0].known)) + "/" + str(len(second)) + "/" + str(len(knowledge[0].frontier)))
    print("Explored remains known: " + str((1, 1) in knowledge[0].known))
    print("Old tile no longer visible: " + str((0, 1) not in knowledge[0].visible))
    print("Visible now: " + point_text(knowledge[0].visible))
    print("Known ruins: " + point_text(knowledge[0].known_ruins))
    print("Ruin terrain: " + knowledge[0].known_terrain[(2, 1)])
    independent: TileKnowledge = observe(knowledge[1], world, sight(world, 4, 4))
    knowledge[1] = independent
    print("Rival knowledge is separate: " + str(len(knowledge[0].known)) + "/" + str(len(knowledge[1].known)))
    return


if __name__ == "__main__":
    main()
