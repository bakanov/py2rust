"""Typed call validation and emission for scalar call operations."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..memory import RuntimeParameter, runtime_argument_use
from ..rules.collections import (
    length_rule,
    render_length,
)
from ..rules.conversions import render_conversion, select_conversion
from ..rules.numeric import render_unary, select_unary_rule
from ..rust_text import quote
from .values import Expr, Type
from .split_emission import split_consumer
from .json_consumers import collection_length

if TYPE_CHECKING:
    from ..service import ServiceCompiler


def emit_key_sorted(compiler: ServiceCompiler, node: ast.Call) -> Expr:
    target, key_node, reverse_nodes = node.py2rust_key_sorted
    source = compiler.expr(node.args[0])
    if source.type.name == "dict":
        source = Expr(
            f"({source.code}).keys().cloned().collect::<Vec<_>>()",
            Type("list", (source.type.args[0],)),
        )
    reverse = compiler.expr(reverse_nodes[0], Type("bool")).code if reverse_nodes else "false"
    if source.type.name not in {"list", "set", "tuple", "tuple_var"} or not source.type.args:
        compiler.error("keyed sorted requires a typed sequence", node)
    if source.type.name == "tuple" and any(item != source.type.args[0] for item in source.type.args):
        compiler.error("keyed sorted requires homogeneous tuple items", node)
    item = source.type.args[0]
    before = compiler.locals.copy()
    compiler.locals[target] = item
    key = compiler.expr(key_node)
    compiler.locals = before
    comparison = "total_cmp" if key.type.name == "float" else "cmp"
    return Expr(
        f"{{ let mut __decorated: Vec<({key.type.rust()}, {item.rust()})> = Vec::new(); "
        f"for __item in ({source.code}).into_iter() {{ let {target} = __item; "
        f"let __key = {{ {key.code} }}; __decorated.push((__key, {target})); }} "
        f"__decorated.sort_by(|left, right| if {reverse} {{ right.0.{comparison}(&left.0) }} else {{ left.0.{comparison}(&right.0) }}); "
        "let mut __result = Vec::new(); for (_, __item) in __decorated { __result.push(__item); } __result }",
        Type("list", (item,)),
    )


def emit_key_extreme(compiler: ServiceCompiler, node: ast.Call) -> Expr:
    target, key_node, name, defaults = node.py2rust_key_extreme
    source = compiler.read_value(node.args[0])
    if source.type.name == "dict":
        source = Expr(
            f"({source.code}).keys().cloned().collect::<Vec<_>>()",
            Type("list", (source.type.args[0],)),
        )
    if source.type.name == "optional" and source.type.args[0].name in {"list", "set", "tuple", "tuple_var"}:
        source = compiler.convert(source, source.type.args[0], node)
    if source.type.name not in {"list", "set", "tuple", "tuple_var"} or not source.type.args:
        compiler.error(f"keyed min/max require a typed sequence, got {source.type}", node)
    if source.type.name == "tuple" and any(item != source.type.args[0] for item in source.type.args):
        compiler.error("keyed min/max require homogeneous tuple items", node)
    item = source.type.args[0]
    before = compiler.locals.copy()
    compiler.locals[target] = item
    key = compiler.expr(key_node)
    compiler.locals = before
    comparison = "<" if name == "min" else ">"
    if defaults:
        default = compiler.expr(defaults[0])
        optional = default.type.name == "None"
        if optional:
            default = compiler.expr(defaults[0], Type("optional", (item,)))
        elif default.type != item:
            compiler.error("min/max default must match the sequence item type", node)
        result = Type("optional", (item,)) if optional else item
        selected = "Some((*__best).clone())" if optional else "(*__best).clone()"
        return Expr(
            f"'__extreme: {{ let __values = {compiler.reference(source)}; let mut __items = __values.iter(); "
            f"let Some(mut __best) = __items.next() else {{ break '__extreme {default.code}; }}; "
            f"let mut __best_key = {{ let {target} = (*__best).clone(); {key.code} }}; "
            f"for __candidate in __items {{ let __key = {{ let {target} = (*__candidate).clone(); {key.code} }}; "
            f"if __key {comparison} __best_key {{ __best = __candidate; __best_key = __key; }} }} "
            f"{selected} }}",
            result,
        )
    return Expr(
        f"{{ let __values = {compiler.reference(source)}; let mut __items = __values.iter(); "
        f'let mut __best = __items.next().ok_or("{name}() arg is an empty sequence")?; '
        f"let mut __best_key = {{ let {target} = (*__best).clone(); {key.code} }}; "
        f"for __candidate in __items {{ let __key = {{ let {target} = (*__candidate).clone(); {key.code} }}; "
        f"if __key {comparison} __best_key {{ __best = __candidate; __best_key = __key; }} }} "
        "(*__best).clone() }",
        item,
    )


def emit_sequence_extreme(compiler: ServiceCompiler, node: ast.Call, name: str) -> Expr:
    value = compiler.read_value(node.args[0])
    if value.type.name == "tuple" and value.type.args and all(item == value.type.args[0] for item in value.type.args):
        value = compiler.convert(value, Type("tuple_var", (value.type.args[0],)), node)
    if value.type.name not in {"list", "tuple_var"} or value.type.args[0].name not in {
        "int",
        "float",
        "str",
        "bool",
    }:
        compiler.error("one-argument min/max require a typed list or homogeneous tuple of ordered scalars", node)
    comparison = "<" if name == "min" else ">"
    # Borrow the collection and clone only the selected scalar. Strict
    # comparison keeps the first equal item, including signed float zero.
    return Expr(
        f"{{ let __values = {compiler.reference(value)}; let mut __items = __values.iter(); "
        f'let mut __best = __items.next().ok_or("{name}() arg is an empty sequence")?; '
        f"for __candidate in __items {{ if __candidate {comparison} __best {{ __best = __candidate; }} }} "
        "(*__best).clone() }",
        value.type.args[0],
    )


def emit_sum(compiler: ServiceCompiler, node: ast.Call) -> Expr:
    value = compiler.expr(node.args[0])
    if value.type.name not in {"list", "set", "tuple_var"} or not value.type.args:
        compiler.error("sum requires a typed numeric sequence", node)
    item = value.type.args[0]
    if item.name not in {"int", "float", "bool"}:
        compiler.error("sum requires a typed numeric sequence", node)
    result = Type("float") if item.name == "float" else Type("int")
    values = f"({value.code}).into_iter()"
    if item.name == "bool":
        values += ".map(|value| value as i64)"
    return Expr(f"{values}.sum::<{result.rust()}>()", result)


def emit_scalar_extreme(compiler: ServiceCompiler, node: ast.Call, name: str) -> Expr:
    value = compiler.expr(node.args[0])
    if value.type.name == "optional" and value.type.args[0].name in {"int", "float", "str", "bool", *compiler.enums}:
        value = compiler.convert(value, value.type.args[0], node)
    if value.type.name not in {"int", "float", "str", "bool", *compiler.enums}:
        compiler.error(f"variadic min/max require ordered scalar values, got {value.type}", node)
    for argument in node.args[1:]:
        right = compiler.expr(argument)
        if value.type.name == "int" and right.type.name == "float":
            value = compiler.convert(value, Type("float"), node)
        elif value.type.name == "float" and right.type.name == "int":
            right = compiler.convert(right, Type("float"), node)
        right = compiler.convert(right, value.type, node)
        value = Expr(f"({value.code}).{name}({right.code})", value.type)
    return value


def emit_ord(compiler: ServiceCompiler, node: ast.Call) -> Expr:
    if len(node.args) != 1:
        compiler.error("ord requires one string, bytes or bytearray argument", node)
    argument = node.args[0]
    if (
        compiler.optimize_text
        and isinstance(argument, ast.Subscript)
        and not isinstance(argument.slice, ast.Slice)
        and isinstance(argument.value, ast.Name)
        and argument.value.id in compiler.indexed_text
        and runtime_argument_use(RuntimeParameter("str", "shared"), [argument], 0).mode == "borrow"
    ):
        position = compiler.expr(argument.slice, Type("int"))
        return Expr(f"{compiler.text_index(argument.value.id)}.codepoint({position.code})?", Type("int"))
    value = compiler.read_value(node.args[0])
    if value.type.name not in {"str", "bytes", "bytearray"}:
        compiler.error("ord requires a string, bytes or bytearray", node)
    helper = "ord_text" if value.type.name == "str" else "ord_bytes"
    return Expr(f"rt::{helper}(&({value.code}))?", Type("int"))


def emit_length(compiler: ServiceCompiler, node: ast.Call) -> Expr:
    if id(node) in compiler.field_length_reads:
        return Expr(compiler.field_length_reads[id(node)], Type("int"))
    argument = node.args[0]
    fused = collection_length(compiler, argument) or split_consumer(compiler, argument)
    if fused is not None:
        return fused
    value = compiler.read_value(argument)
    local_name = argument.id if isinstance(argument, ast.Name) and argument.id in compiler.locals else ""
    if value.type.name == "Json" or value.type.name == "optional" and value.type.args[0].name == "Json":
        value = compiler.convert(value, Type("list", (Type("Json"),)), node)
    if value.type.name == "optional" and value.type.args[0].name in {
        "str",
        "bytes",
        "bytearray",
        "list",
        "set",
        "dict",
        "tuple",
        "tuple_var",
    }:
        value = compiler.convert(value, value.type.args[0], node)
    if value.type.name == "tuple":
        return Expr(f"{{ let _ = {value.code}; {len(value.type.args)}i64 }}", Type("int"))
    rule = length_rule(value.type.name, local_name in compiler.indexed_text, local_name in compiler.cached_lengths)
    if not rule:
        compiler.error(f"len requires a string or collection, got {value.type} in {ast.unparse(node)}", node)
    index = compiler.text_index(local_name) if rule == "length.text_index" else ""
    return Expr(render_length(rule, value.code, len(value.type.args), local_name, index), Type("int"))


def emit_conversion(compiler: ServiceCompiler, node: ast.Call, name: str) -> Expr:
    value = compiler.expr(node.args[0])
    if value.type.name == "optional" and value.type.args[0].name in {"Json", "str", "int", "float", "bool"}:
        value = compiler.convert(value, value.type.args[0], node)
    if value.type.name == "Json" and name in {"str", "int", "float"}:
        value = compiler.convert(value, Type(name), node)
    if name == "int" and value.type.name == "bool":
        return compiler.convert(value, Type("int"), node)
    if name == "int" and value.type.name == "float":
        return compiler.library_call("int_float", node.args, node)
    rule = select_conversion(name, value.type.name)
    if not rule.key:
        messages = {
            "float": "float conversion requires a string, int or float",
            "int": "int conversion requires a decimal string",
            "str": "str conversion supports str, int and float",
        }
        compiler.error(f"{messages[name]}; got {value.type} in {ast.unparse(node)}", node)
    if compiler.optimize and rule.form == "runtime_reference":
        use = runtime_argument_use(RuntimeParameter(value.type.name, "shared"), node.args, 0)
        place = compiler.argument_place(node.args[0], allow_place=use.mode == "borrow")
        if place is not None and place.type == value.type:
            value = place
    call = render_conversion(rule, value.code, compiler.reference(value))
    if compiler.collect_costs and rule.form in {"runtime_value", "runtime_reference"}:
        compiler.record_runtime_helper(node, rule.target)
    return Expr(
        call + ("?" if rule.fallible else ""),
        Type(rule.result),
        result_call=call if rule.fallible else None,
    )


def emit_abs(compiler: ServiceCompiler, node: ast.Call) -> Expr:
    value = compiler.expr(node.args[0])
    rule = select_unary_rule("abs", value.type.name)
    if not rule.key:
        compiler.error("abs requires an int or float", node)
    return Expr(render_unary(rule, value.code), Type(rule.result))


def emit_zip(compiler: ServiceCompiler, node: ast.Call) -> Expr:
    if len(node.args) not in {2, 3}:
        compiler.error("zip requires two sequences and optional strict", node)
    left = compiler.expr(node.args[0])
    right = compiler.expr(node.args[1])
    normalized = []
    for value in (left, right):
        if value.type.name == "Json" or value.type.name == "optional" and value.type.args[0].name == "Json":
            value = compiler.convert(value, Type("list", (Type("Json"),)), node)
        if (
            value.type.name == "tuple"
            and value.type.args
            and all(item == value.type.args[0] for item in value.type.args)
        ):
            value = compiler.convert(value, Type("tuple_var", (value.type.args[0],)), node)
        normalized.append(value)
    left, right = normalized
    if any(value.type.name not in {"list", "set", "tuple_var"} or not value.type.args for value in (left, right)):
        compiler.error("zip requires typed sequences", node)
    strict = compiler.expr(node.args[2], Type("bool")).code if len(node.args) == 3 else "false"
    item = Type("tuple", (left.type.args[0], right.type.args[0]))
    return Expr(
        f"{{ let __left = {left.code}; let __right = {right.code}; "
        f"if {strict} && __left.len() != __right.len() "
        '{ return Err("zip() argument lengths differ".into()); } '
        f"let mut __result: {Type('list', (item,)).rust()} = Vec::new(); "
        "let __length = __left.len().min(__right.len()); "
        "let mut __left_iter = __left.into_iter(); let mut __right_iter = __right.into_iter(); "
        "for __index in 0..__length { "
        "__result.push((__left_iter.next().unwrap(), __right_iter.next().unwrap())); } __result }",
        Type("list", (item,)),
    )


def emit_print(compiler: ServiceCompiler, node: ast.Call) -> Expr:
    values = [compiler.expr(a) for a in node.args]
    if any(v.type.name not in {"str", "int", "float", "bool", "Exception"} for v in values):
        compiler.error("use pretty for structured values", node)
    args = [
        (
            f'if {v.code} {{ "True" }} else {{ "False" }}'
            if v.type.name == "bool"
            else f"rt::float_to_string({v.code})?" if v.type.name == "float" else v.code
        )
        for v in values
    ]
    return Expr(
        f"println!({quote(' '.join('{}' for _ in values))}{', ' if args else ''}{', '.join(args)})",
        Type("None"),
    )
