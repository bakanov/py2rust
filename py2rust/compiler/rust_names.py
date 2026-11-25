"""Readable, collision-safe names at the exported Rust project boundary."""

import re
from collections import Counter

import tree_sitter
import tree_sitter_rust

# Includes reserved/future keywords and names that cannot be raw identifiers.
KEYWORDS = set(
    "as async await break const continue crate dyn else enum extern false fn for if impl in let loop match mod move mut "
    "pub ref return self Self static struct super trait true type unsafe use where while abstract become box do final "
    "macro override priv typeof unsized virtual yield try union gen".split()
)


def component(value: str) -> str:
    if re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", value):
        return value
    return "unicode_" + value.encode().hex()


def readable_names(code: str, symbols: dict[str, str]) -> tuple[str, dict[str, str]]:
    """Rename only parsed identifiers; strings, comments and paths remain intact.

    Reserve all other identifiers, including locals, to avoid introducing name
    capture when linked modules share one Rust scope. Internal analysis IDs stay
    independent of these presentation names.
    """
    data = code.encode()
    parser = tree_sitter.Parser(tree_sitter.Language(tree_sitter_rust.language()))
    tree = parser.parse(data)
    if tree.root_node.has_error:
        raise ValueError("cannot assign readable names to invalid generated Rust")
    identifiers = []
    pending = [tree.root_node]
    while pending:
        node = pending.pop()
        if node.type in {"identifier", "type_identifier", "field_identifier"}:
            identifiers.append(node)
        pending.extend(node.children)
    present = {node.text.decode() for node in identifiers}
    active = {symbol: name for symbol, name in symbols.items() if symbol in present}
    counts = Counter(active.values())
    used = (present - active.keys()) | KEYWORDS | {"main", "_"}
    names = {}
    for symbol, original in sorted(active.items()):
        leaf = component(original)
        parts = symbol.removeprefix("py__").split("__")[:-1]
        modules = [bytes.fromhex(part[8:]).decode() if part.startswith("escaped_") else part for part in parts]
        if original == "main":
            preferred = "run_main"
        else:
            preferred = leaf
        if preferred in used or counts[original] > 1:
            if leaf[0].isupper():
                prefix = "".join(part.title().replace("_", "") for part in modules)
                preferred = component(prefix + leaf)
            else:
                preferred = "_".join([*(component(part) for part in modules), leaf])
        candidate = preferred
        suffix = 2
        while candidate in used:
            candidate = f"{preferred}_{suffix}"
            suffix += 1
        names[symbol] = candidate
        used.add(candidate)
    for node in sorted(identifiers, key=lambda item: item.start_byte, reverse=True):
        name = node.text.decode()
        if name in names and node.type != "field_identifier":
            data = data[: node.start_byte] + names[name].encode() + data[node.end_byte :]
    return data.decode(), names
