"""Choose local borrowed representations without AST or Rust-rendering inputs.

A candidate must be rooted in an existing local place. These rules preserve the
subset's projection choices; they are not an alias or escaping-lifetime proof.
Callers remain responsible for argument-order barriers and owned result uses.
"""

from dataclasses import dataclass

from .ir import ValueType


@dataclass(frozen=True)
class BorrowOptions:
    text: bool
    slices: bool
    json: bool


def projection(
    operation: str,
    parent: ValueType | None,
    *,
    options: BorrowOptions,
    stable: bool,
    record: bool = False,
    indexed_text: bool = False,
) -> str | None:
    """Select a representation for a proven local parent, or require owned lowering.

    Text/JSON indexes and sequence slices require stable operand evaluation.
    Ordinary collection projections preserve their existing lowering; their use
    at a call boundary still needs the separate argument-evaluation policy.
    """
    if parent is None:
        return None
    name = parent.name.removeprefix("builtins.").removeprefix("py2rust.stdlib.")
    if parent.name == "builtins.tuple":
        name = "tuple_var"
    if operation == "field":
        return "field" if record else None
    if operation == "json_array":
        return "json_array" if options.json and name == "Json" else None
    if operation == "slice":
        return (
            "sequence_slice"
            if options.slices and stable and name in {"bytes", "bytearray", "list", "tuple_var"}
            else None
        )
    if operation != "index":
        return None
    if name == "str" and options.text and stable:
        return "indexed_text" if indexed_text else "text"
    if name == "Json" and options.json and stable:
        return "json"
    return {"tuple": "tuple", "list": "sequence", "tuple_var": "sequence", "dict": "mapping"}.get(name)
