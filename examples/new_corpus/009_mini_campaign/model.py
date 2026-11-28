"""Shared records for a complete but deliberately tiny campaign."""

from dataclasses import dataclass, field


@dataclass
class Unit:
    identifier: int
    name: str
    owner: int
    x: int
    y: int
    movement: int = 1
    automated: bool = True


@dataclass
class City:
    identifier: int
    name: str
    owner: int
    x: int
    y: int
    producing: str | None
    size: int = 1
    food_stored: int = 4
    shields_stored: int = 0
    residents: list[tuple[int, int] | None] = field(default_factory=list)

    def __post_init__(self) -> None:
        if len(self.residents) == 0:
            self.residents.append((0, 0))


@dataclass
class Player:
    name: str
    researching: str | None
    science: int = 3
    beakers: int = 0
    known_technologies: set[str] = field(default_factory=set)


@dataclass
class Knowledge:
    known: set[tuple[int, int]] = field(default_factory=set)
    visible: set[tuple[int, int]] = field(default_factory=set)


@dataclass
class Game:
    turn: int
    units: list[Unit]
    cities: list[City]
    players: dict[int, Player]
    visibility: dict[int, Knowledge]
    next_city_id: int = 20
