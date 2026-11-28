"""Campaign commands propagate both returned records and containing collections."""

from model import City, Game, Knowledge, Unit
from world import sight, step_toward


def reveal(game: Game, owner: int, center: tuple[int, int]) -> Game:
    visible: set[tuple[int, int]] = sight(center)
    original: Knowledge = game.visibility[owner]
    refreshed: Knowledge = Knowledge(original.known.copy(), visible)
    refreshed.known.update(visible)
    game.visibility[owner] = refreshed
    return game


def move_unit(game: Game, identifier: int, destination: tuple[int, int]) -> tuple[Game, Unit | None]:
    for index in range(len(game.units)):
        unit: Unit = game.units[index]
        if unit.identifier == identifier:
            if unit.movement <= 0:
                return game, None
            point: tuple[int, int] = step_toward((unit.x, unit.y), destination)
            unit.x, unit.y = point
            unit.movement -= 1
            game.units[index] = unit
            game = reveal(game, unit.owner, point)
            return game, unit
    return game, None


def remove_unit(game: Game, identifier: int) -> tuple[Game, Unit | None]:
    removed: Unit | None = None
    retained: list[Unit] = []
    for unit in game.units:
        if unit.identifier == identifier:
            removed = unit
        else:
            retained.append(unit)
    game.units = retained
    return game, removed


def found_city(game: Game, settler_id: int, name: str) -> tuple[Game, City]:
    settler: Unit | None = next((unit for unit in game.units if unit.identifier == settler_id), None)
    assert settler is not None and settler.name == "Settler"
    city: City = City(game.next_city_id, name, settler.owner, settler.x, settler.y, "Warrior")
    game.next_city_id += 1
    removed: Unit | None
    game, removed = remove_unit(game, settler_id)
    assert removed is not None
    game.cities.append(city)
    game = reveal(game, city.owner, (city.x, city.y))
    return game, city
