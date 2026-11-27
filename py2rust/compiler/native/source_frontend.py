"""Portable source-to-IR frontend. Unsupported semantics fail before emission."""

from py2rust.stdlib import (
    Json,
    json_array,
    json_bool,
    json_is_null,
    json_int,
    json_keys,
    json_string,
    python_syntax_tree,
)

from ..rules.collection_methods import CollectionMethodRule, select_collection_method
from ..rules.conversions import ConversionRule, select_conversion
from ..rules.numeric import NumericRule, select_numeric_rule, select_unary_rule
from ..rules.strings import StringRule, select_string_rule
from .declarations import (
    annotation,
    declarations,
    dotted_name,
    resolve_name,
    source_label,
)
from .diagnostics import trace_phase
from .ir_builder import build_document
from .runtime_contracts import RuntimeContract, runtime_contract
from .source_ownership import validate_ownership
from .source_records import (
    check_record_cycles,
    record_equality_safe,
    structural_equality_safe,
)
from .source_types import contains_runtime_handle, contract_type


def value_type(name: str) -> Json:
    return {"kind": "ValueType", "name": name, "arguments": []}


def annotation_type(descriptor: Json) -> Json:
    arguments: list[Json] = []
    for argument in json_array(descriptor["arguments"]):
        arguments.append(annotation_type(argument))
    return {"kind": "ValueType", "name": descriptor["name"], "arguments": arguments}


def source_node(node: Json, path: str) -> Json:
    return {"kind": "Source", "path": path, "line": node["line"], "column": node["column"]}


def expression_node(
    node: Json, path: str, operation: str, typ: Json, operands: list[Json], tag: str, text: str, operators: list[str]
) -> Json:
    return {
        "kind": "Expression",
        "source": source_node(node, path),
        "operation": operation,
        "type": typ,
        "operands": operands,
        "value": {"kind": tag, "text": text},
        "operators": operators,
    }


def binding_map(context: Json) -> dict[str, str]:
    result: dict[str, str] = {}
    for key in json_keys(context["bindings"]):
        result[key] = json_string(context["bindings"][key])
    return result


def expression_as(
    node: Json, context: Json, locals: dict[str, Json], functions: dict[str, Json], expected: Json
) -> Json:
    kind: str = json_string(node["kind"])
    path: str = json_string(context["path"])
    expected_name: str = json_string(expected["name"])
    arguments: list[Json] = json_array(expected["arguments"])
    if expected_name == "py2rust.stdlib.Json" and kind in ["List", "Dict"]:
        values: list[Json] = []
        if kind == "List":
            for item in json_array(node["elts"]):
                values.append(expression_as(item, context, locals, functions, expected))
        else:
            keys: list[Json] = json_array(node["keys"])
            entries: list[Json] = json_array(node["values"])
            for index in range(len(keys)):
                assert not json_is_null(keys[index]), source_label(path, node) + ": dictionary unpacking unsupported"
                key: Json = expression(keys[index], context, locals, functions)
                assert key["type"] == value_type("builtins.str"), (
                    source_label(path, keys[index]) + ": JSON object keys require str"
                )
                values.append(key)
                values.append(expression_as(entries[index], context, locals, functions, expected))
        return expression_node(
            node, path, "json_array_literal" if kind == "List" else "json_object", expected, values, "none", "", []
        )
    if kind == "List" and expected_name == "builtins.list":
        items: list[Json] = []
        for item in json_array(node["elts"]):
            lowered: Json = expression_as(item, context, locals, functions, arguments[0])
            assert lowered["type"] == arguments[0], source_label(path, item) + ": list item type mismatch"
            items.append(lowered)
        return expression_node(node, path, "list", expected, items, "none", "", [])
    if kind == "Dict" and expected_name == "builtins.dict":
        dictionary_values: list[Json] = []
        dictionary_keys: list[Json] = json_array(node["keys"])
        dictionary_items: list[Json] = json_array(node["values"])
        for index in range(len(dictionary_keys)):
            assert not json_is_null(dictionary_keys[index]), (
                source_label(path, node) + ": dictionary unpacking unsupported"
            )
            key_value: Json = expression_as(dictionary_keys[index], context, locals, functions, arguments[0])
            item_value: Json = expression_as(dictionary_items[index], context, locals, functions, arguments[1])
            assert key_value["type"] == arguments[0] and item_value["type"] == arguments[1], (
                source_label(path, node) + ": dictionary item type mismatch"
            )
            assert json_string(arguments[0]["name"]) in ["builtins.str", "builtins.int", "builtins.bool"], (
                source_label(path, node) + ": unsupported dictionary key type"
            )
            dictionary_values.append(key_value)
            dictionary_values.append(item_value)
        return expression_node(node, path, "dict", expected, dictionary_values, "none", "", [])
    value: Json = expression(node, context, locals, functions)
    if expected_name == "py2rust.stdlib.Json" and value["type"] != expected:
        assert not contains_runtime_handle(value["type"]), source_label(path, node) + ": opaque resources are not JSON"
        return expression_node(node, path, "json_coerce", expected, [value], "none", "", [])
    return value


