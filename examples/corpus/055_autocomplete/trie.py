"""An owned recursive trie with cached word/node counts and Unicode-normalized keys."""

# ruff: noqa: C414, PLR1711 - explicit typed collection conversions and returns

from dataclasses import dataclass

from py2rust.stdlib import Json, json_int, json_keys, json_string, unicode_normalize


@dataclass
class Node:
    terminal: bool
    term: str
    uses: int
    children: dict[str, "Node"]
    nodes: int
    words: int


@dataclass
class Index:
    capacity: int
    steps: int
    root: Node


def blank() -> Node:
    return Node(False, "", 0, {}, 1, 0)


def empty(size: int) -> Index:
    return Index(size, 0, blank())


def exact(value: Json, names: list[str]) -> None:
    assert json_keys(value) == sorted(names), "unexpected object fields"
    return


def capacity(value: Json) -> int:
    size: int = json_int(value)
    assert 1 <= size <= 128, "capacity must be 1..128"
    return size


def normalized(value: Json, allow_empty: bool) -> str:
    text: str = json_string(value)
    assert len(text) <= 128 and len(text.encode()) <= 512, "text exceeds 128 characters or 512 UTF-8 bytes"
    result: str = unicode_normalize("NFKC", text).casefold()
    assert len(result) <= 128 and len(result.encode()) <= 512, "normalized text exceeds bounds"
    assert allow_empty or result != "", "term must not be empty"
    return result


def usage(value: Json) -> int:
    result: int = json_int(value)
    assert 0 <= result <= 1000000000, "usage must be 0..1000000000"
    return result


def find(root: Node, key: str) -> Node:
    current: Node = root
    for position in range(len(key)):
        letter: str = key[position]
        if letter not in current.children:
            return blank()
        current = current.children[letter]
    return current


def change(node: Node, key: str, position: int, active: bool, term: str, uses: int) -> Node:
    children: dict[str, Node] = node.children.copy()
    if position == len(key):
        words: int = node.words + (1 if active else 0) - (1 if node.terminal else 0)
        return Node(active, term, uses, children, node.nodes, words)
    letter: str = key[position]
    original: Node = children.get(letter, blank())
    original_nodes: int = original.nodes if letter in children else 0
    updated: Node = change(original, key, position + 1, active, term, uses)
    updated_nodes: int = updated.nodes
    if updated.words == 0:
        if letter in children:
            del children[letter]  # noqa: RUF051 - typed dictionary pop is unsupported
        updated_nodes = 0
    else:
        children[letter] = updated
    return Node(
        node.terminal,
        node.term,
        node.uses,
        children,
        node.nodes - original_nodes + updated_nodes,
        node.words - original.words + updated.words,
    )


def entry(node: Node, key: str) -> Json:
    return {"key": key, "term": node.term, "uses": node.uses}


def entries(node: Node, prefix: str) -> list[Json]:
    result: list[Json] = []
    if node.terminal:
        result.append(entry(node, prefix))
    for letter in sorted(list(node.children)):
        result.extend(entries(node.children[letter], prefix + letter))
    return result


def suggestions(index: Index, prefix: str, offset: int, limit: int) -> Json:
    assert 0 <= offset <= 128 and 1 <= limit <= 128, "invalid suggestion pagination"
    selected: list[Json] = entries(find(index.root, prefix), prefix)
    ranking: list[tuple[int, str]] = []
    values: dict[str, Json] = {}
    for value in selected:
        key: str = json_string(value["key"])
        values[key] = value
        ranking.append((-json_int(value["uses"]), key))
    ranking.sort()
    hits: list[Json] = []
    for position in range(offset, min(len(ranking), offset + limit)):
        hits.append(values[ranking[position][1]])
    return {"prefix": prefix, "hits": hits, "count": len(ranking), "more": offset + limit < len(ranking)}


def summary(index: Index) -> Json:
    return {"terms": index.root.words, "nodes": index.root.nodes, "capacity": index.capacity}
