"""State transitions mutate real collections and never rely on record identity."""

from model import City, Game, Point, Unit, unit_with_id


def remove_unit(game: Game, identifier: int) -> Unit | None:
    removed: Unit | None = None
    retained: list[Unit] = []
    for unit in game.units:
        if unit.identifier == identifier and removed is None:
            removed = unit
        else:
            retained.append(unit)
    game.units = retained
    return removed


def move_unit(game: Game, identifier: int, x: int, y: int) -> Unit:
    for index in range(len(game.units)):
        unit: Unit = game.units[index]
        if unit.identifier == identifier:
            assert unit.movement > 0, "unit has no movement remaining"
            unit.x = x
            unit.y = y
            unit.movement -= 1
            game.units[index] = unit
            return unit
    raise ValueError("missing unit " + str(identifier))


def found_city(game: Game, settler_id: int, name: str) -> City:
    settler: Unit | None = unit_with_id(game, settler_id)
    assert settler is not None and settler.name == "Settler", "a living settler is required"
    point: Point = settler.point
    city: City = City(game.next_identifier, name, settler.owner, point[0], point[1])
    game.next_identifier += 1
    removed: Unit | None = remove_unit(game, settler_id)
    assert removed is not None
    game.cities.append(city)
    game.ownership[point] = city.identifier
    return city


def transfer_city(game: Game, city_id: int, new_owner: int) -> None:
    for index in range(len(game.cities)):
        city: City = game.cities[index]
        if city.identifier == city_id:
            city.owner = new_owner
            game.cities[index] = city
    return


def describe(game: Game) -> list[str]:
    rows: list[str] = []
    for unit in game.units:
        rows.append(
            "Unit " + str(unit.identifier) + " " + unit.name + " @ " + str(unit.x) + "," + str(unit.y)
        )
    for city in game.cities:
        rows.append(
            "City " + str(city.identifier) + " " + city.name + " owner=" + str(city.owner)
        )
    return rows
