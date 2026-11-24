"""Unicode character positions for reverse substring searches."""

import random
from pathlib import Path

import pytest

from .test_services import run


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_reverse_find_returns_character_offsets(tmp_path: Path, engine: str) -> None:
    cases = [("", ""), ("é😀é", "é"), ("é😀é", ""), ("ababa", "aba"), ("a\0b\0", "\0"), ("hello", "absent")]
    rng = random.Random(39039)
    alphabet = ["a", "b", "é", "世", "😀", "\u0301", "\n"]
    for _ in range(500):
        value = "".join(rng.choices(alphabet, k=rng.randrange(30)))
        needle = "".join(rng.choices(alphabet, k=rng.randrange(5)))
        cases.append((value, needle))
    source = """
def observed(label: str, value: str) -> str:
    print(label)
    return value
def check() -> None:
    assert observed("receiver", "é.x.x").rfind(observed("needle", ".")) == 3
    cases: list[tuple[str, str]] = CASES
    for pair in cases:
        print(pair[0].rfind(pair[1]))
    return
if __name__ == "__main__":
    check()
""".replace("CASES", repr(cases))
    result = run(tmp_path, source, engine)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["receiver", "needle", *[str(value.rfind(needle)) for value, needle in cases]]
    return  # noqa: PLR1711 - explicit return required by repository guidelines
