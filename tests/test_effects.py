"""Effect facts remain conservative across recursion and unknown/native calls."""

# ruff: noqa: EXE002, PLR1711 - exFAT modes and explicit returns
import ast

from py2rust.compiler.effects import (
    RUNTIME_SUMMARIES,
    UNKNOWN,
    Effects,
    summarize_functions,
)


def test_effect_join_is_monotone() -> None:
    read = Effects(costs=frozenset({"scan_input"}))
    write = Effects(io=True, resource_state=True)
    assert read.join(write) == write.join(read)
    assert read.join(read) == read
    assert read.join(UNKNOWN).unknown
    assert "scan_input" in read.join(UNKNOWN).costs
    return


def test_recursive_effect_fixed_point() -> None:
    functions = ast.parse("""
def first(stream, data):
    return second(stream, data)
def second(stream, data):
    third(stream, data)
    tcp_sendall(stream, data)
def third(stream, data):
    return first(stream, data)
""").body
    summaries = summarize_functions(functions)
    assert summarize_functions(list(reversed(functions))) == summaries
    for summary in summaries.values():
        assert summary.effects.io
        assert summary.effects.resource_state
        assert summary.effects.may_fail
        assert summary.effects.may_diverge
        assert not summary.effects.unknown
        assert {"recursion", "write_input", "blocking"} <= summary.effects.costs
    return


def test_unknown_calls_propagate_but_owned_parameter_writes_do_not() -> None:
    functions = ast.parse("""
def wrapper(value):
    return native(value)
def entry(value):
    return wrapper(value)
def changed(value):
    value = 2
    return value
def caller(value):
    return changed(value)
""").body
    summaries = summarize_functions(functions)
    assert summaries["entry"].effects == UNKNOWN
    assert summaries["wrapper"].unknown_calls == frozenset({"native"})
    assert summaries["changed"].parameters_may_write == frozenset({"value"})
    assert summaries["caller"].parameters_may_write == frozenset()
    assert not summaries["caller"].effects.unknown
    return


def test_reviewed_runtime_views_and_costs() -> None:
    assert RUNTIME_SUMMARIES["json_array_ref"].returns_view_of == 0
    assert RUNTIME_SUMMARIES["slice_view"].returns_view_of == 0
    assert "copy_selected_value" in RUNTIME_SUMMARIES["json_array"].effects.costs
    assert "materialize_json" in RUNTIME_SUMMARIES["json_dumps"].effects.costs
    assert "materialize_json" not in RUNTIME_SUMMARIES["json_dumps_view"].effects.costs
    assert RUNTIME_SUMMARIES["monotonic"].effects.global_state
    assert RUNTIME_SUMMARIES["tcp_close"].effects.resource_state
    assert all(summary.reviewed_source for summary in RUNTIME_SUMMARIES.values())
    return


def test_runtime_metadata_agrees_with_registered_fallibility() -> None:
    from py2rust.compiler.service import LIBRARY, RUNTIME_PARAMETERS

    for name, summary in RUNTIME_SUMMARIES.items():
        if name in LIBRARY:
            assert summary.effects.may_fail == LIBRARY[name][2], name
            if summary.returns_view_of is not None:
                assert RUNTIME_PARAMETERS[name][summary.returns_view_of].passing == "shared"
    return


def test_selected_runtime_helper_controls_cost_summary() -> None:
    function = ast.parse("def encode(value):\n    return json_dumps(value)").body[0]
    function.body[0].value.lowered_runtime_helper = "json_dumps_view"
    summary = summarize_functions([function])["encode"]
    assert summary.effects.costs == frozenset({"validate_input", "serialize_output"})
    assert not summary.effects.unknown
    return
