"""Deterministic AI ranking with nested callbacks and finite score sentinels."""

from dataclasses import dataclass


@dataclass
class Unit:
    identifier: int
    x: int
    y: int
    automated: bool


@dataclass
class Plan:
    unit_id: int
    destination: tuple[int, int] | None
    score: int


def distance(left: tuple[int, int], right: tuple[int, int]) -> int:
    return abs(left[0] - right[0]) + abs(left[1] - right[1])


def explore_plans(units: list[Unit], targets: list[tuple[int, int]]) -> list[Plan]:
    plans: list[Plan] = []
    for unit in units:
        best_target: tuple[int, int] | None = None
        best_score: int = -1000000
        origin: tuple[int, int] = unit.x, unit.y
        for target in targets:
            score: int = 100 - distance(origin, target) * 10 - (target[0] + target[1])
            if score > best_score or (score == best_score and best_target is not None and target < best_target):
                best_score = score
                best_target = target
        if unit.automated and best_target is not None:
            plans.append(Plan(unit.identifier, best_target, best_score))
    return plans


def ordered_units(units: list[Unit], preferred: tuple[int, int]) -> list[Unit]:
    def order(unit: Unit) -> tuple[int, int]:
        return distance((unit.x, unit.y), preferred), unit.identifier

    return sorted(units, key=order)
