"""Native typed-IR traversal using the production Rust rendering rules.

This module is compiled from Python during bootstrap. It never imports Python
ASTs or executes source text. Unsupported nodes fail with original locations.
"""

from py2rust.stdlib import Json, json_array, json_int, json_is_null, json_string

from ..rules.access import (
    index_rule,
    render_index,
    render_sequence_slice,
    render_text_slice,
    slice_rule,
)
from ..rules.assignment import render_delete, render_index_assignment
from ..rules.collection_methods import (
    CollectionMethodRule,
    render_collection_method,
    select_collection_method,
)
from ..rules.collections import length_rule, render_length
from ..rules.comparisons import (
    membership_rule,
    render_comparison,
    render_comparison_chain,
    render_membership,
)
from ..rules.control_flow import (
    render_assert,
    render_function,
    render_if,
    render_result_return,
    render_while,
)
from ..rules.conversions import ConversionRule, render_conversion, select_conversion
from ..rules.iteration import (
    IterationRule,
    render_for,
    render_iteration,
    render_range,
    select_iteration,
)
from ..rules.literals import quote_scalar_text
from ..rules.numeric import (
    NumericRule,
    render_numeric,
    render_unary,
    select_numeric_rule,
    select_unary_rule,
)
from ..rules.strings import StringRule, render_string_call, select_string_rule
from .borrowing import parameter_borrowed
from .collection_emission import render_collection_literal
from .diagnostics import trace_phase
from .ir_schema import validate_document
from .names import symbol
from .record_emission import render_record
from .runtime_contracts import RuntimeContract, runtime_contract
from .runtime_emission import render_runtime_call
from .types import rust_type, type_name


def location(nodes: list[Json], node: Json) -> str:
    source: Json = nodes[json_int(node["source"])]
    return json_string(source["path"]) + ":" + str(json_int(source["line"])) + ":" + str(json_int(source["column"]))


def effect_free(nodes: list[Json], index: int) -> bool:
    """A deliberately bounded proof for reading a collection before its index.

    Reviewed runtime value readers can fail but cannot mutate the snapshot.
    Unknown calls remain unproven regardless of their result type.
    """
    node: Json = nodes[index]
    operation: str = json_string(node["operation"])
    if operation == "runtime_call":
        contract: RuntimeContract = runtime_contract(literal_text(node))
        if not contract.value_reader:
            return False
    elif operation == "method_call":
        method_operands: list[Json] = json_array(node["operands"])
        if len(method_operands) == 0:
            return False
        receiver_type: str = expression_type(nodes, nodes[json_int(method_operands[0])])
        method_rule: StringRule = select_string_rule(receiver_type, literal_text(node), len(method_operands) - 1)
        if method_rule.key == "":
            return False
    elif operation == "call":
        arguments: list[Json] = json_array(node["operands"])
        if literal_text(node) != "builtins.len" or len(arguments) != 1:
            return False
        length_type: str = expression_type(nodes, nodes[json_int(arguments[0])])
        if length_type not in ["str", "bytes", "bytearray", "list", "tuple", "dict", "set"]:
            return False
    elif operation not in [
        "literal",
        "name",
        "binary",
        "unary",
        "short_circuit",
        "conditional",
        "compare_chain",
        "index",
        "slice",
        "field",
    ]:
        return False
    for operand in json_array(node["operands"]):
        if not effect_free(nodes, json_int(operand)):
            return False
    return True


def expression_type(nodes: list[Json], node: Json) -> str:
    return type_name(nodes, json_int(node["type"]))


def literal_text(node: Json) -> str:
    return json_string(node["value"]["text"])


def shared_receiver(nodes: list[Json], index: int, fallback: str) -> str:
    """Read a named receiver directly after proving later operands effect-free."""
    node: Json = nodes[index]
    if json_string(node["operation"]) == "name" and not literal_text(node).endswith(".__name__"):
        return symbol(literal_text(node))
    return fallback


