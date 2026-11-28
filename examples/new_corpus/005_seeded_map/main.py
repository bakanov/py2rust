"""Verify that every random draw advances the receiver, including rejected draws."""

from random import MapRandom, unique_civilizations


def main() -> None:
    rng: MapRandom = MapRandom(7)
    names: list[str] = ["Rome", "Egypt", "Greece", "Babylon", "Persia", "China"]
    selected: tuple[list[str], int] = unique_civilizations(rng, names, 4)
    print("Selected: " + ", ".join(selected[0]))
    print("Draws including rejections: " + str(selected[1]))
    print("Next range: " + str(rng.next_range(-10, 11)))
    print("Receiver index/other: " + str(rng.index) + "/" + str(rng.other))
    terrain: list[str] = ["grassland", "plains", "forest", "hills", "desert", "tundra"]
    rng.shuffle(terrain)
    print("Terrain shuffle: " + ", ".join(terrain))
    independent: MapRandom = MapRandom(7)
    repeated: tuple[list[str], int] = unique_civilizations(independent, names, 4)
    print("Independent replay matches: " + str(selected == repeated))
    print("Streams remain independent: " + str(rng.index != independent.index))
    return


if __name__ == "__main__":
    main()
