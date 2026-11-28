"""Allocate citizens and advance production with an empty-city fast path."""

from dataclasses import dataclass

from model import TILE_YIELDS, City, CityFood, CityReport, Player, Point, Resident


@dataclass
class Economy:
    hydrology_calls: int = 0

    def hydrology(self) -> dict[Point, tuple[int, int, int]]:
        self.hydrology_calls += 1
        return TILE_YIELDS

    def city_food(self, city: City) -> CityFood:
        if not city.residents:
            return CityFood(0, 0, 0)
        yields: dict[Point, tuple[int, int, int]] = self.hydrology()
        total: int = 0
        for resident in city.residents:
            point: Point | None = resident.tile_worked
            if point is not None:
                assert point in yields, "resident works an unknown tile"
                total += yields[point][0]
        consumed: int = city.size * 2
        return CityFood(total, consumed, total - consumed)

    def allocate_citizens(self, city: City) -> None:
        used: set[Point] = set()
        for resident in city.residents:
            if resident.tile_worked is not None:
                used.add(resident.tile_worked)
        finished: list[Resident] = []
        for resident in city.residents:
            selected: Point | None = resident.tile_worked
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
        return

    def advance_city(self, city: City) -> CityReport:
        self.allocate_citizens(city)
        food: CityFood = self.city_food(city)
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
            self.allocate_citizens(city)
        city.shields_stored += shields
        completed: str | None = None
        if city.producing is not None and city.shields_stored >= 10:
            completed = city.producing
            city.producing = None
            city.shields_stored -= 10
        return CityReport(food.surplus, shields, trade, grew, completed)


def advance_research(player: Player) -> str | None:
    player.beakers += player.science
    if player.researching is None or player.beakers < player.research_cost:
        return None
    discovered: str = player.researching
    player.beakers -= player.research_cost
    player.researching = None
    if discovered not in player.known_technologies:
        player.known_technologies.add(discovered)
        return discovered
    return None