def expression(node: Json, context: Json, locals: dict[str, Json], functions: dict[str, Json]) -> Json:
    path: str = json_string(context["path"])
    position: str = source_label(path, node)
    kind: str = json_string(node["kind"])
    if kind == "Constant":
        tag: str = json_string(node["tag"])
        text: str = json_string(node["text"])
        name: str = "None"
        if tag in ["str", "bytes", "bool"]:
            name = "builtins." + tag
        elif tag == "number":
            text = text.replace("_", "")
            if "." in text or "e" in text or "E" in text:
                tag = "float"
                text = str(float(text))
            else:
                for digit in text:
                    assert digit in "0123456789", position + ": only decimal integer literals are supported"
                tag = "int"
                text = str(int(text))
            name = "builtins." + tag
        else:
            assert tag == "none", position + ": unsupported literal"
        return expression_node(node, path, "literal", value_type(name), [], tag, text, [])
    if kind == "Name":
        name = json_string(node["id"])
        if name == "__name__" and name not in locals:
            module_name: str = json_string(context["name"])
            if module_name == json_string(context["entry"]):
                module_name = "__main__"
            return expression_node(node, path, "literal", value_type("builtins.str"), [], "str", module_name, [])
        assert name in locals, position + ": name is not definitely assigned: " + name
        return expression_node(node, path, "name", locals[name], [], "str", name, [])
    if kind == "List" or kind == "Dict":
        type_arguments: list[Json] = []
        if kind == "List":
            items: list[Json] = json_array(node["elts"])
            assert len(items) > 0, position + ": empty list requires an expected type"
            first: Json = expression(items[0], context, locals, functions)
            type_arguments.append(first["type"])
        else:
            keys: list[Json] = json_array(node["keys"])
            assert len(keys) > 0 and not json_is_null(keys[0]), (
                position + ": empty or unpacked dict requires an expected type"
            )
            first_key: Json = expression(keys[0], context, locals, functions)
            first_value: Json = expression(node["values"][0], context, locals, functions)
            type_arguments.append(first_key["type"])
            type_arguments.append(first_value["type"])
        container: Json = {
            "kind": "ValueType",
            "name": "builtins.list" if kind == "List" else "builtins.dict",
            "arguments": type_arguments,
        }
        return expression_as(node, context, locals, functions, container)
    if kind == "JoinedStr":
        result: Json = expression_node(node, path, "literal", value_type("builtins.str"), [], "str", "", [])
        for item in json_array(node["values"]):
            part: Json = result
            if json_string(item["kind"]) == "Constant":
                part = expression(item, context, locals, functions)
            else:
                assert json_string(item["kind"]) == "FormattedValue", position + ": unsupported f-string item"
                assert json_is_null(item["format_spec"]), position + ": f-string format specifications are unsupported"
                formatted: Json = expression(item["value"], context, locals, functions)
                conversion_flag: int = json_int(item["conversion"])
                spec: str = "!r" if conversion_flag == 114 else ""
                part = expression_node(
                    item, path, "format_value", value_type("builtins.str"), [formatted], "str", spec, []
                )
            result = expression_node(item, path, "binary", value_type("builtins.str"), [result, part], "str", "+", [])
        return result
    if kind == "Attribute":
        owner: Json = expression(node["value"], context, locals, functions)
        owner_type: str = json_string(owner["type"]["name"])
        assert owner_type in json_keys(context["records"]), position + ": field access requires a record"
        field_name: str = json_string(node["attr"])
        for field in json_array(context["records"][owner_type]["fields"]):
            if json_string(field["name"]) == field_name:
                return expression_node(
                    node, path, "field", annotation_type(field["type"]), [owner], "str", field_name, []
                )
        assert False, position + ": unknown record field: " + field_name
        return {}
    if kind == "Subscript":
        receiver: Json = expression(node["value"], context, locals, functions)
        if json_string(node["slice"]["kind"]) == "Slice":
            slice_node: Json = node["slice"]
            assert json_is_null(slice_node["step"]), position + ": slice steps are unsupported"
            assert json_string(receiver["type"]["name"]) in [
                "builtins.str",
                "builtins.bytes",
                "builtins.bytearray",
                "builtins.list",
            ], (
                position + ": unsupported sliced type"
            )
            slice_values: list[Json] = [receiver]
            slice_operators: list[str] = []
            for field in ["lower", "upper"]:
                if not json_is_null(slice_node[field]):
                    bound: Json = expression(slice_node[field], context, locals, functions)
                    assert bound["type"] == value_type("builtins.int"), position + ": slice bound requires int"
                    slice_values.append(bound)
                    slice_operators.append("start" if field == "lower" else "stop")
            return expression_node(node, path, "slice", receiver["type"], slice_values, "none", "", slice_operators)
        index_value: Json = expression(node["slice"], context, locals, functions)
        container_name: str = json_string(receiver["type"]["name"])
        item_type: Json = value_type("None")
        container_arguments: list[Json] = json_array(receiver["type"]["arguments"])
        if container_name == "builtins.list":
            assert index_value["type"] == value_type("builtins.int"), position + ": list index requires int"
            item_type = container_arguments[0]
        elif container_name == "builtins.dict":
            assert index_value["type"] == container_arguments[0], position + ": dictionary key type mismatch"
            item_type = container_arguments[1]
        elif container_name == "py2rust.stdlib.Json":
            assert json_string(index_value["type"]["name"]) in ["builtins.str", "builtins.int"], (
                position + ": JSON index requires str or int"
            )
            item_type = receiver["type"]
        elif container_name in ["builtins.str", "builtins.bytes", "builtins.bytearray"]:
            assert index_value["type"] == value_type("builtins.int"), position + ": index requires int"
            item_type = value_type("builtins.str" if container_name == "builtins.str" else "builtins.int")
        else:
            assert False, position + ": unsupported indexed type"
        return expression_node(node, path, "index", item_type, [receiver, index_value], "none", "", [])
    if kind == "UnaryOp":
        operand: Json = expression(node["operand"], context, locals, functions)
        unary_names: dict[str, str] = {"USub": "-", "UAdd": "+", "Not": "not", "Invert": "~"}
        unary_name: str = json_string(node["op"])
        assert unary_name in unary_names, position + ": unsupported unary operator"
        operand_name: str = json_string(operand["type"]["name"])
        if unary_name == "UAdd":
            assert operand_name in ["builtins.int", "builtins.float"], position + ": unary plus requires a number"
            return operand
        unary_rule: NumericRule = select_unary_rule(unary_names[unary_name], operand_name[9:])
        assert unary_rule.key != "", position + ": unsupported unary operand"
        return expression_node(
            node,
            path,
            "unary",
            value_type("builtins." + unary_rule.result),
            [operand],
            "str",
            unary_names[unary_name],
            [],
        )
    if kind == "BoolOp":
        boolean_values: list[Json] = []
        for item in json_array(node["values"]):
            boolean: Json = expression(item, context, locals, functions)
            assert boolean["type"] == value_type("builtins.bool"), position + ": boolean operand required"
            boolean_values.append(boolean)
        boolean_operator: str = json_string(node["op"])
        assert boolean_operator in ["And", "Or"], position + ": unsupported boolean operator"
        return expression_node(
            node,
            path,
            "short_circuit",
            value_type("builtins.bool"),
            boolean_values,
            "str",
            "and" if boolean_operator == "And" else "or",
            [],
        )
    if kind == "IfExp":
        test: Json = expression(node["test"], context, locals, functions)
        yes: Json = expression(node["body"], context, locals, functions)
        no: Json = expression(node["orelse"], context, locals, functions)
        assert test["type"] == value_type("builtins.bool"), position + ": boolean condition required"
        assert yes["type"] == no["type"], position + ": conditional expression types differ"
        return expression_node(node, path, "conditional", yes["type"], [test, yes, no], "none", "", [])
    if kind == "BinOp":
        left: Json = expression(node["left"], context, locals, functions)
        right: Json = expression(node["right"], context, locals, functions)
        operations: dict[str, str] = {
            "Add": "+",
            "Sub": "-",
            "Mult": "*",
            "Div": "/",
            "FloorDiv": "//",
            "Mod": "%",
            "Pow": "**",
            "LShift": "<<",
            "RShift": ">>",
            "BitAnd": "&",
            "BitOr": "|",
            "BitXor": "^",
        }
        operator: str = json_string(node["op"])
        assert operator in operations, position + ": unsupported binary operator"
        left_name: str = json_string(left["type"]["name"])
        right_name: str = json_string(right["type"]["name"])
        result_name: str = left_name
        assert left_name == right_name, position + ": binary operands must have matching types"
        if left_name == "builtins.str":
            assert operator == "Add", position + ": unsupported string operation"
        else:
            assert left_name in ["builtins.int", "builtins.float"], position + ": numeric operands required"
            rule: NumericRule = select_numeric_rule(operations[operator], left_name[9:], right_name[9:])
            assert rule.key != "", position + ": unsupported numeric operation"
            result_name = "builtins." + rule.result
        return expression_node(
            node, path, "binary", value_type(result_name), [left, right], "str", operations[operator], []
        )
    if kind == "Compare":
        operands: list[Json] = [expression(node["left"], context, locals, functions)]
        for comparator in json_array(node["comparators"]):
            operands.append(expression(comparator, context, locals, functions))
        comparisons: dict[str, str] = {
            "Eq": "==",
            "NotEq": "!=",
            "Lt": "<",
            "LtE": "<=",
            "Gt": ">",
            "GtE": ">=",
            "In": "in",
            "NotIn": "not in",
        }
        operators: list[str] = []
        for operation in json_array(node["ops"]):
            key: str = json_string(operation)
            assert key in comparisons, position + ": unsupported comparison"
            operators.append(comparisons[key])
        for index in range(len(operators)):
            left_type: Json = operands[index]["type"]
            right_type: Json = operands[index + 1]["type"]
            if operators[index] in ["in", "not in"]:
                assert not contains_runtime_handle(left_type), position + ": opaque resource membership unsupported"
                right_name: str = json_string(right_type["name"])
                if right_name == "builtins.str":
                    assert left_type == value_type("builtins.str"), position + ": string membership requires str"
                else:
                    assert right_name in ["builtins.list", "builtins.dict"], (
                        position + ": unsupported membership container"
                    )
                    assert left_type == right_type["arguments"][0], position + ": membership type mismatch"
            else:
                assert left_type == right_type, position + ": comparison types differ"
                assert json_string(left_type["name"]) in [
                    "builtins.str",
                    "builtins.int",
                    "builtins.float",
                    "builtins.bool",
                ] or (
                    operators[index] in ["==", "!="]
                    and (
                        json_string(left_type["name"]) == "py2rust.stdlib.Json"
                        or json_string(left_type["name"]) in json_keys(context["records"])
                        or structural_equality_safe(left_type, context["records"])
                    )
                ), (
                    position + ": unsupported comparison type"
                )
        for operand in operands:
            compared_name: str = json_string(operand["type"]["name"])
            if compared_name in json_keys(context["records"]):
                assert record_equality_safe(compared_name, context["records"]), (
                    position + ": JSON-valued record equality requires semantic comparison lowering"
                )
        return expression_node(
            node, path, "compare_chain", value_type("builtins.bool"), operands, "none", "", operators
        )
    if kind == "Call":
        constructor: str = resolve_name(dotted_name(node["func"]), binding_map(context))
        if constructor in json_keys(context["records"]):
            constructor_root: str = dotted_name(node["func"]).split(".")[0]
            assert constructor_root not in locals, position + ": shadowed record constructor"
            fields: list[Json] = json_array(context["records"][constructor]["fields"])
            supplied: list[Json] = json_array(node["args"])
            labels: list[str] = []
            raw_values: list[Json] = []
            assert len(supplied) <= len(fields), position + ": too many record arguments"
            for index in range(len(supplied)):
                labels.append(json_string(fields[index]["name"]))
                raw_values.append(supplied[index])
            for keyword in json_array(node["keywords"]):
                assert not json_is_null(keyword["arg"]), position + ": record keyword unpacking unsupported"
                labels.append(json_string(keyword["arg"]))
                raw_values.append(keyword["value"])
            provided: list[str] = []
            constructor_values: list[Json] = []
            for index in range(len(labels)):
                field_name: str = labels[index]
                assert field_name not in provided, position + ": duplicate record argument: " + field_name
                required: Json = None
                for field in fields:
                    if json_string(field["name"]) == field_name:
                        required = annotation_type(field["type"])
                assert not json_is_null(required), position + ": unknown record keyword: " + field_name
                argument: Json = expression_as(raw_values[index], context, locals, functions, required)
                assert argument["type"] == required, position + ": record argument type mismatch"
                constructor_values.append(argument)
                provided.append(field_name)
            for field in fields:
                assert json_string(field["name"]) in provided or not json_is_null(field["default"]), (
                    position + ": missing record argument: " + json_string(field["name"])
                )
            return expression_node(
                node, path, "construct", value_type(constructor), constructor_values, "str", constructor, labels
            )
        assert len(json_array(node["keywords"])) == 0, position + ": keyword calls are not yet lowered"
        called: Json = node["func"]
        if json_string(called["kind"]) == "Attribute":
            owner_name: str = dotted_name(called["value"])
            if owner_name == "" or owner_name.split(".")[0] in locals:
                receiver: Json = expression(called["value"], context, locals, functions)
                method: str = json_string(called["attr"])
                supplied: list[Json] = json_array(node["args"])
                receiver_name: str = json_string(receiver["type"]["name"])
                if receiver_name in ["builtins.list", "builtins.dict"]:
                    collection_rule: CollectionMethodRule = select_collection_method(
                        receiver_name[9:], method, len(supplied), json_string(receiver["operation"]) == "name"
                    )
                    assert collection_rule.key != "" and method != "sort", (
                        position + ": unsupported collection method overload"
                    )
                    collection_arguments: list[Json] = json_array(receiver["type"]["arguments"])
                    collection_values: list[Json] = [receiver]
                    specifications: list[str] = [collection_rule.first, collection_rule.second]
                    for index in range(len(supplied)):
                        required: Json = value_type("builtins.int")
                        if specifications[index] == "item":
                            required = collection_arguments[0]
                        elif specifications[index] == "receiver":
                            required = receiver["type"]
                        else:
                            assert specifications[index] == "int", (
                                position + ": unsupported collection argument contract"
                            )
                        supplied_value: Json = expression_as(supplied[index], context, locals, functions, required)
                        assert supplied_value["type"] == required, (
                            position + ": collection method argument type mismatch"
                        )
                        collection_values.append(supplied_value)
                    result_type: Json = value_type("None")
                    if collection_rule.result == "item":
                        result_type = collection_arguments[0]
                    elif collection_rule.result == "receiver":
                        result_type = receiver["type"]
                    return expression_node(node, path, "method_call", result_type, collection_values, "str", method, [])
                assert receiver["type"] == value_type("builtins.str"), (
                    position + ": source method receiver is not yet supported"
                )
                string_rule: StringRule = select_string_rule("str", method, len(supplied))
                assert string_rule.key != "" and string_rule.form != "trim", (
                    position + ": unsupported string method overload"
                )
                method_values: list[Json] = [receiver]
                for argument_node in supplied:
                    argument: Json = expression_as(
                        argument_node, context, locals, functions, contract_type(string_rule.argument)
                    )
                    assert argument["type"] == contract_type(string_rule.argument), (
                        position + ": string method argument type mismatch"
                    )
                    method_values.append(argument)
                return expression_node(
                    node, path, "method_call", contract_type(string_rule.result), method_values, "str", method, []
                )
        called_name: str = dotted_name(node["func"])
        assert called_name != "" and called_name.split(".")[0] not in locals, (
            position + ": local callable values are unsupported"
        )
        target: str = resolve_name(called_name, binding_map(context))
        source_arguments: list[Json] = json_array(node["args"])
        arguments: list[Json] = []
        result_type: Json = value_type("None")
        if target.startswith("py2rust.stdlib."):
            contract: RuntimeContract = runtime_contract(target[15:])
            assert len(source_arguments) == len(contract.parameters), position + ": runtime argument count mismatch"
            for index in range(len(source_arguments)):
                required: Json = contract_type(
                    "Json" if contract.parameters[index] == "*" else contract.parameters[index]
                )
                argument: Json = expression_as(source_arguments[index], context, locals, functions, required)
                assert argument["type"] == required, position + ": runtime argument type mismatch"
                arguments.append(argument)
            return expression_node(
                node, path, "runtime_call", contract_type(contract.result), arguments, "str", contract.name, []
            )
        if target == "bytes.fromhex":
            assert len(source_arguments) == 1, position + ": bytes.fromhex requires one argument"
            argument: Json = expression(source_arguments[0], context, locals, functions)
            assert argument["type"] == value_type("builtins.str"), position + ": bytes.fromhex requires str"
            return expression_node(
                node, path, "call", value_type("builtins.bytes"), [argument], "str", "builtins.bytes.fromhex", [""]
            )
        if target in ["print", "len", "str", "int", "float", "ord"]:
            for source_argument in source_arguments:
                arguments.append(expression(source_argument, context, locals, functions))
            if target == "print":
                target = "builtins.print"
                for argument in arguments:
                    assert json_string(argument["type"]["name"]) in [
                        "builtins.str",
                        "builtins.int",
                        "builtins.float",
                        "builtins.bool",
                    ], (
                        position + ": scalar print arguments required"
                    )
            elif target == "ord":
                assert len(arguments) == 1 and json_string(arguments[0]["type"]["name"]) in [
                    "builtins.str",
                    "builtins.bytes",
                    "builtins.bytearray",
                ], (
                    position + ": ord requires text or bytes"
                )
                result_type = value_type("builtins.int")
                target = "builtins.ord"
            elif target in ["str", "int", "float"]:
                assert len(arguments) == 1, position + ": conversion requires one argument"
                source_type: str = json_string(arguments[0]["type"]["name"])
                assert source_type.startswith("builtins."), position + ": unsupported scalar conversion"
                conversion: ConversionRule = select_conversion(target, source_type[9:])
                assert conversion.key != "", position + ": unsupported scalar conversion"
                result_type = value_type("builtins." + target)
                target = "builtins." + target
            else:
                assert len(arguments) == 1, position + ": len requires one argument"
                assert json_string(arguments[0]["type"]["name"]) in [
                    "builtins.str",
                    "builtins.bytes",
                    "builtins.bytearray",
                    "builtins.list",
                    "builtins.dict",
                ], (
                    position + ": unsupported len argument"
                )
                target = "builtins.len"
                result_type = value_type("builtins.int")
        else:
            assert target in functions, position + ": unknown function: " + target
            function: Json = functions[target]
            parameters: list[Json] = json_array(function["parameters"])
            assert len(parameters) == len(source_arguments), position + ": argument count mismatch"
            for index in range(len(source_arguments)):
                required = annotation_type(parameters[index]["type"])
                argument = expression_as(source_arguments[index], context, locals, functions, required)
                assert argument["type"] == required, position + ": argument type mismatch"
                arguments.append(argument)
            result_type = annotation_type(function["result"])
        labels: list[str] = []
        for argument in arguments:
            labels.append("")
        return expression_node(node, path, "call", result_type, arguments, "str", target, labels)
    assert False, position + ": source expression not yet lowered: " + kind
    return {}


