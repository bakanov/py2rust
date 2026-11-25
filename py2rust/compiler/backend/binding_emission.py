"""Host AST adapters; semantic decisions and Rust templates remain in explicit rules."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..memory import place_root
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
from .counter_emission import emit_counter_update

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
    typ = getattr(node, "py2rust_representation_type", None) or compiler.typ(node.annotation)
    from .record_cursors import bind_record_cursor

    cursor = bind_record_cursor(compiler, node, typ)
    if cursor is not None:
        return cursor
    from .field_moves import emit_field_move

    moved = emit_field_move(compiler, node, typ)
    if moved is not None:
        return moved
    from .projected_strings import bind_projected_string

    projected = bind_projected_string(compiler, node, typ)
    if projected is not None:
        return projected
    if name in compiler.sequence_views:
        compiler.record_decision(node, "slice", "borrow", "readonly_sequence_slice_of_stable_parameter")
        value = compiler.local_read(node.value)
        if value is None or value.type != typ:
            compiler.error("sequence slice view requires a matching stable source", node)
        compiler.locals[name] = typ
        item = "u8" if typ.name in {"bytes", "bytearray"} else typ.args[0].rust()
        return f"let {name}: &[{item}] = {compiler.reference(value)};"
    if name in compiler.json_text_views:
        source = compiler.local_read(node.value.args[0])
        if source is None or source.type != Type("Json"):
            compiler.error("JSON string view requires a stable JSON source", node)
        compiler.locals[name] = typ
        compiler.borrowed_parameters.add(name)
        compiler.borrowed_str_parameters.add(name)
        compiler.record_decision(node, "json_string", "borrow", "readonly_string_of_stable_json_backing")
        if compiler.collect_costs:
            compiler.record_runtime_helper(node.value, "json_string_ref")
        return f"let {name}: &str = rt::json_string_ref({compiler.reference(source)})?;"
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
    if (
        compiler.optimize
        and compiler.optimize_json_views
        and typ == Type("Json")
        and name not in compiler.mutable_bindings
        and place_root(node.value) in compiler.borrowed_parameters
    ):
        place = compiler.local_read(node.value)
        if place is not None and place.type == typ:
            compiler.locals[name] = typ
            compiler.borrowed_parameters.add(name)
            compiler.record_decision(node, "json_binding", "borrow", "readonly_projection_of_borrowed_source")
            return f"let {name}: &rt::Json = {compiler.reference(place)};"
    value = compiler.expr(node.value, typ)
    compiler.record_owned_boundary(node.value)
    compiler.locals[name] = typ
    if (
        compiler.optimize
        and compiler.optimize_idioms
        and name not in compiler.mutable_bindings
        and typ.name == "dict"
        and typ.args[0] == Type("str")
        and typ.args[1].name in {"str", "int", "bool"}
        and isinstance(node.value, ast.Dict)
        and len(node.value.keys) >= 4
        and all(
            isinstance(item, ast.Constant) and type(item.value) in {str, int, bool}
            for item in [*node.value.keys, *node.value.values]
        )
    ):
        # Literal construction cannot fail or observe state. The binding/write
        # plan proves the table is read-only; escaping owned uses still clone.
        compiler.borrowed_parameters.add(name)
        compiler.record_decision(node, "constant_mapping", "shared", "readonly_scalar_literal_table")
        return (
            f"static __table_{name}: std::sync::OnceLock<{typ.rust()}> = std::sync::OnceLock::new(); "
            f"let {name}: &{typ.rust()} = __table_{name}.get_or_init(|| {value.code});"
        )
    return f"let {compiler.binding(name)}: {typ.rust()} = {value.code};"


def emit_assignment(compiler: ServiceCompiler, node: ast.Assign) -> str:
    from .map_positions import cached_map_operation

    cached = cached_map_operation(compiler, node)
    if cached is not None:
        return cached.code
    from .record_cursors import advance_record_cursor

    cursor = advance_record_cursor(compiler, node)
    if cursor is not None:
        return cursor
    counter = emit_counter_update(compiler, node)
    if counter is not None:
        return counter
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
