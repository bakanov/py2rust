"""Adapt operators, conditionals and comparison chains.

Host AST adaptation only; portable semantic decisions live in rules/.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..memory import RuntimeParameter, runtime_argument_use
from ..rules.comparisons import render_comparison_chain
from ..rules.conditions import boolean_operator
from ..rules.numeric import (
    render_numeric,
    render_unary,
    select_numeric_rule,
    select_unary_rule,
)
from ..rust_text import quote
from .values import Expr, Type

if TYPE_CHECKING:
    from ..service import ServiceCompiler


def emit_conditional(compiler: ServiceCompiler, node: ast.IfExp, expected: Type | None) -> Expr:
    condition = compiler.expr(node.test, Type("bool"))
    left = compiler.expr(node.body, expected)
    right = compiler.expr(node.orelse, expected or left.type)
    return Expr(f"(if {condition.code} {{ {left.code} }} else {{ {right.code} }})", left.type)


def emit_unary(compiler: ServiceCompiler, node: ast.UnaryOp) -> Expr:
    if (
        isinstance(node.op, ast.USub)
        and isinstance(node.operand, ast.Constant)
        and type(node.operand.value) is int
        and node.operand.value == 2**63
    ):
        return Expr("i64::MIN", Type("int"))
    value = compiler.expr(node.operand)
    operators = {ast.Not: "not", ast.Invert: "~", ast.USub: "-"}
    rule = select_unary_rule(operators.get(type(node.op), ""), value.type.name)
    if not rule.key:
        compiler.error("unsupported unary operator", node)
    return Expr(render_unary(rule, value.code), Type(rule.result))


def emit_binary(compiler: ServiceCompiler, node: ast.BinOp, expected: Type | None) -> Expr:
    if isinstance(node.op, ast.Add):
        hint = expected if expected is not None and expected.name == "list" else None
        empty_left = isinstance(node.left, ast.List) and not node.left.elts
        if empty_left and hint is None:
            right = compiler.expr(node.right)
            left = compiler.expr(node.left, right.type if right.type.name == "list" else None)
        else:
            left = compiler.expr(node.left, hint)
            right = compiler.expr(node.right, left.type if left.type.name == "list" else None)
        if left.type.name == "list" and right.type == left.type:
            return Expr(
                f"{{ let mut __left: {left.type.rust()} = {left.code}; "
                f"let __right: {right.type.rust()} = {right.code}; "
                "__left.extend(__right); __left }",
                left.type,
            )
    else:
        left, right = compiler.expr(node.left), compiler.expr(node.right)
    set_methods = {
        ast.BitAnd: "intersection",
        ast.BitOr: "union",
        ast.Sub: "difference",
        ast.BitXor: "symmetric_difference",
    }
    if left.type == right.type and left.type.name == "set" and type(node.op) in set_methods:
        return compiler.set_operation(left, right, set_methods[type(node.op)])
    if isinstance(node.op, ast.Add) and left.type == right.type == Type("str"):
        return Expr(f'format!("{{}}{{}}", {left.code}, {right.code})', left.type)
    if isinstance(node.op, ast.Add) and left.type == right.type == Type("bytes"):
        return Expr(f"[{left.code}, {right.code}].concat()", left.type)
    operators = {
        ast.Add: "+",
        ast.Sub: "-",
        ast.Mult: "*",
        ast.Div: "/",
        ast.FloorDiv: "//",
        ast.Mod: "%",
        ast.BitAnd: "&",
        ast.BitOr: "|",
        ast.BitXor: "^",
        ast.LShift: "<<",
        ast.RShift: ">>",
    }
    rule = select_numeric_rule(operators.get(type(node.op), ""), left.type.name, right.type.name)
    if not rule.key:
        compiler.error("unsupported arithmetic combination", node)
    return Expr(render_numeric(rule, left.code, right.code), Type(rule.result))


def emit_comparison(compiler: ServiceCompiler, node: ast.Compare) -> Expr:
    operands = [node.left, *node.comparators]
    if len(node.ops) == 1:
        left = compiler.expr(operands[0])
        right = (
            compiler.read_value(operands[1])
            if isinstance(node.ops[0], (ast.In, ast.NotIn))
            else compiler.expr(operands[1])
        )
        if (
            compiler.optimize_idioms
            and not isinstance(node.ops[0], (ast.In, ast.NotIn))
            and left.type == right.type == Type("str")
        ):
            compared = []
            for index, (operand, value) in enumerate(zip(operands, (left, right))):
                if isinstance(operand, ast.Constant):
                    code = quote(operand.value)
                elif (
                    isinstance(operand, ast.Name)
                    and operand.id in compiler.locals
                    and runtime_argument_use(RuntimeParameter("str", "shared"), operands, index).mode == "borrow"
                ):
                    place = compiler.local_read(operand)
                    code = (
                        place.code
                        if operand.id in compiler.borrowed_str_parameters or operand.id in compiler.slice_views
                        else f"{place.code}.as_str()"
                    )
                else:
                    code = f"({value.code}).as_str()"
                compared.append(Expr(code, Type("str"), borrowed=True))
            left, right = compared
        return compiler.comparison(left, right, node.ops[0], operands[0], operands[1], node)
    # A middle operand is evaluated once and reused. Later operands live
    # inside nested branches so failed comparisons skip their effects.
    values = [compiler.expr(operand) for operand in operands]
    saved = [Expr(f"__compare_{index}", value.type) for index, value in enumerate(values)]
    tests = [
        compiler.comparison(saved[index], saved[index + 1], operation, operands[index], operands[index + 1], node)
        for index, operation in enumerate(node.ops)
    ]
    return Expr(
        render_comparison_chain(
            [value.code for value in values], [value.code for value in saved], [test.code for test in tests]
        ),
        Type("bool"),
    )


def emit_boolean(compiler: ServiceCompiler, node: ast.BoolOp) -> Expr:
    values = [compiler.expr(v, Type("bool")).code for v in node.values]
    return Expr(
        "(" + (" " + boolean_operator("and" if isinstance(node.op, ast.And) else "or") + " ").join(values) + ")",
        Type("bool"),
    )
