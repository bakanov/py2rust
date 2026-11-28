from pathlib import Path

import pytest

from py2rust.godot import NATIVE_FILES, GodotGenerationError, GodotProject, generate_project


def test_generates_ten_consolidated_modules_and_is_idempotent(tmp_path: Path) -> None:
    tmp_path.joinpath("project.godot").write_text("config_version=5\n")
    project = GodotProject(tmp_path)
    generated = generate_project(project)
    native = tmp_path / "native"
    assert sorted(path.name for path in native.glob("*.rs")) == sorted([*NATIVE_FILES, "lib.rs"])
    assert len(generated) == 14
    assert 'crate-type = ["cdylib", "rlib"]' in (native / "Cargo.toml").read_text()
    assert 'godot = { version = "=0.2.4"' in (native / "Cargo.toml").read_text()
    assert "unsafe impl ExtensionLibrary" in (native / "lib.rs").read_text()
    assert "PythonGame" in (tmp_path / "native-modules.toml").read_text()
    generate_project(project, check=True)


def test_check_reports_differences_without_rewriting(tmp_path: Path) -> None:
    tmp_path.joinpath("project.godot").write_text("config_version=5\n")
    project = GodotProject(tmp_path)
    generate_project(project)
    modified = tmp_path / "native" / "game_node.rs"
    modified.write_text("changed\n")
    with pytest.raises(GodotGenerationError, match="game_node.rs"):
        generate_project(project, check=True)
    assert modified.read_text() == "changed\n"


def test_requires_a_godot_project(tmp_path: Path) -> None:
    with pytest.raises(GodotGenerationError, match="Not a Godot project"):
        generate_project(GodotProject(tmp_path))
