"""Static project linking and automatic native Rust imports for the service subset."""

import argparse
import ast
import copy
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .library_contracts import LIBRARY
from .project_output import cargo_files
from .rust_imports import ProjectError, read_rust_exports, symbol_name
from .rust_text import quote
from .service import ServiceCompiler, ServiceError

STDLIB_MODULES = {
    "json",
    "time",
    "logging",
    "pprint",
    "sys",
    "hmac",
    "math",
    "unicodedata",
    "heapq",
    "zlib",
    "binascii",
}


def standard_library_module(name: str) -> bool:
    return bool(name) and name.partition(".")[0] in sys.stdlib_module_names


LIBRARY_NAMES = {
    *LIBRARY,
    "Json",
    "DateTime",
    "Rational",
    "HttpServer",
    "HttpResponse",
    "WebRequest",
    "WebResponse",
    "StreamChunk",
    "FileHandle",
    "GzipReader",
    "GzipWriter",
    "LineReader",
    "HttpReader",
    "TcpListener",
    "TcpStream",
    "UnixListener",
    "UnixStream",
    "UdpSocket",
    "ProcessPool",
    "Sha256",
    "web_serve",
    "web_serve_stream",
    "parallel_map",
    "http_serve_json",
    "http_serve_json_timeout",
}
MARKER = ".py2rust-project.json"
MODULE_DEFINITIONS = (ast.FunctionDef, ast.ClassDef, ast.AnnAssign, ast.Assign)
if hasattr(ast, "TypeAlias"):
    MODULE_DEFINITIONS += (ast.TypeAlias,)


@dataclass(frozen=True)
class Binding:
    kind: str
    target: str
    member: str = ""


@dataclass
class Module:
    name: str
    path: Path
    package: bool
    tree: ast.Module | None
    bindings: dict[str, Binding] = field(default_factory=dict)


def main_guard(node: ast.AST) -> bool:
    return isinstance(node, ast.If) and not node.orelse and ast.unparse(node.test) == "__name__ == '__main__'"


def type_checking_guard(node: ast.AST) -> bool:
    return isinstance(node, ast.If) and not node.orelse and ast.unparse(node.test) == "TYPE_CHECKING"


def assignment_names(target: ast.AST) -> list[str] | None:
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        names = []
        for element in target.elts:
            child = assignment_names(element)
            if child is None:
                return None
            names.extend(child)
        return names
    return None


