"""Bounded recursive descent for explicit multiplication, division, parentheses and integer powers."""

from units import Unit, combine, power

from py2rust.stdlib import regex_findall, regex_fullmatch


def primary(tokens: list[str], position: int, depth: int, available: dict[str, Unit]) -> tuple[Unit, int]:
    assert position < len(tokens), "expected unit factor"
    name: str = tokens[position]
    position = position + 1
    if name == "(":
        assert depth < 8, "parenthesis depth limit"
        nested: tuple[Unit, int] = expression(tokens, position, depth + 1, available)
        position = nested[1]
        assert position < len(tokens) and tokens[position] == ")", "missing closing parenthesis"
        return (nested[0], position + 1)
    assert name in available, "unknown unit"
    assert name not in ["degC", "degF"], "offset units must stand alone"
    return (available[name], position)


def factor(tokens: list[str], position: int, depth: int, available: dict[str, Unit]) -> tuple[Unit, int]:
    first: tuple[Unit, int] = primary(tokens, position, depth, available)
    unit: Unit = first[0]
    position = first[1]
    if position < len(tokens) and tokens[position] == "^":
        position = position + 1
        sign: str = ""
        if position < len(tokens) and tokens[position] in ["+", "-"]:
            sign = tokens[position]
            position = position + 1
        assert position < len(tokens) and regex_fullmatch("[0-9]{1,2}", tokens[position]), "expected integer power"
        exponent: int = int(sign + tokens[position])
        position = position + 1
        unit = power(unit, exponent)
    return (unit, position)


def expression(tokens: list[str], position: int, depth: int, available: dict[str, Unit]) -> tuple[Unit, int]:
    first: tuple[Unit, int] = factor(tokens, position, depth, available)
    unit: Unit = first[0]
    position = first[1]
    while position < len(tokens) and tokens[position] in ["*", "/"]:
        divide: bool = tokens[position] == "/"
        following: tuple[Unit, int] = factor(tokens, position + 1, depth, available)
        unit = combine(unit, following[0], divide)
        position = following[1]
    return (unit, position)


def parse(text: str, available: dict[str, Unit]) -> Unit:
    assert 1 <= len(text) <= 128, "unit expression length limit"
    stripped: str = text.strip(" \t")
    if stripped in ["degC", "degF"]:
        return available[stripped]
    tokens: list[str] = regex_findall("[A-Za-z_][A-Za-z_0-9]*|[0-9]+|[*/()^+-]", text)
    assert 1 <= len(tokens) <= 96, "unit token limit"
    assert "".join(tokens) == text.replace(" ", "").replace("\t", ""), "invalid unit character"
    result: tuple[Unit, int] = expression(tokens, 0, 0, available)
    assert result[1] == len(tokens), "unexpected unit token"
    return result[0]
