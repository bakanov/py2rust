"""Conservative, transitive effect and cost summaries for diagnostics.

These summaries do not authorize reordering or borrowing. ABI ownership, effects,
and implementation costs are separate facts. Unreviewed/native calls remain unknown.
"""

# ruff: noqa: EXE002, PLR1711 - exFAT modes and explicit returns
from __future__ import annotations

import ast
from collections.abc import Mapping
from dataclasses import dataclass

from .optimization import binding_write_reasons


@dataclass(frozen=True)
class Effects:
    may_fail: bool = False
    io: bool = False
    resource_state: bool = False
    global_state: bool = False
    callbacks: bool = False
    may_diverge: bool = False
    unknown: bool = False
    costs: frozenset[str] = frozenset()

    def join(self, other: Effects) -> Effects:
        return Effects(
            self.may_fail or other.may_fail,
            self.io or other.io,
            self.resource_state or other.resource_state,
            self.global_state or other.global_state,
            self.callbacks or other.callbacks,
            self.may_diverge or other.may_diverge,
            self.unknown or other.unknown,
            self.costs | other.costs,
        )


UNKNOWN = Effects(True, True, True, True, True, True, True, frozenset({"unknown"}))


@dataclass(frozen=True)
class RuntimeSummary:
    effects: Effects
    returns_view_of: int | None = None
    reviewed_source: str = ""


def runtime_summaries() -> dict[str, RuntimeSummary]:
    """Reviewed implementation groups; missing entries must use UNKNOWN.

    Costs describe possible work, not measured latency or allocation counts. The
    compiler must select metadata for the actual helper after choosing its lowering.
    """
    result: dict[str, RuntimeSummary] = {}

    def add(names: str, effects: Effects, source: str, view: int | None = None) -> None:
        if "blocking" in effects.costs:
            effects = effects.join(Effects(may_diverge=True))
        for name in names.split():
            if name in result:
                raise ValueError("duplicate runtime cost summary: " + name)
            result[name] = RuntimeSummary(effects, view, source)
        return

    add("float_to_string", Effects(may_fail=True, costs=frozenset({"allocate_bounded_output"})), "float_text.rs")
    add("json_keys", Effects(may_fail=True, costs=frozenset({"copy_object_keys", "sort_object_keys"})), "lib.rs")
    add("json_equal", Effects(costs=frozenset({"compare_tree"})), "lib.rs")
    add("path_parent", Effects(may_fail=True, costs=frozenset({"scan_input", "allocate_output"})), "resources.rs")
    add("path_join", Effects(may_fail=True, costs=frozenset({"scan_input", "allocate_output"})), "lib.rs")
    add("path_resolve", Effects(may_fail=True, io=True, costs=frozenset({"blocking", "allocate_output"})), "lib.rs")
    add(
        "file_open",
        Effects(may_fail=True, io=True, resource_state=True, costs=frozenset({"blocking", "acquire_resource"})),
        "resources.rs",
    )
    add(
        "regex_search regex_fullmatch",
        Effects(
            may_fail=True,
            global_state=True,
            costs=frozenset({"blocking", "compile_pattern_on_miss", "match_input", "retain_bounded_cache"}),
        ),
        "regular_expressions.rs",
    )
    add(
        "regex_capture_groups",
        Effects(
            may_fail=True,
            global_state=True,
            costs=frozenset(
                {"blocking", "compile_pattern_on_miss", "match_input", "retain_bounded_cache", "allocate_output"}
            ),
        ),
        "regular_expressions.rs",
    )
    add(
        "memoized",
        Effects(
            may_fail=True,
            global_state=True,
            costs=frozenset({"blocking", "retain_bounded_cache", "allocate_bounded_output"}),
        ),
        "memoization.rs",
    )
    add("sha256_digest", Effects(costs=frozenset({"copy_bounded_state", "allocate_bounded_output"})), "resources.rs")
    add("sha256_update", Effects(costs=frozenset({"copy_bounded_state", "scan_input"})), "resources.rs")
    add("char_at_view", Effects(may_fail=True, costs=frozenset({"scan_input"})), "lib.rs", 0)
    add("json_int json_bool json_float", Effects(may_fail=True), "lib.rs")
    add("json_is_null", Effects(), "lib.rs")
    add("json_from_array", Effects(may_fail=True, costs=frozenset({"validate_input"})), "lib.rs")
    add("json_kind", Effects(costs=frozenset({"allocate_bounded_output"})), "lib.rs")
    add("json_array_ref json_index_ref json_string_ref", Effects(may_fail=True), "lib.rs", 0)
    add("json_key_ref", Effects(may_fail=True, costs=frozenset({"map_lookup"})), "lib.rs", 0)
    add("json_string json_array json_index", Effects(may_fail=True, costs=frozenset({"copy_selected_value"})), "lib.rs")
    add("json_key json_get", Effects(may_fail=True, costs=frozenset({"map_lookup", "copy_selected_value"})), "lib.rs")
    add(
        "json_dumps pretty",
        Effects(may_fail=True, costs=frozenset({"materialize_json", "validate_input", "serialize_output"})),
        "lib.rs",
    )
    add(
        "json_dumps_view pretty_view",
        Effects(may_fail=True, costs=frozenset({"validate_input", "serialize_output"})),
        "json_output.rs",
    )
    add(
        "json_canonical_view",
        Effects(may_fail=True, costs=frozenset({"validate_input", "serialize_output", "sort_object_keys"})),
        "lib.rs",
    )
    add(
        "json_canonical",
        Effects(
            may_fail=True,
            costs=frozenset({"materialize_json", "validate_input", "serialize_output", "sort_object_keys"}),
        ),
        "lib.rs",
    )
    add("to_json", Effects(may_fail=True, costs=frozenset({"materialize_json", "validate_input"})), "lib.rs")
    add(
        "json_loads",
        Effects(may_fail=True, costs=frozenset({"parse_input", "allocate_tree", "validate_input"})),
        "lib.rs; unique_json.rs",
    )
    add("slice_view", Effects(), "lib.rs", 0)
    add("bytes_slice list_slice", Effects(costs=frozenset({"copy_selected_value"})), "lib.rs")
    add("str_slice_view", Effects(costs=frozenset({"scan_input"})), "lib.rs", 0)
    add("str_slice", Effects(costs=frozenset({"scan_input", "copy_selected_value"})), "lib.rs")
    add("char_at", Effects(may_fail=True, costs=frozenset({"scan_input", "allocate_bounded_output"})), "lib.rs")
    add("str_find str_rfind", Effects(costs=frozenset({"scan_input"})), "lib.rs")
    add("str_split", Effects(may_fail=True, costs=frozenset({"scan_input", "allocate_output"})), "lib.rs")
    add("str_strip str_split_whitespace", Effects(costs=frozenset({"scan_input", "allocate_output"})), "lib.rs")
    add("monotonic", Effects(global_state=True), "lib.rs")
    add("env_get", Effects(global_state=True, costs=frozenset({"allocate_output"})), "lib.rs")
    add("sleep", Effects(may_fail=True, global_state=True, costs=frozenset({"blocking"})), "lib.rs")
    add(
        "tcp_sendall",
        Effects(may_fail=True, io=True, resource_state=True, costs=frozenset({"blocking", "write_input"})),
        "tcp.rs",
    )
    add(
        "tcp_recv",
        Effects(may_fail=True, io=True, resource_state=True, costs=frozenset({"blocking", "allocate_output"})),
        "tcp.rs",
    )
    add("tcp_set_deadline tcp_close tcp_close_listener", Effects(may_fail=True, io=True, resource_state=True), "tcp.rs")
    return result