class Project:
    def __init__(self, root: Path, entry: str = "main.py") -> None:
        self.root = root.resolve()
        self.entry = (self.root / entry).resolve()
        if not self.entry.is_relative_to(self.root) or self.entry.suffix != ".py" or not self.entry.is_file():
            raise ProjectError("entry must be a Python file inside the project root", self.entry)
        self.modules: dict[str, Module] = {}
        self.loading: list[str] = []
        self.order: list[Module] = []
        self.natives = {}
        self.library: set[str] = set()
        self.stdlib: set[str] = set()
        self.enum_import = False
        self.dataclass_import = False
        self.source_map: dict[str, dict] = {}
        self.optimization_report: dict = {}

    def error(self, message: str, module: Module, node: ast.AST) -> None:
        raise ProjectError(message, module.path, getattr(node, "lineno", 1))

    def locate(self, name: str) -> tuple[Path, bool]:
        if not name or any(not part.isidentifier() for part in name.split(".")):
            raise ProjectError(f"invalid module name: {name}", self.root)
        base = self.root.joinpath(*name.split("."))
        choices = [
            (base.with_suffix(".py"), False),
            (base / "__init__.py", True),
            (base.with_suffix(".rs"), False),
        ]
        choices = [(p, package) for p, package in choices if p.is_file()]
        if len(choices) > 1:
            raise ProjectError(f"ambiguous module {name}: more than one Python/Rust source", base)
        if not choices:
            if base.is_dir():
                choices = [(base / "__init__.py", True)]  # Namespace package.
            else:
                raise ProjectError(
                    f"cannot resolve local module {name}; external Python packages are unsupported",
                    base,
                )
        path, package = choices[0]
        if not path.resolve().is_relative_to(self.root):
            raise ProjectError("module symlink escapes the project root", path)
        return path, package

    def bind(self, module: Module, name: str, binding: Binding, node: ast.AST) -> None:
        if name in module.bindings and module.bindings[name] != binding:
            self.error(f"duplicate module binding: {name}", module, node)
        module.bindings[name] = binding

    def load(self, name: str) -> Module:
        if name in self.loading:
            raise ProjectError(
                "circular imports are unsupported: " + " -> ".join([*self.loading, name]),
                self.modules[name].path,
            )
        if name in self.modules:
            return self.modules[name]
        parts = name.split(".")
        if len(parts) > 1 and ".".join(parts[:-1]) not in self.modules:
            self.load(".".join(parts[:-1]))
            if name in self.modules:
                return self.modules[name]
        if len(parts) > 1 and not self.modules[".".join(parts[:-1])].package:
            raise ProjectError(
                "parent module is not a package",
                self.modules[".".join(parts[:-1])].path,
            )
        path, package = self.locate(name)
        if path.suffix == ".rs":
            module = Module(name, path, False, None)
            self.modules[name] = module
            for exported, function in read_rust_exports(path, name).items():
                module.bindings[exported] = Binding("function", function.binding)
                self.natives[function.binding] = function
                self.source_map[function.binding] = {
                    "file": str(path.relative_to(self.root)),
                    "line": function.lineno,
                    "name": exported,
                }
            return module
        source = path.read_text(encoding="utf-8") if path.is_file() else ""
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            node.source_path = str(path)
        module = Module(name, path, package, tree)
        self.modules[name] = module
        self.loading.append(name)
        # Collect definitions first; import resolution never executes source code.
        for node in tree.body:
            if isinstance(node, MODULE_DEFINITIONS):
                if hasattr(ast, "TypeAlias") and isinstance(node, ast.TypeAlias):
                    definitions = [(node.name.id, "constant")]
                else:
                    targets = node.targets if isinstance(node, ast.Assign) else []
                    if isinstance(node, ast.AnnAssign):
                        targets = [node.target]
                    if targets:
                        names = []
                        for target in targets:
                            target_names = assignment_names(target)
                            if target_names is None:
                                self.error("module constants need simple names", module, node)
                            names.extend(target_names)
                        definitions = [(original, "constant") for original in names]
                    else:
                        definitions = [(node.name, "enum" if isinstance(node, ast.ClassDef) else "function")]
                for original, kind in definitions:
                    if original in module.bindings:
                        self.error(f"duplicate definition: {original}", module, node)
                    renamed = symbol_name(name, original)
                    module.bindings[original] = Binding(kind, renamed)
                    self.source_map[renamed] = {
                        "file": str(path.relative_to(self.root)),
                        "line": node.lineno,
                        "name": original,
                    }
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                self.imports(module, node)
            elif (
                module.path.resolve() != self.entry
                and not isinstance(node, MODULE_DEFINITIONS)
                and not main_guard(node)
                and not type_checking_guard(node)
                and not (
                    isinstance(node, ast.Expr)
                    and isinstance(node.value, ast.Constant)
                    and isinstance(node.value.value, str)
                )
            ):
                self.error(
                    "imported modules may contain declarations, imports and docstrings, not executable top-level statements",
                    module,
                    node,
                )
        self.loading.pop()
        self.order.append(module)
        return module

    def imports(self, module: Module, node: ast.Import | ast.ImportFrom) -> None:
        if isinstance(node, ast.Import):
            for alias in node.names:
                base = self.root.joinpath(*alias.name.split("."))
                local = base.is_dir() or any(
                    path.is_file() or path.is_symlink() for path in [base.with_suffix(".py"), base.with_suffix(".rs")]
                )
                if standard_library_module(alias.name) and (not local or alias.name in {"sys", "time"}):
                    binding = Binding("stdlib", alias.name)
                    self.stdlib.add(alias.name)
                else:
                    self.load(alias.name)
                    binding = Binding(
                        "module",
                        alias.name if alias.asname else alias.name.split(".")[0],
                    )
                self.bind(module, alias.asname or alias.name.split(".")[0], binding, node)
            return
        if any(alias.name == "*" for alias in node.names):
            self.error("star imports are unsupported", module, node)
        base = node.module or ""
        if node.level:
            package = module.name.split(".") if module.package else module.name.split(".")[:-1]
            if node.level > len(package):
                self.error("relative import escapes the project package", module, node)
            base = ".".join([*package[: len(package) - node.level + 1], *([base] if base else [])])
        local_dataclasses = base == "dataclasses" and any(
            path.exists()
            for path in [self.root / "dataclasses.py", self.root / "dataclasses.rs", self.root / "dataclasses"]
        )
        if not node.level and base in {"py2rust.stdlib", "enum", "dataclasses"} and not local_dataclasses:
            for alias in node.names:
                kind = "library"
                if base == "enum" and alias.name == "Enum":
                    self.enum_import = True
                elif base == "dataclasses" and alias.name == "dataclass":
                    self.dataclass_import = True
                elif base == "py2rust.stdlib" and alias.name in LIBRARY_NAMES:
                    self.library.add(alias.name)
                elif base == "py2rust.stdlib":
                    self.error(f"unsupported import {base}.{alias.name}", module, node)
                else:
                    kind = "stdlib"
                    self.stdlib.add(base)
                self.bind(
                    module,
                    alias.asname or alias.name,
                    Binding(kind, alias.name),
                    node,
                )
            return
        local_base = self.root.joinpath(*base.split(".")) if base else self.root
        local = local_base.is_dir() or any(
            path.is_file() or path.is_symlink()
            for path in [local_base.with_suffix(".py"), local_base.with_suffix(".rs")]
        )
        if not node.level and standard_library_module(base) and not local:
            self.stdlib.add(base)
            for alias in node.names:
                self.bind(module, alias.asname or alias.name, Binding("stdlib", alias.name), node)
            return
        target = module if base == module.name else self.load(base)
        for alias in node.names:
            if alias.name in target.bindings:
                binding = Binding("reference", base, alias.name)
            elif target.package:
                child = f"{base}.{alias.name}"
                self.load(child)
                binding = Binding("module", child)
            else:
                self.error(f"{base} has no exported name {alias.name}", module, node)
            self.bind(module, alias.asname or alias.name, binding, node)

    def resolve(self, binding: Binding, seen: frozenset = frozenset()) -> Binding:
        if binding.kind != "reference":
            return binding
        if binding in seen:
            raise ProjectError("circular re-export", self.modules[binding.target].path)
        module = self.modules[binding.target]
        if binding.member not in module.bindings:
            raise ProjectError(f"missing export {binding.member}", module.path)
        return self.resolve(module.bindings[binding.member], seen | {binding})

    def member(self, binding: Binding, name: str, source: Module, node: ast.AST) -> Binding:
        binding = self.resolve(binding)
        target = self.modules[binding.target]
        if name in target.bindings:
            return self.resolve(target.bindings[name])
        child = f"{binding.target}.{name}"
        if child in self.modules:
            return Binding("module", child)
        self.error(
            f"module {binding.target} has no imported/exported member {name}",
            source,
            node,
        )

    def compile(self, *, explain: bool = False) -> str:
        relative = self.entry.relative_to(self.root)
        parts = list(relative.with_suffix("").parts)
        if parts[-1] == "__init__":
            parts.pop()
        if not parts:
            raise ProjectError("root __init__.py cannot be the entry point", self.entry)
        entry = self.load(".".join(parts))
        declarations, statements = [], []
        for module in self.order:
            rewrite = Rewrite(self, module)
            guards = 0
            for original in module.tree.body:
                if isinstance(original, (ast.Import, ast.ImportFrom)):
                    continue
                if (
                    isinstance(original, ast.Expr)
                    and isinstance(original.value, ast.Constant)
                    and isinstance(original.value.value, str)
                ):
                    continue
                if main_guard(original):
                    guards += 1
                    if module == entry:
                        statements.extend(rewrite.visit(copy.deepcopy(n)) for n in original.body)
                    continue
                node = rewrite.visit(copy.deepcopy(original))
                for child in ast.walk(node):
                    child.source_path = str(module.path)
                if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AnnAssign)):
                    declarations.append(node)
                elif module == entry:
                    statements.append(node)
            if guards > 1:
                raise ProjectError("at most one main guard is supported", module.path)
        imports = []
        if self.library:
            imports.append(
                ast.ImportFrom(
                    module="py2rust.stdlib",
                    names=[ast.alias(name=n) for n in sorted(self.library)],
                    level=0,
                )
            )
        if self.enum_import:
            imports.append(ast.ImportFrom(module="enum", names=[ast.alias(name="Enum")], level=0))
        if self.dataclass_import:
            imports.append(ast.ImportFrom(module="dataclasses", names=[ast.alias(name="dataclass")], level=0))
        imports.extend(ast.Import(names=[ast.alias(name=n)]) for n in sorted(self.stdlib))
        # Types must exist before function signatures, including imported enums.
        declarations.sort(key=lambda n: 0 if isinstance(n, ast.ClassDef) else 1)
        guard = ast.parse("if __name__ == '__main__':\n    pass\n").body[0]
        guard.body = statements or [ast.Pass()]
        tree = ast.fix_missing_locations(ast.Module(body=[*imports, *declarations, guard], type_ignores=[]))
        compiler = ServiceCompiler({name: f.signature for name, f in self.natives.items()})
        compiler.collect_costs = explain
        output = compiler.compile_tree(tree)
        self.optimization_report = compiler.optimization_report
        native_code = []
        for module in self.modules.values():
            if module.tree is None:
                relative = (
                    module.path.relative_to(self.root).parent / (symbol_name(module.name, "module_wrapper") + ".rs")
                ).as_posix()
                native_code.append(
                    f"#[path = {quote('native/' + relative)}]\nmod {symbol_name(module.name, 'rust_module')};"
                )
        native_code.extend(f.wrapper() for f in self.natives.values())
        return output + "\n" + "\n\n".join(native_code) + "\n"