def emit_expression(nodes: list[Json], index: int, definitions: dict[str, int], entry: str) -> str:
    node: Json = nodes[index]
    operation: str = json_string(node["operation"])
    operands: list[Json] = json_array(node["operands"])
    typ: str = expression_type(nodes, node)
    if operation == "literal":
        tag: str = json_string(node["value"]["kind"])
        text: str = literal_text(node)
        if tag == "none":
            return "()"
        if tag == "str":
            return quote_scalar_text(text) + ".to_string()"
        if tag == "bool":
            return "true" if text == "True" else "false"
        if tag == "int":
            # Check the runtime range without losing the exact minimum spelling.
            bounded: int = int(text)
            return "(" + str(bounded) + "i64)"
        if tag == "bytes":
            buffer: bytes = bytes.fromhex(text)
            elements: list[str] = []
            for byte in buffer:
                elements.append(str(byte) + "u8")
            return "vec![" + ", ".join(elements) + "]"
        if tag == "float":
            bounded_float: float = float(text)
            return "(" + str(bounded_float) + "f64)"
        assert False, location(nodes, node) + ": native literal not implemented: " + tag
    if operation == "name":
        name: str = literal_text(node)
        if name.endswith(".__name__"):
            module: str = name[:-9]
            return quote_scalar_text("__main__" if module == entry else module) + ".to_string()"
        code: str = symbol(name)
        if typ not in ["int", "float", "bool", "None"]:
            code = code + ".clone()"
        return code
    if operation == "unary" and literal_text(node) == "-" and len(operands) == 1:
        magnitude: Json = nodes[json_int(operands[0])]
        if json_string(magnitude["operation"]) == "literal" and literal_text(magnitude) == "9223372036854775808":
            assert expression_type(nodes, magnitude) == "int", "minimum integer requires an integer literal"
            return "i64::MIN"
    values: list[str] = []
    for operand in operands:
        values.append(emit_expression(nodes, json_int(operand), definitions, entry))
    if operation == "format_value":
        value_type: str = expression_type(nodes, nodes[json_int(operands[0])])
        spec: str = literal_text(node)
        if spec == "!r" and value_type == "str":
            return "rt::repr_text(&(" + values[0] + "))"
        if value_type == "str":
            return values[0]
        if value_type == "int":
            return "(" + values[0] + ").to_string()"
        if value_type == "float":
            return "rt::float_to_string(" + values[0] + ")?"
        if value_type == "bool":
            return "if " + values[0] + ' { "True".to_string() } else { "False".to_string() }'
        assert False, location(nodes, node) + ": unsupported native format value: " + value_type
    if operation == "json_coerce":
        if expression_type(nodes, nodes[json_int(operands[0])]) == "Json":
            return values[0]
        return "rt::to_json(&(" + values[0] + "))?"
    if operation == "json_array_literal":
        items: list[str] = []
        for item in values:
            items.append("rt::to_json(&(" + item + "))?")
        return "rt::Json::Array(vec![" + ", ".join(items) + "])"
    if operation == "json_object":
        entries: list[str] = ["let mut __object = serde_json::Map::new();"]
        for object_index in range(0, len(values), 2):
            entries.append(
                "__object.insert(" + values[object_index] + ", rt::to_json(&(" + values[object_index + 1] + "))?);"
            )
        return "{ " + " ".join(entries) + " rt::Json::Object(__object) }"
    if operation == "runtime_call":
        contract: RuntimeContract = runtime_contract(literal_text(node))
        operand_types: list[str] = []
        for runtime_operand in operands:
            operand_types.append(expression_type(nodes, nodes[json_int(runtime_operand)]))
        return render_runtime_call(contract, values, operand_types)
    if operation in ["list", "dict", "tuple", "set"]:
        return render_collection_literal(operation, rust_type(nodes, json_int(node["type"]), definitions), values)
    if operation == "slice":
        bounds: list[Json] = json_array(node["operators"])
        start: str = "0i64"
        stop: str = "i64::MAX"
        for bound_index in range(len(bounds)):
            bound: str = json_string(bounds[bound_index])
            assert bound != "step", location(nodes, node) + ": native slice steps are unsupported"
            assert effect_free(nodes, json_int(operands[bound_index + 1])), (
                location(nodes, node) + ": native slice needs proven effect-free bounds"
            )
            if bound == "start":
                start = values[bound_index + 1]
            elif bound == "stop":
                stop = values[bound_index + 1]
            else:
                assert False, location(nodes, node) + ": unknown slice bound"
        slice_receiver: str = shared_receiver(nodes, json_int(operands[0]), values[0])
        sliced_type: str = expression_type(nodes, nodes[json_int(operands[0])])
        if sliced_type == "str":
            return render_text_slice("&(" + slice_receiver + ")", start, stop, "", False)
        helper: str = slice_rule(sliced_type)
        assert helper != "", location(nodes, node) + ": native slice not implemented for this type"
        return render_sequence_slice(helper, "&(" + slice_receiver + ")", start, stop)
    if operation == "index":
        assert effect_free(nodes, json_int(operands[1])), (
            location(nodes, node) + ": native index needs a proven effect-free key"
        )
        receiver_type: str = expression_type(nodes, nodes[json_int(operands[0])])
        key_type: str = expression_type(nodes, nodes[json_int(operands[1])])
        indexing: str = index_rule(receiver_type, key_type, False)
        assert indexing != "", location(nodes, node) + ": native index not implemented for this type"
        receiver_code: str = shared_receiver(nodes, json_int(operands[0]), values[0])
        return render_index(indexing, "&(" + receiver_code + ")", values[1])
    if operation == "method_call":
        receiver: Json = nodes[json_int(operands[0])]
        receiver_kind: str = expression_type(nodes, receiver)
        method: str = literal_text(node)
        if receiver_kind == "str":
            string_rule: StringRule = select_string_rule(receiver_kind, method, len(values) - 1)
            assert string_rule.key != "" and string_rule.form != "trim", (
                location(nodes, node) + ": unsupported native string method"
            )
            references: list[str] = []
            for argument_index in range(1, len(values)):
                references.append("&(" + values[argument_index] + ")")
            rendered: str = render_string_call(string_rule, "&(" + values[0] + ")", references)
            assert rendered != "", location(nodes, node) + ": native string rendering failed"
            if string_rule.fallible:
                rendered = rendered + "?"
            return rendered
        named: bool = json_string(receiver["operation"]) == "name"
        collection_method: CollectionMethodRule = select_collection_method(
            receiver_kind, method, len(values) - 1, named
        )
        assert collection_method.key != "", (
            location(nodes, node) + ": native collection method not implemented: " + method
        )
        assert method != "sort", location(nodes, node) + ": native sort requires orderability analysis"
        if collection_method.form == "copy":
            return values[0]
        receiver_name: str = symbol(literal_text(receiver))
        method_args: list[str] = []
        for method_argument in range(1, len(values)):
            method_args.append(values[method_argument])
        if collection_method.form == "add":
            # Finish argument effects before taking the mutable receiver borrow.
            return (
                "{ let __value = "
                + method_args[0]
                + "; "
                + receiver_name
                + "."
                + collection_method.target
                + "(__value); }"
            )
        return render_collection_method(collection_method, receiver_name, method_args)
    if operation == "binary":
        left: str = expression_type(nodes, nodes[json_int(operands[0])])
        right: str = expression_type(nodes, nodes[json_int(operands[1])])
        operator: str = literal_text(node)
        if operator == "+" and left == "str" and right == "str":
            return 'format!("{}{}", ' + values[0] + ", " + values[1] + ")"
        numeric: NumericRule = select_numeric_rule(operator, left, right)
        assert numeric.key != "", location(nodes, node) + ": unsupported native binary operation"
        return render_numeric(numeric, values[0], values[1])
    if operation == "unary":
        unary: NumericRule = select_unary_rule(literal_text(node), expression_type(nodes, nodes[json_int(operands[0])]))
        assert unary.key != "", location(nodes, node) + ": unsupported native unary operation"
        return render_unary(unary, values[0])
    if operation == "short_circuit":
        for boolean_operand in operands:
            assert expression_type(nodes, nodes[json_int(boolean_operand)]) == "bool", "boolean operand required"
        assert literal_text(node) in ["and", "or"], "unsupported short-circuit operator"
        separator: str = " && " if literal_text(node) == "and" else " || "
        return "(" + separator.join(values) + ")"
    if operation == "conditional":
        assert expression_type(nodes, nodes[json_int(operands[0])]) == "bool", "boolean condition required"
        return "if " + values[0] + " { " + values[1] + " } else { " + values[2] + " }"
    if operation == "compare_chain":
        names: list[str] = []
        tests: list[str] = []
        operators: list[Json] = json_array(node["operators"])
        if len(operators) == 1 and json_string(operators[0]) in ["in", "not in"]:
            needle_kind: str = expression_type(nodes, nodes[json_int(operands[0])])
            container_kind: str = expression_type(nodes, nodes[json_int(operands[1])])
            rule: str = membership_rule(needle_kind, container_kind)
            assert rule != "", location(nodes, node) + ": unsupported native membership"
            container: str = shared_receiver(nodes, json_int(operands[1]), values[1])
            # render_membership evaluates the needle before borrowing its container.
            return render_membership(rule, values[0], "&(" + container + ")", json_string(operators[0]) == "not in")
        for position in range(len(values)):
            names.append("__compare_" + str(position))
        for comparison in range(len(operators)):
            comparison_operator: str = json_string(operators[comparison])
            test: str = ""
            if comparison_operator == "in" or comparison_operator == "not in":
                needle_type: str = expression_type(nodes, nodes[json_int(operands[comparison])])
                container_type: str = expression_type(nodes, nodes[json_int(operands[comparison + 1])])
                membership: str = membership_rule(needle_type, container_type)
                test = render_membership(
                    membership, names[comparison], "&" + names[comparison + 1], comparison_operator == "not in"
                )
            else:
                compared_type: str = expression_type(nodes, nodes[json_int(operands[comparison])])
                assert compared_type in ["int", "float", "bool", "str"] or comparison_operator in ["==", "!="], (
                    location(nodes, node) + ": native container ordering needs orderability analysis"
                )
                if compared_type == "Json" and comparison_operator in ["==", "!="]:
                    test = "rt::json_equal(&" + names[comparison] + ", &" + names[comparison + 1] + ")"
                    if comparison_operator == "!=":
                        test = "!(" + test + ")"
                else:
                    test = render_comparison(comparison_operator, names[comparison], names[comparison + 1])
            assert test != "", location(nodes, node) + ": unsupported native comparison"
            tests.append(test)
        return render_comparison_chain(values, names, tests)
    if operation == "field":
        return "(" + values[0] + ")." + symbol(literal_text(node)) + ".clone()"
    if operation == "construct":
        record_name: str = literal_text(node)
        assert record_name in definitions, location(nodes, node) + ": unknown record constructor"
        record: Json = nodes[definitions[record_name]]
        assert json_string(record["kind"]) == "Record", "constructor requires a record"
        fields: list[Json] = json_array(record["fields"])
        labels: list[Json] = json_array(node["operators"])
        provided: dict[str, str] = {}
        statements: list[str] = []
        for position in range(len(values)):
            label: str = ""
            if len(labels) > 0:
                label = json_string(labels[position])
            if label == "":
                assert position < len(fields), "too many record arguments"
                label = json_string(nodes[json_int(fields[position])]["name"])
            assert label not in provided, "duplicate record argument"
            temporary: str = "__record_argument_" + str(position)
            statements.append("let " + temporary + " = " + values[position] + ";")
            provided[label] = temporary
        field_values: list[str] = []
        for field in fields:
            descriptor: Json = nodes[json_int(field)]
            field_name: str = json_string(descriptor["name"])
            field_value: str = ""
            if field_name in provided:
                field_value = provided[field_name]
                del provided[field_name]
            else:
                assert not json_is_null(descriptor["default"]), (
                    location(nodes, node) + ": missing record argument: " + field_name
                )
                default_index: int = json_int(descriptor["default"])
                assert (
                    json_string(nodes[default_index]["operation"]) == "literal"
                ), "native record default requires a literal"
                field_value = emit_expression(nodes, default_index, definitions, entry)
            field_values.append(symbol(field_name) + ": " + field_value)
        assert len(provided) == 0, "unknown record keyword"
        return "{ " + " ".join(statements) + " " + symbol(record_name) + " { " + ", ".join(field_values) + " } }"
    if operation == "call":
        for label in json_array(node["operators"]):
            assert json_string(label) == "", location(nodes, node) + ": native keyword arguments not implemented"
        target: str = literal_text(node)
        if target == "builtins.bytes.fromhex" and len(values) == 1:
            return "rt::bytes_from_hex(&(" + values[0] + "))?"
        if target == "builtins.ord" and len(values) == 1:
            ordinal_type: str = expression_type(nodes, nodes[json_int(operands[0])])
            assert ordinal_type in ["str", "bytes", "bytearray"], "ord requires text or bytes"
            ordinal_helper: str = "ord_text" if ordinal_type == "str" else "ord_bytes"
            return "rt::" + ordinal_helper + "(&(" + values[0] + "))?"
        if target == "builtins.len" and len(values) == 1:
            length_source: Json = nodes[json_int(operands[0])]
            length_type: Json = nodes[json_int(length_source["type"])]
            length: str = length_rule(expression_type(nodes, length_source), False, False)
            assert length != "", location(nodes, node) + ": unsupported native length"
            length_code: str = shared_receiver(nodes, json_int(operands[0]), values[0])
            return render_length(length, length_code, len(json_array(length_type["arguments"])), "", "")
        if target == "builtins.print":
            printed: list[str] = []
            placeholders: list[str] = []
            for position in range(len(values)):
                item_type: str = expression_type(nodes, nodes[json_int(operands[position])])
                item: str = values[position]
                assert item_type in ["str", "int", "float", "bool"], "unsupported print argument"
                if item_type == "bool":
                    item = "if " + item + ' { "True" } else { "False" }'
                if item_type == "float":
                    item = "rt::float_to_string(" + item + ")?"
                printed.append(item)
                placeholders.append("{}")
            arguments: str = ""
            if len(printed) > 0:
                arguments = ", " + ", ".join(printed)
            return "println!(" + quote_scalar_text(" ".join(placeholders)) + arguments + ")"
        if target in ["builtins.str", "builtins.int", "builtins.float"] and len(values) == 1:
            conversion: ConversionRule = select_conversion(
                target[9:], expression_type(nodes, nodes[json_int(operands[0])])
            )
            assert conversion.key != "", location(nodes, node) + ": unsupported native conversion"
            converted: str = render_conversion(conversion, values[0], "&(" + values[0] + ")")
            if conversion.fallible:
                converted = converted + "?"
            return converted
        assert target in definitions, location(nodes, node) + ": native call not implemented: " + target
        declaration: Json = nodes[definitions[target]]
        parameters: list[Json] = json_array(declaration["parameters"])
        assert len(parameters) == len(values), location(nodes, node) + ": function argument count mismatch"
        stable: bool = True
        for operand in operands:
            if not effect_free(nodes, json_int(operand)):
                stable = False
        call_values: list[str] = []
        for position in range(len(parameters)):
            parameter: Json = nodes[json_int(parameters[position])]
            argument: str = values[position]
            if parameter_borrowed(nodes, declaration, parameter):
                if stable:
                    argument = shared_receiver(nodes, json_int(operands[position]), argument)
                argument = "&(" + argument + ")"
            call_values.append(argument)
        return symbol(target) + "(" + ", ".join(call_values) + ")?"
    assert False, location(nodes, node) + ": native expression not implemented: " + operation
    return ""


