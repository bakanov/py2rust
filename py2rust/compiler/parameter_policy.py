"""Function parameter ownership and callback ABI decisions on compiler IR.

The supported subset uses value semantics for containers/records. A parameter may
borrow when writes do not require a private owned value; owned escapes are still
materialized by the use-site policy. Resource handles keep their existing ABI.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from . import ir
from .libraries.method_effects import stable_string_method

READONLY_METHODS = frozenset(
    {
        "startswith",
        "endswith",
        "find",
        "rfind",
        "split",
        "replace",
        "strip",
        "lstrip",
        "rstrip",
        "lower",
        "upper",
        "encode",
        "decode",
        "get",
        "keys",
        "values",
        "items",
        "count",
        "index",
        "copy",
        "hex",
        "join",
        "union",
        "intersection",
        "difference",
        "symmetric_difference",
    }
)
BORROWABLE_TYPES = frozenset(
    {
        "builtins.str",
        "builtins.bytes",
        "builtins.list",
        "builtins.tuple",
        "tuple",
        "builtins.dict",
        "builtins.set",
        "py2rust.stdlib.Json",
    }
)


@dataclass(frozen=True)
class ParameterDecision:
    name: str
    mode: str
    reason: str
    line: int


@dataclass(frozen=True)
class FunctionParameters:
    function: str
    callback: bool
    parameters: tuple[ParameterDecision, ...]


def place_root(expression: ir.Expression) -> str | None:
    while expression.operation in {"field", "index", "slice"}:
        expression = expression.operands[0]
    return str(expression.value) if expression.operation == "name" else None


def write_reasons(
    function: ir.Function, candidates: set[str], initializations: frozenset[ir.Statement] = frozenset()
) -> dict[str, str]:
    reasons: dict[str, str] = {}

    def write(name: str | None, reason: str) -> None:
        if name in candidates:
            reasons[name] = reason
        return  # noqa: PLR1711 - explicit return required by repository guidelines

    def expression(value: ir.Expression) -> None:
        if value.operation == "method_call" and value.value not in READONLY_METHODS and not stable_string_method(value):
            write(place_root(value.operands[0]), "receiver_effects_not_readonly")
        elif value.operation == "intrinsic_call" and str(value.value).startswith("heapq.") and value.operands:
            write(place_root(value.operands[0]), "heap_operation_mutates_parameter")
        for operand in value.operands:
            expression(operand)
        return  # noqa: PLR1711 - explicit return required by repository guidelines

    def block(statements: tuple[ir.Statement, ...]) -> None:
        for statement in statements:
            if statement.operation in {"assign", "for", "resource_scope"} and statement not in initializations:
                write(statement.target, "parameter_or_reachable_value_written")
            elif statement.operation in {"store_field", "store_index", "delete_index"}:
                receiver = statement.expressions[0 if statement.operation == "delete_index" else 1]
                write(place_root(receiver), "parameter_or_reachable_value_written")
            for value in statement.expressions:
                expression(value)
            for child in statement.blocks:
                block(child)
            for handler in statement.handlers:
                write(handler.binding, "exception_target_rebinds_parameter")
                block(handler.body)
        return  # noqa: PLR1711 - explicit return required by repository guidelines

    block(function.body)
    return reasons


def analyze(modules: tuple[ir.Module, ...], expressions: Iterable[ir.Expression]) -> tuple[FunctionParameters, ...]:
    functions = [function for module in modules for function in module.functions]
    names = {function.name for function in functions}
    callbacks = {expr.value for expr in expressions if expr.operation == "name" and expr.value in names}
    records = {record.name for module in modules for record in module.records}
    plans = []
    for function in functions:
        candidates = {param.name for param in function.parameters if param.type.name in BORROWABLE_TYPES | records}
        reasons = write_reasons(function, candidates)
        callback = function.name in callbacks
        parameters = tuple(
            ParameterDecision(
                param.name,
                "borrow" if param.name in candidates and param.name not in reasons and not callback else "owned",
                (
                    "callback_owned_abi"
                    if callback
                    else reasons.get(
                        param.name,
                        "readonly_value_parameter" if param.name in candidates else "unchanged_parameter_abi",
                    )
                ),
                function.source.line,
            )
            for param in function.parameters
        )
        plans.append(FunctionParameters(function.name, callback, parameters))
    return tuple(plans)