class Rewrite(ast.NodeTransformer):
    def __init__(self, project: Project, module: Module) -> None:
        self.project, self.module = project, module
        self.locals: set[str] = set()
        self.in_function = False

    def annotation(self, node: ast.AST) -> ast.AST:
        """Resolve quoted type references in annotation context without changing string values."""
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            try:
                parsed = ast.parse(node.value, mode="eval").body
            except SyntaxError:
                self.project.error("invalid quoted type annotation", self.module, node)
            for child in ast.walk(parsed):
                ast.copy_location(child, node)
            return ast.copy_location(self.annotation(parsed), node)
        if isinstance(node, ast.Subscript):
            node.value = self.visit(node.value)
            node.slice = self.annotation(node.slice)
            return node
        if isinstance(node, ast.Tuple):
            node.elts = [self.annotation(item) for item in node.elts]
            return node
        return self.visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        if self.in_function or node.name not in self.module.bindings:
            self.project.error("nested functions are outside the project subset", self.module, node)
        node.name = self.module.bindings[node.name].target
        # Annotations live in module scope; function locals must not hide them.
        if node.returns:
            node.returns = self.annotation(node.returns)
        for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]:
            if arg.annotation:
                arg.annotation = self.annotation(arg.annotation)
        before = self.locals
        self.locals = {n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
        self.locals.update(n.name for n in ast.walk(node) if isinstance(n, ast.ExceptHandler) and n.name)
        self.locals.update(a.arg for a in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs])
        self.in_function = True
        node.body = [self.visit(n) for n in node.body]
        self.in_function = False
        self.locals = before
        return node

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.ClassDef:
        if self.in_function or node.name not in self.module.bindings:
            self.project.error("nested classes are outside the project subset", self.module, node)
        node.name = self.module.bindings[node.name].target
        node.bases = [self.visit(n) for n in node.bases]
        node.decorator_list = [self.visit(n) for n in node.decorator_list]
        # Field names belong to the record, while their annotations use module imports.
        for member in node.body:
            if isinstance(member, ast.AnnAssign):
                member.annotation = self.annotation(member.annotation)
                if member.value is not None:
                    member.value = self.visit(member.value)
        return node

    def visit_AnnAssign(self, node: ast.AnnAssign) -> ast.AnnAssign:
        if not self.locals and isinstance(node.target, ast.Name) and node.target.id in self.module.bindings:
            binding = self.module.bindings[node.target.id]
            if binding.kind == "constant":
                node.target.id = binding.target
        node.annotation = self.annotation(node.annotation)
        node.target = self.visit(node.target)
        if node.value is not None:
            node.value = self.visit(node.value)
        return node

    def visit_Name(self, node: ast.Name) -> ast.AST:
        if isinstance(node.ctx, ast.Load) and node.id not in self.locals and node.id in self.module.bindings:
            binding = self.project.resolve(self.module.bindings[node.id])
            if binding.kind == "module":
                self.project.error("modules are namespaces, not runtime values", self.module, node)
            node.id = binding.target
        return node

    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
        parts, root = [], node
        while isinstance(root, ast.Attribute):
            parts.insert(0, root.attr)
            root = root.value
        if not isinstance(root, ast.Name) or root.id in self.locals or root.id not in self.module.bindings:
            return self.generic_visit(node)
        binding = self.project.resolve(self.module.bindings[root.id])
        while parts and binding.kind == "module":
            binding = self.project.member(binding, parts.pop(0), self.module, node)
        if binding.kind == "module":
            self.project.error("modules are namespaces, not runtime values", self.module, node)
        result = ast.Name(id=binding.target, ctx=ast.Load())
        for part in parts:
            result = ast.Attribute(value=result, attr=part, ctx=node.ctx)
        ast.copy_location(result, node)
        result.source_path = str(self.module.path)
        return result


