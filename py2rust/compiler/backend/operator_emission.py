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
from .json_consumers import borrowed_string_membership, key_membership

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
    if value.type.name == "optional" and value.type.args[0].name in {"int", "float"}:
        value = compiler.convert(value, value.type.args[0], node)
    if isinstance(node.op, ast.UAdd) and value.type.name in {"int", "float"}:
        return value
    operators = {ast.Not: "not", ast.Invert: "~", ast.USub: "-"}
    rule = select_unary_rule(operators.get(type(node.op), ""), value.type.name)
    if not rule.key:
        compiler.error(f"unsupported unary operator {type(node.op).__name__} on {value.type}", node)
    return Expr(render_unary(rule, value.code), Type(rule.result))


def string_concatenation(compiler: ServiceCompiler, node: ast.BinOp) -> Expr | None:
    """Format one string chain without allocating every intermediate prefix."""
    if not compiler.optimize or not compiler.optimize_idioms or not isinstance(node.op, ast.Add):
        return None
    operands: list[ast.AST] = []

    def gather(value: ast.AST) -> None:
        if isinstance(value, ast.BinOp) and isinstance(value.op, ast.Add):
            gather(value.left)
            gather(value.right)
        else:
            operands.append(value)
        return

    gather(node)
    values = [compiler.expr(operand) for operand in operands]
    if not all(value.type == Type("str") for value in values):
        return None
    arguments = []
    for index, (operand, value) in enumerate(zip(operands, values)):
        use = runtime_argument_use(RuntimeParameter("str", "shared"), operands, index)
        place = compiler.argument_place(operand, allow_place=use.mode == "borrow")
        arguments.append(compiler.reference(place) if place is not None else value.code)
    compiler.record_decision(node, "string_concatenation", "fused", "typed_string_operands_in_source_order")
    return Expr(f'format!("{"{}" * len(arguments)}", {", ".join(arguments)})', Type("str"))


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
        if (
            left.type.name == "list"
            and left.type.args[0].name == "optional"
            and right.type.name == "list"
            and right.type.args[0] == left.type.args[0].args[0]
        ):
            right = compiler.convert(right, left.type, node)
        if left.type.name == "list" and right.type == left.type:
            return Expr(
                f"{{ let mut __left: {left.type.rust()} = {left.code}; "
                f"let __right: {right.type.rust()} = {right.code}; "
                "__left.extend(__right); __left }",
                left.type,
            )
    else:
        left, right = compiler.expr(node.left), compiler.expr(node.right)
    if left.type.name == "union" and right.type.name in {"int", "float"}:
        left = compiler.convert(left, right.type, node)
    elif right.type.name == "union" and left.type.name in {"int", "float"}:
        right = compiler.convert(right, left.type, node)
    if left.type.name == "int" and right.type.name == "float":
        left = compiler.convert(left, Type("float"), node)
    elif right.type.name == "int" and left.type.name == "float":
        right = compiler.convert(right, Type("float"), node)
    if (
        left.type.name == "optional"
        and left.type.args[0].name in {"int", "float"}
        and right.type.name in {"int", "float"}
    ):
        target = Type("float") if left.type.args[0].name == "float" or right.type.name == "float" else right.type
        left = compiler.convert(left, target, node)
        right = compiler.convert(right, target, node)
    elif (
        right.type.name == "optional"
        and right.type.args[0].name in {"int", "float"}
        and left.type.name in {"int", "float"}
    ):
        target = Type("float") if right.type.args[0].name == "float" or left.type.name == "float" else left.type
        left = compiler.convert(left, target, node)
        right = compiler.convert(right, target, node)
    if left.type.name == "Json" and right.type.name in {"int", "float"}:
        left = compiler.convert(left, right.type, node)
    elif right.type.name == "Json" and left.type.name in {"int", "float"}:
        right = compiler.convert(right, left.type, node)
    if left.type.name == "bool" and right.type.name in {"int", "float"}:
        left = compiler.convert(left, right.type, node)
    elif right.type.name == "bool" and left.type.name in {"int", "float"}:
        right = compiler.convert(right, left.type, node)
    if (
        isinstance(node.op, ast.Add)
        and left.type.name in {"list", "tuple_var"}
        and right.type.name
        in {
            "list",
            "tuple",
            "tuple_var",
        }
    ):
        if (
            right.type.name == "tuple"
            and right.type.args
            and all(item == right.type.args[0] for item in right.type.args)
        ):
            right = compiler.convert(right, Type("tuple_var", (right.type.args[0],)), node)
        if right.type.name in {"list", "tuple_var"}:
            right = compiler.convert(right, left.type, node)
            return Expr(
                f"{{ let mut __left: {left.type.rust()} = {left.code}; "
                f"let __right: {right.type.rust()} = {right.code}; "
                "__left.extend(__right); __left }",
                left.type,
            )
    if (
        isinstance(node.op, ast.BitOr)
        and left.type.name == "dict"
        and left.type == right.type
        and left.type.args[1].name == "int"
    ):
        return Expr(
            f"{{ let mut __result = {left.code}; for (__key, __value) in {right.code} {{ "
            "*__result.entry(__key).or_insert(0) += __value; } __result }",
            left.type,
        )
    if (
        left.type.name == "list"
        and right.type.name == "set"
        and type(node.op)
        in {
            ast.Sub,
            ast.BitAnd,
            ast.BitOr,
            ast.BitXor,
        }
    ):
        left = Expr(
            f"({left.code}).into_iter().collect::<std::collections::BTreeSet<_>>()",
            right.type,
        )
    set_methods = {
        ast.BitAnd: "intersection",
        ast.BitOr: "union",
        ast.Sub: "difference",
        ast.BitXor: "symmetric_difference",
    }
    if left.type == right.type == Type("bool") and type(node.op) in {ast.BitAnd, ast.BitOr, ast.BitXor}:
        operator = {ast.BitAnd: "&", ast.BitOr: "|", ast.BitXor: "^"}[type(node.op)]
        return Expr(f"({left.code}) {operator} ({right.code})", Type("bool"))
    if left.type == right.type and left.type.name == "set" and type(node.op) in set_methods:
        return compiler.set_operation(left, right, set_methods[type(node.op)])
    if isinstance(node.op, ast.Add) and left.type == right.type == Type("str"):
        concatenated = string_concatenation(compiler, node)
        if concatenated is not None:
            return concatenated
        return Expr(f'format!("{{}}{{}}", {left.code}, {right.code})', left.type)
    if (
        isinstance(node.op, ast.Add)
        and left.type.name in {"bytes", "bytearray"}
        and right.type.name in {"bytes", "bytearray"}
    ):
        return Expr(f"[{left.code}, {right.code}].concat()", left.type)
    if (
        isinstance(node.op, ast.Mult)
        and left.type.name == "tuple"
        and right.type.name == "int"
        and left.type.args
        and all(item == left.type.args[0] for item in left.type.args)
    ):
        return Expr(
            f"vec![({left.code}).0; std::cmp::max({right.code}, 0) as usize]",
            Type("tuple_var", left.type.args[:1]),
        )
    if (
        isinstance(node.op, ast.Mult)
        and right.type.name == "tuple"
        and left.type.name == "int"
        and right.type.args
        and all(item == right.type.args[0] for item in right.type.args)
    ):
        return Expr(
            f"vec![({right.code}).0; std::cmp::max({left.code}, 0) as usize]",
            Type("tuple_var", right.type.args[:1]),
        )
    if isinstance(node.op, ast.Mult) and left.type.name in {"list", "tuple_var"} and right.type.name == "int":
        return Expr(f"({left.code}).repeat(std::cmp::max({right.code}, 0) as usize)", left.type)
    if isinstance(node.op, ast.Mult) and right.type.name in {"list", "tuple_var"} and left.type.name == "int":
        return Expr(f"({right.code}).repeat(std::cmp::max({left.code}, 0) as usize)", right.type)
    if isinstance(node.op, ast.Mult) and left.type.name in {"bytes", "bytearray"} and right.type.name == "int":
        return Expr(f"({left.code}).repeat(std::cmp::max({right.code}, 0) as usize)", left.type)
    if isinstance(node.op, ast.Mult) and right.type.name in {"bytes", "bytearray"} and left.type.name == "int":
        return Expr(f"({right.code}).repeat(std::cmp::max({left.code}, 0) as usize)", right.type)
    if isinstance(node.op, ast.Pow) and left.type.name == "int" and right.type.name == "int":
        return Expr(
            f'{{ let __exponent = {right.code}; if __exponent < 0 {{ return Err("negative integer exponent".into()); }} '
            f'({left.code}).checked_pow(__exponent as u32).ok_or("integer power overflow")? }}',
            Type("int"),
        )
    if isinstance(node.op, ast.Pow) and left.type.name == "float" and right.type.name in {"int", "float"}:
        exponent = compiler.convert(right, Type("float"), node)
        return Expr(f"({left.code}).powf({exponent.code})", Type("float"))
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
        compiler.error(
            f"unsupported arithmetic combination: {left.type} {type(node.op).__name__} {right.type} "
            f"in {ast.unparse(node)}",
            node,
        )
    return Expr(render_numeric(rule, left.code, right.code), Type(rule.result))


