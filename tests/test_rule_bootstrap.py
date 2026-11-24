"""Compile actual production rule sources to Rust, then execute without Python."""

import os
import subprocess
from pathlib import Path

import pytest

from py2rust.compiler import pipeline, service
from py2rust.compiler.backend import exception_emission
from py2rust.compiler.rules import (
    access,
    assignment,
    byte_methods,
    collection_methods,
    collections,
    comparisons,
    conditions,
    control_flow,
    conversions,
    iteration,
    literals,
    numeric,
    ordering,
    records,
    strings,
    types,
)

from .test_services import program


@pytest.mark.parametrize(
    "family",
    [
        "strings",
        "literals",
        "numeric",
        "records",
        "conversions",
        "conditions",
        "collections",
        "ordering",
        "types",
        "comparisons",
        "iteration",
        "assignment",
        "access",
        "byte_methods",
        "collection_methods",
        "control_flow",
        "exception_emission",
    ],
)
def test_actual_rule_module_compiles_and_runs_without_python(tmp_path: Path, monkeypatch, family: str) -> None:
    """Transpile the production source, not a manually maintained subset copy."""
    module = {
        "strings": strings,
        "literals": literals,
        "types": types,
        "comparisons": comparisons,
        "iteration": iteration,
        "assignment": assignment,
        "access": access,
        "byte_methods": byte_methods,
        "collection_methods": collection_methods,
        "control_flow": control_flow,
        "exception_emission": exception_emission,
        "collections": collections,
        "ordering": ordering,
        "numeric": numeric,
        "records": records,
        "conversions": conversions,
        "conditions": conditions,
    }[family]
    rule_source = Path(module.__file__).read_text()
    rule_path = tmp_path / "rule_module.py"
    rule_path.write_text(rule_source)
    source = """from rule_module import select_string_rule, render_string_call

def run() -> None:
    for receiver in ["str", "bytes", "custom"]:
        for method in ["casefold", "strip", "lstrip", "rstrip", "lower", "upper", "encode", "split", "startswith", "endswith", "find", "rfind", "replace", "join", "unknown"]:
            for arity in [-1, 0, 1, 2, 3]:
                rule = select_string_rule(receiver, method, arity)
                print(rule.key, rule.form, rule.target, rule.result, rule.argument, rule.fallible)
                if rule.key != "" and rule.form != "trim":
                    arguments: list[str] = []
                    for index in range(arity):
                        arguments.append("operand")
                    print(render_string_call(rule, "receiver", arguments))

if __name__ == "__main__":
    run()
"""
    if family == "numeric":
        source = """from rule_module import select_numeric_rule, render_numeric, select_unary_rule, render_unary

def run() -> None:
    for left in ["int", "float", "bool", "str"]:
        for right in ["int", "float", "bool", "str"]:
            for operation in ["+", "-", "*", "/", "//", "%", "<<", ">>", "&", "|", "^", "**", "unknown"]:
                rule = select_numeric_rule(operation, left, right)
                print(rule.key, rule.form, rule.target, rule.result)
                if rule.key != "":
                    print(render_numeric(rule, "left", "right"))
    for operand in ["int", "float", "bool", "str"]:
        for operation in ["not", "~", "-", "abs", "+", "unknown"]:
            unary = select_unary_rule(operation, operand)
            print(unary.key, unary.form, unary.target, unary.result)
            if unary.key != "":
                print(render_unary(unary, "operand"))

if __name__ == "__main__":
    run()
"""
    if family == "records":
        source = """from rule_module import runtime_field_type, borrowed_runtime_field, dictionary_get_style

def run() -> None:
    for record in ["WebRequest", "WebResponse", "HttpReader", "HttpResponse", "Unknown"]:
        for field in ["method", "path", "target", "status", "body", "headers", "query", "unknown"]:
            print(runtime_field_type(record, field), borrowed_runtime_field(record, field))
    for stable in [False, True]:
        for local in [False, True]:
            for literal in [False, True]:
                for empty in [False, True]:
                    print(dictionary_get_style(stable, local, literal, empty))

if __name__ == "__main__":
    run()
"""
    if family == "conversions":
        source = """from rule_module import select_conversion, render_conversion

def run() -> None:
    for target in ["str", "int", "float", "bool", "unknown"]:
        for source in ["str", "int", "float", "Exception", "bool", "unknown"]:
            rule = select_conversion(target, source)
            print(rule.key, rule.form, rule.target, rule.result, rule.fallible)
            if rule.key != "":
                print(render_conversion(rule, "value", "reference"))

if __name__ == "__main__":
    run()
"""
    if family == "conditions":
        source = """from rule_module import condition_problem, boolean_operator

def run() -> None:
    for value_type in ["bool", "builtins.bool", "str", "int", "list", "union", "unknown"]:
        print(condition_problem(value_type))
    for operation in ["and", "or", "unknown"]:
        print(boolean_operator(operation))

if __name__ == "__main__":
    run()
"""
    if family == "collections":
        source = """from rule_module import length_rule, render_length, sequence_constructor_rule, render_sequence_constructor

def run() -> None:
    for kind in ["str", "bytes", "bytearray", "list", "tuple", "tuple_var", "dict", "set", "unknown"]:
        for indexed in [False, True]:
            for cached in [False, True]:
                rule = length_rule(kind, indexed, cached)
                print(rule)
                for local_name in ["", "local"]:
                    print(render_length(rule, "value", 3, local_name, "index"))
        sequence = sequence_constructor_rule(kind)
        print(sequence, render_sequence_constructor(sequence, "value"))

if __name__ == "__main__":
    run()
"""
    if family == "ordering":
        source = """from rule_module import orderable_shape, sorting_rule, render_sorting

def run() -> None:
    for name in ["int", "bool", "str", "float", "tuple", "tuple_var", "list", "record"]:
        for is_enum in [False, True]:
            for size in [0, 1, 12, 13]:
                for ordered in [False, True]:
                    children: list[bool] = []
                    for index in range(size):
                        children.append(ordered)
                    print(orderable_shape(name, is_enum, children))
    for has_key in [False, True]:
        for has_reverse in [False, True]:
            rule = sorting_rule(has_key, has_reverse)
            print(rule, render_sorting(rule, "values", "callback", "direction"))

if __name__ == "__main__":
    run()
"""
    if family == "types":
        source = """from rule_module import render_owned_type

def run() -> None:
    for name in ['int', 'float', 'str', 'bytes', 'bytearray', 'bool', 'None', 'Json', 'DateTime', 'Rational', 'HttpServer', 'HttpResponse', 'WebRequest', 'WebResponse', 'StreamChunk', 'FileHandle', 'GzipReader', 'GzipWriter', 'LineReader', 'HttpReader', 'TcpListener', 'TcpStream', 'UnixListener', 'UnixStream', 'UdpSocket', 'ProcessPool', 'Sha256', 'Exception', 'UserRecord', 'UserEnum']:
        print(render_owned_type(name, []))
    for name in ["list", "tuple_var", "set"]:
        print(render_owned_type(name, ["String"]))
    print(render_owned_type("dict", ["String", "Vec<i64>"]))
    print(render_owned_type("tuple", ["i64"]))
    print(render_owned_type("tuple", ["i64", "String"]))
    inner = render_owned_type("list", ["i64"])
    print(render_owned_type("dict", ["String", inner]))

if __name__ == "__main__":
    run()
"""
    if family == "comparisons":
        source = """from rule_module import membership_rule, render_membership, render_null_identity, render_empty_string, render_comparison, render_comparison_chain, set_order_rule, render_set_order

def run() -> None:
    for needle in ["int", "str", "bytes", "bytearray", "float"]:
        for container in ["bytes", "bytearray", "Json", "dict", "list", "set", "tuple_var", "str", "unknown"]:
            rule = membership_rule(needle, container)
            for inverted in [False, True]:
                print(rule, render_membership(rule, "needle()", "&container()", inverted))
    for inverted in [False, True]:
        for is_json in [False, True]:
            print(render_null_identity("value()", is_json, inverted))
        print(render_empty_string("value()", inverted))
    for operation in ["==", "!=", "<", "<=", ">", ">=", "unknown"]:
        print(render_comparison(operation, "left()", "right()"))
    print(render_comparison_chain(["a()", "b()", "c()"], ["a", "b", "c"], ["a < b", "b < c"]))
    print(render_comparison_chain(["a()", "b()"], ["a", "b"], ["a < b"]))
    try:
        print(render_comparison_chain([], [], []))
    except Exception:
        print("invalid chain rejected")
    for kind in ["set", "list", "tuple_var", "tuple", "int", "unknown"]:
        for contains_set in [False, True]:
            rule = set_order_rule(kind, contains_set)
            for operation in ["<", "<=", ">", ">="]:
                children = ["child comparison"]
                if rule == "tuple.first_unequal":
                    children = ["first comparison", "second comparison"]
                print(rule, render_set_order(rule, operation, "left()", "right()", children))
    try:
        print(render_set_order("set.inclusion", "==", "left", "right", []))
    except Exception:
        print("invalid ordering rejected")
    try:
        print(render_set_order("sequence.first_unequal", "<", "left", "right", []))
    except Exception:
        print("missing child rejected")

if __name__ == "__main__":
    run()
"""
    if family == "iteration":
        source = """from rule_module import select_iteration, render_iteration, render_range, render_for

def run() -> None:
    for container in ["str", "bytes", "bytearray", "list", "tuple_var", "set", "dict", "tuple", "unknown"]:
        for borrowed in [False, True]:
            for scalar in [False, True]:
                for borrow_item in [False, True]:
                    rule = select_iteration(container, borrowed, scalar, borrow_item)
                    print(rule.key, rule.form, rule.borrowed_item)
                    print(render_iteration(rule, container, "source()", 3))
    print(render_range([]))
    print(render_range(["end()"]))
    print(render_range(["start()", "end()"]))
    print(render_range(["start()", "end()", "step()"]))
    print(render_range(["one", "two", "three", "four"]))
    print(render_for("item", "source()", "body();"))

if __name__ == "__main__":
    run()
"""
    if family == "assignment":
        source = """from rule_module import render_index_assignment, render_delete, render_string_append, render_nested_assignment, render_indexed_list_mutation

def run() -> None:
    for kind in ["list", "bytearray", "dict", "Json", "unknown"]:
        print(render_index_assignment(kind, "target", "key()", "value()"))
        print(render_delete(kind, "target", "key()"))
        for method in ["push", "extend"]:
            print(render_indexed_list_mutation(kind, "target", "key()", "value()", method))
    print(render_string_append("target", "suffix()", False))
    print(render_string_append("target", "literal", True))
    print(render_nested_assignment("target", ["outer()", "inner()", "last()"], "value()"))
    print(render_nested_assignment("target", ["key()"], "value()"))
    try:
        print(render_indexed_list_mutation("list", "target", "key", "value", "unsupported"))
    except Exception:
        print("invalid method rejected")

if __name__ == "__main__":
    run()
"""
    if family == "byte_methods":
        source = """from rule_module import select_byte_method, render_byte_method

def run() -> None:
    for receiver in ["bytes", "bytearray", "str"]:
        for method in ["decode", "hex", "find", "join", "startswith", "endswith", "unknown"]:
            for arity in [0, 1, 2]:
                for encoding in ["utf-8", "utf8", "latin-1", "latin1", "iso-8859-1", "iso8859-1", "cp437", "437", "ibm437", "ascii", "unknown"]:
                    rule = select_byte_method(receiver, method, arity, encoding)
                    print(rule.key, rule.form, rule.target, rule.result, rule.argument)
                    print(render_byte_method(rule, "receiver()", "argument()"))

if __name__ == "__main__":
    run()
"""
    if family == "collection_methods":
        source = """from rule_module import select_collection_method, render_collection_method

def run() -> None:
    for receiver in ["list", "dict", "set", "bytearray", "bytes", "str", "unknown"]:
        for method in ["copy", "clear", "insert", "pop", "sort", "reverse", "extend", "append", "add", "unknown"]:
            for arity in [0, 1, 2, 3]:
                for named in [False, True]:
                    rule = select_collection_method(receiver, method, arity, named)
                    print(rule.key, rule.form, rule.target, rule.first, rule.second, rule.result)
                    arguments: list[str] = []
                    for index in range(arity):
                        arguments.append("argument()")
                    print(render_collection_method(rule, "receiver", arguments))

if __name__ == "__main__":
    run()
"""
    if family == "control_flow":
        source = """from rule_module import render_result_return, render_borrow, render_function, render_if, render_while, render_assert, render_reraise

def run() -> None:
    for pending in [False, True]:
        for forward in [False, True]:
            for implicit in [False, True]:
                try:
                    print(render_result_return("value()", "call()", pending, forward, implicit))
                except Exception:
                    print("invalid return plan")
    try:
        print(render_result_return("value()", "", False, True, False))
    except Exception:
        print("missing result call")
    for style in ["existing", "name", "expression", "unknown"]:
        print(render_borrow("value", style))
    print(render_function("fn example() -> Result<()>", ["first();", "second();"], "Ok(())"))
    print(render_if("condition()", ["body();"], []))
    print(render_if("condition()", ["body();"], ["otherwise();"]))
    print(render_while("condition()", ["body();"]))
    print(render_assert("condition()", "message()"))
    print(render_reraise("active_error"))

if __name__ == "__main__":
    run()
"""
    if family == "exception_emission":
        source = """from rule_module import render_finally, render_handler, render_resource

def run() -> None:
    for nested in [False, True]:
        for body_terminates in [False, True]:
            print(render_handler("body();", "success();", "failure();", "String", "caught", nested, body_terminates))
            for cleanup_terminates in [False, True]:
                for statement_terminates in [False, True]:
                    print(render_finally("body();", "cleanup();", "String", 7, "outer_error", nested, body_terminates, cleanup_terminates, statement_terminates))
    print(render_resource("open()", "handle", "rt::FileHandle", "body();"))

if __name__ == "__main__":
    run()
"""
    if family == "access":
        source = """from rule_module import slice_rule, render_sequence_slice, render_text_slice, index_rule, render_index, render_tuple_index

def run() -> None:
    for container in ["str", "bytes", "bytearray", "list", "tuple_var", "dict", "Json", "tuple", "unknown"]:
        helper = slice_rule(container)
        print(helper, render_sequence_slice(helper, "source()", "start()", "end()"))
        for key in ["str", "int", "bool", "tuple"]:
            for prepared in [False, True]:
                rule = index_rule(container, key, prepared)
                print(rule, render_index(rule, "source()", "key()"))
    for prepared_index in ["", "index()"]:
        for view in [False, True]:
            print(render_text_slice("source()", "start()", "end()", prepared_index, view))
    print(render_tuple_index("source()", 0))
    print(render_tuple_index("source()", 2))

if __name__ == "__main__":
    run()
"""
    if family == "literals":
        source = r"""from rule_module import quote_scalar_text

def run() -> None:
    print(quote_scalar_text(""))
    print(quote_scalar_text("quotes: \" backslash: \\ newline: \n tab: \t"))
    print(quote_scalar_text("Заметка 世界 😀"))
    for char in CONTROL_CHARACTERS:
        print(quote_scalar_text(char))

if __name__ == "__main__":
    run()
"""
    if family == "literals":
        source = source.replace("CONTROL_CHARACTERS", repr("".join(chr(number) for number in range(32))))
    monkeypatch.setattr(
        service.ServiceCompiler,
        "compile",
        lambda self, text: pipeline.compile_typed(
            {"main": (tmp_path / "main.py", text), "rule_module": (rule_path, rule_source)}
        ),
    )
    reference = subprocess.run(program(tmp_path, source, "python"), capture_output=True, text=True, check=True)
    binary = program(tmp_path, source, "rust")
    native = subprocess.run(
        binary,
        env=dict(os.environ, PATH="/nonexistent", PYTHONHOME="/nonexistent", PYTHONPATH="/nonexistent"),
        capture_output=True,
        text=True,
        check=True,
    )
    assert native.stdout == reference.stdout
    assert native.stderr == reference.stderr == ""
