"""Ownership policy: parameter passing, mutation barriers, and last-use moves.

Decisions are independent of Rust rendering and do not authorize effect reordering.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass

from .argument_policy import ArgumentUse as ArgumentUse  # noqa: PLC0414 - legacy public API
from .argument_policy import RuntimeParameter as RuntimeParameter  # noqa: PLC0414 - legacy public API
from .argument_policy import runtime_argument_decision
from .parameter_policy import READONLY_METHODS


def runtime_argument_use(parameter: RuntimeParameter, arguments: list[ast.expr], index: int) -> ArgumentUse:
    """Adapt prepared stability facts (or legacy AST analysis) to ownership policy."""
    return runtime_argument_decision(
        parameter,
        (not argument_effects_unknown(argument) for argument in arguments[index:]),
        getattr(arguments[index], "lineno", 0),
    )


def argument_effects_unknown(argument: ast.expr) -> bool:
    proof = getattr(argument, "py2rust_evaluation", None)
    if proof is not None:
        return not proof.stable
    return _legacy_argument_effects_unknown(argument)


def _legacy_argument_effects_unknown(argument: ast.expr) -> bool:
    effects = (
        ast.Call,
        ast.NamedExpr,
        ast.Await,
        ast.Yield,
        ast.YieldFrom,
        ast.ListComp,
        ast.SetComp,
        ast.DictComp,
        ast.GeneratorExp,
    )
    return any(
        isinstance(node, effects)
        and not (isinstance(node, ast.Call) and getattr(node, "py2rust_nonmutating_call", False))
        for node in ast.walk(argument)
    )


@dataclass(frozen=True)
class ParameterUse:
    """Locally read-only parameters may borrow; owned escapes remain copies."""

    name: str
    mode: str
    reason: str
    line: int


def place_root(node: ast.AST) -> str | None:
    while isinstance(node, (ast.Attribute, ast.Subscript)):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def binding_write_reasons(
    function: ast.AST,
    candidates: set[str],
    initializations: frozenset[int] = frozenset(),
) -> dict[str, str]:
    reasons: dict[str, str] = {}
    for node in ast.walk(function):
        if isinstance(node, (ast.Name, ast.Attribute, ast.Subscript)) and isinstance(node.ctx, (ast.Store, ast.Del)):
            root = place_root(node)
            if root in candidates and id(node) not in initializations:
                reasons[root] = "parameter_or_reachable_value_written"
        if isinstance(node, ast.ExceptHandler) and node.name in candidates:
            reasons[node.name] = "exception_target_rebinds_parameter"
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            root = place_root(node.func.value)
            if root in candidates and node.func.attr not in READONLY_METHODS:
                reasons[root] = "receiver_effects_not_readonly"
            if ast.unparse(node.func).startswith("heapq.") and node.args:
                root = place_root(node.args[0])
                if root in candidates:
                    reasons[root] = "heap_operation_mutates_parameter"
    return reasons


def parameter_uses(function: ast.FunctionDef, candidates: set[str], callback: bool) -> dict[str, ParameterUse]:
    prepared = getattr(function, "py2rust_parameter_plan", None)
    if prepared is not None:
        return {item.name: ParameterUse(item.name, item.mode, item.reason, item.line) for item in prepared.parameters}
    return _legacy_parameter_uses(function, candidates, callback)


def _legacy_parameter_uses(function: ast.FunctionDef, candidates: set[str], callback: bool) -> dict[str, ParameterUse]:
    reasons = binding_write_reasons(function, candidates)
    return {
        arg.arg: ParameterUse(
            arg.arg,
            ("borrow" if arg.arg in candidates and arg.arg not in reasons and not callback else "owned"),
            (
                "callback_owned_abi"
                if callback
                else reasons.get(
                    arg.arg,
                    ("readonly_value_parameter" if arg.arg in candidates else "unchanged_parameter_abi"),
                )
            ),
            arg.lineno,
        )
        for arg in function.args.args
    }


def callback_functions(tree: ast.Module, function_names: set[str]) -> set[str]:
    direct_calls = {id(node.func) for node in ast.walk(tree) if isinstance(node, ast.Call)}
    return {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and node.id in function_names and id(node) not in direct_calls
    }


@dataclass(frozen=True)
class OwnershipUse:
    name: str
    line: int
    mode: str
    reason: str


@dataclass
class FlowNode:
    reads: list[ast.Name]
    writes: set[str]
    successors: set[int]
    protected: bool = False


def last_uses(function: ast.FunctionDef) -> dict[int, OwnershipUse]:
    prepared = getattr(function, "py2rust_ownership_uses", None)
    return prepared if prepared is not None else _legacy_last_uses(function)


def _legacy_last_uses(function: ast.FunctionDef) -> dict[int, OwnershipUse]:
    """Backward liveness across branches and loop backedges.

    Try/with regions are conservative atomic barriers: their reads include handlers,
    cleanup and closure captures. No value is moved within those regions yet.
    """
    from collections import Counter

    graph: list[FlowNode] = []
    outer_bindings = {arg.arg for arg in function.args.args} | {
        node.target.id
        for node in ast.walk(function)
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }

    def names(node: ast.AST) -> list[ast.Name]:
        return [item for item in ast.walk(node) if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load)]

    def add(
        reads: list[ast.Name],
        writes: set[str],
        successors: set[int],
        protected: bool = False,
    ) -> int:
        graph.append(FlowNode(reads, writes, successors, protected))
        return len(graph) - 1

    def block(statements: list[ast.stmt], following: set[int], stop: set[int], again: set[int]) -> set[int]:
        entry = following
        for statement in reversed(statements):
            if isinstance(statement, ast.If):
                left = block(statement.body, entry, stop, again)
                right = block(statement.orelse, entry, stop, again)
                entry = {add(names(statement.test), set(), left | right)}
            elif isinstance(statement, (ast.For, ast.While)):
                expression = statement.iter if isinstance(statement, ast.For) else statement.test
                writes = (
                    {statement.target.id}
                    if isinstance(statement, ast.For)
                    and isinstance(statement.target, ast.Name)
                    and statement.target.id not in outer_bindings
                    else set()
                )
                header = add(
                    [] if isinstance(statement, ast.For) else names(expression),
                    writes,
                    set(),
                )
                normal_exit = block(statement.orelse, entry, stop, again)
                body = block(statement.body, {header}, entry, {header})
                graph[header].successors = body | normal_exit
                # A for iterable is evaluated once, outside its loop backedge.
                entry = {add(names(expression), set(), {header})} if isinstance(statement, ast.For) else {header}
            elif isinstance(statement, ast.Break):
                entry = {add([], set(), stop)}
            elif isinstance(statement, ast.Continue):
                entry = {add([], set(), again)}
            else:
                protected = isinstance(statement, (ast.Try, ast.With))
                writes = (
                    set()
                    if protected
                    else {
                        item.id
                        for item in ast.walk(statement)
                        if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Store)
                    }
                )
                successors = set() if isinstance(statement, (ast.Return, ast.Raise)) else entry
                entry = {add(names(statement), writes, successors, protected)}
        return entry

    block(function.body, set(), set(), set())
    live_in: list[set[str]] = [set() for _ in graph]
    live_out: list[set[str]] = [set() for _ in graph]
    changed = True
    while changed:
        changed = False
        for index, node in enumerate(graph):
            outgoing = set().union(*(live_in[successor] for successor in node.successors))
            incoming = {name.id for name in node.reads} | (outgoing - node.writes)
            if incoming != live_in[index] or outgoing != live_out[index]:
                live_in[index], live_out[index] = incoming, outgoing
                changed = True
    decisions: dict[int, OwnershipUse] = {}
    for index, node in enumerate(graph):
        counts = Counter(name.id for name in node.reads)
        for name in node.reads:
            reason = (
                "protected_control_flow"
                if node.protected
                else (
                    "value_live_after_use"
                    if name.id in live_out[index]
                    else ("repeated_use_in_expression" if counts[name.id] != 1 else "last_use_on_all_successors")
                )
            )
            decisions[id(name)] = OwnershipUse(
                name.id,
                name.lineno,
                "move" if reason == "last_use_on_all_successors" else "copy",
                reason,
            )
    return decisions


@dataclass(frozen=True)
class IterationUse:
    mode: str
    borrow_item: bool
    reason: str
    source: str | None


def iteration_use(node: ast.For) -> IterationUse:
    prepared = getattr(node, "py2rust_iteration", None)
    if prepared is not None:
        return prepared
    return _legacy_iteration_use(node)


def _legacy_iteration_use(node: ast.For) -> IterationUse:
    source = node.iter
    if (
        isinstance(source, ast.Call)
        and isinstance(source.func, ast.Name)
        and source.func.id == "json_array"
        and len(source.args) == 1
    ):
        source = source.args[0]
    root = place_root(source)
    if root is None or not isinstance(node.target, ast.Name) or root == node.target.id:
        return IterationUse("snapshot", False, "iteration_source_not_a_stable_place", root)
    body = ast.Module(body=node.body, type_ignores=[])
    reasons = binding_write_reasons(body, {root, node.target.id})
    if root in reasons:
        return IterationUse("snapshot", False, "iteration_source_may_change", root)
    return IterationUse(
        "borrow",
        node.target.id not in reasons,
        "stable_readonly_iteration_source",
        root,
    )


def json_array_views(function: ast.FunctionDef, parameters: set[str]) -> dict[str, str]:
    prepared = getattr(function, "py2rust_view_plan", None)
    if prepared is not None:
        return prepared.bindings("array")
    return _legacy_json_array_views(function, parameters)


def _legacy_json_array_views(function: ast.FunctionDef, parameters: set[str]) -> dict[str, str]:
    """Read-only array locals may view an unchanged JSON parameter."""
    from collections import Counter

    stable = parameters - binding_write_reasons(function, parameters).keys()
    stores = Counter(
        node.id for node in ast.walk(function) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
    )
    stores.update(node.name for node in ast.walk(function) if isinstance(node, ast.ExceptHandler) and node.name)
    candidates = [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and stores[node.target.id] == 1
        and ast.unparse(node.annotation) == "list[Json]"
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "json_array"
        and len(node.value.args) == 1
        and not node.value.keywords
        and place_root(node.value.args[0]) in stable
        and runtime_argument_use(RuntimeParameter("Json", "shared"), node.value.args, 0).mode == "borrow"
    ]
    writes = binding_write_reasons(
        function,
        {node.target.id for node in candidates},
        frozenset(id(node.target) for node in candidates),
    )
    return {node.target.id: place_root(node.value.args[0]) for node in candidates if node.target.id not in writes}


def sequence_slice_views(function: ast.FunctionDef, parameters: set[str]) -> dict[str, str]:
    prepared = getattr(function, "py2rust_view_plan", None)
    if prepared is not None:
        return prepared.bindings("sequence")
    return _legacy_sequence_slice_views(function, parameters)


def _legacy_sequence_slice_views(function: ast.FunctionDef, parameters: set[str]) -> dict[str, str]:
    """Read-only slice locals borrow unchanged sequence parameters or other views."""
    from collections import Counter

    stable = parameters - binding_write_reasons(function, parameters).keys()
    stores = Counter(
        node.id for node in ast.walk(function) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
    )
    stores.update(node.name for node in ast.walk(function) if isinstance(node, ast.ExceptHandler) and node.name)
    candidates = [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and stores[node.target.id] == 1
        and (
            (isinstance(node.annotation, ast.Name) and node.annotation.id in {"bytes", "bytearray"})
            or (
                isinstance(node.annotation, ast.Subscript)
                and isinstance(node.annotation.value, ast.Name)
                and node.annotation.value.id in {"list", "tuple"}
            )
        )
        and isinstance(node.value, ast.Subscript)
        and isinstance(node.value.slice, ast.Slice)
        and isinstance(node.value.value, ast.Name)
        and runtime_argument_use(RuntimeParameter("bytes", "shared"), [node.value], 0).mode == "borrow"
    ]
    writes = binding_write_reasons(
        function,
        {node.target.id for node in candidates},
        frozenset(id(node.target) for node in candidates),
    )
    views: dict[str, str] = {}
    changed = True
    while changed:
        before = set(views)
        for node in candidates:
            source = node.value.value.id
            if node.target.id not in writes and source in stable | views.keys():
                views[node.target.id] = source if source in stable else views[source]
        changed = before != set(views)
    return views


def mutable_bindings(function: ast.AST) -> set[str]:
    prepared = getattr(function, "py2rust_mutable_bindings", None)
    if prepared is not None:
        return set(prepared)
    return _legacy_mutable_bindings(function)


def _legacy_mutable_bindings(function: ast.AST) -> set[str]:
    """Bindings need mutability only for updates after their declaration."""
    candidates = {node.id for node in ast.walk(function) if isinstance(node, ast.Name)}
    candidates.update(node.arg for node in ast.walk(function) if isinstance(node, ast.arg))
    declarations = frozenset(
        id(node.target)
        for node in ast.walk(function)
        if isinstance(node, (ast.AnnAssign, ast.For)) and isinstance(node.target, ast.Name)
    )
    return set(binding_write_reasons(function, candidates, declarations))