RUNTIME_SUMMARIES = runtime_summaries()


@dataclass(frozen=True)
class FunctionSummary:
    name: str
    filename: str | None
    line: int
    parameters_may_write: frozenset[str]
    callees: frozenset[str]
    unknown_calls: frozenset[str]
    effects: Effects


def summarize_functions(
    functions: list[ast.FunctionDef], runtime: Mapping[str, RuntimeSummary] | None = None
) -> dict[str, FunctionSummary]:
    """Monotone fixed point over resolved application calls, including recursion.

    Parameter writes describe this function's owned parameter values. They are not
    propagated as writes to caller data: this subset copies at mutating boundaries.
    Shared resource/global effects are propagated. Names must already be resolved
    by the project linker; aliases must be canonicalized by the caller.
    """
    registry = RUNTIME_SUMMARIES if runtime is None else runtime
    names = {function.name for function in functions}
    direct: dict[str, Effects] = {}
    calls: dict[str, set[str]] = {}
    unknown: dict[str, set[str]] = {}
    for function in functions:
        effect = Effects()
        calls[function.name] = set()
        unknown[function.name] = set()
        for node in ast.walk(function):
            if isinstance(node, (ast.Assert, ast.Raise, ast.BinOp, ast.UnaryOp, ast.Subscript)):
                effect = effect.join(Effects(may_fail=True))
            if isinstance(node, (ast.For, ast.While)):
                effect = effect.join(Effects(may_diverge=True, costs=frozenset({"loop"})))
            if isinstance(node, ast.With):
                effect = effect.join(UNKNOWN.join(Effects(costs=frozenset({"resource_cleanup"}))))
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node, "lowered_runtime_helper", None) or ast.unparse(node.func)
            if name in names:
                calls[function.name].add(name)
            elif name in registry:
                effect = effect.join(registry[name].effects)
            elif name == "print":
                effect = effect.join(
                    Effects(may_fail=True, io=True, global_state=True, costs=frozenset({"format_output"}))
                )
            elif name in {
                "len",
                "range",
                "min",
                "max",
                "int",
                "float",
                "bool",
                "str",
                "bytes",
                "bytearray",
                "list",
                "tuple",
                "sorted",
                "ord",
                "chr",
            }:
                effect = effect.join(Effects(may_fail=True, costs=frozenset({"type_dependent_builtin"})))
            else:
                unknown[function.name].add(name)
                effect = effect.join(UNKNOWN)
        direct[function.name] = effect

    for name in names:
        pending = list(calls[name])
        visited: set[str] = set()
        while pending:
            callee = pending.pop()
            if callee == name:
                direct[name] = direct[name].join(Effects(may_diverge=True, costs=frozenset({"recursion"})))
                break
            if callee not in visited:
                visited.add(callee)
                pending.extend(calls[callee])

    effects = direct.copy()
    changed = True
    while changed:
        changed = False
        for name in sorted(names):
            combined = direct[name]
            for callee in sorted(calls[name]):
                combined = combined.join(effects[callee])
            if effects[name] != combined:
                effects[name] = combined
                changed = True
    return {
        function.name: FunctionSummary(
            function.name,
            getattr(function, "source_path", None),
            function.lineno,
            frozenset(binding_write_reasons(function, {argument.arg for argument in function.args.args})),
            frozenset(calls[function.name]),
            frozenset(unknown[function.name]),
            effects[function.name],
        )
        for function in functions
    }
