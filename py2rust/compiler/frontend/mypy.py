"""Consume the analyzed AST and type map that also feed mypyc's IR builder.

Keep upstream objects inside this frontend boundary. The lowering adapter must
validate our subset and translate types into our own IR; accepting a program here
alone is never evidence that it can be compiled to standalone Rust.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mypy.nodes import Expression, MypyFile
    from mypy.types import Type


class FrontendError(ValueError):
    def __init__(self, diagnostics: list[str]) -> None:
        self.diagnostics = tuple(diagnostics)
        self.filename: str | None = None
        self.lineno = 1
        for diagnostic in diagnostics:
            location = re.match(r"^(.*?):(\d+)(?::\d+)?: ", diagnostic)
            if location:
                self.filename = location.group(1)
                self.lineno = int(location.group(2))
                break
        super().__init__("\n".join(diagnostics))


@dataclass(frozen=True)
class TypedModule:
    name: str
    path: str
    tree: MypyFile


@dataclass(frozen=True)
class TypedProgram:
    modules: dict[str, TypedModule]
    expression_types: dict[Expression, Type]
    json_coercions: frozenset[Expression] = frozenset()


def analyze(
    sources: dict[str, tuple[Path, str]],
    *,
    search_paths: tuple[Path, ...] = (),
    stubs: dict[str, tuple[Path, str]] | None = None,
) -> TypedProgram:
    """Analyze explicit module sources without importing or executing application code.

    The module name is supplied by project resolution, not guessed from a temporary
    filename. Exported types retain narrowing at individual expression sites.
    """
    from .compatibility import ensure_frontend

    ensure_frontend()
    from mypy.build import build
    from mypy.errors import CompileError
    from mypy.modulefinder import BuildSource
    from mypy.options import Options

    options = Options()
    options.incremental = False
    # Non-incremental analysis still writes mypy caches unless explicitly disabled.
    options.cache_dir = os.devnull
    options.export_types = True
    options.preserve_asts = True
    options.check_untyped_defs = True
    options.follow_imports = "normal"
    options.mypy_path = [str(path) for path in search_paths]
    from .coercions import SubsetCoercions

    coercions = SubsetCoercions(options, set(sources) if stubs and "py2rust.stdlib" in stubs else set())
    try:
        result = build(
            sources=[
                BuildSource(str(path), name, source) for name, (path, source) in {**(stubs or {}), **sources}.items()
            ],
            options=options,
            extra_plugins=[coercions],
        )
    except CompileError as error:
        raise FrontendError(error.messages) from error
    if result.errors:
        raise FrontendError(result.errors)
    return TypedProgram(
        modules={name: TypedModule(name, str(path), result.files[name]) for name, (path, _) in sources.items()},
        expression_types=dict(result.types),
        json_coercions=frozenset(coercions.inserted),
    )
