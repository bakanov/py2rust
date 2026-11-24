"""Hand-labeled source-only fixtures; none may be imported or executed by the browser."""

import ast
import base64
import hashlib
from collections import Counter
from pathlib import PurePosixPath

FILES = {
    "main.py": b"""import os
import pkg.logic as logic
import pkg.missing
import namespace
import duplicate
from pkg import logic, missing
from pkg.logic import outer
from pkg import *
from ghost import value
from . import impossible
open("EXECUTED", "w").write("bad")
raise RuntimeError("analyzed source must never execute")
""",
    "pkg/__init__.py": b"from .logic import outer\n",
    "pkg/logic.py": b"""import math
from . import helper

@decorate
def outer(flag):
    value = "<script>alert('x')</script> & \\\"quoted\\\""
    if flag:
        value += "!"
    def inner():
        return 1
    class Nested:
        def method(self):
            pass
    return value
""",
    "pkg/helper.py": b"""async def poll(items):
    async for item in items:
        if item:
            await send(item)
    async with guard():
        return None
""",
    "pkg/branches.py": b"""def branches(x):
    try:
        match x:
            case 0:
                return 0
            case _:
                return 1
    except ValueError:
        raise
    else:
        pass
    finally:
        pass
""",
    "namespace/data.py": b"type Pair[T] = tuple[T, T]\nfrom ..pkg import helper\n",
    "duplicate.py": b"pass\n",
    "duplicate/__init__.py": b"from . import child\n",
    "duplicate/child.py": b"value = 1; other = 2\n",
    "constructs.py": b"""class Container:
    @staticmethod
    def method():
        global counter
        for item in (1, 2):
            while item:
                if item > 1: break
                else: continue
        else:
            pass
        with open("never-opened") as handle:
            assert handle
        try:
            pass
        except* ValueError:
            pass
        finally:
            pass

def expressions():
    values = [item for item in range(3) if item]
    choose = lambda x: x if x else 0
    return choose(values)
""",
    "empty.py": b"",
    "unicode.py": '\ufeff@tag("世界")\r\ndef café():\r\n    "doc 🙂"\r\n    return "e\u0301\u2028"\r\n'.encode(),
}
DEFINITIONS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
CONTROL = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.TryStar, ast.With, ast.AsyncWith, ast.Match)


def normalize(raw: bytes) -> str:
    return raw.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")


def child_statements(node: ast.AST) -> list[ast.stmt]:
    result = []
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.stmt):
            result.append(child)
        elif not isinstance(child, ast.expr):
            result.extend(child_statements(child))
    return result


def owned(scope: ast.AST) -> dict:
    kinds = Counter()
    depths = []
    controls = 0

    def visit(node: ast.stmt, depth: int) -> None:
        nonlocal controls
        kinds[type(node).__name__] += 1
        depths.append(depth)
        controls += isinstance(node, CONTROL)
        if not isinstance(node, DEFINITIONS):
            for child in child_statements(node):
                visit(child, depth + 1)
        return  # noqa: PLR1711 - explicit repository convention

    for node in scope.body:
        visit(node, 0)
    return {
        "statements": sum(kinds.values()),
        "control_statements": controls,
        "max_depth": max(depths, default=0),
        "kinds": dict(kinds),
    }


def identity(relative: str, prefix: str) -> tuple[str, bool]:
    path = PurePosixPath(relative)
    package = path.name == "__init__.py"
    parts = list(path.parent.parts) if package else [*path.parent.parts, path.stem]
    return ".".join(([prefix] if prefix else []) + parts), package


