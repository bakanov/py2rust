"""Readable Rust choices, independent of expression evaluation and ownership.

Only exhaustive function-tail branches gain implicit returns. Cleanup/resource
regions remain explicit until their lifetime and drop-order rules are planned.
"""

from dataclasses import dataclass

from . import ir
from .binding_policy import mutable_bindings
from .project_policy import module_layout


@dataclass(frozen=True)
class ReadabilityPlan:
    tail_returns: frozenset[ir.Statement]
    bindings: tuple[tuple[str, frozenset[str]], ...] = ()
    entry_bindings: frozenset[str] | None = None


def analyze(modules: tuple[ir.Module, ...], *, entry: str = "main") -> ReadabilityPlan:
    def tail_returns(block: tuple[ir.Statement, ...]) -> frozenset[ir.Statement] | None:
        if not block:
            return None
        last = block[-1]
        if last.operation == "return":
            return frozenset({last})
        if last.operation != "if":
            return None
        branches = [tail_returns(branch) for branch in last.blocks]
        if any(branch is None for branch in branches):
            return None
        return frozenset().union(*branches)

    selected: set[ir.Statement] = set()
    for module in modules:
        for function in module.functions:
            selected.update(tail_returns(function.body) or ())
    functions = tuple(
        (function.name, mutable_bindings(function.body, {p.name for p in function.parameters}))
        for module in modules
        for function in module.functions
    )
    entry_body = next((module_layout(module, entry)[1] for module in modules if module.name == entry), ())
    return ReadabilityPlan(frozenset(selected), functions, mutable_bindings(entry_body, set()))


@dataclass(frozen=True)
class ReturnStyle:
    pending: bool
    forward_result: bool
    implicit: bool


def return_style(*, optimize: bool, protected: bool, tail: bool, result_call: bool) -> ReturnStyle:
    """Never forward a Result or use a tail expression across pending cleanup."""
    return ReturnStyle(
        pending=protected,
        forward_result=optimize and not protected and result_call,
        implicit=optimize and not protected and tail,
    )


def reference_style(*, borrowed: bool, simple_name: bool, optimize: bool) -> str:
    """Reuse a proven reference; group compound owned expressions before borrowing."""
    if borrowed:
        return "existing"
    return "name" if optimize and simple_name else "expression"
