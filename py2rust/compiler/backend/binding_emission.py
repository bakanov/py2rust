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
        if typ and typ.name == "list" and isinstance(target.slice, ast.Slice):
            if target.slice.step is not None:
                compiler.error("slice deletion does not support a step", node)
            start = compiler.expr(target.slice.lower, Type("int")).code if target.slice.lower else "0i64"
            stop = compiler.expr(target.slice.upper, Type("int")).code if target.slice.upper else f"{name}.len() as i64"

            def clamp(value: str) -> str:
                return (
                    f"({{ let mut __value = {value}; if __value < 0 "
                    f"{{ __value = ({name}.len() as i64 + __value).max(0); }} "
                    f"(__value as usize).min({name}.len()) }})"
                )

            return (
                "{ let __start = " + clamp(start) + "; "
                "let __stop = " + clamp(stop) + "; "
                f"{name}.drain(__start..__stop); }}"
            )
        if typ and typ.name == "list" and not isinstance(target.slice, ast.Slice):
            key = compiler.expr(target.slice, Type("int"))
            return f"{name}.remove(rt::index({name}.len(), {key.code})?);"
        if typ and typ.name == "bytearray" and not isinstance(target.slice, ast.Slice):
            key = compiler.expr(target.slice, Type("int"))
            return render_delete(typ.name, name, key.code)
        if typ and typ.name in {"dict", "Json"}:
            key = compiler.expr(target.slice, Type("str") if typ.name == "Json" else typ.args[0])
            return render_delete(typ.name, name, key.code)
    if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Attribute):
        owner = compiler.expr(target.value)
        if owner.type.name == "list" and isinstance(target.slice, ast.Slice):
            if target.slice.step is not None:
                compiler.error("slice deletion does not support a step", node)
            start = compiler.expr(target.slice.lower, Type("int")).code if target.slice.lower else "0i64"
            stop = (
                compiler.expr(target.slice.upper, Type("int")).code
                if target.slice.upper
                else f"({owner.code}).len() as i64"
            )
            return (
                f"{{ let __start = rt::clamp_index(({owner.code}).len(), {start}); "
                f"let __stop = rt::clamp_index(({owner.code}).len(), {stop}); "
                f"({owner.code}).drain(__start..__stop); }}"
            )
        if owner.type.name == "list" and not isinstance(target.slice, ast.Slice):
            key = compiler.expr(target.slice, Type("int"))
            return f"({owner.code}).remove(rt::index(({owner.code}).len(), {key.code})?);"
        if owner.type.name in {"dict", "Json"}:
            key = compiler.expr(target.slice, Type("str") if owner.type.name == "Json" else owner.type.args[0])
            return render_delete(owner.type.name, owner.code, key.code)
    compiler.error(f"del supports a named dictionary, JSON object or bytearray and one key: {ast.unparse(node)}", node)