def emit_block(nodes: list[Json], body: list[Json], definitions: dict[str, int], entry: str) -> list[str]:
    lines: list[str] = []
    for reference in body:
        node: Json = nodes[json_int(reference)]
        operation: str = json_string(node["operation"])
        expressions: list[Json] = json_array(node["expressions"])
        blocks: list[Json] = json_array(node["blocks"])
        lines.append("// " + location(nodes, node).replace("\n", " ").replace("\r", " "))
        if operation == "pass":
            lines.append("")
        elif operation == "break" or operation == "continue":
            lines.append(operation + ";")
        elif operation == "return":
            value: str = "()"
            if len(expressions) > 0:
                value = emit_expression(nodes, json_int(expressions[0]), definitions, entry)
            lines.append(render_result_return(value, "", False, False, False))
        elif operation == "expression":
            lines.append(emit_expression(nodes, json_int(expressions[0]), definitions, entry) + ";")
        elif operation == "store_field":
            record_receiver: Json = nodes[json_int(expressions[1])]
            assert json_string(record_receiver["operation"]) == "name", (
                location(nodes, node) + ": native field assignment requires a named record"
            )
            field_value: str = emit_expression(nodes, json_int(expressions[0]), definitions, entry)
            lines.append(
                symbol(literal_text(record_receiver))
                + "."
                + symbol(json_string(node["target"]))
                + " = "
                + field_value
                + ";"
            )
        elif operation == "store_index":
            stored: Json = nodes[json_int(expressions[1])]
            assert json_string(stored["operation"]) == "name", (
                location(nodes, node) + ": native nested assignment not implemented"
            )
            replacement: str = emit_expression(nodes, json_int(expressions[0]), definitions, entry)
            key: str = emit_expression(nodes, json_int(expressions[2]), definitions, entry)
            assignment: str = render_index_assignment(
                expression_type(nodes, stored), symbol(literal_text(stored)), key, replacement
            )
            assert assignment != "", location(nodes, node) + ": unsupported native indexed assignment"
            lines.append(assignment)
        elif operation == "delete_index":
            deleted: Json = nodes[json_int(expressions[0])]
            assert json_string(deleted["operation"]) == "name", (
                location(nodes, node) + ": native deletion requires a named receiver"
            )
            deleted_key: str = emit_expression(nodes, json_int(expressions[1]), definitions, entry)
            deletion: str = render_delete(expression_type(nodes, deleted), symbol(literal_text(deleted)), deleted_key)
            assert deletion != "", location(nodes, node) + ": unsupported native deletion"
            lines.append(deletion)
        elif operation == "assign":
            assigned: str = emit_expression(nodes, json_int(expressions[0]), definitions, entry)
            target: str = symbol(json_string(node["target"]))
            lines.append(target + " = " + assigned + ";")
        elif operation == "if":
            assert len(blocks) == len(expressions) + 1, "invalid conditional blocks"
            otherwise: list[str] = emit_block(nodes, json_array(blocks[-1]), definitions, entry)
            for branch in range(len(expressions) - 1, -1, -1):
                condition: str = emit_expression(nodes, json_int(expressions[branch]), definitions, entry)
                body_lines: list[str] = emit_block(nodes, json_array(blocks[branch]), definitions, entry)
                otherwise = [render_if(condition, body_lines, otherwise)]
            lines.extend(otherwise)
        elif operation == "while":
            assert len(json_array(blocks[1])) == 0, location(nodes, node) + ": while else not implemented"
            condition_code: str = emit_expression(nodes, json_int(expressions[0]), definitions, entry)
            loop_body: list[str] = emit_block(nodes, json_array(blocks[0]), definitions, entry)
            lines.append(render_while(condition_code, loop_body))
        elif operation == "for":
            assert len(json_array(blocks[1])) == 0, location(nodes, node) + ": for else not implemented"
            iterable: Json = nodes[json_int(expressions[0])]
            iterator: str = ""
            if json_string(iterable["operation"]) == "call" and literal_text(iterable) == "builtins.range":
                bounds: list[str] = []
                for bound in json_array(iterable["operands"]):
                    bounds.append(emit_expression(nodes, json_int(bound), definitions, entry))
                iterator = render_range(bounds)
                assert iterator != "", "invalid range argument count"
            else:
                iterable_type: str = expression_type(nodes, iterable)
                assert iterable_type in ["list", "dict", "set", "str", "bytes", "bytearray"], (
                    location(nodes, node) + ": native iterable type not implemented"
                )
                iteration: IterationRule = select_iteration(iterable_type, False, False, False)
                snapshot: str = emit_expression(nodes, json_int(expressions[0]), definitions, entry)
                iterator = render_iteration(iteration, iterable_type, snapshot, 0)
            loop_lines: list[str] = emit_block(nodes, json_array(blocks[0]), definitions, entry)
            lines.append(render_for("mut " + symbol(json_string(node["target"])), iterator, "\n".join(loop_lines)))
        elif operation == "assert":
            message: str = '"".to_string()'
            if len(expressions) > 1:
                message = emit_expression(nodes, json_int(expressions[1]), definitions, entry)
            lines.append(render_assert(emit_expression(nodes, json_int(expressions[0]), definitions, entry), message))
        else:
            assert False, location(nodes, node) + ": native statement not implemented: " + operation
    return lines


