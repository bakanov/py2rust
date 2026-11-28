"""Owned game records addressed by stable IDs and map coordinates."""

from dataclasses import dataclass, field

Point = tuple[int, int]


@dataclass
class Unit:
    identifier: int
    name: str
    owner: int
    x: int
    y: int
    movement: int

    @property
    def point(self) -> Point:
        return self.x, self.y


@dataclass
class City:
    identifier: int
    name: str
    owner: int
    x: int
    y: int
    population: int = 1


@dataclass
class Game:
    units: list[Unit] = field(default_factory=list)
    cities: list[City] = field(default_factory=list)
    ownership: dict[Point, int] = field(default_factory=dict)
    next_identifier: int = 10


def unit_with_id(game: Game, identifier: int) -> Unit | None:
    for unit in game.units:
        if unit.identifier == identifier:
            return unit
    return None


def city_with_id(game: Game, identifier: int) -> City | None:
    for city in game.cities:
        if city.identifier == identifier:
            return city
    return None