def emit_local(compiler: ServiceCompiler, node: ast.AnnAssign) -> str:
    name = node.target.id
    compiler.check_name(name, node)
    typ = getattr(node, "py2rust_representation_type", None) or compiler.typ(node.annotation)
    if name in compiler.locals:
        if compiler.locals[name] != typ:
            compiler.error(f"local {name} changed type from {compiler.locals[name]} to {typ}", node)
        value = compiler.expr(node.value, typ)
        return f"{name} = {value.code};"
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
        isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "__defaultdict_list"
    ):
        compiler.defaultdicts.add(name)
    if (
        isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "__defaultdict_set"
    ):
        compiler.defaultdict_sets.add(name)
    if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == "__counter":
        compiler.counters.add(name)
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
    return f"let mut {name}: {typ.rust()} = {value.code};"


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
    if isinstance(target, ast.Tuple):
        typ = compiler.typ(node.py2rust_unpack_annotation)
        names = []
        before = set(compiler.locals)

        def bind(pattern: ast.expr, item_type: Type) -> None:
            if isinstance(pattern, ast.Name):
                names.append(pattern.id)
                compiler.check_name(pattern.id, node)
                compiler.locals[pattern.id] = item_type
                return
            if (
                isinstance(pattern, ast.Tuple)
                and item_type.name == "tuple"
                and len(pattern.elts) == len(item_type.args)
            ):
                for element, element_type in zip(pattern.elts, item_type.args):
                    bind(element, element_type)
                return
            compiler.error("tuple assignment arity does not match its value", node)

        bind(target, typ)
        reassignment = any(name in before for name in names)
        value = compiler.expr(node.value, typ)
        if all(name in before for name in names):
            return f"{ast.unparse(target)} = {value.code};"
        if reassignment and all(isinstance(item, ast.Name) for item in target.elts):
            bindings = ", ".join(("_" if item.id == "_" else "mut " + item.id) for item in target.elts)
            return f"let ({bindings},): {typ.rust()} = {value.code};"

        def mutable_pattern(pattern: ast.expr) -> str:
            if isinstance(pattern, ast.Name):
                return "_" if pattern.id == "_" else "mut " + pattern.id
            if isinstance(pattern, ast.Tuple):
                return "(" + ", ".join(mutable_pattern(item) for item in pattern.elts) + ",)"
            return ast.unparse(pattern)

        return f"let {mutable_pattern(target)}: {typ.rust()} = {value.code};"
    if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Subscript):
        return compiler.nested_list_assignment(target, node.value)
    if (
        isinstance(target, ast.Subscript)
        and isinstance(target.value, ast.Attribute)
        and isinstance(target.slice, ast.Slice)
    ):
        owner = compiler.expr(target.value)
        if owner.type.name == "list":
            if target.slice.lower is not None or target.slice.upper is not None or target.slice.step is not None:
                compiler.error("slice stores currently require a full slice", node)
            value = compiler.expr(node.value, owner.type)
            return f"({owner.code}).clear(); ({owner.code}).extend({value.code});"
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
    if (
        isinstance(target, ast.Attribute)
        and isinstance(target.value, ast.Attribute)
        and isinstance(target.value.value, ast.Name)
    ):
        owner = target.value.value.id
        owner_type = compiler.locals.get(owner)
        if owner_type and owner_type.name in compiler.records:
            parent = compiler.records[owner_type.name].get(target.value.attr)
            if parent is not None and parent[0].name in compiler.records:
                field = compiler.records[parent[0].name].get(target.attr)
                if field is None:
                    compiler.error("unknown nested dataclass field: " + target.attr, target)
                value = compiler.expr(node.value, field[0])
                return f"{owner}.{target.value.attr}.{target.attr} = {value.code};"
            if parent is not None and parent[0].name == "optional" and parent[0].args[0].name in compiler.records:
                field = compiler.records[parent[0].args[0].name].get(target.attr)
                if field is None:
                    value = compiler.expr(node.value, parent[0])
                    return f"{owner}.{target.value.attr} = {value.code};"
                value = compiler.expr(node.value, field[0])
                return f'{owner}.{target.value.attr}.as_mut().ok_or("expected a value")?.{target.attr} = {value.code};'
    if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
        typ = compiler.locals.get(target.value.id)
        if typ and typ.name in compiler.records:
            field = compiler.records[typ.name].get(target.attr)
            if field is None:
                compiler.error("unknown dataclass field: " + target.attr, target)
            value = compiler.expr(node.value, field[0])
            return f"{target.value.id}.{target.attr} = {value.code};"
        if typ and typ.name == "optional" and typ.args and typ.args[0].name in compiler.records:
            field = compiler.records[typ.args[0].name].get(target.attr)
            if field is None:
                compiler.error("unknown dataclass field: " + target.attr, target)
            value = compiler.expr(node.value, field[0])
            return f'{target.value.id}.as_mut().ok_or("expected a value")?.{target.attr} = {value.code};'
    if (
        isinstance(target, ast.Attribute)
        and isinstance(target.value, ast.Subscript)
        and isinstance(target.value.value, ast.Attribute)
        and isinstance(target.value.value.value, (ast.Name, ast.Attribute))
    ):
        root = target.value.value.value
        if isinstance(root, ast.Name):
            owner = root.id
            owner_path = owner
            owner_type = compiler.locals.get(owner)
        else:
            if not isinstance(root.value, ast.Name):
                compiler.error("nested record assignment requires a named root", root)
            owner = root.value.id
            owner_path = f"{owner}.{root.attr}"
            root_type = compiler.locals.get(owner)
            owner_type = compiler.records.get(root_type.name, {}).get(root.attr, (None, None))[0] if root_type else None
        parent_name = target.value.value.attr
        owner_path += "." + parent_name
        if owner_type and owner_type.name in compiler.records:
            parent = compiler.records[owner_type.name].get(parent_name)
            if (
                parent is not None
                and parent[0].name in {"list", "dict"}
                and parent[0].args[-1].name in compiler.records
            ):
                record_type = parent[0].args[-1]
                field = compiler.records[record_type.name].get(target.attr)
                if field is None:
                    compiler.error("unknown nested dataclass field: " + target.attr, target)
                key = compiler.expr(target.value.slice, Type("int") if parent[0].name == "list" else parent[0].args[0])
                value = compiler.expr(node.value, field[0])
                if parent[0].name == "dict":
                    return f'{owner_path}.get_mut(&{key.code}).ok_or("missing record")?.{target.attr} = {value.code};'
                return (
                    f"{{ let __index = rt::index({owner_path}.len(), {key.code})?; "
                    f'{owner_path}.get_mut(__index).ok_or("missing record")?.{target.attr} = {value.code}; }}'
                )
            compiler.error(f"nested record assignment does not match {owner_type}.{parent_name}: {parent}", target)
    if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Subscript):
        owner_expression = compiler.expr(target.value.value)
        owner = ast.unparse(target.value.value)
        typ = owner_expression.type
        if typ and typ.name in {"list", "dict"}:
            record_type = typ.args[0 if typ.name == "list" else 1]
            if record_type.name in compiler.records:
                field = compiler.records[record_type.name].get(target.attr)
                if field is None:
                    compiler.error("unknown dataclass field: " + target.attr, target)
                key = compiler.expr(target.value.slice, Type("int") if typ.name == "list" else typ.args[0])
                value = compiler.expr(node.value, field[0])
                if typ.name == "list":
                    return (
                        f"{{ let __index = rt::index({owner}.len(), {key.code})?; "
                        f'{owner}.get_mut(__index).ok_or("missing record")?.{target.attr} = {value.code}; }}'
                    )
                return f'{owner}.get_mut(&{key.code}).ok_or("missing record")?.{target.attr} = {value.code};'
    if (
        isinstance(target, ast.Subscript)
        and isinstance(target.value, ast.Attribute)
        and isinstance(target.value.value, ast.Name)
    ):
        owner = target.value.value.id
        owner_type = compiler.locals.get(owner)
        if owner_type and owner_type.name in compiler.records:
            field = compiler.records[owner_type.name].get(target.value.attr)
            if field is not None and field[0].name == "dict":
                key = compiler.expr(target.slice, field[0].args[0])
                value = compiler.expr(node.value, field[0].args[1])
                return f"{owner}.{target.value.attr}.insert({key.code}, {value.code});"
            if field is not None and field[0].name == "list":
                key = compiler.expr(target.slice, Type("int"))
                value = compiler.expr(node.value, field[0].args[0])
                return (
                    f"{{ let __index = rt::index({owner}.{target.value.attr}.len(), {key.code})?; "
                    f"{owner}.{target.value.attr}[__index] = {value.code}; }}"
                )
    if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name):
        name = target.value.id
        typ = compiler.locals.get(name)
        if typ and typ.name == "bytearray" and not isinstance(target.slice, ast.Slice):
            key = compiler.expr(target.slice, Type("int"))
            value = compiler.expr(node.value, Type("int"))
            return render_index_assignment(typ.name, name, key.code, value.code)
        if typ and typ.name == "list" and isinstance(target.slice, ast.Slice):
            if target.slice.lower is not None or target.slice.upper is not None or target.slice.step is not None:
                compiler.error("slice stores currently require a full slice", node)
            value = compiler.expr(node.value, typ)
            return f"{name}.clear(); {name}.extend({value.code});"
        if typ and typ.name == "list":
            key = compiler.expr(target.slice, Type("int"))
            value = compiler.expr(node.value, typ.args[0])
            return render_index_assignment(typ.name, name, key.code, value.code)
        if typ and typ.name in {"dict", "Json"}:
            key = compiler.expr(target.slice, Type("str") if typ.name == "Json" else typ.args[0])
            value = compiler.expr(node.value, Type("Json") if typ.name == "Json" else typ.args[1])
            return render_index_assignment(typ.name, name, key.code, value.code)
        if typ and typ.name == "optional" and typ.args[0].name in {"dict", "Json"}:
            inner = typ.args[0]
            key = compiler.expr(target.slice, Type("str") if inner.name == "Json" else inner.args[0])
            value = compiler.expr(node.value, Type("Json") if inner.name == "Json" else inner.args[1])
            receiver = f'{name}.as_mut().ok_or("expected a value")?'
            return render_index_assignment(inner.name, receiver, key.code, value.code)
    if (
        isinstance(target, ast.Subscript)
        and isinstance(target.value, ast.Call)
        and isinstance(target.value.func, ast.Attribute)
        and target.value.func.attr == "setdefault"
        and isinstance(target.value.func.value, ast.Name)
        and len(target.value.args) == 2
    ):
        mapping = target.value.func.value.id
        mapping_type = compiler.locals.get(mapping)
        if mapping_type and mapping_type.name == "dict" and mapping_type.args[1].name == "dict":
            owner_key = compiler.expr(target.value.args[0], mapping_type.args[0])
            default = compiler.expr(target.value.args[1], mapping_type.args[1])
            key = compiler.expr(target.slice, mapping_type.args[1].args[0])
            value = compiler.expr(node.value, mapping_type.args[1].args[1])
            return f"{mapping}.entry({owner_key.code}).or_insert({default.code}).insert({key.code}, {value.code});"
    compiler.error(
        f"new locals need annotations; only named/list/dict assignments are supported: {ast.unparse(node)}",
        node,
    )
