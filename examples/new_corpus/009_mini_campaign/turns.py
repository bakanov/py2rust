"""Advance movement, cities, and research as separate observable phases."""

from actions import move_unit, reveal
from model import Game, Player, Unit
from world import YIELDS, terrain


def required_text(value: str | None) -> str:
    assert value is not None
    return value


def advance_cities(game: Game) -> tuple[Game, list[str]]:
    messages: list[str] = []
    for index in range(len(game.cities)):
        city = game.cities[index]
        food: int = 0
        shields: int = 0
        for offset in city.residents:
            if offset is not None:
                point: tuple[int, int] = city.x + offset[0], city.y + offset[1]
                values: tuple[int, int, int] = YIELDS[terrain(point)]
                food += values[0]
                shields += values[1]
        surplus: int = food - city.size * 2
        city.food_stored = max(0, city.food_stored + surplus)
        growth_cost: int = city.size * 2 + 4
        if city.food_stored >= growth_cost:
            city.food_stored -= growth_cost
            city.size += 1
            city.residents.append((1, 0))
            messages.append(city.name + " grew to " + str(city.size))
        city.shields_stored += shields
        producing: str | None = city.producing
        if producing is not None and city.shields_stored >= 5:
            messages.append(city.name + " completed " + required_text(producing))
            city.producing = None
            city.shields_stored -= 5
        game.cities[index] = city
    return game, messages


def advance_research(player: Player) -> tuple[Player, str | None]:
    player.beakers += player.science
    if player.researching is None or player.beakers < 6:
        return player, None
    discovered: str = player.researching
    player.researching = None
    player.beakers -= 6
    if discovered in player.known_technologies:
        return player, None
    player.known_technologies.add(discovered)
    return player, discovered


def advance_turn(game: Game) -> tuple[Game, list[str]]:
    messages: list[str] = []
    for index in range(len(game.units)):
        unit: Unit = game.units[index]
        unit.movement = 1
        game.units[index] = unit
    moved: Unit | None
    game, moved = move_unit(game, 2, (3, 1))
    if moved is not None:
        messages.append("Warrior reached " + str(moved.x) + "," + str(moved.y))
    game, moved = move_unit(game, 3, (3, 3))
    if moved is not None:
        messages.append("Rival scout reached " + str(moved.x) + "," + str(moved.y))
    city_messages: list[str]
    game, city_messages = advance_cities(game)
    messages.extend(city_messages)
    for owner in sorted(game.players):
        player: Player = game.players[owner]
        discovered: str | None
        player, discovered = advance_research(player)
        game.players[owner] = player
        if discovered is not None:
            messages.append(player.name + " discovered " + required_text(discovered))
    for city in game.cities:
        game = reveal(game, city.owner, (city.x, city.y))
    game.turn += 1
    return game, messages
