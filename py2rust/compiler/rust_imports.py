"""Infer a deliberately small callable interface from real Rust syntax trees."""

import re
from dataclasses import dataclass
from pathlib import Path

import tree_sitter
import tree_sitter_rust

from .backend.values import Type


class ProjectError(ValueError):
    def __init__(self, message: str, filename: Path, lineno: int = 1) -> None:
        self.filename, self.lineno = str(filename), lineno
        super().__init__(message)


def symbol_name(module: str, name: str) -> str:
    # Ordinary names remain readable. Escape components that could collide with
    # the double-underscore separator or the escape prefix.
    parts = [*module.split("."), name]
    return "py__" + "__".join(
        (
            p
            if re.fullmatch(r"[a-zA-Z][a-zA-Z0-9]*(?:_[a-zA-Z0-9]+)*", p) and not p.startswith("escaped_")
            else "escaped_" + p.encode().hex()
        )
        for p in parts
    )


@dataclass(frozen=True)
class NativeType:
    python: Type
    conversion: str = "identity"

    def argument(self, name: str) -> str:
        if self.conversion == "borrow":
            return f"&{name}"
        if self.conversion == "integer":
            return f"{name}.try_into()?"
        return name

    def result(self, value: str) -> str:
        if self.conversion == "borrow":
            value = f"({value}).to_owned()"
        if self.conversion == "integer":
            value = f"i64::try_from({value})?"
        return validate_result(value, self.python)


def validate_result(value: str, typ: Type) -> str:
    """Keep native results within the service profile's numeric/JSON contract."""
    if typ.name == "float":
        return f"rt::finite({value})?"
    if typ.name == "Json":
        return f"rt::to_json(&({value}))?"
    if typ.name == "list":
        child = validate_result("item", typ.args[0])
        if child != "item":
            return (
                f"({value}).into_iter().map(|item| -> rt::Result<_> {{ Ok({child}) }}).collect::<rt::Result<Vec<_>>>()?"
            )
    if typ.name == "tuple":
        children = [validate_result(f"value.{i}", t) for i, t in enumerate(typ.args)]
        if any(c != f"value.{i}" for i, c in enumerate(children)):
            return f"{{ let value = {value}; ({', '.join(children)},) }}"
    return value


def native_type(node: tree_sitter.Node | None, path: Path) -> NativeType:
    if node is None:
        return NativeType(Type("None"))
    text = re.sub(r"\s+", "", node.text.decode())
    scalars = {
        "String": "str",
        "std::string::String": "str",
        "i64": "int",
        "f64": "float",
        "bool": "bool",
        "()": "None",
        "serde_json::Value": "Json",
        "py2rust_service_runtime::Json": "Json",
    }
    if text in scalars:
        return NativeType(Type(scalars[text]))
    if re.fullmatch(r"(?:[ui](?:8|16|32|64|128)|[ui]size)", text):
        return NativeType(Type("int"), "integer")
    if re.fullmatch(r"&(?:'[a-zA-Z_][a-zA-Z_0-9]*)?str", text):
        return NativeType(Type("str"), "borrow")
    if text in {"Vec<u8>", "std::vec::Vec<u8>"}:
        return NativeType(Type("bytes"))
    if re.fullmatch(r"&(?:'[a-zA-Z_][a-zA-Z_0-9]*)?\[u8\]", text):
        return NativeType(Type("bytes"), "borrow")
    if node.type == "generic_type" and node.child_by_field_name("type").text.decode() in {"Vec", "std::vec::Vec"}:
        children = node.child_by_field_name("type_arguments").named_children
        if len(children) == 1:
            item = native_type(children[0], path)
            if item.conversion == "identity" and item.python.name != "None":
                return NativeType(Type("list", (item.python,)))
    if node.type == "tuple_type":
        items = [native_type(c, path) for c in node.named_children]
        if items and all(t.conversion == "identity" and t.python.name != "None" for t in items):
            return NativeType(Type("tuple", tuple(t.python for t in items)))
    raise ProjectError(
        f"unsupported Rust boundary type: {node.text.decode()}",
        path,
        node.start_point.row + 1,
    )


