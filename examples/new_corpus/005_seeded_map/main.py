"""Verify that every random draw advances the receiver, including rejected draws."""

from map_random import MapRandom, unique_civilizations


def main() -> None:
    rng: MapRandom = MapRandom(7)
    names: list[str] = ["Rome", "Egypt", "Greece", "Babylon", "Persia", "China"]
    selected: list[str]
    draws: int
    rng, selected, draws = unique_civilizations(rng, names, 5)
    print("Selected: " + ", ".join(selected))
    print("Draws including rejections: " + str(draws))
    next_value: int
    rng, next_value = rng.next_range(-10, 11)
    print("Next range: " + str(next_value))
    print("Receiver index/other: " + str(rng.index) + "/" + str(rng.other))
    terrain: list[str] = ["grassland", "plains", "forest", "hills", "desert", "tundra"]
    rng, terrain = rng.shuffle(terrain)
    print("Terrain shuffle: " + ", ".join(terrain))
    independent: MapRandom = MapRandom(7)
    repeated: list[str]
    repeated_draws: int
    independent, repeated, repeated_draws = unique_civilizations(independent, names, 5)
    print("Independent replay matches: " + ("True" if selected == repeated and draws == repeated_draws else "False"))
    print("Streams remain independent: " + ("True" if rng.index != independent.index else "False"))
    return


if __name__ == "__main__":
    main()
