"""A three-turn alternate entry point resembling the reduced OpenCiv3 console."""

from actions import found_city
from model import City, Game, Knowledge, Player, Unit
from turns import advance_turn


def main() -> None:
    game: Game = Game(
        0,
        [Unit(1, "Settler", 0, 1, 1), Unit(2, "Warrior", 0, 0, 1), Unit(3, "Scout", 1, 4, 3)],
        [],
        {0: Player("Rome", "Pottery"), 1: Player("Egypt", None, science=2)},
        {0: Knowledge(), 1: Knowledge()},
    )
    print("Mini campaign: " + str(len(game.players)) + " civilizations, " + str(len(game.units)) + " units")
    rome: City
    game, rome = found_city(game, 1, "Rome")
    print("Founded " + rome.name + "; units remaining=" + str(len(game.units)))
    for unused in range(3):
        messages: list[str]
        updated: Game
        updated, messages = advance_turn(game)
        game = updated
        print("Turn " + str(game.turn) + " begins")
        for message in messages:
            print(message)
        rome = game.cities[0]
        print("Rome pop/food/shields: " + str(rome.size) + "/" + str(rome.food_stored) + "/" + str(rome.shields_stored))
        print("Known/visible tiles: " + str(len(game.visibility[0].known)) + "/" + str(len(game.visibility[0].visible)))
    print("Technologies: " + ", ".join(sorted(game.players[0].known_technologies)))
    print("Final units/cities: " + str(len(game.units)) + "/" + str(len(game.cities)))
    return


if __name__ == "__main__":
    main()
