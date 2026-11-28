"""Reduced deterministic subtractive RNG matching the OpenCiv3 map stream."""

from dataclasses import dataclass, field

MAXIMUM: int = 2147483647


def seed32(value: int) -> int:
    return (value + 2**31) % 2**32 - 2**31


@dataclass
class MapRandom:
    seed: int
    values: list[int] = field(default_factory=list)
    index: int = 0
    other: int = 21

    def __post_init__(self) -> None:
        seed: int = seed32(self.seed)
        previous: int = 161803398 - (MAXIMUM if seed == -2147483648 else abs(seed))
        self.values = [0] * 56
        self.values[55] = previous
        current: int = 1
        for position in range(1, 55):
            slot: int = 21 * position % 55
            self.values[slot] = current
            current = seed32(previous - current)
            if current < 0:
                current += MAXIMUM
            previous = self.values[slot]
        for unused in range(4):
            for position in range(1, 56):
                self.values[position] = seed32(self.values[position] - self.values[1 + (position + 30) % 55])
                if self.values[position] < 0:
                    self.values[position] += MAXIMUM
        self.index = 0
        self.other = 21
        return

    def sample(self) -> int:
        self.index = self.index + 1 if self.index < 55 else 1
        self.other = self.other + 1 if self.other < 55 else 1
        value: int = seed32(self.values[self.index] - self.values[self.other])
        if value == MAXIMUM:
            value -= 1
        if value < 0:
            value += MAXIMUM
        self.values[self.index] = value
        return value

    def next_double(self) -> float:
        return self.sample() * (1.0 / MAXIMUM)

    def next_range(self, minimum: int, maximum: int) -> int:
        if not -2147483648 <= minimum <= maximum <= MAXIMUM:
            raise ValueError("invalid random range")
        span: int = maximum - minimum
        if span <= MAXIMUM:
            return int(self.next_double() * span) + minimum
        value: int = self.sample()
        if self.sample() % 2 == 0:
            value = -value
        sample: float = (float(value) + (MAXIMUM - 1)) / (2 * MAXIMUM - 1)
        return int(sample * span) + minimum

    def shuffle(self, values: list[str]) -> None:
        for position in range(len(values) - 1):
            other: int = self.next_range(position, len(values))
            values[position], values[other] = values[other], values[position]
        return


def unique_civilizations(rng: MapRandom, names: list[str], count: int) -> tuple[list[str], int]:
    selected: list[str] = []
    draws: int = 0
    while len(selected) < count:
        assert draws < 100, "rejection sampling exceeded its budget"
        candidate: str = names[rng.next_range(0, len(names))]
        draws += 1
        if candidate not in selected:
            selected.append(candidate)
    return selected, draws
