"""Typed frontend declarations for interfaces parsed from native Rust files."""

from pathlib import Path

from ..backend.values import Type
from ..rust_imports import NativeFunction, read_rust_exports


def python_type(typ: Type, *, builtins: str, json_type: str) -> str:
    name = "None" if typ.name == "None" else json_type if typ.name == "Json" else f"{builtins}.{typ.name}"
    if not typ.args:
        return name
    arguments = ", ".join(python_type(arg, builtins=builtins, json_type=json_type) for arg in typ.args)
    return f"{name}[{arguments}]"


def declarations(paths: dict[str, Path], root: Path) -> tuple[dict, dict[str, NativeFunction]]:
    stubs = {}
    functions = {}
    for module, path in paths.items():
        exports = read_rust_exports(path.resolve(), module)
        builtin_alias = "_py2rust_builtins"
        while builtin_alias in exports:
            builtin_alias += "_"
        json_alias = "_py2rust_json"
        while json_alias in exports:
            json_alias += "_"
        lines = [f"import builtins as {builtin_alias}", f"from py2rust.stdlib import Json as {json_alias}"]
        for exported, function in exports.items():
            functions[f"{module}.{exported}"] = function
            args = ", ".join(
                f"arg{i}: {python_type(param.python, builtins=builtin_alias, json_type=json_alias)}"
                for i, param in enumerate(function.parameters)
            )
            if args:
                args += ", /"
            result = python_type(function.result.python, builtins=builtin_alias, json_type=json_alias)
            lines.append(f"def {exported}({args}) -> {result}: ...")
        stubs[module] = (root.joinpath(*module.split(".")).with_suffix(".pyi"), "\n".join(lines))
    return stubs, functions
