"""IR summaries include recursion and committed runtime helper choices."""

from dataclasses import replace
from pathlib import Path

import pytest

from py2rust.compiler import diagnostics, effect_policy, ir, pipeline, service
from py2rust.compiler.effects import UNKNOWN

from .test_services import parity

SOURCE = """from py2rust.stdlib import Json, json_dumps, json_array, file_open, file_size

def first(count: int) -> int:
    if count <= 0:
        return 0
    return second(count - 1)

def second(count: int) -> int:
    print(count)
    return first(count)

def encode(value: Json) -> str:
    return json_dumps(value)

def wrapper(value: Json) -> str:
    return encode(value)

def items(document: Json) -> int:
    entries: list[Json] = json_array(document)
    return len(entries)

def resource() -> int:
    with file_open("missing", "rb") as handle:
        return file_size(handle)

def changed(value: int) -> int:
    value = value + 1
    return value

def caller(value: int) -> int:
    return changed(value)

def uncertain(value: list[int]) -> int:
    value.append(1)
    return len(value)

if __name__ == "__main__":
    assert first(2) == 0
    assert caller(2) == 3
    assert uncertain([1]) == 2
    assert items([1, 2]) == 2
    print(wrapper({"ok": True}))
"""


def forbidden(*args, **kwargs) -> None:
    raise AssertionError("typed effects fell back to AST summary analysis")


def test_prepared_effect_report_matches_legacy(tmp_path: Path, monkeypatch) -> None:
    prepared = pipeline.prepare_typed({"main": (tmp_path / "main.py", SOURCE)})
    current = pipeline.emit_program(prepared, explain=True)
    original_link = pipeline.linked_tree

    def legacy(*args, **kwargs):
        kwargs["effect_plan"] = None
        return original_link(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(pipeline, "linked_tree", legacy)
        previous = pipeline.emit_program(prepared, explain=True)
        assert previous == current
    monkeypatch.setattr(diagnostics, "summarize_functions", forbidden)
    assert pipeline.emit_program(prepared, explain=True) == current
    rows = {row["symbol"]: row for row in current.optimization_report["functions"]}
    assert "recursion" in rows["py__main__first"]["effects"]["costs"]
    assert rows["py__main__first"]["effects"]["io"]
    assert rows["py__main__changed"]["parameters_may_write"] == ["value"]
    assert rows["py__main__caller"]["parameters_may_write"] == []
    assert rows["py__main__uncertain"]["effects"]["unknown"]
    assert rows["py__main__resource"]["effects"]["unknown"]
    assert "resource_cleanup" in rows["py__main__resource"]["effects"]["costs"]
    assert rows["py__main__wrapper"]["effects"]["costs"] == ["serialize_output", "validate_input"]
    return  # noqa: PLR1711


def test_native_unknown_and_recursive_order_independence() -> None:
    source = ir.Source("main.py", 1, 0)
    typ = ir.ValueType("builtins.int")
    native = ir.Expression("native_call", typ, source, value="native.work")
    call_a = ir.Expression("call", typ, source, value="main.a")
    call_b = ir.Expression("call", typ, source, value="main.b")
    first = ir.Function("main.a", (), typ, (ir.Statement("return", source, (call_b,)),), source)
    second = ir.Function(
        "main.b",
        (),
        typ,
        (ir.Statement("expression", source, (native,)), ir.Statement("return", source, (call_a,))),
        source,
    )
    plan = effect_policy.analyze((ir.Module("main", (first, second)),))
    symbols = {"main.a": "a", "main.b": "b", "native.work": "native_work"}
    summaries = plan.summarize({}, symbols)
    assert replace(plan, functions=tuple(reversed(plan.functions))).summarize({}, symbols) == summaries
    for summary in summaries.values():
        assert summary.effects.unknown and summary.effects.may_diverge
        assert UNKNOWN.costs | {"recursion"} <= summary.effects.costs
    assert summaries["b"].unknown_calls == frozenset({"native_work"})
    return  # noqa: PLR1711


@pytest.mark.parametrize("optimize", [False, True])
def test_committed_helper_costs_and_native_execution(tmp_path: Path, monkeypatch, optimize: bool) -> None:
    original_init = service.ServiceCompiler.__init__

    def initialize(self, *args, **kwargs) -> None:
        kwargs["optimize"] = optimize
        original_init(self, *args, **kwargs)
        return  # noqa: PLR1711

    monkeypatch.setattr(service.ServiceCompiler, "__init__", initialize)
    monkeypatch.setattr(diagnostics, "summarize_functions", forbidden)
    prepared = pipeline.prepare_typed({"main": (tmp_path / "main.py", SOURCE)})
    result = pipeline.emit_program(prepared, explain=True)
    assert result.code == pipeline.emit_program(prepared).code
    wrapper = next(row for row in result.optimization_report["functions"] if row["symbol"] == "py__main__wrapper")
    assert ("materialize_json" in wrapper["effects"]["costs"]) == (not optimize)
    items = next(row for row in result.optimization_report["functions"] if row["symbol"] == "py__main__items")
    assert ("copy_selected_value" in items["effects"]["costs"]) == (not optimize)
    monkeypatch.setattr(
        service.ServiceCompiler,
        "compile",
        lambda self, value: pipeline.compile_typed({"main": (tmp_path / "main.py", value)}),
    )
    parity(tmp_path, SOURCE)
    return  # noqa: PLR1711
