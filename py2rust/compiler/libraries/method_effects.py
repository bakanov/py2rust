"""Reviewed receiver contracts used by the memory oracle, not cost summaries."""

from .. import ir
from ..rules.strings import select_string_rule


def stable_string_method(expression: ir.Expression) -> bool:
    """The operation cannot mutate input values; operand effects need separate proof."""
    return (
        expression.operation == "method_call"
        and bool(expression.operands)
        and expression.operands[0].type == ir.ValueType("builtins.str")
        and bool(select_string_rule("str", str(expression.value), len(expression.operands) - 1).key)
    )