def emit_comparison(compiler: ServiceCompiler, node: ast.Compare) -> Expr:
    fused = borrowed_string_membership(compiler, node) or key_membership(compiler, node)
    if fused is not None:
        return fused
    operands = [node.left, *node.comparators]
    if len(node.ops) == 1:
        if isinstance(node.ops[0], (ast.Is, ast.IsNot)) and any(
            isinstance(operand, ast.Constant) and operand.value is None for operand in operands
        ):
            first_is_none = isinstance(operands[0], ast.Constant) and operands[0].value is None
            other = compiler.read_value(operands[1] if first_is_none else operands[0])
            from .union_emission import identity

            union_identity = identity(compiler, other, node.ops[0])
            if union_identity is not None:
                return union_identity
            if other.type.name == "optional":
                method = "is_none" if isinstance(node.ops[0], ast.Is) else "is_some"
                return Expr(f"({other.code}).{method}()", Type("bool"))
        null_identity = (
            compiler.optimize
            and isinstance(node.ops[0], (ast.Is, ast.IsNot))
            and any(isinstance(operand, ast.Constant) and operand.value is None for operand in operands)
        )
        left = compiler.read_value(operands[0]) if null_identity else compiler.expr(operands[0])
        right = (
            compiler.read_value(operands[1])
            if null_identity or isinstance(node.ops[0], (ast.In, ast.NotIn))
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
                elif (
                    isinstance(operand, (ast.Attribute, ast.Subscript))
                    and runtime_argument_use(RuntimeParameter("str", "shared"), operands, index).mode == "borrow"
                    and (place := compiler.local_read(operand)) is not None
                    and place.type == Type("str")
                ):
                    # A checked string projection can be compared in place.
                    # AsRef works for both String-backed and str-backed views.
                    code = f"AsRef::<str>::as_ref({compiler.reference(place)})"
                    compiler.record_decision(operand, "string_comparison", "borrow", "stable_projected_string")
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
    first = compiler.expr(node.values[0])
    if first.type.name != "bool":
        value = first
        for operand in node.values[1:]:
            right = compiler.expr(operand)
            if isinstance(node.op, ast.Or) and value.type.name == "optional" and right.type == value.type.args[0]:
                return Expr(
                    f"match ({value.code}) {{ Some(__value) => __value, None => {right.code} }}",
                    right.type,
                )
            if right.type != value.type:
                remaining = [value, right]
                remaining.extend(compiler.expr(item) for item in node.values[node.values.index(operand) + 1 :])
                tests = [compiler.convert(item, Type("bool"), node).code for item in remaining]
                return Expr(
                    "("
                    + (" " + boolean_operator("and" if isinstance(node.op, ast.And) else "or") + " ").join(tests)
                    + ")",
                    Type("bool"),
                )
            truth = {
                "int": f"({value.code}) != 0",
                "float": f"({value.code}) != 0.0",
                "str": f"!({value.code}).is_empty()",
                "bytes": f"!({value.code}).is_empty()",
                "bytearray": f"!({value.code}).is_empty()",
                "list": f"!({value.code}).is_empty()",
                "set": f"!({value.code}).is_empty()",
                "dict": f"!({value.code}).is_empty()",
                "tuple_var": f"!({value.code}).is_empty()",
                "optional": f"({value.code}).is_some()",
            }.get(value.type.name)
            if truth is None:
                compiler.error(f"short-circuit operand does not support truthiness: {value.type}", node)
            temporary = f"__boolean_{id(operand)}"
            truth = truth.replace(value.code, temporary)
            if isinstance(node.op, ast.Or):
                code = f"if {truth} {{ {temporary} }} else {{ {right.code} }}"
            else:
                code = f"if {truth} {{ {right.code} }} else {{ {temporary} }}"
            value = Expr(f"{{ let {temporary} = {value.code}; {code} }}", value.type)
        return value
    values = [first.code]
    values.extend(compiler.expr(v, Type("bool")).code for v in node.values[1:])
    return Expr(
        "(" + (" " + boolean_operator("and" if isinstance(node.op, ast.And) else "or") + " ").join(values) + ")",
        Type("bool"),
    )
