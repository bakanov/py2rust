from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from py2rust.compiler.modular import ModuleSource, ModularEmissionError, emit_modules, write_modular_project

HEADER = """#![allow(unused_mut, unused_variables, unused_parens, dead_code, non_camel_case_types, non_snake_case)]
use py2rust_service_runtime as rt;
"""

FLAT = HEADER + """
#[derive(Clone, PartialEq)]
struct py__model__Item {
    name: String,
    value: i64,
}

// Python: @ROOT@/model.py:4
fn py__model__new(name: &str) -> rt::Result<py__model__Item> {
    Ok(py__model__Item { name: name.to_string(), value: 3i64 })
}

// Python: @ROOT@/helpers.py:3
fn py__helpers__describe(item: &py__model__Item) -> rt::Result<String> {
    Ok(format!("{}{}{}", item.name.clone(), ":", item.value))
}

// Python: @ROOT@/main.py:4
fn py__main__main() -> rt::Result<i64> {
    let mut item: py__model__Item = py__model__new("Rome")?;
    println!("{}", py__helpers__describe(&item)?);
    Ok(0i64)
}

fn main() -> rt::Result<()> {
    py__main__main()?;
    Ok(())
}
"""


def sources(root: Path) -> list[ModuleSource]:
    return [
        ModuleSource("main", root / "main.py"),
        ModuleSource("model", root / "model.py"),
        ModuleSource("helpers", root / "helpers.py"),
    ]


def flat(root: Path) -> str:
    return FLAT.replace("@ROOT@", str(root))


def test_emits_real_files_with_qualified_cross_module_references(tmp_path: Path) -> None:
    emission = emit_modules(flat(tmp_path), sources(tmp_path), source_root=tmp_path)
    assert set(emission.files) == {"src/main.rs", "src/entry.rs", "src/model.rs", "src/helpers.rs"}
    model = emission.files["src/model.rs"]
    helpers = emission.files["src/helpers.rs"]
    entry = emission.files["src/entry.rs"]
    main = emission.files["src/main.rs"]
    assert "pub(crate) struct Item" in model
    assert "pub(crate) name: String" in model
    assert "pub(crate) fn new" in model
    assert "// Python: model.py:4" in model
    assert "item: &crate::model::Item" in helpers
    assert "crate::model::new" in entry
    assert "crate::helpers::describe" in entry
    assert "pub(crate) mod entry;" in main
    assert "crate::entry::main()" in main
    assert len(main.splitlines()) < 20
    assert "py__" not in "\n".join(emission.files.values())
    assert emission.symbols["py__model__Item"].file == "src/model.rs"


def test_duplicate_type_names_use_separate_module_namespaces(tmp_path: Path) -> None:
    code = HEADER + """
#[derive(Clone, PartialEq)]
struct py__left__Item { value: i64, }
#[derive(Clone, PartialEq)]
struct py__right__Item { value: i64, }
fn py__main__select(item: &py__left__Item, other: &py__right__Item) -> rt::Result<i64> {
    Ok(item.value + other.value)
}
fn main() -> rt::Result<()> { Ok(()) }
"""
    modules = [
        ModuleSource("main", tmp_path / "main.py"),
        ModuleSource("left", tmp_path / "left.py"),
        ModuleSource("right", tmp_path / "right.py"),
    ]
    emission = emit_modules(code, modules)
    assert "struct Item" in emission.files["src/left.rs"]
    assert "struct Item" in emission.files["src/right.rs"]
    entry = emission.files["src/entry.rs"]
    assert "item: &crate::left::Item" in entry
    assert "other: &crate::right::Item" in entry


def test_recursive_record_storage_stays_with_its_record(tmp_path: Path) -> None:
    code = HEADER + """
#[derive(Clone)]
struct NodeStorage {
    value: i64,
    next: Option<py__model__Node>,
}
impl PartialEq for NodeStorage {
    fn eq(&self, other: &Self) -> bool { self.value == other.value && self.next == other.next }
}
#[derive(Clone, PartialEq)]
struct py__model__Node(std::sync::Arc<NodeStorage>);
impl std::ops::Deref for py__model__Node {
    type Target = NodeStorage;
    fn deref(&self) -> &Self::Target { &self.0 }
}
fn main() -> rt::Result<()> { Ok(()) }
"""
    emission = emit_modules(code, [ModuleSource("model", tmp_path / "model.py")])
    model = emission.files["src/model.rs"]
    assert "pub(crate) struct NodeStorage" in model
    assert "pub(crate) struct Node" in model
    assert "pub(crate) std::sync::Arc<NodeStorage>" in model
    assert "pub(crate) value: i64" in model
    assert "impl PartialEq for NodeStorage" in model
    assert set(emission.files) == {"src/main.rs", "src/model.rs"}


def test_native_module_path_is_relative_to_its_new_rust_file(tmp_path: Path) -> None:
    code = HEADER + """
#[path = "native/bridge/py__bridge__math__module_wrapper.rs"]
mod py__bridge__math__rust_module;
fn py__bridge__math__double() -> rt::Result<i64> {
    Ok(py__bridge__math__rust_module::r#math::double(21))
}
fn main() -> rt::Result<()> { Ok(()) }
"""
    modules = [
        ModuleSource("bridge", tmp_path / "bridge/__init__.py", package=True),
        ModuleSource("bridge.math", tmp_path / "bridge/math.rs"),
    ]
    emission = emit_modules(code, modules)
    module = emission.files["src/bridge/math.rs"]
    assert '#[path = "../native/bridge/py__bridge__math__module_wrapper.rs"]' in module
    assert "pub(crate) mod rust_module;" in module
    assert "rust_module::r#math::double" in module
    assert "pub(crate) mod math;" in emission.files["src/bridge/mod.rs"]


def test_writer_separates_runtime_and_refuses_to_overwrite(tmp_path: Path) -> None:
    output = tmp_path / "generated"
    write_modular_project(flat(tmp_path), sources(tmp_path), output, source_root=tmp_path, format_rust=False)
    assert (output / "runtime/lib.rs").is_file()
    assert not (output / "src/lib.rs").exists()
    assert 'path = "runtime/lib.rs"' in (output / "Cargo.toml").read_text()
    assert (output / ".py2rust-modular.json").is_file()
    with pytest.raises(ModularEmissionError, match="new or empty"):
        write_modular_project(flat(tmp_path), sources(tmp_path), output, source_root=tmp_path)


def test_generated_modules_build_and_run(tmp_path: Path) -> None:
    output = tmp_path / "generated"
    write_modular_project(flat(tmp_path), sources(tmp_path), output, source_root=tmp_path)
    result = subprocess.run(
        ["cargo", "run", "--quiet", "--locked", "--offline", "--manifest-path", str(output / "Cargo.toml")],
        env=dict(os.environ, CARGO_TARGET_DIR=str(tmp_path / "target")),
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "Rome:3\n"
