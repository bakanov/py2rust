"""Build a typed recursive AST; parse all branches before executing any statement."""

from dataclasses import dataclass

from lexing import Token

from py2rust.stdlib import Json


@dataclass
class Node:
    kind: str
    value: str
    location: str
    children: list["Node"]
    height: int


@dataclass
class Parsed:
    node: Node
    position: int


def make(kind: str, value: str, location: str, children: list[Node]) -> Node:
    height: int = 1
    for child in children:
        height = max(height, child.height + 1)
    assert height <= 64, location + "AST depth exceeds 64"
    return Node(kind, value, location, children, height)


def precedence(operator: str) -> int:
    if operator in ["==", "!=", "<", "<=", ">", ">="]:
        return 10
    if operator in ["+", "-"]:
        return 20
    return 30 if operator in ["*", "//", "%"] else 0


def expression(tokens: list[Token], position: int, minimum: int, depth: int) -> Parsed:
    token: Token = tokens[position]
    assert depth <= 32, token.location + "expression nesting exceeds 32"
    position = position + 1
    node: Node = make(token.kind, token.text, token.location, [])
    if token.kind == "name":
        assert token.text not in ["let", "set", "if", "else", "repeat", "emit"], token.location + "reserved name"
    elif token.kind == "number":
        pass
    elif token.text in ["+", "-"]:
        if token.text == "-" and tokens[position].kind == "number":
            node = make("number", "-" + tokens[position].text, token.location, [])
            position = position + 1
        else:
            child: Parsed = expression(tokens, position, 40, depth + 1)
            node = make("unary", token.text, token.location, [child.node])
            position = child.position
    elif token.text == "(":
        child: Parsed = expression(tokens, position, 1, depth + 1)
        assert tokens[child.position].text == ")", tokens[child.position].location + "expected closing parenthesis"
        node = child.node
        position = child.position + 1
    else:
        assert False, token.location + "expected expression"
    compared: bool = False
    while precedence(tokens[position].text) >= minimum:
        operator: Token = tokens[position]
        if precedence(operator.text) == 10:
            assert not compared, operator.location + "comparison chains are unsupported"
            compared = True
        child: Parsed = expression(tokens, position + 1, precedence(operator.text) + 1, depth + 1)
        node = make("binary", operator.text, operator.location, [node, child.node])
        position = child.position
    return Parsed(node, position)


def block(tokens: list[Token], position: int, depth: int, nested: bool) -> Parsed:
    location: str = tokens[position].location
    assert depth <= 16, location + "block nesting exceeds 16"
    nodes: list[Node] = []
    while tokens[position].kind != "end" and tokens[position].text != "}":
        if tokens[position].text in ["\n", ";"]:
            position = position + 1
            continue
        token: Token = tokens[position]
        command: str = token.text
        assert command in ["let", "set", "emit", "if", "repeat"], token.location + "expected statement"
        position = position + 1
        name: str = ""
        if command in ["let", "set"]:
            variable: Token = tokens[position]
            assert variable.kind == "name" and variable.text not in ["let", "set", "if", "else", "repeat", "emit"], (
                variable.location + "expected variable name"
            )
            name = variable.text
            position = position + 1
            assert tokens[position].text == "=", tokens[position].location + "expected equals sign"
            position = position + 1
        parsed: Parsed = expression(tokens, position, 1, 0)
        children: list[Node] = [parsed.node]
        position = parsed.position
        if command in ["if", "repeat"]:
            assert tokens[position].text == "{", tokens[position].location + "expected opening brace"
            body: Parsed = block(tokens, position + 1, depth + 1, True)
            children.append(body.node)
            position = body.position
            if command == "if":
                look: int = position
                while tokens[look].text == "\n":
                    look = look + 1
                other: Node = make("block", "", token.location, [])
                if tokens[look].text == "else":
                    assert tokens[look + 1].text == "{", tokens[look + 1].location + "expected opening brace"
                    body = block(tokens, look + 2, depth + 1, True)
                    other = body.node
                    position = body.position
                children.append(other)
        nodes.append(make(command, name, token.location, children))
        assert tokens[position].text in ["\n", ";", "}", ""], tokens[position].location + "expected statement separator"
    if nested:
        assert tokens[position].text == "}", tokens[position].location + "expected closing brace"
        position = position + 1
    else:
        assert tokens[position].kind == "end", tokens[position].location + "unexpected closing brace"
    return Parsed(make("block", "", location, nodes), position)


def describe(node: Node) -> Json:
    """Flat preorder nodes preserve deep syntax without exceeding JSON nesting limits."""
    pending: list[Node] = [node]
    parents: list[int] = [-1]
    indexes: list[int] = [0]
    rows: list[Json] = []
    while len(pending) > 0:
        current: Node = pending.pop()
        parent: int = parents.pop()
        child_index: int = indexes.pop()
        number: int = len(rows)
        rows.append(
            {
                "kind": current.kind,
                "value": current.value,
                "location": current.location,
                "parent": parent,
                "child_index": child_index,
            }
        )
        for index in range(len(current.children) - 1, -1, -1):
            pending.append(current.children[index])
            parents.append(number)
            indexes.append(index)
    return {"version": 1, "nodes": rows}
