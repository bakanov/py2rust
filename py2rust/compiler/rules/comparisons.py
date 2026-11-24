"""Comparison rendering after source type and identity checks.

Membership binds the needle before its container: Rust method syntax alone would
reverse Python's evaluation order. Record equality requires source
admission checks; the adapter traverses types to supply recursive child comparisons.
"""


def membership_rule(needle: str, container: str) -> str:
    if container == "bytes" or container == "bytearray":
        if needle == "int":
            return "bytes.integer"
        if needle == "bytes" or needle == "bytearray":
            return "bytes.buffer"
        return ""
    if container == "Json" and needle == "str":
        return "json.string"
    if container == "dict":
        return "dictionary.key"
    if container == "list" or container == "set" or container == "tuple_var":
        return "collection.item"
    if container == "str" and needle == "str":
        return "string.substring"
    return ""


def render_membership(rule: str, needle: str, container_reference: str, inverted: bool) -> str:
    test = ""
    if rule == "bytes.integer":
        test = "__container.contains(&rt::byte_value(__needle)?)"
    elif rule == "bytes.buffer":
        test = "(rt::bytes_find(__container, &__needle) >= 0)"
    elif rule == "json.string":
        test = "rt::json_contains_string(__container, &__needle)?"
    elif rule == "dictionary.key":
        test = "__container.contains_key(&__needle)"
    elif rule == "collection.item" or rule == "string.substring":
        test = "__container.contains(&__needle)"
    else:
        return ""
    prefix = ""
    if inverted:
        prefix = "!"
    return "{ let __needle = " + needle + "; let __container = " + container_reference + "; " + prefix + test + " }"


def render_null_identity(value: str, is_json: bool, inverted: bool) -> str:
    test = "{ " + value + "; true }"
    if is_json:
        test = "(" + value + ").is_null()"
    if inverted:
        return "!(" + test + ")"
    return test


def render_empty_string(value: str, inverted: bool) -> str:
    prefix = ""
    if inverted:
        prefix = "!"
    return prefix + "(" + value + ").is_empty()"


def render_comparison(operator: str, left: str, right: str) -> str:
    if (
        operator == "=="
        or operator == "!="
        or operator == "<"
        or operator == "<="
        or operator == ">"
        or operator == ">="
    ):
        return "(" + left + " " + operator + " " + right + ")"
    return ""


def render_comparison_chain(values: list[str], names: list[str], tests: list[str]) -> str:
    """Bind each operand once; failed comparisons skip all remaining operands."""
    assert (
        len(tests) >= 1 and len(values) == len(tests) + 1 and len(names) == len(values)
    ), "comparison chain needs one more operand than tests"
    code = tests[-1]
    for index in range(len(tests) - 2, -1, -1):
        code = (
            "if "
            + tests[index]
            + " { let "
            + names[index + 2]
            + " = "
            + values[index + 2]
            + "; "
            + code
            + " } else { false }"
        )
    return "{ let " + names[0] + " = " + values[0] + "; let " + names[1] + " = " + values[1] + "; " + code + " }"


def set_order_rule(type_name: str, contains_set: bool) -> str:
    if type_name == "set":
        return "set.inclusion"
    if not contains_set:
        return "order.direct"
    if type_name == "list" or type_name == "tuple_var":
        return "sequence.first_unequal"
    if type_name == "tuple":
        return "tuple.first_unequal"
    return ""


def render_set_order(rule: str, operator: str, left: str, right: str, children: list[str]) -> str:
    """Compose checked child comparisons; never inherit BTreeSet's total order."""
    assert (
        operator == "<" or operator == "<=" or operator == ">" or operator == ">="
    ), "set ordering requires an ordering operator"
    opening = "{ let __left = " + left + "; let __right = " + right + "; "
    if rule == "set.inclusion":
        method = "is_superset"
        if operator == "<" or operator == "<=":
            method = "is_subset"
        strict = ""
        if operator == "<" or operator == ">":
            strict = "__left != __right && "
        return opening + strict + "__left." + method + "(__right) }"
    if rule == "order.direct":
        return opening + "__left " + operator + " __right }"
    if rule == "sequence.first_unequal":
        assert len(children) == 1, "sequence ordering requires one child comparison"
        return (
            opening
            + "let mut __answer = __left.len() "
            + operator
            + " __right.len(); "
            + "for (__item_left, __item_right) in __left.iter().zip(__right.iter()) { "
            + "if __item_left != __item_right { __answer = "
            + children[0]
            + "; break; } } __answer }"
        )
    if rule == "tuple.first_unequal":
        code = "false"
        if operator == "<=" or operator == ">=":
            code = "true"
        for index in range(len(children) - 1, -1, -1):
            field = str(index)
            code = "if __left." + field + " != __right." + field + " { " + children[index] + " } else { " + code + " }"
        return opening + code + " }"
    return ""
