"""Iterator representation after ownership and element-type validation.

The memory oracle decides whether the source and elements may be borrowed.
These rules render that decision; they never infer stability from Rust text.
"""

from dataclasses import dataclass


@dataclass
class IterationRule:
    key: str
    form: str
    borrowed_item: bool


def select_iteration(container: str, borrowed_source: bool, scalar_item: bool, borrow_item: bool) -> IterationRule:
    if container == "str":
        return IterationRule("string.characters", "characters", False)
    if container == "bytes" or container == "bytearray":
        if borrowed_source:
            return IterationRule("bytes.borrow", "byte_refs", False)
        return IterationRule("bytes.consume", "byte_values", False)
    if container == "list" or container == "tuple_var" or container == "set" or container == "dict":
        if borrowed_source:
            if borrow_item and not scalar_item:
                return IterationRule("collection.borrow_items", "references", True)
            if scalar_item:
                return IterationRule("collection.copy_items", "copies", False)
            return IterationRule("collection.clone_items", "clones", False)
        if container == "dict":
            return IterationRule("dictionary.owned_keys", "keys", False)
        return IterationRule("collection.owned_items", "owned", False)
    if container == "tuple" and not borrowed_source:
        return IterationRule("tuple.owned_items", "tuple_array", False)
    return IterationRule("", "", False)


def render_iteration(rule: IterationRule, container: str, source: str, tuple_size: int) -> str:
    if rule.form == "characters":
        return "(" + source + ").chars().map(|__character| __character.to_string())"
    if rule.form == "byte_refs":
        return "(" + source + ").iter().copied().map(i64::from)"
    if rule.form == "byte_values":
        return "(" + source + ").into_iter().map(i64::from)"
    if rule.form == "references" or rule.form == "copies" or rule.form == "clones":
        method = "iter()"
        if container == "dict":
            method = "keys()"
        result = "(" + source + ")." + method
        if rule.form == "copies":
            result = result + ".copied()"
        elif rule.form == "clones":
            result = result + ".cloned()"
        return result
    if rule.form == "keys":
        return "(" + source + ").into_keys()"
    if rule.form == "owned":
        return source
    if rule.form == "tuple_array":
        fields: list[str] = []
        for index in range(tuple_size):
            fields.append("__tuple_items." + str(index))
        return "{ let __tuple_items = " + source + "; [" + ", ".join(fields) + "] }"
    return ""


def render_range(arguments: list[str]) -> str:
    if len(arguments) == 1:
        return "0i64.." + arguments[0]
    if len(arguments) == 2:
        return arguments[0] + ".." + arguments[1]
    if len(arguments) == 3:
        return "rt::integer_range(" + ", ".join(arguments) + ")?"
    return ""


def render_for(binding: str, iterator: str, body: str) -> str:
    return "for " + binding + " in " + iterator + " {\n" + body + "\n}"
