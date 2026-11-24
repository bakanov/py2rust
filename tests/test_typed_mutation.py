"""Typed detachment facts preserve indexed mutation safety and diagnostics."""

from pathlib import Path

import pytest

from py2rust.compiler import pipeline, service

from . import test_service_nested_assignment as cases


def forbidden(*args, **kwargs) -> None:
    raise AssertionError("typed collection safety fell back to AST scanning")


@pytest.mark.parametrize(
    "statement",
    [
        "grid[0][len(grid.pop()) - 1] = 7",
        "grid[0][heapq.heappop(grid)[0]] = 7",
        "grid[0][heapq.heapreplace(grid, [0])[0]] = 7",
        "grid[0].append(grid.pop()[0])",
        "grid[0].extend(grid.pop())",
        "grid[0].append(heapq.heappop(grid)[0])",
        "grid[0].extend(heapq.heapreplace(grid, [0]))",
    ],
)
def test_detachment_rejection_has_original_location(tmp_path: Path, monkeypatch, statement: str) -> None:
    source = "import heapq\ndef check() -> None:\n    grid: list[list[int]] = [[0], [1]]\n    " + statement
    source += "\nif __name__ == '__main__':\n    check()\n"
    path = tmp_path / "main.py"
    prepared = pipeline.prepare_typed({"main": (path, source)})
    assert any(proof.mutations for _, proof in prepared.memory.evaluations)
    monkeypatch.setattr(service.ServiceCompiler, "_legacy_collection_mutation_in", forbidden)
    with pytest.raises(service.ServiceError, match="cannot mutate its parent collection") as caught:
        pipeline.emit_rust(prepared)
    assert caught.value.filename == str(path)
    assert caught.value.lineno == 4
    return  # noqa: PLR1711


@pytest.mark.parametrize("optimize", [False, True])
@pytest.mark.parametrize(
    "case",
    [
        cases.test_nested_assignment_bounds_depth_and_values,
        cases.test_nested_assignment_evaluation_and_failure_order,
        cases.test_nested_assignment_large_grid,
    ],
)
def test_native_nested_updates(tmp_path: Path, monkeypatch, optimize: bool, case) -> None:
    original_init = service.ServiceCompiler.__init__

    def initialize(self, *args, **kwargs) -> None:
        kwargs["optimize"] = optimize
        original_init(self, *args, **kwargs)
        return  # noqa: PLR1711

    monkeypatch.setattr(service.ServiceCompiler, "__init__", initialize)
    monkeypatch.setattr(service.ServiceCompiler, "_legacy_collection_mutation_in", forbidden)
    monkeypatch.setattr(
        service.ServiceCompiler,
        "compile",
        lambda self, source: pipeline.compile_typed({"main": (tmp_path / "main.py", source)}),
    )
    case(tmp_path)
    return  # noqa: PLR1711
