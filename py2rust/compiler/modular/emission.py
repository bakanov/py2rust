"""Partition flat generated Rust into real modules using Rust syntax trees."""

from __future__ import annotations

import json
import posixpath
from dataclasses import dataclass
from pathlib import Path

import tree_sitter
import tree_sitter_rust

from ..rust_imports import symbol_name
from ..rust_names import KEYWORDS, component
from ..rust_text import quote

_ITEM_TYPES = {
    "const_item",
    "enum_item",
    "function_item",
    "impl_item",
    "mod_item",
    "static_item",
    "struct_item",
    "type_item",
}
_PREFIX_TYPES = {"attribute_item", "block_comment", "line_comment"}
_IDENTIFIER_TYPES = {"identifier", "type_identifier"}


class ModularEmissionError(ValueError):
    pass


@dataclass(frozen=True)
class ModuleSource:
    name: str
    path: Path
    package: bool = False

    @classmethod
    def from_project(cls, module) -> ModuleSource:
        return cls(module.name, module.path, module.package)


@dataclass(frozen=True)
class EmittedSymbol:
    module: str
    name: str
    file: str
    path: str


@dataclass(frozen=True)
class ModuleEmission:
    files: dict[str, str]
    modules: dict[str, str]
    symbols: dict[str, EmittedSymbol]


@dataclass
class _Bundle:
    start: int
    end: int
    node: tree_sitter.Node
    module: str | None = None


@dataclass(frozen=True)
class _Edit:
    start: int
    end: int
    text: bytes


def _parser() -> tree_sitter.Parser:
    return tree_sitter.Parser(tree_sitter.Language(tree_sitter_rust.language()))


def _walk(node: tree_sitter.Node):
    pending = list(reversed(node.named_children))
    while pending:
        current = pending.pop()
        yield current
        pending.extend(reversed(current.named_children))


def _item_name(node: tree_sitter.Node) -> tree_sitter.Node | None:
    name = node.child_by_field_name("name")
    if name is not None:
        return name
    return next(
        (child for child in node.named_children if child.type in {"identifier", "type_identifier"}),
        None,
    )


def _text(data: bytes, node: tree_sitter.Node) -> str:
    return data[node.start_byte : node.end_byte].decode()


def _has_visibility(node: tree_sitter.Node) -> bool:
    return any(child.type == "visibility_modifier" for child in node.named_children)


def _safe_name(value: str) -> str:
    name = component(value)
    if name in KEYWORDS:
        name += "_"
    return name


def _module_prefix(module: str) -> str:
    return symbol_name(module, "placeholder").removesuffix("__placeholder")


def _local_part(symbol: str, prefix: str) -> str:
    parts = symbol[len(prefix) + 2 :].split("__")
    decoded = [bytes.fromhex(part[8:]).decode() if part.startswith("escaped_") else part for part in parts]
    return "__".join(decoded)


def _apply_edits(data: bytes, start: int, end: int, edits: list[_Edit]) -> bytes:
    result = data[start:end]
    for edit in sorted(edits, key=lambda item: (item.start, item.end), reverse=True):
        relative_start = edit.start - start
        relative_end = edit.end - start
        result = result[:relative_start] + edit.text + result[relative_end:]
    return result


def _error_location(data: bytes, tree: tree_sitter.Tree) -> str:
    def first_error(node: tree_sitter.Node):
        if node.is_error or node.is_missing:
            return node
        for child in node.named_children:
            if child.has_error:
                found = first_error(child)
                if found is not None:
                    return found
        return None

    error = first_error(tree.root_node)
    if error is None:
        return "unknown location"
    return f"line {error.start_point.row + 1}, column {error.start_point.column + 1}: {_text(data, error)}"


