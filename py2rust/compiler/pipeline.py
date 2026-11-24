"""Typed frontend pipeline, under migration before replacing CLI compilation."""

from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

from .backend.legacy_adapter import linked_tree
from .backend.legacy_adapter import name as rust_symbol
from .effect_policy import EffectPlan
from .effect_policy import analyze as effect_plan
from .efficiency_policy import EfficiencyPlan
from .efficiency_policy import analyze as efficiency_plan
from .exception_policy import ExceptionPlan, ExceptionPolicyError
from .exception_policy import analyze as exception_plan
from .frontend import FrontendError, analyze
from .frontend.native import declarations
from .libraries import STANDARD
from .libraries.stubs import sources as library_stubs
from .memory_oracle import MemoryPlan
from .memory_oracle import analyze as memory_plan
from .readability import ReadabilityPlan
from .readability import analyze as readability_plan
from .rust_imports import symbol_name
from .rust_text import quote
from .service import ServiceCompiler, ServiceError

if TYPE_CHECKING:
    from .ir import Module
    from .project import Project
    from .rust_imports import NativeFunction


@dataclass(frozen=True)
class PreparedProgram:
    """Compiler-owned typed input and policy decisions, without mypy objects."""

    modules: tuple[Module, ...]
    entry: str
    memory: MemoryPlan
    exceptions: ExceptionPlan
    readability: ReadabilityPlan
    efficiency: EfficiencyPlan
    effects: EffectPlan
    native_sources: tuple[tuple[str, Path], ...]
    native_functions: tuple[NativeFunction, ...]


def prepare_typed(
    sources: dict[str, tuple[Path, str]],
    *,
    entry: str = "main",
    native_sources: dict[str, Path] | None = None,
) -> PreparedProgram:
    """Resolve and type-check Python, lower to IR, then compute memory policy."""
    with TemporaryDirectory(prefix="py2rust-stubs-") as directory:
        stubs = library_stubs(Path(directory))
        native_sources = native_sources or {}
        # Local project modules take precedence over standard-library fallbacks.
        # Explicit runtime and third-party contracts remain reserved.
        standard_modules = {name.rsplit(".", 1)[0] for name in STANDARD}
        local_modules = sources.keys() | native_sources.keys()
        collisions = local_modules & (stubs.keys() - standard_modules)
        if collisions:
            raise FrontendError(["project modules shadow reserved runtime contracts: " + ", ".join(sorted(collisions))])
        if native_sources.keys() & sources.keys():
            raise FrontendError(["native modules conflict with Python modules"])
        for name in local_modules & standard_modules:
            stubs.pop(name, None)
        native_stubs, native_functions = declarations(native_sources, Path(directory))
        stubs.update(native_stubs)
        program = analyze(sources, stubs=stubs)
    from .frontend.lowering import lower

    modules = lower(program, native_functions=frozenset(native_functions))
    memory = memory_plan(modules)
    return PreparedProgram(
        modules,
        entry,
        memory,
        exception_plan(modules),
        readability_plan(modules, entry=entry),
        efficiency_plan(modules, frozenset(expr for expr, proof in memory.evaluations if proof.stable)),
        effect_plan(modules),
        tuple(native_sources.items()),
        tuple(native_functions.values()),
    )


@dataclass(frozen=True)
class RustEmission:
    code: str
    optimization_report: dict