def write_if_changed(path: Path, data: bytes) -> None:
    if path.is_file() and path.read_bytes() == data:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def create_project(
    root: Path, output: Path, entry: str = "main.py", binary_name: str = "py2rust-service", *, frontend: str = "typed"
) -> Project:
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", binary_name):
        raise ProjectError(
            "binary name must start with a letter and contain only letters, digits, underscores or hyphens", output
        )
    root, output = root.resolve(), output.resolve()
    if output == root or root.is_relative_to(output):
        raise ProjectError("generated output must not replace the source root or its parents", output)
    if output.exists() and any(output.iterdir()) and not (output / MARKER).is_file():
        raise ProjectError("output directory is not empty or managed by py2rust-project", output)
    project = Project(root, entry)
    # Validate through the selected frontend before writing anything.
    if frontend == "typed":
        from .pipeline import compile_loaded_project

        code = compile_loaded_project(project, packaged=True)
    elif frontend == "legacy":
        code = project.compile()
    else:
        raise ProjectError("unknown compiler frontend: " + frontend, root)
    from .rust_names import readable_names

    symbols = {symbol: location["name"] for symbol, location in project.source_map.items()}
    symbols.update(
        (symbol_name(module.name, "rust_module"), module.name.replace(".", "_") + "_native")
        for module in project.modules.values()
        if module.tree is None
    )
    code, emitted_names = readable_names(code, symbols)
    for row in project.optimization_report.get("functions", []):
        row["rust_symbol"] = emitted_names.get(row["symbol"], row["symbol"])
    formatted = subprocess.run(
        ["rustfmt", "--edition=2021", "--config", "skip_children=true"],
        input=code,
        text=True,
        capture_output=True,
        check=False,
    )
    if formatted.returncode:
        raise ProjectError("generated Rust formatting failed: " + formatted.stderr, project.entry)
    files = cargo_files(formatted.stdout, binary_name)
    # Preserve relative Rust module paths. Generated/build/hidden directories are
    # excluded; non-Rust include! assets and external Cargo dependencies are not inferred.
    ignored = {"target", "build", "__pycache__"}
    for directory, dirs, names in os.walk(root):
        dirs[:] = [
            d
            for d in dirs
            if not d.startswith(".")
            and d not in ignored
            and (Path(directory) / d).resolve() != output
            and not (Path(directory) / d).is_symlink()
        ]
        for name in names:
            source = Path(directory) / name
            if source.suffix == ".rs":
                if not source.resolve().is_relative_to(root):
                    raise ProjectError("Rust source symlink escapes the project root", source)
                files["src/native/" + source.relative_to(root).as_posix()] = source.read_bytes()
    for module in project.modules.values():
        if module.tree is None:
            files["src/native/" + module.path.relative_to(root).as_posix()] = module.path.read_bytes()
            wrapper = module.path.relative_to(root).parent / (symbol_name(module.name, "module_wrapper") + ".rs")
            files["src/native/" + wrapper.as_posix()] = f"pub mod r#{module.path.stem};\n".encode()
    previous = {}
    if not (output / MARKER).resolve().is_relative_to(output):
        raise ProjectError("project marker symlink escapes the output directory", output / MARKER)
    if (output / MARKER).exists():
        metadata = json.loads((output / MARKER).read_text())
        if metadata.get("format") != 1 or metadata.get("root") != str(root):
            raise ProjectError("output belongs to another project or an unsupported format", output)
        previous = metadata["files"]
    # Never traverse a generated-directory symlink or overwrite hand edits.
    for name in {*previous, *files}:
        destination = (output / name).resolve()
        if not destination.is_relative_to(output):
            raise ProjectError("generated file path escapes its output directory", output / name)
        if destination.exists() and (
            name not in previous or hashlib.sha256(destination.read_bytes()).hexdigest() != previous[name]
        ):
            raise ProjectError(
                "generated file has local edits; move edits into source or choose a new output directory",
                destination,
            )
    provenance = {
        "format": 1,
        "root": str(root),
        "entry": entry,
        "binary_name": binary_name,
        "frontend": frontend,
        "symbols": {emitted_names.get(symbol, symbol): location for symbol, location in project.source_map.items()},
        "files": {name: hashlib.sha256(data).hexdigest() for name, data in files.items()},
    }
    # Managed files are replaced; user files and Cargo target caches are retained.
    for name, data in files.items():
        write_if_changed(output / name, data)
    for name in previous.keys() - files.keys():
        (output / name).unlink(missing_ok=True)
    write_if_changed(
        output / MARKER,
        (json.dumps(provenance, indent=2, sort_keys=True) + "\n").encode(),
    )
    return project


