"""Portable Park-Miller draws with rejection sampling; no platform RNG dependency."""

from dataclasses import dataclass


@dataclass
class Generator:
    state: int
    draws: int


def draw(generator: Generator, low: int, high: int) -> tuple[Generator, int]:
    width: int = high - low + 1
    limit: int = (2147483646 // width) * width
    while True:
        assert generator.draws < 65536, "generator draw limit reached"
        generator.state = (16807 * generator.state) % 2147483647
        generator.draws = generator.draws + 1
        value: int = generator.state - 1
        if value < limit:
            return (generator, low + value % width)
    return (generator, low)
