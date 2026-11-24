"""JSON representation contracts shared by library lowering and conversion.

Direct output is permitted only when validation, ordering and numeric spelling
match the existing JSON path. Ownership and argument evaluation are separate.
"""

from dataclasses import dataclass

from ..ir import ValueType


def representation(typ: ValueType) -> str:
    if typ.name == "builtins.tuple":
        return "tuple_var"
    return typ.name.removeprefix("builtins.").removeprefix("py2rust.stdlib.")


def serializable(typ: ValueType) -> bool:
    name = representation(typ)
    if name in {"Json", "str", "int", "float", "bool", "None"}:
        return True
    if name in {"list", "tuple", "tuple_var"}:
        return all(serializable(argument) for argument in typ.arguments)
    return (
        name == "dict"
        and len(typ.arguments) == 2
        and representation(typ.arguments[0]) == "str"
        and serializable(typ.arguments[1])
    )


def direct_output(typ: ValueType) -> bool:
    name = representation(typ)
    if name in {"Json", "str", "int", "bool", "None"}:
        return True
    if name in {"list", "tuple_var", "tuple"}:
        return (name != "tuple" or 0 < len(typ.arguments) <= 12) and all(
            direct_output(argument) for argument in typ.arguments
        )
    return False


@dataclass(frozen=True)
class OutputSelection:
    helper: str
    reason: str


def select_output(helper: str, typ: ValueType, *, optimize: bool) -> OutputSelection:
    if not optimize:
        return OutputSelection(helper, "serialization_optimization_disabled")
    if helper in {"json_dumps", "pretty"} and direct_output(typ):
        return OutputSelection(helper + "_view", "representation_matches_json_output")
    if helper == "json_canonical" and representation(typ) == "Json":
        return OutputSelection("json_canonical_view", "canonical_json_representation")
    return OutputSelection(helper, "existing_runtime_representation_required")
