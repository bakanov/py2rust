"""Python-shaped generated Rust projects and their source mappings."""

from .emission import EmittedSymbol, ModuleEmission, ModuleSource, ModularEmissionError, emit_modules
from .project import write_modular_project

__all__ = [
    "EmittedSymbol",
    "ModuleEmission",
    "ModuleSource",
    "ModularEmissionError",
    "emit_modules",
    "write_modular_project",
]
