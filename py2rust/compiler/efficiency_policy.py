"""Representation and work-reuse decisions on compiler-owned typed IR."""

from dataclasses import dataclass

from . import ir
from .view_policy import statements


@dataclass(frozen=True)
class TextIndexDecision:
    target: str
    source: ir.Source
    representation: str
    reason: str = "repeated_immutable_text_access"


@dataclass(frozen=True)
class LengthCacheDecision:
    target: str
    source: ir.Source
    reason: str = "immutable_string_parameter_length"


@dataclass(frozen=True)
class FunctionEfficiency:
    function: str
    indexes: tuple[TextIndexDecision, ...]
    lengths: tuple[LengthCacheDecision, ...]


@dataclass(frozen=True)
class StringAppendDecision:
    target: str
    source: ir.Source
    suffix_count: int
    reason: str = "owned_string_self_append"


def string_append(statement: ir.Statement) -> StringAppendDecision | None:
    if statement.operation != "assign" or statement.target_type != ir.ValueType("builtins.str"):
        return None
    prefix = statement.expressions[0]
    count = 0
    while prefix.operation == "binary" and prefix.value == "+":
        count += 1
        prefix = prefix.operands[0]
    if count and prefix.operation == "name" and prefix.value == statement.target:
        return StringAppendDecision(statement.target, statement.expressions[0].source, count)
    return None


@dataclass(frozen=True)
class EfficiencyPlan:
    functions: tuple[FunctionEfficiency, ...]
    appends: tuple[tuple[ir.Statement, StringAppendDecision | None], ...] = ()


def analyze_function(function: ir.Function, stable_expressions: frozenset[ir.Expression]) -> FunctionEfficiency:
    body = statements(function.body)
    written = {item.target for item in body if item.operation in {"assign", "for", "resource_scope"}}
    written.update(handler.binding for item in body for handler in item.handlers)
    stable = {param.name for param in function.parameters if param.type.name == "builtins.str"} - written
    accesses: dict[str, list[ir.Expression]] = {}
    repeated: set[ir.Expression] = set()
    numeric: set[ir.Expression] = set()
    lengths: dict[str, ir.Source] = {}

    def expression(value: ir.Expression, in_loop: bool) -> None:
        if value.operation in {"index", "slice"} and value.operands[0].operation == "name":
            target = str(value.operands[0].value)
            if target in stable:
                accesses.setdefault(target, []).append(value)
                if in_loop:
                    repeated.add(value)
        if value.operation == "call" and len(value.operands) == 1:
            argument = value.operands[0]
            if value.value == "builtins.ord" and argument.operation == "index" and argument in stable_expressions:
                numeric.add(argument)
            elif value.value == "builtins.len" and argument.operation == "name" and argument.value in stable:
                lengths.setdefault(str(argument.value), value.source)
        for operand in value.operands:
            expression(operand, in_loop)
        return  # noqa: PLR1711

    def block(items: tuple[ir.Statement, ...], in_loop: bool = False) -> None:
        for item in items:
            loop = in_loop or item.operation in {"for", "while"}
            for value in item.expressions:
                expression(value, loop)
            for child in item.blocks:
                block(child, loop)
            for handler in item.handlers:
                block(handler.body, loop)
        return  # noqa: PLR1711

    block(function.body)
    return FunctionEfficiency(
        function.name,
        tuple(
            TextIndexDecision(
                target,
                values[0].source,
                "CodepointIndex" if all(value in numeric for value in values) else "TextIndex",
            )
            for target, values in accesses.items()
            if len(values) > 1 or any(value in repeated for value in values)
        ),
        tuple(LengthCacheDecision(target, source) for target, source in lengths.items()),
    )


def analyze(modules: tuple[ir.Module, ...], stable_expressions: frozenset[ir.Expression]) -> EfficiencyPlan:
    return EfficiencyPlan(
        tuple(analyze_function(function, stable_expressions) for module in modules for function in module.functions),
        tuple(
            (item, string_append(item))
            for module in modules
            for body in [module.body, *(function.body for function in module.functions)]
            for item in statements(body)
            if item.operation == "assign"
        ),
    )