def emit_program(
    program: PreparedProgram, *, native_module_paths: dict[str, str] | None = None, explain: bool = False
) -> RustEmission:
    """Render prepared IR and optionally collect the decisions used by emission."""
    native_sources = dict(program.native_sources)
    if native_module_paths is not None and native_module_paths.keys() != native_sources.keys():
        raise FrontendError(["packaged native module paths must match discovered native modules"])
    tree = linked_tree(
        program.modules,
        program.entry,
        nonmutating_calls=program.memory.nonmutating_functions,
        exception_facts=program.exceptions.facts(),
        tail_returns=program.readability.tail_returns,
        evaluation_facts=program.memory.evaluation_facts(),
        parameter_plans=program.memory.parameters,
        liveness=program.memory.liveness,
        move_safety=program.memory.move_safety,
        view_plans=program.memory.views,
        efficiency_plans=program.efficiency.functions,
        append_facts=dict(program.efficiency.appends),
        effect_plan=program.effects,
        iteration_facts=dict(program.memory.iterations),
        binding_plans=program.readability.bindings,
        entry_bindings=program.readability.entry_bindings,
    )
    compiler = ServiceCompiler({function.binding: function.signature for function in program.native_functions})
    compiler.collect_costs = explain
    code = compiler.compile_tree(tree)
    for module, path in native_sources.items():
        if native_module_paths is not None:
            code += f"\n#[path = {quote(native_module_paths[module])}] mod {symbol_name(module, 'rust_module')};\n"
            continue
        code += (
            f"\nmod {symbol_name(module, 'rust_module')} {{\n"
            f"#[path = {quote(str(path.resolve()))}] pub mod r#{path.stem};\n}}\n"
        )
    code += "\n".join(function.wrapper() for function in program.native_functions)
    report = compiler.optimization_report
    if explain:
        decisions = {rust_symbol(item.function): asdict(item) for item in program.memory.functions}
        for row in report["functions"]:
            row["memory_oracle"] = decisions.get(row["symbol"])
        report["frontend"] = "typed"
        report["coverage"]["memory_oracle"] = (
            "conservative IR nonmutation proofs; rejection is not proof of mutation; "
            "does not establish alias, escape or ownership-transfer contracts"
        )
    return RustEmission(code, report)


def emit_rust(program: PreparedProgram, *, native_module_paths: dict[str, str] | None = None) -> str:
    """Render prepared compiler IR without reading or analyzing Python source."""
    return emit_program(program, native_module_paths=native_module_paths).code


def compile_typed(
    sources: dict[str, tuple[Path, str]],
    *,
    entry: str = "main",
    native_sources: dict[str, Path] | None = None,
    native_module_paths: dict[str, str] | None = None,
) -> str:
    """Compile through the typed preparation and Rust emission stages."""
    program = prepare_typed(sources, entry=entry, native_sources=native_sources)
    return emit_rust(program, native_module_paths=native_module_paths)


def compile_project(root: Path, *, entry: str = "main.py") -> str:
    """Discover a whole mixed-language project before using the typed pipeline."""
    from .project import Project

    return compile_loaded_project(Project(root, entry))


def compile_loaded_project(project: Project, *, packaged: bool = False, explain: bool = False) -> str:
    """Use the shared discovery and packaging inventory without legacy emission."""
    from .rust_imports import ProjectError

    parts = list(project.entry.relative_to(project.root).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    if not parts:
        raise ProjectError("root __init__.py cannot be the entry point", project.entry)
    module_name = ".".join(parts)
    project.load(module_name)
    sources = {
        name: (
            module.path,
            ("" if module.package and not module.path.exists() else module.path.read_text()),
        )
        for name, module in project.modules.items()
        if module.tree is not None
    }
    natives = {name: module.path for name, module in project.modules.items() if module.tree is None}
    paths = None
    if packaged:
        paths = {
            name: "native/"
            + (path.relative_to(project.root).parent / (symbol_name(name, "module_wrapper") + ".rs")).as_posix()
            for name, path in natives.items()
        }
    try:
        prepared = prepare_typed(sources, entry=module_name, native_sources=natives)
    except (FrontendError, ExceptionPolicyError) as error:
        if error.filename is None:
            raise
        location = ast.Pass(lineno=error.lineno, col_offset=0)
        location.source_path = error.filename
        raise ServiceError(str(error), location) from error
    emitted = emit_program(prepared, native_module_paths=paths, explain=explain)
    project.optimization_report = emitted.optimization_report
    return emitted.code