def local_types(nodes: list[Json], body: list[Json], definitions: dict[str, int]) -> dict[str, int]:
    """Hoist typed local storage; Rust still checks definite assignment.

    Lowered block-local names are already disambiguated by the source frontend.
    This avoids confusing an explicit source annotation with a first assignment.
    """
    types: dict[str, int] = {}
    for statement in body:
        node: Json = nodes[json_int(statement)]
        if json_string(node["operation"]) == "assign":
            name: str = json_string(node["target"])
            type_index: int = 0
            if json_is_null(node["target_type"]):
                expressions: list[Json] = json_array(node["expressions"])
                type_index = json_int(nodes[json_int(expressions[0])]["type"])
            else:
                type_index = json_int(node["target_type"])
            if name in types:
                assert rust_type(nodes, types[name], definitions) == rust_type(
                    nodes, type_index, definitions
                ), f"native local changes type: {name}: {rust_type(nodes, types[name], definitions)} != {rust_type(nodes, type_index, definitions)}"
            types[name] = type_index
        for block in json_array(node["blocks"]):
            nested: dict[str, int] = local_types(nodes, json_array(block), definitions)
            for nested_name in nested:  # noqa: PLC0206 - portable subset has no items unpacking
                if nested_name in types:
                    assert rust_type(nodes, types[nested_name], definitions) == rust_type(
                        nodes, nested[nested_name], definitions
                    ), f"native local changes type: {nested_name}: {rust_type(nodes, types[nested_name], definitions)} != {rust_type(nodes, nested[nested_name], definitions)}"
                types[nested_name] = nested[nested_name]
    return types


