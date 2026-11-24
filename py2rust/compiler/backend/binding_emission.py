"""Host AST adapters; semantic decisions and Rust templates remain in explicit rules."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..optimization import (
    string_append,
)
from ..rules.assignment import (
    render_delete,
    render_index_assignment,
    render_string_append,
)
from ..rust_text import quote
from .values import Type

if TYPE_CHECKING:
    from ..service import ServiceCompiler


def emit_delete(compiler: ServiceCompiler, node: ast.Delete) -> str:
    target = node.targets[0]
    if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name):
        name = target.value.id
        typ = compiler.locals.get(name)
        if typ and typ.name == "bytearray" and not isinstance(target.slice, ast.Slice):
            key = compiler.expr(target.slice, Type("int"))
            return render_delete(typ.name, name, key.code)
        if typ and typ.name in {"dict", "Json"}:
            key = compiler.expr(target.slice, Type("str") if typ.name == "Json" else typ.args[0])
            return render_delete(typ.name, name, key.code)
    compiler.error("del supports a named dictionary, JSON object or bytearray and one key", node)


def emit_local(compiler: ServiceCompiler, node: ast.AnnAssign) -> str:
    name = node.target.id
    compiler.check_name(name, node)
    if name in compiler.locals:
        compiler.error("use assignment to update an existing local", node)
    typ = compiler.typ(node.annotation)
    if name in compiler.sequence_views:
        compiler.record_decision(node, "slice", "borrow", "readonly_sequence_slice_of_stable_parameter")
        value = compiler.local_read(node.value)
        if value is None or value.type != typ:
            compiler.error("sequence slice view requires a matching stable source", node)
        compiler.locals[name] = typ
        item = "u8" if typ.name in {"bytes", "bytearray"} else typ.args[0].rust()
        return f"let {name}: &[{item}] = {compiler.reference(value)};"
    if name in compiler.array_views:
        compiler.record_decision(node, "json_array", "borrow", "readonly_array_of_stable_json_parameter")
        value = compiler.local_read(node.value)
        if value is None or value.type != typ:
            compiler.error("JSON array view requires a stable JSON source", node)
        compiler.locals[name] = typ
        return f"let {name}: &[rt::Json] = {compiler.reference(value)};"
    if name in compiler.slice_views:
        compiler.record_decision(node, "slice", "borrow", "readonly_string_slice_of_stable_parameter")
        obj = compiler.read_value(node.value.value)
        if obj.type != Type("str"):
            compiler.error("string slice view requires str", node)
        value = compiler.string_slice(node.value, obj, view=True)
        compiler.locals[name] = typ
        return f"let {name}: &str = {value.code};"
    value = compiler.expr(node.value, typ)
    compiler.record_owned_boundary(node.value)
    compiler.locals[name] = typ
    return f"let {compiler.binding(name)}: {typ.rust()} = {value.code};"


def emit_assignment(compiler: ServiceCompiler, node: ast.Assign) -> str:
    target = node.targets[0]
    if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Subscript):
        return compiler.nested_list_assignment(target, node.value)
    if isinstance(target, ast.Name) and target.id in compiler.locals:
        plan = string_append(target.id, compiler.locals[target.id].name, node.value) if compiler.optimize else None
        if plan is not None:
            compiler.record_decision(node, "string_append", "builder", plan.reason)
            suffix = compiler.expr(plan.suffix, Type("str"))  # Validate even literal fast paths.
            if isinstance(plan.suffix, ast.Constant) and isinstance(plan.suffix.value, str):
                return render_string_append(plan.target, quote(plan.suffix.value), True)
            # Complete RHS evaluation first. A throw leaves the destination
            # unchanged, and self-references observe its previous contents.
            return render_string_append(plan.target, suffix.code, False)
        value = compiler.expr(node.value, compiler.locals[target.id])
        compiler.record_owned_boundary(node.value)
        return f"{target.id} = {value.code};"
    if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
        typ = compiler.locals.get(target.value.id)
        if typ and typ.name in compiler.records:
            field = compiler.records[typ.name].get(target.attr)
            if field is None:
                compiler.error("unknown dataclass field: " + target.attr, target)
            value = compiler.expr(node.value, field[0])
            return f"{target.value.id}.{target.attr} = {value.code};"
    if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name):
        name = target.value.id
        typ = compiler.locals.get(name)
        if typ and typ.name == "bytearray" and not isinstance(target.slice, ast.Slice):
            key = compiler.expr(target.slice, Type("int"))
            value = compiler.expr(node.value, Type("int"))
            return render_index_assignment(typ.name, name, key.code, value.code)
        if typ and typ.name == "list":
            key = compiler.expr(target.slice, Type("int"))
            value = compiler.expr(node.value, typ.args[0])
            return render_index_assignment(typ.name, name, key.code, value.code)
        if typ and typ.name in {"dict", "Json"}:
            key = compiler.expr(target.slice, Type("str") if typ.name == "Json" else typ.args[0])
            value = compiler.expr(node.value, Type("Json") if typ.name == "Json" else typ.args[1])
            return render_index_assignment(typ.name, name, key.code, value.code)
    compiler.error(
        "new locals need annotations; only named/list/dict assignments are supported",
        node,
    )
