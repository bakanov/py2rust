"""Adapt record attributes and checked indexing/slicing.

Host AST adaptation only; portable semantic decisions live in rules/.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from .split_emission import split_consumer
from ..libraries import CONSTANTS
from ..memory import RuntimeParameter, runtime_argument_use
from ..rules.access import (
    index_rule,
    render_index,
    render_sequence_slice,
    render_tuple_index,
    slice_rule,
)
from ..rules.records import runtime_field_type
from ..rust_text import quote
from .values import Expr, Type

if TYPE_CHECKING:
    from ..service import ServiceCompiler


def emit_attribute(compiler: ServiceCompiler, node: ast.Attribute) -> Expr:
    if isinstance(node.value, ast.Name) and node.value.id in compiler.enums and node.attr == "__members__":
        enum = node.value.id
        entries = ", ".join(f"({quote(member)}.to_owned(), {enum}::{member})" for member in compiler.enums[enum])
        typ = Type("dict", (Type("str"), Type(enum)))
        return Expr(f"[{entries}].into_iter().collect::<{typ.rust()}>()", typ)
    if isinstance(node.value, ast.Name) and node.value.id in compiler.enums:
        if node.attr not in compiler.enums[node.value.id]:
            compiler.error("unknown enum member", node)
        return Expr(f"{node.value.id}::{node.attr}", Type(node.value.id))
    if isinstance(node.value, ast.Name) and node.value.id in compiler.modules:
        fullname = f"{node.value.id}.{node.attr}"
        if fullname in CONSTANTS:
            value = CONSTANTS[fullname]
            return Expr(
                f"{value!r}f64" if isinstance(value, float) else f"{value}i64",
                Type("float" if isinstance(value, float) else "int"),
            )
    obj = compiler.expr(node.value)
    if obj.type.name == "WebRequest":
        field_type = runtime_field_type(obj.type.name, node.attr)
        if field_type:
            if isinstance(node.value, ast.Name):
                return Expr(f"{node.value.id}.{node.attr}.clone()", compiler.named_type(field_type))
            return Expr(f"({obj.code}).{node.attr}", compiler.named_type(field_type))
    if obj.type.name == "HttpResponse" and node.attr in {"body", "status"}:
        return Expr(
            f"({obj.code}).{node.attr}",
            Type("str" if node.attr == "body" else "int"),
        )
    if (obj.type.name == "WebResponse" and node.attr in {"status", "body", "headers"}) or (
        obj.type.name == "HttpReader" and node.attr in {"status", "headers"}
    ):
        receiver = node.value.id if isinstance(node.value, ast.Name) else f"({obj.code})"
        if node.attr == "status":
            return Expr(f"({receiver}.status as i64)", Type("int"))
        typ = Type("bytes") if node.attr == "body" else compiler.named_type("dict[str,str]")
        return Expr(f"{receiver}.{node.attr}.clone()", typ)
    from .union_emission import field as union_field

    projected_union = union_field(compiler, obj, node.attr, node)
    if projected_union is not None:
        return projected_union
    optional_record = obj.type.name == "optional" and obj.type.args and obj.type.args[0].name in compiler.records
    if optional_record:
        inner = obj.type.args[0]
        obj = Expr(f'(*({obj.code}).as_ref().ok_or("expected a value")?).clone()', inner)
    if obj.type.name in compiler.records:
        fields = compiler.records[obj.type.name]
        if node.attr not in fields:
            compiler.error(f"unknown dataclass field {obj.type.name}.{node.attr} in {ast.unparse(node)}", node)
        # Project through stable local storage without owning each ancestor record.
        # The final field still crosses an owned boundary: collections/records must
        # remain independent values, whereas scalar fields can be copied directly.
        parent = compiler.local_read(node.value) if compiler.optimize and not optional_record else None
        receiver = (
            f"({parent.code})"
            if parent is not None
            else node.value.id if isinstance(node.value, ast.Name) and not optional_record else f"({obj.code})"
        )
        typ = fields[node.attr][0]
        from .union_emission import clone_dynamic

        dynamic = clone_dynamic(Expr(f"{receiver}.{node.attr}", typ))
        if dynamic is not None:
            return dynamic
        suffix = "" if compiler.optimize and typ.name in {"int", "float", "bool", "None"} else ".clone()"
        return Expr(f"{receiver}.{node.attr}{suffix}", typ)
    if obj.type.name in compiler.enums and node.attr in {"name", "value"}:
        values = compiler.enums[obj.type.name]
        arms = []
        for name, value in values.items():
            out = name if node.attr == "name" else value
            arms.append(
                f"{obj.type.name}::{name} => {quote(out) + '.to_string()' if isinstance(out, str) else str(out) + 'i64'}"
            )
        typ = Type("str" if node.attr == "name" or isinstance(next(iter(values.values())), str) else "int")
        return Expr(f"match {obj.code} {{ {', '.join(arms)} }}", typ)
    compiler.error("unsupported attribute", node)


def emit_subscript(compiler: ServiceCompiler, node: ast.Subscript) -> Expr:
    if (
        isinstance(node.value, ast.Name)
        and node.value.id in compiler.counters
        and not isinstance(node.slice, ast.Slice)
    ):
        mapping = compiler.expr(node.value)
        key = compiler.expr(node.slice, mapping.type.args[0])
        return Expr(f"({mapping.code}).get(&({key.code})).cloned().unwrap_or_default()", Type("int"))
    if (
        isinstance(node.value, ast.Name)
        and node.value.id in compiler.defaultdict_sets
        and not isinstance(node.slice, ast.Slice)
    ):
        mapping = compiler.expr(node.value)
        key = compiler.expr(node.slice, mapping.type.args[0])
        return Expr(
            f"({mapping.code}).entry({key.code}).or_insert_with(std::collections::BTreeSet::new).clone()",
            mapping.type.args[1],
        )
    if (
        isinstance(node.value, ast.Name)
        and node.value.id in compiler.defaultdicts
        and not isinstance(node.slice, ast.Slice)
    ):
        mapping = compiler.expr(node.value)
        key = compiler.expr(node.slice, mapping.type.args[0])
        return Expr(
            f"({mapping.code}).entry({key.code}).or_insert_with(Vec::new).clone()",
            mapping.type.args[1],
        )
    from .map_positions import cached_map_operation

    cached = cached_map_operation(compiler, node)
    if cached is not None:
        return cached
    constant = node.slice
    position = None
    if isinstance(constant, ast.Constant) and type(constant.value) is int:
        position = constant.value
    elif (
        isinstance(constant, ast.UnaryOp)
        and isinstance(constant.op, ast.USub)
        and isinstance(constant.operand, ast.Constant)
        and type(constant.operand.value) is int
    ):
        position = -constant.operand.value
    if position is not None and -(2**63) <= position < 2**63:
        fused = split_consumer(compiler, node.value, position)
        if fused is not None:
            return fused
    use = runtime_argument_use(RuntimeParameter("*", "shared"), [node], 0)
    obj = compiler.read_value(node.value) if use.mode == "borrow" else compiler.expr(node.value)
    if obj.type.name == "str" and isinstance(node.slice, ast.Slice):
        return compiler.string_slice(node, obj)
    if obj.type.name in {"str", "bytes", "bytearray", "list", "tuple_var"} and isinstance(node.slice, ast.Slice):
        if node.slice.step is not None:
            compiler.error("string/bytes/list slice steps are unsupported", node)
        start = compiler.expr(node.slice.lower, Type("int")).code if node.slice.lower else "0i64"
        end = compiler.expr(node.slice.upper, Type("int")).code if node.slice.upper else "i64::MAX"
        return Expr(render_sequence_slice(slice_rule(obj.type.name), compiler.reference(obj), start, end), obj.type)
    if (
        obj.type.name == "tuple"
        and position is None
        and obj.type.args
        and all(item.name in {"int", "float"} for item in obj.type.args)
        and any(item.name == "float" for item in obj.type.args)
    ):
        fields = ", ".join(f"({obj.code}).{index} as f64" for index in range(len(obj.type.args)))
        obj = Expr(f"vec![{fields}]", Type("tuple_var", (Type("float"),)))
    elif (
        obj.type.name == "tuple"
        and position is None
        and obj.type.args
        and all(item == obj.type.args[0] for item in obj.type.args)
    ):
        obj = compiler.convert(obj, Type("tuple_var", (obj.type.args[0],)), node)
    if obj.type.name == "tuple":
        if position is None or not -len(obj.type.args) <= position < len(obj.type.args):
            compiler.error(f"tuple index must be a constant in bounds: {ast.unparse(node)}", node)
        index = position % len(obj.type.args)
        field = obj.type.args[index]
        if field.name == "$json_ref":
            return Expr(f"(*({obj.code}).{index}).clone()", Type("Json"))
        return Expr(render_tuple_index(obj.code, index), field)
    if obj.type.name == "optional" and obj.type.args[0].name in {
        "str",
        "bytes",
        "bytearray",
        "list",
        "dict",
        "tuple",
        "tuple_var",
        "Json",
    }:
        obj = compiler.convert(obj, obj.type.args[0], node)
    if obj.type.name == "tuple" and position is not None:
        if not -len(obj.type.args) <= position < len(obj.type.args):
            compiler.error(f"tuple index must be a constant in bounds: {ast.unparse(node)}", node)
        index = position % len(obj.type.args)
        return Expr(render_tuple_index(obj.code, index), obj.type.args[index])
    key = compiler.expr(node.slice)
    prepared_text = isinstance(node.value, ast.Name) and node.value.id in compiler.indexed_text
    if obj.type.name == "Json":
        if key.type.name not in {"str", "int"}:
            compiler.error("JSON index must be str or int", node)
        result = Type("Json")
    elif obj.type.name == "dict":
        key = compiler.convert(key, obj.type.args[0], node)
        result = obj.type.args[1]
    else:
        key = compiler.convert(key, Type("int"), node)
        if obj.type.name == "str":
            result = Type("str")
        elif obj.type.name in {"bytes", "bytearray"}:
            result = Type("int")
        elif obj.type.name in {"list", "tuple_var"}:
            result = obj.type.args[0]
        else:
            compiler.error(f"unsupported indexed value {obj.type} in {ast.unparse(node)}", node)
    rule = index_rule(obj.type.name, key.type.name, prepared_text)
    source = compiler.reference(obj)
    if rule == "dictionary.value":
        source = obj.code
    elif rule == "text.indexed":
        source = compiler.text_index(node.value.id)
    if compiler.optimize and key.type.name == "str" and rule in {"json.key", "dictionary.value"}:
        place = compiler.argument_place(node.slice)
        if place is not None:
            key_reference = compiler.reference(place)
            if rule == "json.key":
                return Expr(f"rt::json_key({source}, {key_reference})?", result)
            return Expr(f'({source}).get({key_reference}).ok_or("missing dict key")?.clone()', result)
    from .union_emission import clone_dynamic

    dynamic = clone_dynamic(Expr(render_index(rule, source, key.code), result))
    return dynamic or Expr(render_index(rule, source, key.code), result)