@dataclass(frozen=True)
class NativeFunction:
    module: str
    name: str
    parameters: tuple[NativeType, ...]
    result: NativeType
    fallible: bool
    path: Path
    lineno: int

    @property
    def binding(self) -> str:
        return symbol_name(self.module, self.name)

    @property
    def signature(self) -> tuple:
        return tuple(t.python for t in self.parameters), self.result.python

    def wrapper(self) -> str:
        args = ", ".join(f"a{i}: {t.python.rust()}" for i, t in enumerate(self.parameters))
        values = ", ".join(t.argument(f"a{i}") for i, t in enumerate(self.parameters))
        call = f"{symbol_name(self.module, 'rust_module')}::r#{self.path.stem}::{self.name}({values})"
        if self.fallible:
            call += "?"
        call = self.result.result(call)
        return f"fn {self.binding}({args}) -> rt::Result<{self.result.python.rust()}> {{ Ok({call}) }}"


def read_rust_exports(path: Path, module: str) -> dict[str, NativeFunction]:
    if path.stem in {"self", "Self", "super", "crate"}:
        raise ProjectError("Rust module filename is a reserved keyword", path)
    parser = tree_sitter.Parser(tree_sitter.Language(tree_sitter_rust.language()))
    tree = parser.parse(path.read_bytes())
    if tree.root_node.has_error:

        def first_error(node):
            for child in node.named_children:
                if child.has_error:
                    return first_error(child)
            return node

        bad = first_error(tree.root_node)
        raise ProjectError("invalid Rust syntax", path, bad.start_point.row + 1)
    exports = {}
    attributes = []
    for node in tree.root_node.named_children:
        if node.type == "attribute_item":
            attributes.append(node.text.decode())
            continue
        attrs, attributes = attributes, []
        if node.type != "function_item":
            continue
        visibility = next((c for c in node.named_children if c.type == "visibility_modifier"), None)
        if visibility is None or visibility.text != b"pub":
            continue
        name = node.child_by_field_name("name").text.decode()
        line = node.start_point.row + 1
        if not re.fullmatch(r"[a-zA-Z_][a-zA-Z_0-9]*", name):
            raise ProjectError("Rust exports need plain identifiers", path, line)
        if node.child_by_field_name("type_parameters") or any(
            c.type == "where_clause"
            or (c.type == "function_modifiers" and re.search(rb"\b(async|unsafe|extern)\b", c.text))
            for c in node.named_children
        ):
            raise ProjectError(
                f"Rust export {name} must be a safe, synchronous, nongeneric function",
                path,
                line,
            )
        if any(re.search(r"\b(cfg|cfg_attr)\b", a) for a in attrs):
            raise ProjectError(f"conditional Rust export {name} is unsupported", path, line)
        parameters = []
        for parameter in node.child_by_field_name("parameters").named_children:
            if parameter.type != "parameter" or parameter.child_by_field_name("type") is None:
                raise ProjectError("unsupported Rust parameter", path, line)
            parameters.append(native_type(parameter.child_by_field_name("type"), path))
        result = node.child_by_field_name("return_type")
        fallible = False
        if (
            result
            and result.type == "generic_type"
            and result.child_by_field_name("type").text.decode() in {"Result", "std::result::Result"}
        ):
            arguments = result.child_by_field_name("type_arguments").named_children
            if len(arguments) != 2:
                raise ProjectError(
                    "Rust Result exports need explicit value and error types",
                    path,
                    line,
                )
            result, fallible = arguments[0], True
        exports[name] = NativeFunction(
            module,
            name,
            tuple(parameters),
            native_type(result, path),
            fallible,
            path,
            line,
        )
    return exports
