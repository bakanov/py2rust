"""Deterministic AI ranking with nested callbacks and finite score sentinels."""

from dataclasses import dataclass

Point = tuple[int, int]


@dataclass
class Unit:
    identifier: int
    x: int
    y: int
    automated: bool


@dataclass
class Plan:
    unit_id: int
    destination: Point | None
    score: int


def distance(left: Point, right: Point) -> int:
    return abs(left[0] - right[0]) + abs(left[1] - right[1])


def explore_plans(units: list[Unit], targets: list[Point]) -> list[Plan]:
    plans: list[Plan] = []
    for unit in units:
        best_target: Point | None = None
        best_score: int = -1000000
        origin: Point = unit.x, unit.y
        for target in targets:
            score: int = 100 - distance(origin, target) * 10 - (target[0] + target[1])
            if score > best_score or (score == best_score and best_target is not None and target < best_target):
                best_score = score
                best_target = target
        if unit.automated and best_target is not None:
            plans.append(Plan(unit.identifier, best_target, best_score))
    return plans


def ordered_units(units: list[Unit], preferred: Point) -> list[Unit]:
    def order(unit: Unit) -> tuple[int, int]:
        return distance((unit.x, unit.y), preferred), unit.identifier

    return sorted(units, key=order)
