"""Typed lowering decisions, independent of Rust source rendering.

The first operation is a string builder update. Further ownership/effect analysis
can add operations without pattern matching on generated Rust text.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass

from .memory import (
    ArgumentUse as ArgumentUse,
)
from .memory import (
    FlowNode as FlowNode,
)
from .memory import (
    IterationUse as IterationUse,
)
from .memory import (
    OwnershipUse as OwnershipUse,
)
from .memory import (
    ParameterUse as ParameterUse,
)
from .memory import (
    RuntimeParameter as RuntimeParameter,
)
from .memory import (
    binding_write_reasons as binding_write_reasons,
)
from .memory import (
    callback_functions as callback_functions,
)
from .memory import (
    iteration_use as iteration_use,
)
from .memory import (
    json_array_views as json_array_views,
)
from .memory import (
    last_uses as last_uses,
)
from .memory import (
    mutable_bindings as mutable_bindings,
)
from .memory import (
    parameter_uses as parameter_uses,
)
from .memory import (
    place_root as place_root,
)
from .memory import (
    runtime_argument_use as runtime_argument_use,
)
from .memory import (
    sequence_slice_views as sequence_slice_views,
)


@dataclass(frozen=True)
class StringAppend:
    """Evaluate suffix completely before mutating an owned local string."""

    target: str
    suffix: ast.expr
    line: int
    reason: str = "owned_string_self_append"


def string_append(target: str, type_name: str, value: ast.expr) -> StringAppend | None:
    if hasattr(value, "py2rust_string_append"):
        return value.py2rust_string_append
    return _legacy_string_append(target, type_name, value)


def _legacy_string_append(target: str, type_name: str, value: ast.expr) -> StringAppend | None:
    """Recognize only a typed named-local self-concatenation assignment."""
    if type_name != "str":
        return None
    suffixes: list[ast.expr] = []
    prefix = value
    while isinstance(prefix, ast.BinOp) and isinstance(prefix.op, ast.Add):
        suffixes.append(prefix.right)
        prefix = prefix.left
    if not suffixes or not isinstance(prefix, ast.Name) or prefix.id != target:
        return None
    suffixes.reverse()
    suffix = suffixes[0]
    for part in suffixes[1:]:
        suffix = ast.copy_location(ast.BinOp(left=suffix, op=ast.Add(), right=part), part)
    return StringAppend(target, suffix, value.lineno)


@dataclass(frozen=True)
class CachedLength:
    """Lazily count an unchanged string parameter at its first length use."""

    target: str
    line: int
    reason: str = "immutable_string_parameter_length"


def cached_lengths(function: ast.FunctionDef, string_parameters: set[str]) -> dict[str, CachedLength]:
    prepared = getattr(function, "py2rust_efficiency_plan", None)
    if prepared is not None:
        return {
            item.target: CachedLength(item.target, item.source.line, item.reason)
            for item in prepared.lengths
            if item.target in string_parameters
        }
    return _legacy_cached_lengths(function, string_parameters)


def _legacy_cached_lengths(function: ast.FunctionDef, string_parameters: set[str]) -> dict[str, CachedLength]:
    """Reject any parameter binding that can change, including exception targets."""
    written = {
        node.id
        for node in ast.walk(function)
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del))
    }
    written.update(node.name for node in ast.walk(function) if isinstance(node, ast.ExceptHandler) and node.name)
    plans: dict[str, CachedLength] = {}
    for node in ast.walk(function):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "len"
            and len(node.args) == 1
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id in string_parameters - written
        ):
            name = node.args[0].id
            plans[name] = CachedLength(name, node.lineno)
    return plans


@dataclass(frozen=True)
class TextAccess:
    target: str
    line: int
    reason: str = "repeated_immutable_text_access"
    representation: str = "TextIndex"


def immutable_strings(function: ast.FunctionDef, parameters: set[str]) -> set[str]:
    written = {node.id for node in ast.walk(function) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)}
    written.update(node.name for node in ast.walk(function) if isinstance(node, ast.ExceptHandler) and node.name)
    return parameters - written


def text_accesses(
    function: ast.FunctionDef, parameters: set[str], *, builtin_ord: bool = False
) -> dict[str, TextAccess]:
    prepared = getattr(function, "py2rust_efficiency_plan", None)
    if prepared is not None:
        return {
            item.target: TextAccess(item.target, item.source.line, item.reason, item.representation)
            for item in prepared.indexes
            if item.target in parameters
        }
    return _legacy_text_accesses(function, parameters, builtin_ord=builtin_ord)


def _legacy_text_accesses(
    function: ast.FunctionDef, parameters: set[str], *, builtin_ord: bool = False
) -> dict[str, TextAccess]:
    stable = immutable_strings(function, parameters)
    accesses: dict[str, list[ast.Subscript]] = {}
    repeated = {
        id(node) for loop in ast.walk(function) if isinstance(loop, (ast.For, ast.While)) for node in ast.walk(loop)
    }
    for node in ast.walk(function):
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id in stable:
            accesses.setdefault(node.value.id, []).append(node)
    codepoint_reads = {
        id(node.args[0])
        for node in ast.walk(function)
        if builtin_ord
        and isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "ord"
        and len(node.args) == 1
        and isinstance(node.args[0], ast.Subscript)
        and not isinstance(node.args[0].slice, ast.Slice)
        and runtime_argument_use(RuntimeParameter("str", "shared"), node.args, 0).mode == "borrow"
    }
    return {
        name: TextAccess(
            name,
            nodes[0].lineno,
            representation="CodepointIndex" if all(id(node) in codepoint_reads for node in nodes) else "TextIndex",
        )
        for name, nodes in accesses.items()
        if len(nodes) > 1 or any(id(node) in repeated for node in nodes)
    }


def string_slice_views(function: ast.FunctionDef, parameters: set[str]) -> dict[str, str]:
    prepared = getattr(function, "py2rust_view_plan", None)
    if prepared is not None:
        return prepared.bindings("text")
    return _legacy_string_slice_views(function, parameters)


def _legacy_string_slice_views(function: ast.FunctionDef, parameters: set[str]) -> dict[str, str]:
    from collections import Counter

    stable = immutable_strings(function, parameters)
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
        and isinstance(node.annotation, ast.Name)
        and node.annotation.id == "str"
        and isinstance(node.value, ast.Subscript)
        and isinstance(node.value.slice, ast.Slice)
        and isinstance(node.value.value, ast.Name)
    ]
    views: dict[str, str] = {}
    changed = True
    while changed:
        before = set(views)
        for node in candidates:
            if node.value.value.id in stable | views.keys():
                source = node.value.value.id
                views[node.target.id] = source if source in stable else views[source]
        changed = before != set(views)
    return views
