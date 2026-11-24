"""Parse escaped substitutions, conditions, loops and named includes into recursive nodes."""

# ruff: noqa: PLC0206 - explicit returns and supported subset operations
from dataclasses import dataclass


@dataclass
class Node:
    kind: str
    location: str
    value: str
    binding: str
    children: list["Node"]
    fallback: list["Node"]


@dataclass
class Parsed:
    nodes: list[Node]
    position: int
    closing: str
    location: str


def identifier(value: str) -> bool:
    if value == "" or value[0] not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_":
        return False
    for character in value:
        if character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789":
            return False
    return True


def expression(value: str, location: str) -> str:
    assert 1 <= len(value) <= 256, location + "invalid expression length"
    for part in value.split("."):
        assert identifier(part), location + "expression requires dotted identifiers"
    return value


def spot(text: str, position: int, source: str) -> str:
    lines: list[str] = text[:position].split("\n")
    return source + ":" + str(len(lines)) + ":" + str(len(lines[-1]) + 1) + ": "


def parse(text: str, position: int, depth: int, source: str) -> Parsed:
    assert depth <= 12, spot(text, position, source) + "template nesting exceeds 12"
    nodes: list[Node] = []
    while position < len(text):
        tail: str = text[position:]
        variable: int = tail.find("{{")
        command: int = tail.find("{%")
        offset: int = variable if command < 0 or (variable >= 0 and variable < command) else command
        if offset < 0:
            nodes.append(Node("text", spot(text, position, source), tail, "", [], []))
            return Parsed(nodes, len(text), "", "")
        if offset > 0:
            nodes.append(Node("text", spot(text, position, source), tail[:offset], "", [], []))
        location: str = spot(text, position + offset, source)
        opening: str = text[position + offset : position + offset + 2]
        end_marker: str = "}}" if opening == "{{" else "%}"
        start: int = position + offset + 2
        length: int = text[start:].find(end_marker)
        assert length >= 0, location + "unclosed template token"
        value: str = text[start : start + length].strip()
        position = start + length + 2
        if opening == "{{":
            nodes.append(Node("value", location, expression(value, location), "", [], []))
            continue
        if value in ["else", "endif", "endfor"]:
            return Parsed(nodes, position, value, location)
        words: list[str] = []
        for word in value.split(" "):
            if word != "":
                words.append(word)
        assert len(words) >= 2, location + "invalid template command"
        if words[0] == "include":
            assert len(words) == 2 and len(words[1]) <= 64 and identifier(words[1]), (
                location + "include requires a template identifier"
            )
            nodes.append(Node("include", location, words[1], "", [], []))
        elif words[0] == "if":
            assert len(words) == 2, location + "if requires one expression"
            path: str = expression(words[1], location)
            body: Parsed = parse(text, position, depth + 1, source)
            other: list[Node] = []
            if body.closing == "else":
                alternative: Parsed = parse(text, body.position, depth + 1, source)
                assert alternative.closing == "endif", location + "if requires endif"
                other = alternative.nodes
                position = alternative.position
            else:
                assert body.closing == "endif", location + "if requires endif"
                position = body.position
            nodes.append(Node("if", location, path, "", body.nodes, other))
        elif words[0] == "for":
            assert len(words) == 4 and words[2] == "in" and len(words[1]) <= 64 and identifier(words[1]), (
                location + "invalid for command"
            )
            path: str = expression(words[3], location)
            body: Parsed = parse(text, position, depth + 1, source)
            assert body.closing == "endfor", location + "for requires endfor"
            nodes.append(Node("for", location, path, words[1], body.nodes, []))
            position = body.position
        else:
            assert False, location + "unknown template command: " + words[0]
    return Parsed(nodes, position, "", "")


def compile_template(text: str, source: str) -> list[Node]:
    result: Parsed = parse(text, 0, 0, source)
    assert result.closing == "", result.location + "unexpected closing template command"
    return result.nodes


def includes(nodes: list[Node]) -> dict[str, str]:
    result: dict[str, str] = {}
    for node in nodes:
        if node.kind == "include":
            result[node.value] = node.location
        for branch in [node.children, node.fallback]:
            nested: dict[str, str] = includes(branch)
            for name in nested:
                result[name] = nested[name]
    return result


def node_count(nodes: list[Node]) -> int:
    count: int = 0
    for node in nodes:
        count = count + 1 + node_count(node.children) + node_count(node.fallback)
    return count
