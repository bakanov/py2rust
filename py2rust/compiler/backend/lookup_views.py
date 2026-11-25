"""Read-only integer map views for byte traversal, with conservative use auditing."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..memory import argument_effects_unknown, binding_write_reasons
from .values import Type

if TYPE_CHECKING:
    from ..service import ServiceCompiler


def integer_lookup_views(compiler: ServiceCompiler, loop: ast.For) -> str:
    body = ast.Module(body=loop.body, type_ignores=[])
    nodes = list(ast.walk(body))
    parents = {id(child): parent for parent in nodes for child in ast.iter_child_nodes(parent)}
    candidates = {name for name, typ in compiler.locals.items() if typ.name == "dict" and typ.args[0] == Type("int")}
    writes = binding_write_reasons(body, candidates)
    output = []
    for name in sorted(candidates - writes.keys() - compiler.integer_views):
        uses = [node for node in nodes if isinstance(node, ast.Name) and node.id == name]
        if not uses:
            continue
        if any(
            not (
                isinstance(parent := parents.get(id(node)), ast.Subscript)
                and parent.value is node
                and isinstance(parent.ctx, ast.Load)
                and not isinstance(parent.slice, ast.Slice)
                and not argument_effects_unknown(parent.slice)
            )
            for node in uses
        ):
            continue
        source = compiler.local_read(uses[0])
        output.append(f"let {name} = &rt::IntLookup::new({compiler.reference(source)});\n")
        compiler.borrowed_parameters.add(name)
        compiler.integer_views.add(name)
        compiler.record_decision(loop, "integer_lookup", "borrow", "readonly_index_only_map_in_byte_loop")
    return "".join(output)
