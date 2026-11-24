"""Named collection mutations and owned copies, independent of source ASTs.

Argument labels `item` and `receiver` refer to the adapter's checked types;
`byteslike` admits bytes or bytearray. Only copy permits a computed receiver.
"""

from dataclasses import dataclass


@dataclass
class CollectionMethodRule:
    key: str
    form: str
    target: str
    first: str
    second: str
    result: str


def select_collection_method(receiver: str, method: str, arity: int, named: bool) -> CollectionMethodRule:
    empty = CollectionMethodRule("", "", "", "", "", "")
    if receiver != "list" and receiver != "dict" and receiver != "set" and receiver != "bytearray":
        return empty
    if method == "copy" and arity == 0:
        return CollectionMethodRule("collection.owned_copy", "copy", "", "", "", "receiver")
    if not named:
        return empty
    if method == "clear" and arity == 0:
        return CollectionMethodRule("collection.clear", "direct", "clear", "", "", "None")
    if receiver == "list":
        if method == "insert" and arity == 2:
            return CollectionMethodRule("list.insert", "insert", "", "int", "item", "None")
        if method == "pop" and (arity == 0 or arity == 1):
            return CollectionMethodRule("list.pop", "pop", "", "int", "", "item")
        if (method == "sort" or method == "reverse") and arity == 0:
            return CollectionMethodRule("list." + method, "direct", method, "", "", "None")
        if method == "extend" and arity == 1:
            return CollectionMethodRule("list.extend", "extend", "", "receiver", "", "None")
        if method == "append" and arity == 1:
            return CollectionMethodRule("list.append", "add", "push", "item", "", "None")
    if receiver == "set" and method == "add" and arity == 1:
        return CollectionMethodRule("set.add", "add", "insert", "item", "", "None")
    if receiver == "bytearray":
        if method == "reverse" and arity == 0:
            return CollectionMethodRule("bytearray.reverse", "direct", "reverse", "", "", "None")
        if method == "append" and arity == 1:
            return CollectionMethodRule("bytearray.append", "byte_append", "", "int", "", "None")
        if method == "extend" and arity == 1:
            return CollectionMethodRule("bytearray.extend", "byte_extend", "", "byteslike", "", "None")
        if method == "pop" and (arity == 0 or arity == 1):
            return CollectionMethodRule("bytearray.pop", "byte_pop", "", "int", "", "int")
    return empty


def render_collection_method(rule: CollectionMethodRule, receiver: str, arguments: list[str]) -> str:
    if rule.form == "copy":
        return receiver
    if rule.form == "direct":
        return receiver + "." + rule.target + "()"
    if rule.form == "insert":
        return (
            "{ let __key = "
            + arguments[0]
            + "; let __value = "
            + arguments[1]
            + "; let __length = "
            + receiver
            + ".len() as i128; let __index = if __key < 0 { (__length + __key as i128).max(0) } "
            + "else { (__key as i128).min(__length) }; "
            + receiver
            + ".insert(__index as usize, __value); }"
        )
    if rule.form == "pop" or rule.form == "byte_pop":
        key = "-1i64"
        if len(arguments) == 1:
            key = arguments[0]
        suffix = ""
        if rule.form == "byte_pop":
            suffix = " as i64"
        return (
            "{ let __key = "
            + key
            + "; let __index = rt::index("
            + receiver
            + ".len(), __key)?; "
            + receiver
            + ".remove(__index)"
            + suffix
            + " }"
        )
    if rule.form == "byte_append":
        return "{ let __value = " + arguments[0] + "; rt::byte_buffer_append(&mut " + receiver + ", __value)?; }"
    if rule.form == "byte_extend":
        return "{ let __values = " + arguments[0] + "; rt::byte_buffer_extend(&mut " + receiver + ", &__values)?; }"
    if rule.form == "extend":
        return "{ let __values = " + arguments[0] + "; " + receiver + ".extend(__values); }"
    if rule.form == "add":
        return "{ " + receiver + "." + rule.target + "(" + arguments[0] + "); }"
    return ""
