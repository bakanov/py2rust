"""Counter specialization preserves checked failure behavior and fallback effects."""

from pathlib import Path

import pytest

from py2rust.compiler import pipeline, service
from .test_services import parity, program
import subprocess

SOURCE = """def step() -> int:
    print("step")
    return 2

def check() -> None:
    counts: dict[str, int] = {}
    for key in "a|a|世界|b|世界".split("|"):
        counts[key] = counts.get(key, 0) + 1
    key: str = "new"
    counts[key] = counts.get(key, 5) + -2
    assert counts["new"] == 3
    counts[key] = counts.get(key, 5) + -2
    assert counts["new"] == 1
    assert counts["a"] == 2 and counts["世界"] == 2 and counts["b"] == 1
    counts[key] = counts.get(key, 0) + step()
    assert counts[key] == 3
    print("counters passed")
    return

if __name__ == "__main__":
    check()
"""


@pytest.mark.parametrize("frontend", ["typed", "legacy"])
def test_counter_parity(tmp_path: Path, monkeypatch, frontend: str) -> None:
    if frontend == "typed":
        monkeypatch.setattr(
            service.ServiceCompiler,
            "compile",
            lambda self, source: pipeline.compile_typed({"main": (tmp_path / "main.py", source)}),
        )
    assert parity(tmp_path, SOURCE) == "step\ncounters passed\n"


@pytest.mark.parametrize("optimize", [False, True])
def test_overflow_does_not_change_dictionary(tmp_path: Path, monkeypatch, optimize: bool) -> None:
    original = service.ServiceCompiler.__init__

    def initialize(self, *args, **kwargs) -> None:
        kwargs["optimize"] = optimize
        original(self, *args, **kwargs)

    monkeypatch.setattr(service.ServiceCompiler, "__init__", initialize)
    source = """def check() -> None:
    values: dict[str, int] = {"full": 9223372036854775807}
    key: str = "missing"
    try:
        values[key] = values.get(key, 9223372036854775807) + 1
    except Exception:
        print("missing overflow")
    assert key not in values
    key = "full"
    try:
        values[key] = values.get(key, 0) + 1
    except Exception:
        print("existing overflow")
    assert values[key] == 9223372036854775807
    print("unchanged")
    return
if __name__ == "__main__":
    check()
"""
    result = subprocess.run(program(tmp_path, source, "rust"), text=True, capture_output=True, check=True)
    assert result.stdout == "missing overflow\nexisting overflow\nunchanged\n"
