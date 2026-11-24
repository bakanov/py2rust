"""Python string operation -> Rust operation, for the documented subset.

This module is compiler input as well as compiler implementation: use only the
supported typed subset. Do not import ast, mypy, the emitter, or reflection here.
An accepted rule proves only that the operation itself does not mutate inputs.
Operand evaluation and escaping results require independent ownership checks.
"""

from dataclasses import dataclass


@dataclass
class StringRule:
    key: str
    form: str
    target: str
    result: str
    argument: str
    fallible: bool


def select_string_rule(receiver: str, method: str, arity: int) -> StringRule:
    """Match exact receiver and overload; an empty key means unsupported."""
    if receiver != "str" or arity < 0:
        return StringRule("", "", "", "", "", False)
    if method == "casefold" and arity == 0:
        return StringRule("str.casefold", "runtime", "casefold", "str", "", False)
    if method == "strip" and arity == 0:
        return StringRule("str.strip.whitespace", "runtime", "str_strip", "str", "", False)
    if (method == "strip" or method == "lstrip" or method == "rstrip") and arity <= 1:
        return StringRule("str." + method + ".edges", "trim", "str_strip_edges", "str", "str_or_none", False)
    if method == "lower" and arity == 0:
        return StringRule("str.lower", "method", "to_lowercase", "str", "", False)
    if method == "upper" and arity == 0:
        return StringRule("str.upper", "method", "to_uppercase", "str", "", False)
    if method == "encode" and arity == 0:
        return StringRule("str.encode.utf8", "method", "as_bytes().to_vec", "bytes", "", False)
    if method == "split" and arity == 0:
        return StringRule("str.split.whitespace", "runtime", "str_split_whitespace", "list[str]", "", False)
    if method == "split" and arity == 1:
        return StringRule("str.split.separator", "runtime", "str_split", "list[str]", "str", True)
    if method == "startswith" and arity == 1:
        return StringRule("str.startswith", "method", "starts_with", "bool", "str", False)
    if method == "endswith" and arity == 1:
        return StringRule("str.endswith", "method", "ends_with", "bool", "str", False)
    if (method == "find" or method == "rfind") and arity == 1:
        return StringRule("str." + method, "runtime", "str_" + method, "int", "str", False)
    if method == "replace" and arity == 2:
        return StringRule("str.replace", "method", "replace", "str", "str", False)
    if method == "join" and arity == 1:
        return StringRule("str.join", "join", "join", "str", "list[str]", False)
    return StringRule("", "", "", "", "", False)


def render_string_call(rule: StringRule, receiver: str, arguments: list[str]) -> str:
    """Render already checked references; preserve receiver-first evaluation.

    Trim has optional-argument setup and is rendered by its adapter. Join reverses
    Rust's receiver/argument positions, so explicitly bind the Python receiver first.
    Returns the Result call without `?`; its consumer controls error propagation.
    """
    if rule.form == "runtime":
        operands: str = receiver
        for argument in arguments:
            operands = operands + ", " + argument
        return "rt::" + rule.target + "(" + operands + ")"
    if rule.form == "method":
        return "(" + receiver + ")." + rule.target + "(" + ", ".join(arguments) + ")"
    if rule.form == "join":
        return "{ let __separator = " + receiver + "; (" + arguments[0] + ").join(__separator) }"
    return ""
