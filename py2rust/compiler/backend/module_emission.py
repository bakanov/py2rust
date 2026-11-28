"""Coordinate module emission and per-function state for the AST adapter.

Source admission and portable rules are separate. This host adapter still depends
on Python ASTs and is not claimed to be self-hosted.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..memory import (
    callback_functions,
    json_array_views,
    last_uses,
    mutable_bindings,
    parameter_uses,
    sequence_slice_views,
)
from ..optimization import cached_lengths, string_slice_views, text_accesses
from ..rules.control_flow import render_function
from .declarations import collect_declarations
from .values import Type

if TYPE_CHECKING:
    from ..service import ServiceCompiler


def emit_module(compiler: ServiceCompiler, tree: ast.Module) -> str:
    compiler.move_safety = getattr(tree, "py2rust_move_safety", None)
    compiler.lowering_decisions = []
    compiler.optimization_report = {}
    compiler.runtime_effect_selections = {}
    functions, main = collect_declarations(compiler, tree)
    from .regex_consumers import prepare_regex_consumers

    prepare_regex_consumers(compiler, functions)
    from .projected_strings import prepare_projected_strings

    prepare_projected_strings(compiler, functions)
    from .shared_records import prepare_shared_records, record_definition

    prepare_shared_records(compiler)
    output = [
        "#![allow(unused_mut, unused_variables, unused_parens, dead_code, non_camel_case_types, non_snake_case)]\nuse py2rust_service_runtime as rt;"
    ]
    for name, values in compiler.enums.items():
        output.append(
            f"#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Hash, serde::Serialize)]\nenum {name} {{ {', '.join(values)} }}"
        )
    for name in compiler.records:
        output.append(record_definition(compiler, name))
    legacy_functions = {node.name for node in functions if not hasattr(node, "py2rust_parameter_plan")}
    callbacks = callback_functions(tree, legacy_functions) if legacy_functions else set()
    compiler.parameter_uses = (
        {
            node.name: parameter_uses(
                node,
                {
                    arg.arg
                    for arg, typ in zip(node.args.args, compiler.functions[node.name][0])
                    if typ.name
                    in {"str", "bytes", "list", "tuple_var", "dict", "set", "tuple", "Json", *compiler.records}
                },
                node.name in callbacks,
            )
            for node in functions
        }
        if compiler.optimize
        else {}
    )
    compiler.mutable_parameter_functions = {node.name: set() for node in functions}
    compiler.stateful_methods = {
        node.name
        for node in functions
        if any(
            isinstance(expression, ast.Attribute)
            and isinstance(expression.value, ast.Name)
            and expression.value.id == "self_"
            and isinstance(expression.ctx, ast.Store)
            or isinstance(expression, ast.Call)
            and isinstance(expression.func, ast.Attribute)
            and isinstance(expression.func.value, ast.Attribute)
            and isinstance(expression.func.value.value, ast.Name)
            and expression.func.value.value.id == "self_"
            and expression.func.attr in {"next", "next_range", "shuffle"}
            for expression in ast.walk(node)
        )
    }
    for node in functions:
        compiler.current_function = node.name
        compiler.mutable_bindings = mutable_bindings(node)
        compiler.ownership_uses = last_uses(node) if compiler.optimize else {}
        types, compiler.result = compiler.functions[node.name]
        compiler.borrowed_parameters = {
            name for name, decision in compiler.parameter_uses.get(node.name, {}).items() if decision.mode == "borrow"
        }
        compiler.borrowed_str_parameters = {
            arg.arg
            for arg, typ in zip(node.args.args, types)
            if arg.arg in compiler.borrowed_parameters and typ.name == "str"
        }
        compiler.locals = {}
        compiler.counters = set()
        compiler.mutable_parameters = compiler.mutable_parameter_functions[node.name]
        args = []
        for arg, typ in zip(node.args.args, types):
            compiler.check_name(arg.arg, arg)
            compiler.locals[arg.arg] = typ
            stateful_turn_controller = (
                (
                    node.name.startswith("py__openciv3__turn_controller__TurnController__")
                    and node.name.rsplit("__", 1)[-1] in {"advance", "autoplay_human_turn", "respond_to_trade"}
                    and arg.arg == "self_"
                )
                or (
                    node.name.startswith("py__civ3_ai__civilization_ai__CivilizationAI__")
                    and not node.name.endswith("__pending_trade")
                    and arg.arg == "self_"
                )
                or (
                    node.name.startswith("py__civ3_console__session__ConsoleSession__")
                    and not node.name.endswith("escaped_5f5f706f73745f696e69745f5f")
                    and arg.arg == "self_"
                )
                or (
                    node.name
                    in {
                        "py__openciv3__human_units__HumanUnits__confirm_founding",
                        "py__openciv3__human_research__HumanResearch__choose",
                        "py__openciv3__human_economy__HumanEconomy__apply",
                    }
                    and arg.arg == "self_"
                )
            )
            if arg.arg in compiler.mutable_parameters or stateful_turn_controller:
                args.append(f"mut {arg.arg}: &mut {typ.rust()}")
                continue
            if arg.arg in compiler.borrowed_parameters:
                mutable_random = (
                    node.name.startswith("py__strategy__random__MapRandom__")
                    and node.name.rsplit("__", 1)[-1] in {"escaped_5f73616d706c65", "next", "next_double", "next_range"}
                    or node.name.startswith("py__openciv3__world_resources__escaped_5f506c6163656d656e74__")
                    and node.name.rsplit("__", 1)[-1] in {"generate", "appearance", "place_rare", "place_bonus"}
                    or node.name.startswith("py__openciv3__world_rivers__escaped_5f526976657247726f777468__")
                    and node.name.rsplit("__", 1)[-1] in {"generate", "flow"}
                    or node.name.startswith("py__openciv3__turn_controller__TurnController__")
                    and node.name.rsplit("__", 1)[-1] in {"advance", "autoplay_human_turn", "respond_to_trade"}
                )
                rust_type = (
                    "&mut " + typ.rust()
                    if typ.name == "py__strategy__random__MapRandom" or mutable_random and arg.arg == "self_"
                    else (
                        "&str"
                        if typ.name == "str"
                        else (
                            "&[u8]"
                            if typ.name == "bytes"
                            else f"&[{typ.args[0].rust()}]" if typ.name in {"list", "tuple_var"} else f"&{typ.rust()}"
                        )
                    )
                )
                binding = "mut " if rust_type.startswith("&mut ") else ""
                args.append(f"{binding}{arg.arg}: {rust_type}")
            else:
                rust_type = typ.rust()
                if typ.name == "callable":
                    rust_type = rust_type.replace("fn", "impl Fn", 1)
                    if node.name.endswith("__continue_routes") and arg.arg == "report_automated_move":
                        rust_type = "&" + rust_type
                args.append(f"mut {arg.arg}: {rust_type}")
        string_parameters = {arg.arg for arg, typ in zip(node.args.args, types) if typ.name == "str"}
        compiler.indexed_text = (
            text_accesses(node, string_parameters, builtin_ord="ord" not in compiler.functions)
            if compiler.optimize_text
            else {}
        )
        compiler.slice_views = string_slice_views(node, string_parameters) if compiler.optimize_text else {}
        compiler.array_views = (
            json_array_views(node, {arg.arg for arg, typ in zip(node.args.args, types) if typ.name == "Json"})
            if compiler.optimize_iteration and compiler.optimize_json_views
            else {}
        )
        view_plan = getattr(node, "py2rust_view_plan", None)
        compiler.json_text_views = (
            view_plan.bindings("json_text")
            if view_plan is not None and compiler.optimize_json_views and compiler.optimize
            else {}
        )
        compiler.sequence_views = (
            sequence_slice_views(
                node,
                {
                    arg.arg
                    for arg, typ in zip(node.args.args, types)
                    if typ.name in {"bytes", "bytearray", "list", "tuple_var"}
                },
            )
            if compiler.optimize_slices
            else {}
        )
        compiler.cached_lengths = (
            cached_lengths(node, string_parameters - compiler.indexed_text.keys()) if compiler.optimize else {}
        )
        from .record_views import prepare_record_views

        prepare_record_views(compiler, node)
        from .field_moves import prepare_field_moves

        prepare_field_moves(compiler, node)
        from .record_cursors import prepare_record_cursors

        prepare_record_cursors(compiler, node)
        from .borrowed_maps import prepare_borrowed_maps

        prepare_borrowed_maps(compiler, node)
        statements = node.body
        documentation = ast.get_docstring(node)
        if documentation:
            statements = statements[1:]
        from .legacy_adapter import annotation

        walrus_declarations = []
        for expression in ast.walk(node):
            if isinstance(expression, ast.NamedExpr) and expression.target.id not in compiler.locals:
                value_type = getattr(expression.value, "py2rust_value_type", None)
                if value_type is not None:
                    typ = compiler.typ(annotation(value_type))
                    compiler.locals[expression.target.id] = typ
                    walrus_declarations.append(f"let mut {expression.target.id}: {typ.rust()};")
        body = (
            walrus_declarations
            + [
                f"let __length_{name}: std::cell::OnceCell<i64> = std::cell::OnceCell::new();"
                for name in compiler.cached_lengths
            ]
            + [
                f"let __text_{name}: std::cell::OnceCell<rt::{compiler.indexed_text[name].representation}<'_>> = std::cell::OnceCell::new();"
                for name in compiler.indexed_text
            ]
            + compiler.block(statements, scoped=False)
        )
        from .memoization import wrap_parser

        body = wrap_parser(compiler, node, body)
        success = "Ok(())" if compiler.result == Type("None") and not compiler.always_returns(statements) else ""
        output.append(
            ("\n".join("/// " + line for line in documentation.splitlines()) + "\n" if documentation else "")
            + (f"// Python: {node.source_path}:{node.lineno}\n" if hasattr(node, "source_path") else "")
            + str(
                render_function(
                    f"fn {node.name}({', '.join(args)}) -> rt::Result<{compiler.result.rust()}>",
                    body,
                    return_success=success,
                )
            )
        )
    compiler.current_function = None
    compiler.locals, compiler.result = {}, Type("None")
    compiler.cached_lengths = {}
    compiler.borrowed_parameters = set()
    compiler.borrowed_str_parameters = set()
    compiler.ownership_uses = {}
    compiler.record_cursors = {}
    compiler.record_cursor_steps = {}
    compiler.borrowed_maps = {}
    compiler.borrowed_map_loops = set()
    compiler.field_moves = {}
    compiler.field_length_reads = {}
    compiler.indexed_text = {}
    compiler.slice_views = {}
    compiler.array_views = {}
    compiler.sequence_views = {}
    compiler.json_text_views = {}
    compiler.mutable_bindings = mutable_bindings(main)
    output.append(
        str(
            render_function(
                "fn main() -> rt::Result<()>",
                compiler.block(main.body),
                return_success="Ok(())",
            )
        )
    )
    if compiler.collect_costs:
        from ..diagnostics import build_report

        effect_plan = getattr(tree, "py2rust_effect_plan", None)
        summaries = (
            effect_plan.summarize(compiler.runtime_effect_selections, tree.py2rust_effect_symbols)
            if effect_plan is not None
            else None
        )
        compiler.optimization_report = build_report(
            functions, compiler.parameter_uses, compiler.lowering_decisions, summaries=summaries
        )
    return "\n\n".join(output) + "\n"
