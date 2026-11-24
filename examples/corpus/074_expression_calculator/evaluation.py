"""Precedence-climbing evaluation without host-language eval or code execution."""

from dataclasses import dataclass

from arithmetic import combine, literal, unary
from lexing import Token, location

from py2rust.stdlib import Json


@dataclass
class Parsed:
    value: Json
    position: int


@dataclass
class Statement:
    value: Json
    binding: str


def precedence(operator: str) -> int:
    if operator in ["+", "-"]:
        return 10
    if operator in ["*", "/", "//", "%"]:
        return 20
    return 0


def expression(tokens: list[Token], position: int, minimum: int, variables: dict[str, Json], depth: int) -> Parsed:
    token: Token = tokens[position]
    assert depth <= 32, location(token.column) + "expression nesting exceeds 32"
    position = position + 1
    value: Json = None
    if token.kind == "number":
        value = literal(token.text, token.column)
    elif token.kind == "name":
        assert token.text in variables, location(token.column) + "undefined variable: " + token.text
        value = variables[token.text]
    elif token.text in ["+", "-"]:
        # Fold a signed literal so the smallest signed integer is representable.
        if token.text == "-" and tokens[position].kind == "number":
            value = literal("-" + tokens[position].text, token.column)
            position = position + 1
        else:
            child: Parsed = expression(tokens, position, 30, variables, depth + 1)
            value = unary(token.text, child.value, token.column)
            position = child.position
    elif token.text == "(":
        child: Parsed = expression(tokens, position, 1, variables, depth + 1)
        assert tokens[child.position].text == ")", (
            location(tokens[child.position].column) + "expected closing parenthesis"
        )
        value = child.value
        position = child.position + 1
    else:
        assert False, location(token.column) + "expected number, variable or parenthesis"
    while precedence(tokens[position].text) >= minimum:
        operator: Token = tokens[position]
        child: Parsed = expression(tokens, position + 1, precedence(operator.text) + 1, variables, depth + 1)
        value = combine(operator.text, value, child.value, operator.column)
        position = child.position
    return Parsed(value, position)


def statement(tokens: list[Token], variables: dict[str, Json]) -> Statement:
    binding: str = ""
    start: int = 0
    if tokens[0].kind == "name" and tokens[1].text == "=":
        binding = tokens[0].text
        start = 2
    result: Parsed = expression(tokens, start, 1, variables, 0)
    assert tokens[result.position].kind == "end", location(tokens[result.position].column) + "unexpected trailing token"
    assert binding == "" or binding in variables or len(variables) < 256, "session exceeds 256 variables"
    return Statement(result.value, binding)
