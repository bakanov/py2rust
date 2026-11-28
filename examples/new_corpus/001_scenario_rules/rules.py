"""Small rule catalog with derived indexes and typed JSON decoding."""

from collections import Counter
from dataclasses import dataclass, field

from py2rust.stdlib import Json

TERRAIN_RULES: dict[str, tuple[int, int, int]] = {
    "grassland": (2, 1, 1),
    "plains": (1, 2, 1),
    "forest": (1, 2, 0),
    "hills": (1, 2, 0),
}
CIVILIZATIONS: tuple[str, ...] = ("Rome", "Egypt", "Greece", "Babylon")
TECHNOLOGY_ROWS: list[tuple[str, int, str]] = [
    ("Alphabet", 8, ""),
    ("Pottery", 6, "Alphabet"),
    ("Bronze Working", 10, "Alphabet"),
]


@dataclass
class Technology:
    name: str
    cost: int
    prerequisite: str


@dataclass
class RuleCatalog:
    technologies: list[Technology]
    technology_ids: dict[str, int] = field(init=False, default_factory=dict)
    eras: dict[int, str] = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        for index in range(len(self.technologies)):
            technology: Technology = self.technologies[index]
            self.technology_ids[technology.name] = index
            self.eras[index] = "Ancient"

    def find_technology(self, name: str) -> int | None:
        if name not in self.technology_ids:
            return None
        return self.technology_ids[name]

    def research_cost(self, name: str, discount: int) -> int:
        identifier: int | None = self.find_technology(name)
        if identifier is None:
            raise ValueError("unknown technology")
        cost: int = self.technologies[identifier].cost - discount
        assert cost > 0, "discount cannot eliminate research cost"
        return cost


def catalog() -> RuleCatalog:
    technologies: list[Technology] = []
    for row in TECHNOLOGY_ROWS:
        technologies.append(Technology(row[0], row[1], row[2]))
    return RuleCatalog(technologies)


def integer(row: dict[str, Json], key: str, default: int = 0) -> int:
    value: Json = row.get(key, default)
    if value is None:
        return default
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(key + " must be an integer")
    assert -100 <= value <= 100, key + " is outside the supported range"
    return value


def resource_counts(resources: list[str]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for resource in resources:
        counts[resource] += 1
    return counts


def available_technologies(rules: RuleCatalog, known: set[str]) -> list[str]:
    result: list[str] = []
    for technology in rules.technologies:
        if technology.name not in known and (not len(technology.prerequisite) == 0 or technology.prerequisite in known):
            result.append(technology.name)
    return result


def terrain_total(names: tuple[str, ...]) -> tuple[int, int, int]:
    food: int = 0
    shields: int = 0
    trade: int = 0
    for name in names:
        values: tuple[int, int, int] = TERRAIN_RULES[name]
        food += values[0]
        shields += values[1]
        trade += values[2]
    return food, shields, trade