def statement_node(
    node: Json, path: str, operation: str, expressions: list[Json], blocks: list[Json], target: Json, typ: Json
) -> Json:
    return {
        "kind": "Statement",
        "source": source_node(node, path),
        "operation": operation,
        "expressions": expressions,
        "blocks": blocks,
        "target": target,
        "target_type": typ,
        "handlers": [],
        "declaration": not json_is_null(typ),
    }


def block(
    body: list[Json], context: Json, initial: dict[str, Json], functions: dict[str, Json], expected: Json
) -> Json:
    locals: dict[str, Json] = initial.copy()
    statements: list[Json] = []
    terminated: bool = False
    path: str = json_string(context["path"])
    for node in body:
        assert not terminated, source_label(path, node) + ": unreachable statement"
        kind: str = json_string(node["kind"])
        if kind in ["Import", "ImportFrom", "FunctionDef", "ClassDef"]:
            assert json_bool(context["top_level"]), source_label(path, node) + ": nested declarations are unsupported"
            continue
        if kind == "Pass":
            continue
        if kind == "Expr":
            literal: Json = node["value"]
            if json_string(literal["kind"]) == "Constant" and json_string(literal["tag"]) == "str":
                continue
            value: Json = expression(node["value"], context, locals, functions)
            statements.append(statement_node(node, path, "expression", [value], [], None, None))
        elif kind == "Assert":
            tested: Json = expression(node["test"], context, locals, functions)
            assert tested["type"] == value_type("builtins.bool"), source_label(path, node) + ": assertion requires bool"
            assertion_values: list[Json] = [tested]
            if not json_is_null(node["msg"]):
                message: Json = expression(node["msg"], context, locals, functions)
                assert message["type"] == value_type("builtins.str"), (
                    source_label(path, node) + ": assertion message requires str"
                )
                assertion_values.append(message)
            statements.append(statement_node(node, path, "assert", assertion_values, [], None, None))
        elif kind == "Break" or kind == "Continue":
            assert json_bool(context["in_loop"]), source_label(path, node) + ": loop control outside loop"
            statements.append(
                statement_node(node, path, "break" if kind == "Break" else "continue", [], [], None, None)
            )
            terminated = True
        elif kind == "While" or kind == "For":
            assert not json_bool(context["module_body"]), (
                source_label(path, node) + ": module loops are not yet lowered"
            )
            assert len(json_array(node["orelse"])) == 0, source_label(path, node) + ": loop else is not yet lowered"
            loop_context: Json = {
                "path": context["path"],
                "name": context["name"],
                "entry": context["entry"],
                "bindings": context["bindings"],
                "records": context["records"],
                "module_body": False,
                "in_loop": True,
                "top_level": False,
            }
            loop_locals: dict[str, Json] = locals.copy()
            loop_target: Json = None
            loop_type: Json = None
            loop_expression: Json = None
            if kind == "While":
                loop_expression = expression(node["test"], context, locals, functions)
                assert loop_expression["type"] == value_type("builtins.bool"), (
                    source_label(path, node) + ": boolean loop condition required"
                )
            else:
                assert json_string(node["target"]["kind"]) == "Name", (
                    source_label(path, node) + ": named iteration target required"
                )
                loop_name: str = json_string(node["target"]["id"])
                assert loop_name not in locals, source_label(path, node) + ": iteration target already bound"
                iterable: Json = node["iter"]
                if (
                    json_string(iterable["kind"]) == "Call"
                    and resolve_name(dotted_name(iterable["func"]), binding_map(context)) == "range"
                ):
                    assert "range" not in locals and len(json_array(iterable["keywords"])) == 0, (
                        source_label(path, node) + ": invalid range binding or keywords"
                    )
                    bounds: list[Json] = []
                    for bound in json_array(iterable["args"]):
                        range_value: Json = expression(bound, context, locals, functions)
                        assert range_value["type"] == value_type("builtins.int"), (
                            source_label(path, bound) + ": range bound requires int"
                        )
                        bounds.append(range_value)
                    assert len(bounds) >= 1 and len(bounds) <= 3, (
                        source_label(path, node) + ": range expects one to three bounds"
                    )
                    loop_expression = expression_node(
                        iterable, path, "call", value_type("builtins.range"), bounds, "str", "builtins.range", []
                    )
                    loop_type = value_type("builtins.int")
                else:
                    loop_expression = expression(iterable, context, locals, functions)
                    iterable_type: str = json_string(loop_expression["type"]["name"])
                    if iterable_type in ["builtins.list", "builtins.dict"]:
                        loop_type = loop_expression["type"]["arguments"][0]
                    elif iterable_type in ["builtins.str", "builtins.bytes", "builtins.bytearray"]:
                        loop_type = value_type("builtins.str" if iterable_type == "builtins.str" else "builtins.int")
                    else:
                        assert False, source_label(path, node) + ": unsupported iterable type"
                loop_target = loop_name
                loop_locals[loop_name] = loop_type
            loop_body: Json = block(json_array(node["body"]), loop_context, loop_locals, functions, expected)
            statements.append(
                statement_node(
                    node,
                    path,
                    "while" if kind == "While" else "for",
                    [loop_expression],
                    [loop_body["body"], []],
                    loop_target,
                    loop_type,
                )
            )
        elif kind == "Return":
            assert not json_bool(context["module_body"]), source_label(path, node) + ": return outside function"
            values: list[Json] = []
            actual: Json = value_type("None")
            if not json_is_null(node["value"]):
                returned: Json = expression_as(node["value"], context, locals, functions, expected)
                actual = returned["type"]
                values.append(returned)
            assert actual == expected, source_label(path, node) + ": return type mismatch"
            statements.append(statement_node(node, path, "return", values, [], None, None))
            terminated = True
        elif kind == "Assign" or kind == "AnnAssign":
            assert not json_bool(context["module_body"]), (
                source_label(path, node) + ": module variable bindings are not yet lowered"
            )
            assert not json_is_null(node["value"]), source_label(path, node) + ": assignment requires a value"
            target: Json = None
            if kind == "Assign":
                targets: list[Json] = json_array(node["targets"])
                assert len(targets) == 1, source_label(path, node) + ": chained assignment is unsupported"
                target = targets[0]
            else:
                target = node["target"]
            if json_string(target["kind"]) == "Subscript":
                assert kind == "Assign", source_label(path, node) + ": indexed annotations are unsupported"
                receiver: Json = expression(target["value"], context, locals, functions)
                assert json_string(receiver["operation"]) == "name", (
                    source_label(path, node) + ": nested mutation is unsupported"
                )
                key: Json = expression(target["slice"], context, locals, functions)
                receiver_type: str = json_string(receiver["type"]["name"])
                arguments: list[Json] = json_array(receiver["type"]["arguments"])
                required: Json = value_type("None")
                key_type: Json = value_type("builtins.int")
                if receiver_type == "builtins.list":
                    required = arguments[0]
                elif receiver_type == "builtins.dict":
                    key_type = arguments[0]
                    required = arguments[1]
                else:
                    assert receiver_type == "py2rust.stdlib.Json", (
                        source_label(path, node) + ": unsupported indexed store"
                    )
                    key_type = value_type("builtins.str")
                    required = receiver["type"]
                assert key["type"] == key_type, source_label(path, node) + ": indexed store key type mismatch"
                replacement: Json = expression_as(node["value"], context, locals, functions, required)
                assert replacement["type"] == required, source_label(path, node) + ": indexed store value type mismatch"
                statements.append(
                    statement_node(node, path, "store_index", [replacement, receiver, key], [], None, None)
                )
                continue
            assert json_string(target["kind"]) == "Name", source_label(path, node) + ": named assignment required"
            name: str = json_string(target["id"])
            typ: Json = value_type("None")
            assigned: Json = None
            if kind == "AnnAssign":
                typ = annotation_type(
                    annotation(node["annotation"], binding_map(context), json_keys(context["records"]), path)
                )
                assigned = expression_as(node["value"], context, locals, functions, typ)
                assert typ == assigned["type"], source_label(path, node) + ": assignment type mismatch"
            elif name in locals:
                typ = locals[name]
                assigned = expression_as(node["value"], context, locals, functions, typ)
                assert assigned["type"] == typ, source_label(path, node) + ": local changes type"
            else:
                assigned = expression(node["value"], context, locals, functions)
                typ = assigned["type"]
            if name in locals:
                assert locals[name] == typ, source_label(path, node) + ": local changes type"
            locals[name] = typ
            statements.append(statement_node(node, path, "assign", [assigned], [], name, typ))
        elif kind == "Delete":
            for target in json_array(node["targets"]):
                assert json_string(target["kind"]) == "Subscript", (
                    source_label(path, node) + ": only indexed deletion is supported"
                )
                receiver: Json = expression(target["value"], context, locals, functions)
                assert json_string(receiver["operation"]) == "name", (
                    source_label(path, node) + ": named deletion receiver required"
                )
                receiver_type: str = json_string(receiver["type"]["name"])
                assert receiver_type in ["builtins.dict", "py2rust.stdlib.Json"], (
                    source_label(path, node) + ": only mapping deletion is supported"
                )
                key_type: Json = value_type("builtins.str")
                if receiver_type == "builtins.dict":
                    key_type = receiver["type"]["arguments"][0]
                key: Json = expression(target["slice"], context, locals, functions)
                assert key["type"] == key_type, source_label(path, node) + ": deletion key type mismatch"
                statements.append(statement_node(node, path, "delete_index", [receiver, key], [], None, None))
        elif kind == "If":
            condition: Json = expression(node["test"], context, locals, functions)
            assert condition["type"] == value_type("builtins.bool"), (
                source_label(path, node) + ": boolean condition required"
            )
            branch_context: Json = {
                "path": context["path"],
                "name": context["name"],
                "entry": context["entry"],
                "bindings": context["bindings"],
                "records": context["records"],
                "module_body": context["module_body"],
                "in_loop": context["in_loop"],
                "top_level": False,
            }
            then: Json = block(json_array(node["body"]), branch_context, locals, functions, expected)
            other: Json = block(json_array(node["orelse"]), branch_context, locals, functions, expected)
            for name in json_keys(then["locals"]):
                if name in json_keys(other["locals"]):
                    assert then["locals"][name] == other["locals"][name], (
                        source_label(path, node) + ": branch types differ"
                    )
                    locals[name] = then["locals"][name]
            statements.append(statement_node(node, path, "if", [condition], [then["body"], other["body"]], None, None))
            terminated = json_bool(then["terminated"]) and json_bool(other["terminated"])
        else:
            assert False, source_label(path, node) + ": source statement not yet lowered: " + kind
    return {"body": statements, "locals": locals, "terminated": terminated}


