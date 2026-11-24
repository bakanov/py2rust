"""The subset deliberately requires bools rather than Python truthiness.

Value-returning `and`/`or` must not silently become Rust boolean operators.
Optional values and collections need an explicit source comparison instead.
"""


def condition_problem(type_name: str) -> str:
    if type_name == "bool" or type_name == "builtins.bool":
        return ""
    return "condition.bool: expected bool; implicit truthiness is unsupported; use an explicit comparison"


def boolean_operator(operation: str) -> str:
    if operation == "and":
        return "&&"
    if operation == "or":
        return "||"
    return ""
