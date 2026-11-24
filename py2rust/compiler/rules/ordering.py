"""Total ordering and stable sorting rules for supported value shapes."""


def orderable_shape(name: str, is_enum: bool, children: list[bool]) -> bool:
    if is_enum or name == "int" or name == "bool" or name == "str":
        return True
    if name != "list" and name != "tuple" and name != "tuple_var":
        return False
    if name == "tuple" and len(children) > 12:
        return False
    for child in children:
        if not child:
            return False
    return True


def sorting_rule(has_key: bool, has_reverse: bool) -> str:
    if has_key:
        return "sort.key_once"
    if has_reverse:
        return "sort.stable_direction"
    return "sort.stable_ascending"


def render_sorting(rule: str, values: str, callback: str, reverse: str) -> str:
    if rule == "sort.key_once":
        # The runtime decorates each item once, then performs stable key sorting.
        # Never substitute sort_by_key: it can call a key repeatedly.
        return (
            "{ let __values = "
            + values
            + "; let __reverse = "
            + reverse
            + "; rt::sorted_by_key(__values, "
            + callback
            + ", __reverse)? }"
        )
    if rule == "sort.stable_direction":
        # Reverse the comparator, not the final sequence: preserve equal-key order.
        return (
            "{ let mut __sorted = "
            + values
            + "; let __reverse = "
            + reverse
            + "; __sorted.sort_by(|left, right| if __reverse { right.cmp(left) } "
            + "else { left.cmp(right) }); __sorted }"
        )
    if rule == "sort.stable_ascending":
        return "{ let mut __sorted = " + values + "; __sorted.sort(); __sorted }"
    return ""
