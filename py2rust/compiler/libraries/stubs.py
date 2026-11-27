"""Generate frontend stubs from the same contracts used for Rust calls."""

import ast
from pathlib import Path

from ..exception_policy import RESOURCE_TYPES
from . import CONSTANTS, RUNTIME, STANDARD, Replacement
from .web import FIELDS


def signature(replacement: Replacement) -> str:
    if replacement.python_name == "json.dumps":
        return (
            "def dumps(value: object, /, *, ensure_ascii: bool = True, allow_nan: bool = True, "
            "separators: tuple[str, str] = (', ', ': '), sort_keys: bool = False) -> str: ..."
        )
    if replacement.python_name == "json.loads":
        return "def loads(text: str | bytes, /, *, object_pairs_hook: object = None) -> Json: ..."
    required = len(replacement.parameters) - len(replacement.trailing_defaults)
    parts = []
    for index, typ in enumerate(replacement.parameters):
        parameter = f"arg{index}: {'object' if typ in {'*', 'Json'} else typ}"
        if index >= required:
            parameter += f" = {replacement.trailing_defaults[index - required]}"
        parts.append(parameter)
    parameters = ", ".join(parts)
    return (
        f"def {replacement.python_name.rsplit('.', 1)[1]}({parameters}, /) -> {replacement.result}: ..."
        if parameters
        else f"def {replacement.python_name.rsplit('.', 1)[1]}() -> {replacement.result}: ..."
    )


def class_definition(name: str) -> str:
    members = [f"{field}: {typ}" for field, typ in FIELDS.get(name, {}).items()]
    if name in RESOURCE_TYPES:
        members.extend(
            [
                f"def __enter__(self) -> {name}: ...",
                "def __exit__(self, kind: object, error: object, traceback: object) -> None: ...",
            ]
        )
    if name == "Json":
        members.extend(
            [
                "def __getitem__(self, key: str | int, /) -> Json: ...",
                "def __setitem__(self, key: str | int, value: object, /) -> None: ...",
                "def __contains__(self, key: str, /) -> bool: ...",
                "def __delitem__(self, key: str, /) -> None: ...",
            ]
        )
    if name == "DateTime":
        members.extend(
            f"def __{operation}__(self, other: DateTime, /) -> bool: ..." for operation in ("lt", "le", "gt", "ge")
        )
    return f"class {name}:\n" + "\n".join("    " + member for member in (members or ["..."]))


def sources(root: Path) -> dict[str, tuple[Path, str]]:
    """Nominal runtime types prevent Json and resource handles becoming Any."""
    names = set()
    for replacement in RUNTIME.values():
        for typ in (replacement.result, *replacement.parameters):
            if typ == "*":
                continue
            names.update(
                node.id
                for node in ast.walk(ast.parse(typ, mode="eval"))
                if isinstance(node, ast.Name) and node.id[0].isupper()
            )
    names.discard("Callable")
    definitions = "from typing import Callable\n" + "\n".join(class_definition(name) for name in sorted(names))
    result = {
        "py2rust": (root / "py2rust" / "__init__.pyi", ""),
        "py2rust.stdlib": (
            root / "py2rust" / "stdlib.pyi",
            definitions
            + "\ndef _json_coerce(value: object, /) -> Json: ...\n"
            + "\n".join(signature(item) for item in RUNTIME.values()),
        ),
    }
    from .third_party import REPLACEMENTS

    groups: dict[str, list[Replacement]] = {}
    for item in (*STANDARD.values(), *REPLACEMENTS.values()):
        if item.python_name.startswith(("logging.", "builtins.")):
            continue  # Keep typeshed builtin/logging types; lowering validates the supported call form.
        groups.setdefault(item.python_name.rsplit(".", 1)[0], []).append(item)
    for module, replacements in groups.items():
        imports = "from typing import Callable, TextIO\nfrom py2rust.stdlib import " + ", ".join(sorted(names)) + "\n"
        path = root.joinpath(*module.split("."))
        is_package = any(other.startswith(module + ".") for other in groups)
        stub_path = path / "__init__.pyi" if is_package else path.with_suffix(".pyi")
        constants = "\n".join(
            f"{name.rsplit('.', 1)[1]}: {type(value).__name__}"
            for name, value in CONSTANTS.items()
            if name.rpartition(".")[0] == module and name not in {"sys.stdin", "sys.stdout", "sys.stderr"}
        )
        streams = "\nstdin: TextIO\nstdout: TextIO\nstderr: TextIO" if module == "sys" else ""
        result[module] = (
            stub_path,
            imports + "\n".join(signature(item) for item in replacements) + "\n" + constants + streams,
        )
        parent = module.rpartition(".")[0]
        while parent:
            result.setdefault(parent, (root.joinpath(*parent.split(".")) / "__init__.pyi", ""))
            parent = parent.rpartition(".")[0]
    return result
