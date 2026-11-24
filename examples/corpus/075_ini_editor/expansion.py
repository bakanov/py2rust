"""Resolve local/global references once in dependency order, rejecting cycles and oversized expansions."""

# ruff: noqa: PLC0206, C414, FURB192 - supported subset operations
from syntax import identifier


def target(reference: str, owner: str, values: dict[str, str]) -> str:
    pieces: list[str] = reference.split(".")
    assert 1 <= len(pieces) <= 2, owner + ": invalid variable reference"
    key: str = pieces[-1]
    assert identifier(key), owner + ": invalid variable reference"
    section: str = owner.split(".")[0] if len(pieces) == 1 else pieces[0]
    assert section == "" or identifier(section), owner + ": invalid variable reference"
    name: str = section + "." + key
    if len(pieces) == 1 and name not in values:
        name = "." + key
    assert name in values, owner + ": unknown variable: " + reference
    return name


def segments(value: str, owner: str, values: dict[str, str]) -> list[tuple[bool, str]]:
    result: list[tuple[bool, str]] = []
    position: int = 0
    literal: str = ""
    tokens: int = 0
    while position < len(value):
        tail: str = value[position:]
        dollar: int = tail.find("$")
        if dollar < 0:
            literal = literal + tail
            break
        tokens = tokens + 1
        assert tokens <= 512, owner + ": more than 512 dollar tokens"
        literal = literal + tail[:dollar]
        position = position + dollar + 1
        if position < len(value) and value[position] == "$":
            literal = literal + "$"
            position = position + 1
        elif position < len(value) and value[position] == "{":
            length: int = value[position:].find("}")
            assert length >= 0, owner + ": unclosed variable reference"
            if literal != "":
                result.append((False, literal))
                literal = ""
            result.append((True, target(value[position + 1 : position + length], owner, values)))
            position = position + length + 1
        else:
            literal = literal + "$"
    if literal != "":
        result.append((False, literal))
    return result


def expand(values: dict[str, str]) -> dict[str, str]:
    parts: dict[str, list[tuple[bool, str]]] = {}
    graph: dict[str, set[str]] = {}
    pending: set[str] = set(list(values))
    for name in values:
        parts[name] = segments(values[name], name, values)
        dependencies: set[str] = set()
        for part in parts[name]:
            if part[0]:
                dependencies.add(part[1])
        graph[name] = dependencies
    resolved: dict[str, str] = {}
    total: int = 0
    while len(pending) > 0:
        ready: list[str] = []
        for name in sorted(list(pending)):
            if graph[name] <= set(list(resolved)):
                ready.append(name)
        if len(ready) == 0:
            current: str = sorted(list(pending))[0]
            chain: list[str] = []
            while current not in chain:
                chain.append(current)
                for child in sorted(list(graph[current])):
                    if child in pending:
                        current = child
                        break
            assert False, "variable cycle: " + " -> ".join(chain + [current])
        for name in ready:
            text: str = ""
            for part in parts[name]:
                text = text + (resolved[part[1]] if part[0] else part[1])
                assert len(text.encode()) <= 65536, name + ": expanded value exceeds 65536 bytes"
            resolved[name] = text
            total = total + len(text.encode())
            assert total <= 1048576, "expanded values exceed 1 MiB"
        pending = pending.difference(set(ready))
    return resolved
