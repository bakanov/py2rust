"""Parse pipelines and boolean expressions into flat plans; no evaluation of Python source."""

from syntax import Token, fail, field, lex

from py2rust.stdlib import Json, json_kind, json_string


def predicate(query: str, tokens: list[Token], cursor: int) -> tuple[Json, int]:
    operator: str = tokens[cursor].text
    prefix: bool = operator in ["exists", "missing"]
    if prefix:
        cursor = cursor + 1
    node: Json = field(query, tokens[cursor])
    cursor = cursor + 1
    value: Json = None
    if not prefix:
        operator = tokens[cursor].text
        if operator not in ["==", "!=", "<", "<=", ">", ">=", "in", "contains"]:
            fail(query, tokens[cursor].position, "expected a comparison operator")
        cursor = cursor + 1
        if not tokens[cursor].literal:
            fail(query, tokens[cursor].position, "expected a JSON literal")
        value = tokens[cursor].value
        if operator == "in" and json_kind(value) != "array":
            fail(query, tokens[cursor].position, "in requires an array literal")
        if operator in ["<", "<=", ">", ">="] and json_kind(value) not in ["null", "bool", "number", "string"]:
            fail(query, tokens[cursor].position, "ordered comparison requires a scalar literal")
        cursor = cursor + 1
    node["operator"] = operator
    node["value"] = value
    return (node, cursor)


def expression(query: str, tokens: list[Token], cursor: int) -> tuple[list[Json], int]:
    output: list[Json] = []
    operators: list[Token] = []
    priority: dict[str, int] = {"(": 0, "or": 1, "and": 2, "not": 3}
    operand: bool = True
    while tokens[cursor].text not in ["", "|"]:
        token: Token = tokens[cursor]
        if operand:
            if token.text in ["not", "("]:
                operators.append(token)
                cursor = cursor + 1
            else:
                parsed: tuple[Json, int] = predicate(query, tokens, cursor)
                output.append(parsed[0])
                cursor = parsed[1]
                operand = False
        elif token.text in ["and", "or"]:
            while len(operators) > 0 and priority[operators[-1].text] >= priority[token.text]:
                output.append({"operator": operators.pop().text})
            operators.append(token)
            cursor = cursor + 1
            operand = True
        elif token.text == ")":
            while len(operators) > 0 and operators[-1].text != "(":
                output.append({"operator": operators.pop().text})
            if len(operators) == 0:
                fail(query, token.position, "unmatched closing parenthesis")
            operators.pop()
            cursor = cursor + 1
        else:
            fail(query, token.position, "expected a boolean operator")
    if operand:
        fail(query, tokens[cursor].position, "expected a predicate")
    while len(operators) > 0:
        token: Token = operators.pop()
        if token.text == "(":
            fail(query, token.position, "unclosed parenthesis")
        output.append({"operator": token.text})
    return (output, cursor)


def columns(query: str, tokens: list[Token], cursor: int, ordering: bool) -> tuple[list[Json], int]:
    result: list[Json] = []
    names: set[str] = set()
    while True:
        spec: Json = field(query, tokens[cursor])
        cursor = cursor + 1
        if ordering:
            if tokens[cursor].text not in ["asc", "desc"]:
                fail(query, tokens[cursor].position, "expected asc or desc")
            spec["descending"] = tokens[cursor].text == "desc"
            cursor = cursor + 1
        else:
            if tokens[cursor].text != "as":
                fail(query, tokens[cursor].position, "expected as")
            cursor = cursor + 1
            label: Token = tokens[cursor]
            if not label.literal or json_kind(label.value) != "string":
                fail(query, label.position, "expected a quoted output name")
            name: str = json_string(label.value)
            if not 1 <= len(name.encode()) <= 128 or name in names:
                fail(query, label.position, "empty, oversized or duplicate output name")
            names.add(name)
            spec["name"] = name
            cursor = cursor + 1
        result.append(spec)
        if len(result) > 8:
            fail(query, tokens[cursor].position, "stage exceeds 8 fields")
        if tokens[cursor].text != ",":
            break
        cursor = cursor + 1
    return (result, cursor)


def parse(query: str) -> list[Json]:
    tokens: list[Token] = lex(query)
    stages: list[Json] = []
    cursor: int = 0
    while tokens[cursor].text != "":
        token: Token = tokens[cursor]
        cursor = cursor + 1
        stage: Json = {"kind": token.text, "sums": []}
        if token.text == "filter":
            condition: tuple[list[Json], int] = expression(query, tokens, cursor)
            stage["tests"] = condition[0]
            cursor = condition[1]
        elif token.text in ["select", "order", "group"]:
            parsed: tuple[list[Json], int] = columns(query, tokens, cursor, token.text == "order")
            stage["fields"] = parsed[0]
            cursor = parsed[1]
            if token.text == "group" and tokens[cursor].text == "sum":
                parsed = columns(query, tokens, cursor + 1, False)
                stage["sums"] = parsed[0]
                cursor = parsed[1]
        else:
            fail(query, token.position, "expected filter, select, order or group")
        stages.append(stage)
        if len(stages) > 8:
            fail(query, token.position, "pipeline exceeds 8 stages")
        if tokens[cursor].text != "":
            if tokens[cursor].text != "|":
                fail(query, tokens[cursor].position, "expected pipeline separator")
            cursor = cursor + 1
            if tokens[cursor].text == "":
                fail(query, tokens[cursor].position, "expected pipeline stage")
    return stages