class _Emitter:
    def __init__(self, code: str, modules: tuple[ModuleSource, ...], source_root: Path | None) -> None:
        self.data = code.encode()
        self.tree = _parser().parse(self.data)
        if self.tree.root_node.has_error:
            raise ModularEmissionError("invalid flat Rust: " + _error_location(self.data, self.tree))
        self.specs = {module.name: module for module in modules}
        if len(self.specs) != len(modules):
            raise ModularEmissionError("duplicate Python module names")
        self.source_root = source_root.resolve() if source_root is not None else None
        self.prefixes = {name: _module_prefix(name) for name in self.specs}
        self.preamble: list[str] = []
        self.bundles = self._partition()
        self.paths = self._module_paths()
        self.module_files = {name: self._module_file(name) for name in self.specs}
        self.symbols = self._discover_symbols()
        self.local_names: dict[str, str] = {}
        self.symbol_modules: dict[str, str] = {}

    def _partition(self) -> list[_Bundle]:
        bundles = []
        prefix_start = None
        for node in self.tree.root_node.named_children:
            if node.type == "inner_attribute_item":
                self.preamble.append(_text(self.data, node))
                continue
            if node.type == "use_declaration":
                if _text(self.data, node).strip() != "use py2rust_service_runtime as rt;":
                    raise ModularEmissionError("top-level imports other than the runtime alias are unsupported")
                continue
            if node.type in _PREFIX_TYPES:
                if prefix_start is None:
                    prefix_start = node.start_byte
                continue
            if node.type not in _ITEM_TYPES:
                raise ModularEmissionError(f"unsupported top-level Rust node: {node.type}")
            bundles.append(_Bundle(node.start_byte if prefix_start is None else prefix_start, node.end_byte, node))
            prefix_start = None
        if prefix_start is not None:
            raise ModularEmissionError("trailing attributes or comments do not belong to a Rust item")
        return bundles

    def _owner(self, symbol: str) -> str:
        matches = [name for name, prefix in self.prefixes.items() if symbol.startswith(prefix + "__")]
        if not matches:
            raise ModularEmissionError(f"cannot determine the Python module for {symbol}")
        return max(matches, key=lambda name: len(self.prefixes[name]))

    def _discover_symbols(self) -> dict[str, str]:
        symbols = {}
        for node in _walk(self.tree.root_node):
            if node.type not in _IDENTIFIER_TYPES:
                continue
            text = _text(self.data, node)
            if text.startswith("py__"):
                symbols[text] = self._owner(text)
        return symbols

    def _module_paths(self) -> dict[str, list[str]]:
        paths: dict[str, list[str]] = {}
        used: dict[str | None, set[str]] = {}
        for name in sorted(self.specs, key=lambda item: (item.count("."), item == "main", item)):
            parent = name.rpartition(".")[0] or None
            preferred = "entry" if name == "main" and parent is None else _safe_name(name.rsplit(".", 1)[-1])
            siblings = used.setdefault(parent, set())
            candidate = preferred
            suffix = 2
            while candidate in siblings:
                candidate = f"{preferred}_{suffix}"
                suffix += 1
            siblings.add(candidate)
            paths[name] = [*(paths.get(parent, [])), candidate]
        return paths

    def _module_file(self, name: str) -> str:
        path = "/".join(self.paths[name])
        has_children = any(other.rpartition(".")[0] == name and "." in other for other in self.specs)
        if self.specs[name].package or has_children:
            return f"src/{path}/mod.rs"
        return f"src/{path}.rs"

    def _assign_modules(self) -> None:
        helpers: dict[str, str] = {}
        for bundle in self.bundles:
            node = bundle.node
            if node.type == "mod_item" and node.child_by_field_name("body") is not None:
                raise ModularEmissionError("inline native Rust modules require packaged module paths")
            if node.type == "impl_item":
                target = node.child_by_field_name("type")
                if target is not None:
                    name = _text(self.data, target)
                    if name.startswith("py__"):
                        bundle.module = self._owner(name)
                continue
            if node.type not in _ITEM_TYPES:
                continue
            name_node = _item_name(node)
            if name_node is None:
                continue
            name = _text(self.data, name_node)
            if node.type == "function_item" and name == "main":
                bundle.module = None
            elif name.startswith("py__"):
                bundle.module = self._owner(name)
            elif node.type == "struct_item" and name.rstrip("_").endswith("Storage"):
                continue
            elif node.type != "impl_item":
                raise ModularEmissionError(f"cannot assign top-level {node.type} {name!r} to a Python module")
        for index, bundle in enumerate(self.bundles):
            if bundle.node.type != "struct_item" or bundle.module is not None:
                continue
            name = _text(self.data, _item_name(bundle.node))
            following = next(
                (
                    other
                    for other in self.bundles[index + 1 :]
                    if other.node.type == "struct_item" and other.module is not None
                ),
                None,
            )
            if following is None:
                raise ModularEmissionError(f"cannot assign recursive-record storage {name!r}")
            bundle.module = following.module
            helpers[name] = following.module
        previous = None
        for bundle in self.bundles:
            if bundle.node.type == "impl_item" and bundle.module is None:
                target = bundle.node.child_by_field_name("type")
                name = _text(self.data, target) if target is not None else ""
                bundle.module = helpers.get(name) or previous
                if bundle.module is None:
                    raise ModularEmissionError(f"cannot assign implementation for {name!r}")
            if bundle.module is not None:
                previous = bundle.module

    def _allocate_names(self) -> None:
        used: dict[str, set[str]] = {name: set() for name in self.specs}
        for bundle in self.bundles:
            if bundle.module is None:
                continue
            for node in _walk(bundle.node):
                if node.type not in {*_IDENTIFIER_TYPES, "field_identifier"}:
                    continue
                if node.type == "field_identifier" or node.parent.type in {
                    "scoped_identifier",
                    "scoped_type_identifier",
                }:
                    continue
                text = _text(self.data, node)
                if not text.startswith("py__"):
                    used[bundle.module].add(text)
        for symbol in sorted(self.symbols):
            module = self.symbols[symbol]
            preferred = _safe_name(_local_part(symbol, self.prefixes[module]))
            candidate = preferred
            suffix = 2
            while candidate in used[module]:
                candidate = f"{preferred}_{suffix}"
                suffix += 1
            used[module].add(candidate)
            self.local_names[symbol] = candidate
            self.symbol_modules[symbol] = module

    def _comment_edit(self, node: tree_sitter.Node) -> _Edit | None:
        text = _text(self.data, node)
        if self.source_root is None or not text.startswith("// Python: "):
            return None
        location = text.removeprefix("// Python: ")
        filename, separator, line = location.rpartition(":")
        if not separator:
            return None
        try:
            relative = Path(filename).resolve().relative_to(self.source_root)
        except ValueError:
            return None
        return _Edit(node.start_byte, node.end_byte, f"// Python: {relative.as_posix()}:{line}".encode())

    def _render_bundle(self, bundle: _Bundle) -> str:
        edits = []
        node = bundle.node
        if bundle.module is not None and node.type in {
            "const_item",
            "enum_item",
            "function_item",
            "mod_item",
            "static_item",
            "struct_item",
            "type_item",
        }:
            if not _has_visibility(node):
                edits.append(_Edit(node.start_byte, node.start_byte, b"pub(crate) "))
        if node.type == "struct_item":
            for child in _walk(node):
                if child.type == "field_declaration" and not _has_visibility(child):
                    edits.append(_Edit(child.start_byte, child.start_byte, b"pub(crate) "))
                if child.type == "ordered_field_declaration_list":
                    visible = False
                    for field in child.named_children:
                        if field.type == "visibility_modifier":
                            visible = True
                            continue
                        if not visible:
                            edits.append(_Edit(field.start_byte, field.start_byte, b"pub(crate) "))
                        visible = False
        declaration = _item_name(node)
        for child in _walk(node):
            if child.type in {"line_comment", "block_comment"}:
                edit = self._comment_edit(child)
                if edit is not None:
                    edits.append(edit)
            if child.type not in _IDENTIFIER_TYPES:
                continue
            symbol = _text(self.data, child)
            if symbol not in self.symbols:
                continue
            owner = self.symbols[symbol]
            local = self.local_names[symbol]
            is_declaration = declaration is not None and child.start_byte == declaration.start_byte
            if is_declaration or owner == bundle.module:
                replacement = local
            else:
                replacement = "crate::" + "::".join([*self.paths[owner], local])
            edits.append(_Edit(child.start_byte, child.end_byte, replacement.encode()))
        for child in self.tree.root_node.named_children:
            if bundle.start <= child.start_byte < node.start_byte and child.type in _PREFIX_TYPES:
                edit = self._comment_edit(child)
                if edit is not None:
                    edits.append(edit)
                if node.type == "mod_item" and child.type == "attribute_item":
                    for literal in _walk(child):
                        if literal.type != "string_literal":
                            continue
                        try:
                            path = json.loads(_text(self.data, literal))
                        except json.JSONDecodeError as error:
                            raise ModularEmissionError("unsupported escape in native module path") from error
                        if not path.startswith("native/") or bundle.module is None:
                            raise ModularEmissionError("native modules must use packaged native/ paths")
                        target = "src/" + path
                        directory = posixpath.dirname(self.module_files[bundle.module])
                        relative = posixpath.relpath(target, directory)
                        edits.append(_Edit(literal.start_byte, literal.end_byte, quote(relative).encode()))
        return _apply_edits(self.data, bundle.start, bundle.end, edits).decode()

    def _children(self, parent: str | None) -> list[str]:
        if parent is None:
            return sorted(name for name in self.specs if "." not in name)
        return sorted(name for name in self.specs if name.rpartition(".")[0] == parent and "." in name)

    def _module_declarations(self, parent: str | None) -> list[str]:
        return [f"pub(crate) mod {self.paths[name][-1]};" for name in self._children(parent)]

    def run(self) -> ModuleEmission:
        self._assign_modules()
        self._allocate_names()
        rendered = {id(bundle): self._render_bundle(bundle) for bundle in self.bundles}
        files = {}
        for name in self.specs:
            declarations = self._module_declarations(name)
            items = [rendered[id(bundle)] for bundle in self.bundles if bundle.module == name]
            runtime = ["use py2rust_service_runtime as rt;"] if any("rt::" in item for item in items) else []
            files[self.module_files[name]] = "\n\n".join([*declarations, *runtime, *items]).rstrip() + "\n"
        entry = [rendered[id(bundle)] for bundle in self.bundles if bundle.module is None]
        if not any(bundle.node.type == "function_item" for bundle in self.bundles if bundle.module is None):
            raise ModularEmissionError("flat Rust has no executable main function")
        root = [
            *self.preamble,
            *self._module_declarations(None),
            *(["use py2rust_service_runtime as rt;"] if any("rt::" in item for item in entry) else []),
            *entry,
        ]
        files["src/main.rs"] = "\n\n".join(root).rstrip() + "\n"
        parser = _parser()
        for filename, content in files.items():
            tree = parser.parse(content.encode())
            if tree.root_node.has_error:
                raise ModularEmissionError(f"invalid generated {filename}: {_error_location(content.encode(), tree)}")
        symbols = {
            symbol: EmittedSymbol(
                module,
                self.local_names[symbol],
                self.module_files[module],
                "crate::" + "::".join([*self.paths[module], self.local_names[symbol]]),
            )
            for symbol, module in self.symbols.items()
        }
        return ModuleEmission(files, dict(self.module_files), symbols)


def emit_modules(
    code: str,
    modules: tuple[ModuleSource, ...] | list[ModuleSource],
    *,
    source_root: Path | None = None,
) -> ModuleEmission:
    """Convert one flat generated main.rs into a Python-shaped Rust module tree."""
    return _Emitter(code, tuple(modules), source_root).run()
