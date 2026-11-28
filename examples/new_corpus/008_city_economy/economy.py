"""Allocate citizens and advance production with an empty-city fast path."""

from __future__ import annotations

from dataclasses import dataclass

from model import TILE_YIELDS, City, CityFood, CityReport, Player, Resident


@dataclass
class Economy:
    hydrology_calls: int = 0

    def hydrology(self) -> tuple[Economy, dict[tuple[int, int], tuple[int, int, int]]]:
        self.hydrology_calls += 1
        return self, TILE_YIELDS

    def city_food(self, city: City) -> tuple[Economy, CityFood]:
        if len(city.residents) == 0:
            return self, CityFood(0, 0, 0)
        yields: dict[tuple[int, int], tuple[int, int, int]]
        self, yields = self.hydrology()
        total: int = 0
        for resident in city.residents:
            point: tuple[int, int] | None = resident.tile_worked
            if point is not None:
                assert point in yields, "resident works an unknown tile"
                total += yields[point][0]
        consumed: int = city.size * 2
        return self, CityFood(total, consumed, total - consumed)

    def allocate_citizens(self, city: City) -> City:
        used: set[tuple[int, int]] = set()
        for resident in city.residents:
            if resident.tile_worked is not None:
                used.add(resident.tile_worked)
        finished: list[Resident] = []
        for resident in city.residents:
            selected: tuple[int, int] | None = resident.tile_worked
            if selected is None:
                best_score: int = -1000000
                for point in sorted(TILE_YIELDS):
                    if point in used:
                        continue
                    values: tuple[int, int, int] = TILE_YIELDS[point]
                    score: int = values[0] * 100 + values[1] * 10 + values[2]
                    if score > best_score:
                        best_score = score
                        selected = point
                if selected is not None:
                    used.add(selected)
            finished.append(Resident(selected))
        city.residents = finished
        return city

    def advance_city(self, city: City) -> tuple[Economy, City, CityReport]:
        city = self.allocate_citizens(city)
        food: CityFood
        self, food = self.city_food(city)
        shields: int = 0
        trade: int = 0
        for resident in city.residents:
            if resident.tile_worked is not None:
                values: tuple[int, int, int] = TILE_YIELDS[resident.tile_worked]
                shields += values[1]
                trade += values[2]
        city.food_stored = max(0, city.food_stored + food.surplus)
        grew: bool = False
        growth_cost: int = city.size * 2 + 4
        if food.surplus >= 0 and city.food_stored >= growth_cost:
            city.food_stored -= growth_cost
            city.size += 1
            city.residents.append(Resident())
            grew = True
            city = self.allocate_citizens(city)
        city.shields_stored += shields
        completed: str | None = None
        if city.producing is not None and city.shields_stored >= 10:
            completed = city.producing
            city.producing = None
            city.shields_stored -= 10
        return self, city, CityReport(food.surplus, shields, trade, grew, completed)


def advance_research(player: Player) -> tuple[Player, str | None]:
    player.beakers += player.science
    if player.researching is None or player.beakers < player.research_cost:
        return player, None
    discovered: str = player.researching
    player.beakers -= player.research_cost
    player.researching = None
    if discovered not in player.known_technologies:
        player.known_technologies.add(discovered)
        return player, discovered
    return player, None
