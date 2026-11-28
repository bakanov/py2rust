"""Run four economic rounds, including one growth and one discovery event."""

from economy import Economy, advance_research
from model import City, CityReport, Player, Resident


def required_text(value: str | None) -> str:
    assert value is not None
    return value


def main() -> None:
    economy: Economy = Economy()
    rome: City = City("Rome", 2, 7, 0, [Resident((0, 0)), Resident((1, 0))], "Granary")
    player: Player = Player(4, 0, "Pottery", 10)
    for turn in range(1, 5):
        report: CityReport
        updated_economy: Economy
        updated_rome: City
        updated_economy, updated_rome, report = economy.advance_city(rome)
        economy = updated_economy
        rome = updated_rome
        discovered: str | None
        updated_player: Player
        updated_player, discovered = advance_research(player)
        player = updated_player
        print(
            "Turn "
            + str(turn)
            + ": pop="
            + str(rome.size)
            + " food="
            + str(report.food)
            + " shields="
            + str(report.shields)
            + " stored="
            + str(rome.shields_stored)
        )
        print("Worked tiles: " + str(sum(resident.tile_worked is not None for resident in rome.residents)))
        if report.grew:
            print("Rome grew; food stored=" + str(rome.food_stored))
        completed: str | None = report.completed
        if completed is not None:
            print("Completed " + required_text(completed))
        if discovered is not None:
            print("Discovered " + required_text(discovered))
    print("Known technologies: " + ", ".join(sorted(player.known_technologies)))
    print("Research target cleared: " + ("True" if player.researching is None else "False"))
    print("Hydrology builds: " + str(economy.hydrology_calls))
    empty: City = City("Empty", 0, 0, 0, [], None)
    economy, food = economy.city_food(empty)
    print(
        "Empty-city fast path: "
        + str(food.total)
        + "/"
        + str(food.surplus)
        + "; hydrology="
        + str(economy.hydrology_calls)
    )
    return


if __name__ == "__main__":
    main()