def describe(relative: str, raw: bytes, prefix: str, thresholds: dict, page: str) -> dict:
    text = normalize(raw)
    tree = ast.parse(text, feature_version=(3, 12))
    name, package = identity(relative, prefix)
    flat, definitions, imports = [], [], []

    def visit(node: ast.AST, scope: str) -> None:
        if isinstance(node, ast.stmt):
            index = len(flat)
            flat.append(node)
            if isinstance(node, DEFINITIONS):
                qualified = scope + "." + node.name
                start = min([node.lineno, *(d.lineno for d in node.decorator_list)])
                metrics = owned(node)
                flags = []
                span = node.end_lineno - start + 1
                if not isinstance(node, ast.ClassDef):
                    for key, value in [
                        ("lines", span),
                        ("statements", metrics["statements"]),
                        ("depth", metrics["max_depth"]),
                    ]:
                        if value > thresholds[key]:
                            flags.append(key)
                definitions.append(
                    {
                        "id": index,
                        "kind": type(node).__name__,
                        "name": node.name,
                        "qualified": qualified,
                        "line": node.lineno,
                        "column": node.col_offset,
                        "end_line": node.end_lineno,
                        "end_column": node.end_col_offset,
                        "start_line": start,
                        "lines": span,
                        "metrics": metrics,
                        "flags": flags,
                    }
                )
                scope = qualified + ("" if isinstance(node, ast.ClassDef) else ".<locals>")
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    imports.append(
                        {
                            "kind": type(node).__name__,
                            "line": node.lineno,
                            "column": node.col_offset,
                            "scope": scope,
                            "module": getattr(node, "module", None) or "",
                            "level": getattr(node, "level", 0),
                            "name": alias.name,
                            "alias": alias.asname or "",
                            "status": "",
                            "target": "",
                            "href": "",
                        }
                    )
        for child in ast.iter_child_nodes(node):
            visit(child, scope)
        return  # noqa: PLR1711

    visit(tree, name)
    functions = sum(d["kind"] != "ClassDef" for d in definitions)
    return {
        "path": relative,
        "name": name,
        "package": package,
        "page": page,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "lines": text.count("\n") + int(bool(text) and not text.endswith("\n")),
        "statements": len(flat),
        "kinds": dict(Counter(type(n).__name__ for n in flat)),
        "top_level": owned(tree),
        "definitions": definitions,
        "functions": functions,
        "classes": len(definitions) - functions,
        "flagged_functions": sum(bool(d["flags"]) for d in definitions),
        "imports": imports,
    }


def resolve(modules: list[dict]) -> None:
    paths = {}
    prefixes = set()
    for module in modules:
        paths.setdefault(module["name"], []).append(module["page"])
        components = module["name"].split(".")
        prefixes.update(".".join(components[:n]) for n in range(1, len(components)))
    known = set(paths) | prefixes
    for module in modules:
        for row in module["imports"]:
            parts = module["name"].split(".") if module["package"] else module["name"].split(".")[:-1]
            if row["level"] > len(parts):
                row.update(status="outside_root", target="")
                continue
            base = row["module"]
            if row["level"]:
                parent = parts[: len(parts) - row["level"] + 1]
                base = ".".join(parent + ([base] if base else []))
            target = (base + "." if row["kind"] == "ImportFrom" else "") + row["name"]
            status = "local_module"
            if target not in known and row["kind"] == "ImportFrom" and base in known:
                target = base
                status = "local_wildcard" if row["name"] == "*" else "local_member"
            if target in paths:
                if len(paths[target]) != 1:
                    row.update(status="ambiguous", target=target)
                else:
                    row.update(status=status, target=target, href=paths[target][0])
            elif target in prefixes:
                row.update(status="namespace" if status == "local_module" else status, target=target, href="index.html")
            else:
                status = "missing_local" if row["level"] or target.split(".")[0] in known else "external"
                row.update(status=status, target=target)
    return  # noqa: PLR1711


def expected(files: dict[str, bytes], config: dict) -> dict:
    modules = [
        describe(path, raw, config["package"], config["thresholds"], f"module-{index}.html")
        for index, (path, raw) in enumerate(sorted(files.items()))
    ]
    resolve(modules)
    summary = {"modules": len(modules)}
    for key in ["functions", "classes", "statements", "flagged_functions"]:
        summary[key] = sum(module[key] for module in modules)
    return {
        "version": 1,
        "package": config["package"],
        "thresholds": config["thresholds"],
        "summary": summary,
        "modules": modules,
    }


def archive(files: dict[str, bytes], config: dict) -> dict:
    return {
        "version": 1,
        "package": config["package"],
        "exclude": config["exclude"],
        "thresholds": config["thresholds"],
        "files": [{"path": name, "data": base64.b64encode(raw).decode()} for name, raw in sorted(files.items())],
    }