def local_declarations(
    nodes: list[Json], body: list[Json], parameters: list[str], definitions: dict[str, int]
) -> list[str]:
    types: dict[str, int] = local_types(nodes, body, definitions)
    declarations: list[str] = []
    for name in types:  # noqa: PLC0206 - portable subset has no items unpacking
        if name not in parameters:
            declarations.append("let mut " + symbol(name) + ": " + rust_type(nodes, types[name], definitions) + ";")
    return declarations


def emit_document(document: Json) -> str:
    trace_phase("emit Rust")
    validate_document(document)
    entry: str = json_string(document["entry"])
    nodes: list[Json] = json_array(document["nodes"])
    definitions: dict[str, int] = {}
    for root in json_array(document["modules"]):
        module: Json = nodes[json_int(root)]
        for record in json_array(module["records"]):
            record_index: int = json_int(record)
            record_name: str = json_string(nodes[record_index]["name"])
            assert record_name not in definitions, "duplicate record declaration"
            definitions[record_name] = record_index
        assert len(json_array(module["enums"])) == 0, "native enums not implemented"
        for function in json_array(module["functions"]):
            index: int = json_int(function)
            name: str = json_string(nodes[index]["name"])
            assert name not in definitions, "duplicate function"
            definitions[name] = index
    output: list[str] = [
        "#![allow(unused_mut, unused_variables, unused_parens, dead_code)]\nuse py2rust_service_runtime as rt;"
    ]
    for function_name in definitions:  # noqa: PLC0206 - no items unpacking in portable subset
        trace_phase("emit " + function_name)
        declaration: Json = nodes[definitions[function_name]]
        if json_string(declaration["kind"]) == "Record":
            output.append(render_record(nodes, definitions[function_name], definitions))
            continue
        parameters: list[str] = []
        parameter_names: list[str] = []
        for parameter in json_array(declaration["parameters"]):
            row: Json = nodes[json_int(parameter)]
            parameter_names.append(json_string(row["name"]))
            parameter_type: str = rust_type(nodes, json_int(row["type"]), definitions)
            qualifier: str = "mut "
            if parameter_borrowed(nodes, declaration, row):
                parameter_type = "&" + parameter_type
                qualifier = ""
            parameters.append(qualifier + symbol(json_string(row["name"])) + ": " + parameter_type)
        result: str = rust_type(nodes, json_int(declaration["result"]), definitions)
        signature: str = "fn " + symbol(function_name) + "(" + ", ".join(parameters) + ") -> rt::Result<" + result + ">"
        body: list[str] = local_declarations(nodes, json_array(declaration["body"]), parameter_names, definitions)
        body.extend(emit_block(nodes, json_array(declaration["body"]), definitions, entry))
        success: str = "Ok(())" if result == "()" else ""
        output.append(render_function(signature, body, success))
    main_body: list[str] = []
    for module_root in json_array(document["modules"]):
        module_node: Json = nodes[json_int(module_root)]
        if json_string(module_node["name"]) == entry:
            main_body = local_declarations(nodes, json_array(module_node["body"]), [], definitions)
            main_body.extend(emit_block(nodes, json_array(module_node["body"]), definitions, entry))
        else:
            assert len(json_array(module_node["body"])) == 0, "native imported module execution not implemented"
    output.append(render_function("fn main() -> rt::Result<()>", main_body, "Ok(())"))
    return "\n".join(output)
