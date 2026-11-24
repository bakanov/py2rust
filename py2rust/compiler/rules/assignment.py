"""Assignments and deletion for checked places in the owned-value subset.

Assignments evaluate the replacement before indices. Indexed method calls instead
resolve their receiver before evaluating arguments. The adapter must reject
argument/index effects that can detach an already-selected parent collection.
"""


def mapping_receiver(kind: str, name: str) -> str:
    if kind == "Json":
        return name + '.as_object_mut().ok_or("expected JSON object")?'
    return name


def render_index_assignment(kind: str, name: str, key: str, value: str) -> str:
    opening = "{ let __value = " + value + "; let __key = " + key + "; "
    if kind == "bytearray":
        return (
            opening
            + "let __byte = rt::byte_value(__value)?; let __index = rt::index("
            + name
            + ".len(), __key)?; "
            + name
            + "[__index] = __byte; }"
        )
    if kind == "list":
        return opening + "let __index = rt::index(" + name + ".len(), __key)?; " + name + "[__index] = __value; }"
    if kind == "dict" or kind == "Json":
        return opening + mapping_receiver(kind, name) + ".insert(__key, __value); }"
    return ""


def render_delete(kind: str, name: str, key: str) -> str:
    opening = "{ let __key = " + key + "; "
    if kind == "bytearray":
        return opening + "let __index = rt::index(" + name + ".len(), __key)?; " + name + ".remove(__index); }"
    if kind == "dict" or kind == "Json":
        method = "shift_remove"
        if kind == "Json":
            method = "remove"
        return opening + mapping_receiver(kind, name) + "." + method + '(&__key).ok_or("missing dict key")?; }'
    return ""


def render_string_append(target: str, suffix: str, literal: bool) -> str:
    if literal:
        return target + ".push_str(" + suffix + ");"
    return "{ let __append_suffix: String = " + suffix + "; " + target + ".push_str(&__append_suffix); }"


def render_nested_assignment(name: str, keys: list[str], value: str) -> str:
    statements: list[str] = ["let __nested_value = " + value + ";"]
    receiver = name
    for depth in range(len(keys)):
        suffix = str(depth)
        statements.append("let __nested_key_" + suffix + " = " + keys[depth] + ";")
        statements.append(
            "let __nested_index_" + suffix + " = rt::index(" + receiver + ".len(), __nested_key_" + suffix + ")?;"
        )
        receiver = receiver + "[__nested_index_" + suffix + "]"
    statements.append(receiver + " = __nested_value;")
    return "{ " + " ".join(statements) + " }"


def render_indexed_list_mutation(kind: str, name: str, key: str, value: str, method: str) -> str:
    assert method == "push" or method == "extend", "unsupported indexed list mutation"
    opening = "{ let __key = " + key + "; "
    if kind == "list":
        return (
            opening
            + "let __index = rt::index("
            + name
            + ".len(), __key)?; let __value = "
            + value
            + "; "
            + name
            + "[__index]."
            + method
            + "(__value); }"
        )
    if kind == "dict":
        return (
            opening
            + name
            + '.get(&__key).ok_or("missing dict key")?; let __value = '
            + value
            + "; "
            + name
            + '.get_mut(&__key).ok_or("missing dict key")?.'
            + method
            + "(__value); }"
        )
    return ""