def compile_sources(sources: list[Json], entry: str) -> Json:
    trace_phase("parse")
    parsed: list[Json] = []
    for source in sources:
        parsed.append(
            {
                "name": source["name"],
                "package": source["package"],
                "path": source["path"],
                "tree": python_syntax_tree(json_string(source["source"])),
            }
        )
    trace_phase("declarations")
    program: Json = declarations(parsed)
    functions: dict[str, Json] = {}
    records: dict[str, Json] = {}
    for module in json_array(program["modules"]):
        for record in json_array(module["records"]):
            records[json_string(record["name"])] = {
                "name": record["name"],
                "fields": record["fields"],
                "syntax": record["syntax"],
                "path": module["path"],
            }
        for function in json_array(module["functions"]):
            functions[json_string(function["name"])] = function
    check_record_cycles(records)
    modules: list[Json] = []
    for module in json_array(program["modules"]):
        trace_phase("lower " + json_string(module["name"]))
        context: Json = {
            "name": module["name"],
            "entry": entry,
            "path": module["path"],
            "bindings": module["bindings"],
            "records": records,
            "module_body": False,
            "in_loop": False,
            "top_level": False,
        }
        record_nodes: list[Json] = []
        for record in json_array(module["records"]):
            field_nodes: list[Json] = []
            saw_default: bool = False
            for field in json_array(record["fields"]):
                field_type: Json = annotation_type(field["type"])
                default: Json = None
                if not json_is_null(field["default"]):
                    assert json_string(field["default"]["kind"]) == "Constant", (
                        source_label(json_string(module["path"]), field["syntax"])
                        + ": record defaults require scalar literals"
                    )
                    default = expression(field["default"], context, {}, functions)
                    assert default["type"] == field_type, (
                        source_label(json_string(module["path"]), field["syntax"]) + ": record default type mismatch"
                    )
                    saw_default = True
                else:
                    assert not saw_default, (
                        source_label(json_string(module["path"]), field["syntax"])
                        + ": required record field follows default"
                    )
                field_nodes.append(
                    {
                        "kind": "Field",
                        "name": field["name"],
                        "type": field_type,
                        "default": default,
                        "source": source_node(field["syntax"], json_string(module["path"])),
                    }
                )
            record_nodes.append(
                {
                    "kind": "Record",
                    "name": record["name"],
                    "fields": field_nodes,
                    "source": source_node(record["syntax"], json_string(module["path"])),
                }
            )
        lowered: list[Json] = []
        for function in json_array(module["functions"]):
            parameters: list[Json] = []
            locals: dict[str, Json] = {}
            for parameter in json_array(function["parameters"]):
                assert json_is_null(parameter["default"]), "default parameters are not yet lowered"
                typ: Json = annotation_type(parameter["type"])
                name: str = json_string(parameter["name"])
                locals[name] = typ
                parameters.append({"kind": "Parameter", "name": name, "type": typ})
            result: Json = annotation_type(function["result"])
            body: Json = block(json_array(function["syntax"]["body"]), context, locals, functions, result)
            assert result == value_type("None") or json_bool(body["terminated"]), (
                source_label(json_string(module["path"]), function["syntax"]) + ": function may exit without returning"
            )
            lowered.append(
                {
                    "kind": "Function",
                    "name": function["name"],
                    "parameters": parameters,
                    "result": result,
                    "body": body["body"],
                    "defaults": [],
                    "source": source_node(function["syntax"], json_string(module["path"])),
                }
            )
        context["module_body"] = True
        context["top_level"] = True
        main: Json = block(json_array(module["syntax"]["body"]), context, {}, functions, value_type("None"))
        modules.append(
            {
                "kind": "Module",
                "name": module["name"],
                "functions": lowered,
                "body": main["body"],
                "records": record_nodes,
                "enums": [],
            }
        )
    trace_phase("ownership")
    validate_ownership(modules)
    trace_phase("flatten IR")
    return build_document(modules, entry)
