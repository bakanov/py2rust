"""IR binding writes and borrowed iteration decisions."""

from dataclasses import dataclass

from . import ir
from .parameter_policy import place_root, statement_targets, write_reasons
from .view_policy import statements


def mutable_bindings(body: tuple[ir.Statement, ...], parameters: set[str]) -> frozenset[str]:
    candidates = set(parameters)
    initializations = set()

    def expression(value: ir.Expression) -> None:
        if value.operation == "name":
            candidates.add(str(value.value))
        for operand in value.operands:
            expression(operand)
        return  # noqa: PLR1711

    def block(items: tuple[ir.Statement, ...], bindings: set[str]) -> None:
        for item in items:
            targets = statement_targets(item)
            candidates.update(targets)
            if item.operation in {"assign", "unpack_assign"} and any(target not in bindings for target in targets):
                initializations.add(item)
                bindings.update(targets)
            if item.operation == "for":
                initializations.add(item)
            for value in item.expressions:
                expression(value)
            for index, child in enumerate(item.blocks):
                nested = bindings.copy()
                if index == 0 and item.operation in {"for", "resource_scope"}:
                    nested.add(item.target)
                block(child, nested)
            for handler in item.handlers:
                nested = bindings.copy()
                if handler.binding is not None:
                    candidates.add(handler.binding)
                    nested.add(handler.binding)
                block(handler.body, nested)
        return  # noqa: PLR1711

    block(body, set(parameters))
    function = ir.Function("", (), ir.ValueType("None"), body, ir.Source("", 0, 0))
    return frozenset(write_reasons(function, candidates, frozenset(initializations)))


@dataclass(frozen=True)
class IterationDecision:
    mode: str
    borrow_item: bool
    reason: str
    source: str | None


def iteration_use(statement: ir.Statement) -> IterationDecision:
    value = statement.expressions[0]
    if value.operation == "runtime_call" and value.value == "json_array" and len(value.operands) == 1:
        value = value.operands[0]
    root = place_root(value)
    if root is None or root == statement.target:
        return IterationDecision("snapshot", False, "iteration_source_not_a_stable_place", root)
    body = ir.Function("", (), ir.ValueType("None"), statement.blocks[0], statement.source)
    writes = write_reasons(body, {root, statement.target})
    if root in writes:
        return IterationDecision("snapshot", False, "iteration_source_may_change", root)
    return IterationDecision("borrow", statement.target not in writes, "stable_readonly_iteration_source", root)


def iterations(modules: tuple[ir.Module, ...]) -> tuple[tuple[ir.Statement, IterationDecision], ...]:
    return tuple(
        (item, iteration_use(item))
        for module in modules
        for body in [module.body, *(function.body for function in module.functions)]
        for item in statements(body)
        if item.operation == "for"
    )
