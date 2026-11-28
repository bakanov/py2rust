"""Build a reproducible permutation and sample a tiny deterministic height map."""

from noise import TerrainNoise, advance, checksum


def main() -> None:
    noise: TerrainNoise = TerrainNoise(123456789)
    print("Permutation prefix: " + ", ".join(str(value) for value in noise.permutation[:8]))
    print("Permutation checksum: " + str(checksum(noise.permutation)))
    samples: list[int] = []
    for y in range(-2, 3):
        row: list[str] = []
        for x in range(-2, 3):
            value: int = noise.sample(x, y)
            samples.append(value)
            row.append(str(value))
        print("Height row: " + ", ".join(row))
    print("Sample checksum: " + str(checksum(samples)))
    replay: TerrainNoise = TerrainNoise(123456789)
    print("Replay matches: " + str(noise.permutation == replay.permutation))
    print("Wrapping sequence: " + ", ".join([str(advance(9223372036854775807)), str(advance(-9223372036854775808))]))
    return


if __name__ == "__main__":
    main()
