"""Found, move, transfer, and disband objects without Python identity comparisons."""

from actions import describe, found_city, move_unit, remove_unit, transfer_city
from model import City, Game, Unit, city_with_id


def main() -> None:
    game: Game = Game(
        units=[
            Unit(1, "Settler", 0, 4, 4, 1),
            Unit(2, "Warrior", 0, 3, 4, 1),
            Unit(3, "Scout", 1, 7, 7, 2),
        ]
    )
    rome: City = found_city(game, 1, "Rome")
    print("Founded " + rome.name + " with ID " + str(rome.identifier))
    warrior: Unit = move_unit(game, 2, 4, 5)
    print("Moved warrior " + str(warrior.identifier) + " to " + str(warrior.x) + "," + str(warrior.y))
    transfer_city(game, rome.identifier, 2)
    selected: City | None = city_with_id(game, rome.identifier)
    assert selected is not None
    print("Rome's new owner: " + str(selected.owner))
    duplicate: Unit = Unit(4, "Warrior", 0, 4, 5, 0)
    game.units.append(duplicate)
    print("Same record shape, distinct IDs: " + str(warrior.identifier != duplicate.identifier))
    removed: Unit | None = remove_unit(game, duplicate.identifier)
    assert removed is not None
    print("Removed only ID " + str(removed.identifier))
    for row in describe(game):
        print(row)
    print("Owned tiles: " + str(len(game.ownership)) + "; units: " + str(len(game.units)))
    return


if __name__ == "__main__":
    main()
