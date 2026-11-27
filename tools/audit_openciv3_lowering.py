"""Report independently lowered OpenCiv3 modules without building Rust."""

from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from mypy import nodes as n

from py2rust.compiler.frontend.lowering import Lowering, user_class_method
from py2rust.compiler.frontend.mypy import analyze
from py2rust.compiler.libraries.stubs import sources as library_stubs
from py2rust.compiler.project import Project

ROOT = Path(
    os.environ.get("OPENCIV3_ROOT", str(Path.home() / "experimental/OpenCiv3-Development/OpenCiv3-Development/C7"))
)
ENTRY = os.environ.get("OPENCIV3_ENTRY", "civ3_console/standalone.py")


def main() -> None:
    project = Project(ROOT, ENTRY)
    project.load(Path(ENTRY).with_suffix("").as_posix().replace("/", "."))
    sources = {
        name: (module.path, "" if module.package and not module.path.exists() else module.path.read_text())
        for name, module in project.modules.items()
        if module.tree is not None
    }
    with TemporaryDirectory() as directory:
        program = analyze(sources, stubs=library_stubs(Path(directory)), search_paths=(ROOT,), python_scope=True)
    passed = []
    failed = []
    for name, module in program.modules.items():
        adapter = Lowering(program, module, python_scope=True)
        try:
            for node in module.tree.defs:
                if isinstance(node, n.ExpressionStmt) and isinstance(node.expr, n.StrExpr):
                    continue
                if isinstance(node, (n.Import, n.ImportFrom, n.ImportAll, n.TypeAliasStmt)):
                    continue
                if isinstance(node, n.ClassDef):
                    if node.info.is_enum:
                        if node.fullname not in adapter.int_flags:
                            adapter.enum(node)
                        for member in node.defs.body:
                            method = user_class_method(node, member)
                            if method is not None:
                                adapter.function(method)
                    else:
                        adapter.record(node)
                        if not node.info.is_protocol:
                            for member in node.defs.body:
                                method = user_class_method(node, member)
                                if method is not None:
                                    adapter.function(method)
                elif isinstance(node, n.FuncDef):
                    if node.name != "__getattr__":
                        adapter.function(node)
                else:
                    adapter.statement(node)
            passed.append(name)
        except Exception as error:
            failed.append({"module": name, "error": str(error).split("\n")[0]})
    report = {
        "entry": ENTRY,
        "total": len(passed) + len(failed),
        "passed": len(passed),
        "blockers": len(failed),
        "failed": failed,
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
