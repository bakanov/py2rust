"""Collection reads: preserve evaluation and distinguish characters from bytes."""


def length_rule(type_name: str, indexed_text: bool, cached_text: bool) -> str:
    if type_name == "str":
        if indexed_text:
            return "length.text_index"
        if cached_text:
            return "length.text_cache"
        return "length.characters"
    if type_name == "tuple":
        return "length.fixed_tuple"
    if (
        type_name == "bytes"
        or type_name == "bytearray"
        or type_name == "list"
        or type_name == "tuple_var"
        or type_name == "dict"
        or type_name == "set"
    ):
        return "length.collection"
    return ""


def render_length(rule: str, value: str, tuple_size: int, local_name: str, index: str) -> str:
    if rule == "length.text_index":
        return "(" + index + ".len() as i64)"
    if rule == "length.text_cache":
        return "(*__length_" + local_name + ".get_or_init(|| " + local_name + ".chars().count() as i64))"
    if rule == "length.characters":
        return "((" + value + ").chars().count() as i64)"
    if rule == "length.collection":
        return "((" + value + ").len() as i64)"
    if rule == "length.fixed_tuple":
        size: str = str(tuple_size)
        if local_name == "":
            # Even a statically known length cannot erase a call or bounds error.
            return "({ let __length_value = " + value + "; " + size + " } as i64)"
        return "(" + size + " as i64)"
    return ""


def sequence_constructor_rule(source: str) -> str:
    if source == "bytes" or source == "bytearray":
        return "sequence.byte_values"
    if source == "dict":
        return "sequence.key_snapshot"
    if source == "list" or source == "set" or source == "tuple_var":
        return "sequence.item_snapshot"
    return ""


def render_sequence_constructor(rule: str, value: str) -> str:
    if rule == "sequence.byte_values":
        return "(" + value + ").iter().map(|value| *value as i64).collect::<Vec<_>>()"
    if rule == "sequence.key_snapshot":
        return "(" + value + ").keys().cloned().collect::<Vec<_>>()"
    if rule == "sequence.item_snapshot":
        return "(" + value + ").iter().cloned().collect::<Vec<_>>()"
    return ""
