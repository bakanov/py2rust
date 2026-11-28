"""Cities and road tiles used by the reduced trade-network builder."""

from collections import Counter
from dataclasses import dataclass, field

Point = tuple[int, int]


@dataclass
class City:
    identifier: int
    name: str
    x: int
    y: int
    resources: list[str] = field(default_factory=list)
    airport: bool = False
    capital: bool = False

    @property
    def point(self) -> Point:
        return self.x, self.y


@dataclass
class NetworkSegment:
    network_id: int
    cities: list[int]
    tiles: set[Point]
    resources: Counter[str]
    has_airport: bool


def city_at(cities: list[City], point: Point) -> City | None:
    for city in cities:
        if city.point == point:
            return city
    return None


def city_with_id(cities: list[City], identifier: int) -> City | None:
    for city in cities:
        if city.identifier == identifier:
            return city
    return None
