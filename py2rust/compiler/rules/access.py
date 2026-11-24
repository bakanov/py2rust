"""Checked indexing and slicing; source adapters prove borrowing and key types."""


def slice_rule(container: str) -> str:
    if container == "list" or container == "tuple_var":
        return "list_slice"
    if container == "bytes" or container == "bytearray":
        return "bytes_slice"
    return ""


def render_sequence_slice(helper: str, source_reference: str, start: str, end: str) -> str:
    if helper == "":
        return ""
    return "rt::" + helper + "(" + source_reference + ", " + start + ", " + end + ")"


def render_text_slice(source_reference: str, start: str, end: str, prepared_index: str, view: bool) -> str:
    if prepared_index != "":
        result = prepared_index + ".slice(" + start + ", " + end + ")"
        if not view:
            result = result + ".to_owned()"
        return result
    helper = "str_slice"
    if view:
        helper = "str_slice_view"
    return "rt::" + helper + "(" + source_reference + ", " + start + ", " + end + ")"


def index_rule(container: str, key: str, prepared_text: bool) -> str:
    if container == "Json":
        if key == "str":
            return "json.key"
        if key == "int":
            return "json.index"
        return ""
    if container == "dict":
        return "dictionary.value"
    if key != "int":
        return ""
    if container == "str":
        if prepared_text:
            return "text.indexed"
        return "text.character"
    if container == "bytes" or container == "bytearray":
        return "byte.value"
    if container == "list" or container == "tuple_var":
        return "sequence.value"
    return ""


def render_index(rule: str, source: str, key: str) -> str:
    """Source is a checked reference, a mapping expression, or a prepared text index."""
    if rule == "json.key":
        return "rt::json_key(" + source + ", &(" + key + "))?"
    if rule == "json.index":
        return "rt::json_index(" + source + ", " + key + ")?"
    if rule == "dictionary.value":
        return "(" + source + ").get(&(" + key + ')).ok_or("missing dict key")?.clone()'
    if rule == "text.indexed":
        return source + ".at(" + key + ")?"
    if rule == "text.character":
        return "rt::char_at(" + source + ", " + key + ")?"
    if rule == "byte.value":
        return "(rt::at(" + source + ", " + key + ")? as i64)"
    if rule == "sequence.value":
        return "rt::at(" + source + ", " + key + ")?"
    return ""


def render_tuple_index(source: str, position: int) -> str:
    """Adapter has already checked the constant position against tuple arity."""
    return "(" + source + ")." + str(position) + ".clone()"
