"""Scalar replacement for nonescaping lists of immutable JSON object views.

Checked frontend types select fields; all list/item uses are audited. Only JSON
paths rooted in borrowed parameters may remain borrowed. Dynamic keys, escaping
objects, mutation, mixed shapes and unknown types keep ordinary JSON lowering.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..memory import argument_effects_unknown, place_root
from .values import Type

if TYPE_CHECKING:
    from ..service import ServiceCompiler


def prepare_record_views(compiler: ServiceCompiler, function: ast.FunctionDef) -> None:
    if not compiler.optimize or not compiler.optimize_json_views or not compiler.optimize_iteration:
        return
    parents = {id(child): parent for parent in ast.walk(function) for child in ast.iter_child_nodes(parent)}
    nodes = list(ast.walk(function))
    for declaration in nodes:
        if not (
            isinstance(declaration, ast.AnnAssign)
            and isinstance(declaration.target, ast.Name)
            and isinstance(declaration.value, ast.List)
            and declaration.value.elts
            and compiler.typ(declaration.annotation) == Type("list", (Type("Json"),))
        ):
            continue
        name = declaration.target.id
        constructors = list(declaration.value.elts)
        consumers = []
        valid = True
        for use in nodes:
            if not isinstance(use, ast.Name) or use.id != name or use is declaration.target:
                continue
            parent = parents.get(id(use))
            if isinstance(parent, ast.For) and parent.iter is use and isinstance(parent.target, ast.Name):
                consumers.append(parent)
            elif isinstance(parent, ast.Attribute) and parent.value is use and parent.attr == "append":
                call = parents.get(id(parent))
                if isinstance(call, ast.Call) and len(call.args) == 1 and not call.keywords:
                    constructors.append(call.args[0])
                else:
                    valid = False
            else:
                valid = False
        if not valid or len(consumers) != 1:
            continue
        loop = consumers[0]
        if any(getattr(value, "lineno", 0) >= loop.lineno for value in constructors):
            continue
        if not all(isinstance(value, ast.Dict) for value in constructors):
            continue
        first = constructors[0]
        if not 1 <= len(first.keys) <= 12 or not all(
            isinstance(key, ast.Constant) and isinstance(key.value, str) for key in first.keys
        ):
            continue
        keys = [key.value for key in first.keys]
        if len(set(keys)) != len(keys):
            continue
        fields = []
        for value in first.values:
            checked = getattr(value, "py2rust_value_type", None)
            kind = checked.name.removeprefix("builtins.").removeprefix("py2rust.stdlib.") if checked else ""
            if kind not in {"str", "int", "bool", "Json"}:
                valid = False
            fields.append(Type("$json_ref" if kind == "Json" else kind))
        if not valid or not any(field.name == "$json_ref" for field in fields):
            continue
        for constructor in constructors:
            if len(constructor.keys) != len(keys) or any(
                not isinstance(key, ast.Constant) or key.value != expected
                for key, expected in zip(constructor.keys, keys)
            ):
                valid = False
                break
            for value, expected in zip(constructor.values, fields):
                checked = getattr(value, "py2rust_value_type", None)
                kind = checked.name.removeprefix("builtins.").removeprefix("py2rust.stdlib.") if checked else ""
                if kind != ("Json" if expected.name == "$json_ref" else expected.name):
                    valid = False
                if expected.name == "$json_ref" and (
                    place_root(value) not in compiler.borrowed_parameters
                    or not isinstance(value, (ast.Name, ast.Attribute, ast.Subscript))
                    or argument_effects_unknown(value)
                ):
                    valid = False
        projections = []
        for use in nodes:
            if not isinstance(use, ast.Name) or use.id != loop.target.id or use is loop.target:
                continue
            parent = parents.get(id(use))
            if (
                isinstance(parent, ast.Subscript)
                and parent.value is use
                and isinstance(parent.ctx, ast.Load)
                and isinstance(parent.slice, ast.Constant)
                and parent.slice.value in keys
            ):
                projections.append(parent)
            else:
                valid = False
        if not valid:
            continue
        # Commit only after every use and constructor has passed the proof.
        for constructor in constructors:
            for value in constructor.values:
                value.py2rust_json_coercion = False
            replacement = ast.copy_location(ast.Tuple(elts=constructor.values, ctx=ast.Load()), constructor)
            parent = parents[id(constructor)]
            for field, value in ast.iter_fields(parent):
                if isinstance(value, list):
                    setattr(parent, field, [replacement if item is constructor else item for item in value])
                elif value is constructor:
                    setattr(parent, field, replacement)
        declaration.py2rust_representation_type = Type("list", (Type("tuple", tuple(fields)),))
        for projection in projections:
            projection.slice = ast.copy_location(ast.Constant(keys.index(projection.slice.value)), projection.slice)
        compiler.record_decision(
            declaration, "json_record_view", "borrow_fields", "nonescaping_uniform_objects_of_stable_parameters"
        )
    return
