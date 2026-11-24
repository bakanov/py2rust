"""Runtime summaries distinguish lexical paths, I/O and bounded hash state."""

# ruff: noqa: EXE002, PLR1711 - exFAT modes and explicit returns
import ast

from py2rust.compiler.effects import RUNTIME_SUMMARIES, summarize_functions


def test_runtime_cost_categories() -> None:
    lexical = RUNTIME_SUMMARIES["path_join"].effects
    resolved = RUNTIME_SUMMARIES["path_resolve"].effects
    assert not lexical.io and resolved.io and resolved.may_diverge
    opened = RUNTIME_SUMMARIES["file_open"].effects
    assert opened.resource_state and opened.io and opened.may_fail
    regex = RUNTIME_SUMMARIES["regex_fullmatch"].effects
    assert regex.global_state and regex.may_fail and regex.may_diverge
    assert {"compile_pattern_on_miss", "retain_bounded_cache", "match_input"} <= regex.costs
    for name in ["sha256_digest", "sha256_update"]:
        effect = RUNTIME_SUMMARIES[name].effects
        assert not effect.resource_state and not effect.global_state and not effect.io
        assert "copy_bounded_state" in effect.costs
    assert "copy_object_keys" in RUNTIME_SUMMARIES["json_keys"].effects.costs
    assert RUNTIME_SUMMARIES["char_at_view"].returns_view_of == 0
    return


def test_known_costs_propagate_without_becoming_unknown() -> None:
    functions = ast.parse("""
def resolve(base, child):
    return path_resolve(path_join(base, child))
def open_data(base, child):
    return file_open(resolve(base, child), "rb")
""").body
    summary = summarize_functions(functions)["open_data"]
    assert not summary.effects.unknown
    assert summary.effects.io and summary.effects.resource_state
    assert {"blocking", "allocate_output", "acquire_resource"} <= summary.effects.costs
    return
