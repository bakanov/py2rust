"""Generate consolidated Rust GDExtension projects for Godot-hosted Python games."""

from .generator import NATIVE_FILES, GodotGenerationError, GodotProject, generate_project

__all__ = ["NATIVE_FILES", "GodotGenerationError", "GodotProject", "generate_project"]
