"""Reduced deterministic subtractive RNG matching the OpenCiv3 map stream."""

from __future__ import annotations

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

    def sample(self) -> tuple[MapRandom, int]:
        self.index = self.index + 1 if self.index < 55 else 1
        self.other = self.other + 1 if self.other < 55 else 1
        value: int = seed32(self.values[self.index] - self.values[self.other])
        if value == MAXIMUM:
            value -= 1
        if value < 0:
            value += MAXIMUM
        self.values[self.index] = value
        return self, value

    def next_double(self) -> tuple[MapRandom, float]:
        value: int
        self, value = self.sample()
        return self, value * (1.0 / MAXIMUM)

    def next_range(self, minimum: int, maximum: int) -> tuple[MapRandom, int]:
        if not -2147483648 <= minimum <= maximum <= MAXIMUM:
            raise ValueError("invalid random range")
        span: int = maximum - minimum
        if span <= MAXIMUM:
            sample_value: float
            self, sample_value = self.next_double()
            return self, int(sample_value * span) + minimum
        value: int
        self, value = self.sample()
        parity: int
        self, parity = self.sample()
        if parity % 2 == 0:
            value = -value
        sample: float = (float(value) + (MAXIMUM - 1)) / (2 * MAXIMUM - 1)
        return self, int(sample * span) + minimum

    def shuffle(self, values: list[str]) -> tuple[MapRandom, list[str]]:
        for position in range(len(values) - 1):
            other: int
            updated: MapRandom
            updated, other = self.next_range(position, len(values))
            self = updated
            values[position], values[other] = values[other], values[position]
        return self, values


def unique_civilizations(rng: MapRandom, names: list[str], count: int) -> tuple[MapRandom, list[str], int]:
    selected: list[str] = []
    draws: int = 0
    while len(selected) < count:
        assert draws < 100, "rejection sampling exceeded its budget"
        index: int
        updated: MapRandom
        updated, index = rng.next_range(0, len(names))
        rng = updated
        candidate: str = names[index]
        draws += 1
        if candidate not in selected:
            selected.append(candidate)
    return rng, selected, draws