def main() -> int:
    parser = argparse.ArgumentParser(description="Transpile, build and run a typed Python/Rust project")
    parser.add_argument("action", choices=["transpile", "build", "run", "explain"])
    parser.add_argument("project", type=Path, nargs="?", default=Path("."))
    parser.add_argument("--entry", default=None, help="entry Python file relative to the project root")
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument("--frontend", choices=["legacy", "typed"], default="typed")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--release", action="store_true")
    parser.add_argument("--name", default="py2rust-service", help="generated Cargo executable name")
    parser.add_argument("--function", action="append", help="explain: file.py:function or generated-symbol glob")
    parser.add_argument(
        "--deny",
        action="append",
        choices=["unknown-effects", "snapshot-iteration", "owned-boundary-copy"],
        help="explain: fail a scoped cost check",
    )
    args = parser.parse_args()
    if args.action != "explain" and (args.function or args.deny):
        parser.error("--function and --deny require the explain action")
    root = args.project.resolve()
    entry = args.entry or ("main.py" if (root / "main.py").is_file() else "__main__.py")
    output = args.output or root / ".py2rust" / "rust"
    try:
        if args.action == "explain":
            from .diagnostics import select_and_check

            project = Project(root, entry)
            if args.frontend == "typed":
                from .pipeline import compile_loaded_project

                compile_loaded_project(project, explain=True)
            else:
                project.compile(explain=True)
            report = select_and_check(
                project.optimization_report, project.source_map, args.function or ["*"], args.deny or []
            )
            print(json.dumps(report, indent=2, sort_keys=True))
            return 2 if report["violations"] else 0
        create_project(root, output, entry, args.name, frontend=args.frontend)
        if args.action == "transpile":
            print(output.resolve())
            return 0
        command = [
            "cargo",
            "build",
            "--locked",
            "--manifest-path",
            str(output.resolve() / "Cargo.toml"),
        ]
        if args.offline:
            command.append("--offline")
        if args.release:
            command.append("--release")
        # An explicit target directory gives a predictable executable even if the
        # caller sets CARGO_TARGET_DIR or a global Cargo configuration.
        command.extend(["--target-dir", str(output.resolve() / "target")])
        result = subprocess.run(command, check=False)
        if result.returncode or args.action == "build":
            return result.returncode
        executable = (
            output.resolve()
            / "target"
            / ("release" if args.release else "debug")
            / (args.name + (".exe" if os.name == "nt" else ""))
        )
        return subprocess.run([str(executable)], cwd=root, check=False).returncode
    except (ProjectError, ServiceError, SyntaxError, OSError, ValueError) as error:
        print(
            f"{getattr(error, 'filename', None) or root}:{getattr(error, 'lineno', 1)}: {error}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
