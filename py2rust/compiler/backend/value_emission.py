"""Adapt literals, local reads and collection constructors.

Host AST adaptation only; portable semantic decisions live in rules/.
"""

from __future__ import annotations

import ast
import math
from typing import TYPE_CHECKING

from ..rust_text import quote
from .values import Expr, Type

if TYPE_CHECKING:
    from ..service import ServiceCompiler


def emit_literal(compiler: ServiceCompiler, node: ast.Constant, expected: Type | None) -> Expr:
    value = node.value
    name = type(value).__name__ if value is not None else "None"
    if name == "str":
        return Expr(
            "String::new()" if compiler.optimize_idioms and not value else quote(value) + ".to_string()", Type(name)
        )
    if name == "bytes":
        if not value:
            return Expr("Vec::<u8>::new()", Type(name))
        return Expr("vec![" + ",".join(f"{n}u8" for n in value) + "]", Type(name))
    if name == "bool":
        return Expr(str(value).lower(), Type(name))
    if name == "int" and -(2**63) <= value < 2**63:
        return Expr(f"{value}i64", Type(name))
    if name == "float" and math.isfinite(value):
        return Expr(f"{value!r}f64", Type(name))
    if value is None:
        return Expr(
            "serde_json::Value::Null" if expected == Type("Json") else "()",
            Type("Json") if expected == Type("Json") else Type("None"),
        )
    compiler.error(f"unsupported literal or out-of-range number: {value!r}", node)


def emit_name(compiler: ServiceCompiler, node: ast.Name) -> Expr:
    if node.id in compiler.constant_nodes and node.id not in compiler.locals:
        return compiler.materialize_constant(node.id)
    if node.id in compiler.enums and node.id not in compiler.locals:
        members = ", ".join(f"{node.id}::{member}" for member in compiler.enums[node.id])
        return Expr(f"vec![{members}]", Type("list", (Type(node.id),)))
    value_type = getattr(node, "py2rust_value_type", None)
    if node.id in compiler.functions and value_type is not None and value_type.name == "callable":
        from .legacy_adapter import annotation

        return Expr(node.id, compiler.typ(annotation(value_type)))
    if node.id not in compiler.locals:
        compiler.error(
            f"undefined variable: {node.id} at {getattr(node, 'source_path', '<unknown>')}:{node.lineno}", node
        )
    typ = compiler.locals[node.id]
    if node.id in compiler.mutable_parameters:
        return Expr(f"(*{node.id}).clone()", typ)
    if compiler.comprehension_depth == 0 and compiler.can_move_local(node, typ):
        return Expr(node.id, typ)
    from .union_emission import clone_dynamic

    dynamic = clone_dynamic(Expr(node.id, typ))
    if dynamic is not None:
        return dynamic
    if (
        node.id in compiler.borrowed_parameters
        or node.id in compiler.slice_views
        or node.id in compiler.array_views
        or node.id in compiler.sequence_views
    ):
        owned = (
            f"{node.id}.to_owned()"
            if typ.name == "str"
            else (
                f"{node.id}.to_vec()"
                if typ.name in {"bytes", "bytearray", "list", "tuple_var"}
                else f"(*{node.id}).clone()"
            )
        )
        return Expr(owned, typ)
    if typ.name == "callable" and node.id in compiler.functions:
        return Expr(node.id, typ)
    if typ.name in {"HttpServer", "callable"}:
        return Expr(node.id, typ)
    return Expr(node.id if typ.name in {"int", "float", "bool"} else f"{node.id}.clone()", typ)


def emit_sequence(compiler: ServiceCompiler, node: ast.List | ast.Set | ast.Tuple, expected: Type | None) -> Expr:
    if expected and expected.name == "optional":
        value = compiler.expr(node, expected.args[0])
        return Expr(f"Some({value.code})", expected)
    kind = {ast.List: "list", ast.Set: "set", ast.Tuple: "tuple"}[type(node)]
    if expected and expected.name == "union":
        variants = [
            variant
            for variant in expected.args
            if variant.name == kind and (kind != "tuple" or len(variant.args) == len(node.elts))
        ]
        if len(variants) != 1:
            compiler.error(f"collection does not select one union variant: {expected}", node)
        expected = variants[0]
    if expected and expected.name == "Json":
        if kind == "set":
            compiler.error("sets are not JSON serializable", node)
        values = [compiler.expr(x, Type("Json")).code for x in node.elts]
        return Expr(f"serde_json::Value::Array(vec![{', '.join(values)}])", expected)
    if kind == "tuple" and expected and expected.name in {"list", "set", "tuple_var"}:
        kind = expected.name
    elif kind == "tuple" and expected and expected.name == "tuple_var":
        kind = "tuple_var"
    if expected and (expected.name != kind or (kind == "tuple" and len(expected.args) != len(node.elts))):
        compiler.error(f"collection shape does not match annotation {expected}: {ast.unparse(node)}", node)
    elements = [
        compiler.expr(
            x,
            (expected.args[i if kind == "tuple" else 0] if expected and expected.args else None),
        )
        for i, x in enumerate(node.elts)
    ]
    if not elements and (not expected or expected.name != kind):
        compiler.error(
            f"empty collection requires a type annotation at "
            f"{getattr(node, 'source_path', '<unknown>')}:{node.lineno}: {ast.unparse(node)}",
            node,
        )
    types = tuple(x.type for x in elements) if kind == "tuple" else ((elements[0].type,) if elements else expected.args)
    if kind != "tuple" and any(x.type != types[0] for x in elements):
        compiler.error("collection elements must have one type", node)
    values = ", ".join(x.code for x in elements)
    code = f"({values},)" if kind == "tuple" else f"vec![{values}]"
    if kind == "set":
        code = (
            f"{{ let mut __result = std::collections::BTreeSet::new(); "
            f"for __item in {code}.into_iter() {{ __result.insert(__item); }} __result }}"
        )
    return Expr(code, Type(kind, types))


def emit_mapping(compiler: ServiceCompiler, node: ast.Dict, expected: Type | None) -> Expr:
    if any(k is None for k in node.keys):
        compiler.error("dict unpacking is unsupported", node)
    if expected == Type("Json"):
        pairs = [
            (compiler.expr(k, Type("str")).code, compiler.expr(v, Type("Json")).code)
            for k, v in zip(node.keys, node.values)
        ]
        code = ", ".join(f"({k}, {v})" for k, v in pairs)
        return Expr(
            f"serde_json::Value::Object([{code}].into_iter().collect())",
            expected,
        )
    if expected and expected.name != "dict":
        compiler.error("dict literal needs a dict or Json annotation", node)
    pairs = [
        (
            compiler.expr(k, expected.args[0] if expected else None),
            compiler.expr(v, expected.args[1] if expected else None),
        )
        for k, v in zip(node.keys, node.values)
    ]
    if not pairs and not expected:
        compiler.error("empty dict requires a type annotation", node)
    types = (pairs[0][0].type, pairs[0][1].type) if pairs else expected.args
    if any((k.type, v.type) != types for k, v in pairs):
        compiler.error("dict keys and values need homogeneous types", node)
    if not compiler.hashable(types[0]):
        compiler.error("dictionary requires immutable hashable keys", node)
    code = ", ".join(f"({k.code}, {v.code})" for k, v in pairs)
    return Expr(
        f"[{code}].into_iter().collect::<indexmap::IndexMap<_, _>>()",
        Type("dict", types),
    )
