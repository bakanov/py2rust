"""Partial record moves preserve old-field observations and exceptional paths."""

from pathlib import Path

import pytest

from py2rust.compiler import pipeline, service
from .test_services import parity, run

SOURCE = """from dataclasses import dataclass
@dataclass
class State:
    items: list[int]
    trace: list[int]
    count: int

def update(state: State) -> State:
    items: list[int] = state.items
    trace: list[int] = state.trace
    items.append(state.count)
    state.items = items
    trace.append(len(state.trace) + len(state.items))
    state.trace = trace
    state.count = state.count + 1
    return state

def observe(state: State) -> State:
    items: list[int] = state.items
    assert state.items[0] == 1
    items.append(3)
    state.items = items
    return state

def inspect(state: State) -> int:
    return len(state.items)

def whole(state: State) -> State:
    items: list[int] = state.items
    assert inspect(state) == 1
    items.append(2)
    state.items = items
    return state

def protected(state: State) -> State:
    items: list[int] = state.items
    try:
        assert False, "stop"
        state.items = items
    except Exception:
        assert state.items == [1]
    return state

def check() -> None:
    state: State = State([], [], 0)
    for i in range(4):
        state = update(state)
    assert state.items == [0, 1, 2, 3]
    assert state.trace == [1, 3, 5, 7]
    assert observe(State([1], [], 0)).items == [1, 3]
    assert whole(State([1], [], 0)).items == [1, 2]
    assert protected(State([1], [], 0)).items == [1]
    print("owned fields")
    return
if __name__ == "__main__":
    check()
"""


@pytest.mark.parametrize("frontend", ["typed", "legacy"])
@pytest.mark.parametrize("optimize", [False, True])
def test_owned_field_moves(tmp_path: Path, monkeypatch, frontend: str, optimize: bool) -> None:
    original = service.ServiceCompiler.__init__

    def initialize(self, *args, **kwargs) -> None:
        kwargs["optimize"] = optimize
        original(self, *args, **kwargs)
        return

    monkeypatch.setattr(service.ServiceCompiler, "__init__", initialize)
    if frontend == "typed":
        monkeypatch.setattr(
            service.ServiceCompiler,
            "compile",
            lambda self, source: pipeline.compile_typed({"main": (tmp_path / "main.py", source)}),
        )
    generated = service.ServiceCompiler().compile(SOURCE)
    assert ("__field_length_trace" in generated) == optimize
    assert parity(tmp_path, SOURCE) == "owned fields\n"
    return


def test_old_metadata_remains_snapshot_after_local_mutation(tmp_path: Path) -> None:
    source = """from dataclasses import dataclass
@dataclass
class State:
    text: str
    items: list[int]
def update(state: State) -> State:
    text: str = state.text
    items: list[int] = state.items
    text = text + "!"
    items.append(2)
    assert len(state.text) == 2
    assert len(state.items) == 1
    state.text = text
    state.items = items
    return state
def check() -> None:
    state: State = State("世界", [1])
    changed: State = update(state)
    assert state.text == "世界" and state.items == [1]
    assert changed.text == "世界!" and changed.items == [1, 2]
    print("metadata snapshots")
    return
if __name__ == "__main__":
    check()
"""
    result = run(tmp_path, source, "rust")
    assert result.returncode == 0 and result.stdout == "metadata snapshots\n", result.stderr
    return
