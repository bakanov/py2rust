"""Residents, cities, and research use explicit optional values."""

from dataclasses import dataclass, field

TILE_YIELDS: dict[tuple[int, int], tuple[int, int, int]] = {
    (0, 0): (2, 1, 1),
    (1, 0): (3, 1, 2),
    (2, 0): (1, 2, 0),
    (3, 0): (1, 3, 0),
}


@dataclass
class Resident:
    tile_worked: tuple[int, int] | None = None


@dataclass
class City:
    name: str
    size: int
    food_stored: int
    shields_stored: int
    residents: list[Resident]
    producing: str | None


@dataclass
class Player:
    science: int
    beakers: int
    researching: str | None
    research_cost: int
    known_technologies: set[str] = field(default_factory=set)


@dataclass
class CityFood:
    total: int
    consumed: int
    surplus: int


@dataclass
class CityReport:
    food: int
    shields: int
    trade: int
    grew: bool
    completed: str | None
