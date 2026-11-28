"""Integer-only terrain noise seeding with an explicit signed-64-bit contract."""

from dataclasses import dataclass, field

from py2rust.stdlib import wrapping_add, wrapping_mul

MULTIPLIER: int = 6364136223846793005
INCREMENT: int = 1442695040888963407
GRADIENTS: tuple[tuple[int, int], ...] = ((1, 0), (0, 1), (-1, 0), (0, -1), (1, 1), (-1, 1))


def advance(seed: int) -> int:
    return wrapping_add(wrapping_mul(seed, MULTIPLIER), INCREMENT)


@dataclass
class TerrainNoise:
    seed: int
    permutation: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        seed: int = self.seed
        source: list[int] = list(range(256))
        self.permutation = [0] * 256
        for unused in range(3):
            seed = advance(seed)
        for index in range(255, -1, -1):
            seed = advance(seed)
            selected: int = wrapping_add(seed, 31) % (index + 1)
            self.permutation[index] = source[selected]
            source[selected] = source[index]

    def gradient(self, x: int, y: int) -> tuple[int, int]:
        first: int = self.permutation[x & 255]
        second: int = self.permutation[(first + y) & 255]
        return GRADIENTS[second % len(GRADIENTS)]

    def sample(self, x: int, y: int) -> int:
        gradient: tuple[int, int] = self.gradient(x, y)
        attenuation: int = max(0, 16 - x * x - y * y)
        return attenuation * (gradient[0] * x + gradient[1] * y)


def checksum(values: list[int]) -> int:
    result: int = 0
    for value in values:
        result = wrapping_add(wrapping_mul(result, MULTIPLIER), value)
    return result
