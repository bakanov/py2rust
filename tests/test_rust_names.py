"""Exported names preserve linking and avoid Rust scope capture."""

import json

import pytest

from py2rust.compiler.project import MARKER, create_project
from py2rust.compiler.rust_names import readable_names
from .test_project import run_project, sources


def test_identifier_renaming_does_not_change_literals_or_capture_locals():
    source = """fn py__left__find() { let find = 1; let left_find = 2;
        println!("py__left__find"); }
// py__left__find
fn py__right__type() {}
"""
    code, names = readable_names(source, {"py__left__find": "find", "py__right__type": "type"})
    assert names == {"py__left__find": "left_find_2", "py__right__type": "right_type"}
    assert 'println!("py__left__find")' in code
    assert "// py__left__find" in code
    assert "fn left_find_2()" in code
    assert readable_names(source, {"py__right__type": "type", "py__left__find": "find"}) == (code, names)


@pytest.mark.parametrize("frontend", ["typed", "legacy"])
def test_exported_record_and_entry_names(tmp_path, frontend):
    root = sources(
        tmp_path,
        {
            "main.py": """from dataclasses import dataclass
@dataclass
class Summary:
    count: int

def main() -> None:
    value: Summary = Summary(3)
    print(value.count)
    return
if __name__ == "__main__":
    main()
""",
        },
    )
    create_project(root, tmp_path / "rust", frontend=frontend)
    code = (tmp_path / "rust/src/entry.rs").read_text()
    assert "struct Summary" in code
    assert "fn main(" in code
    metadata = json.loads((tmp_path / "rust" / MARKER).read_text())
    assert metadata["symbols"]["crate::entry::Summary"]["name"] == "Summary"
    assert metadata["symbols"]["crate::entry::Summary"]["rust"] == "src/entry.rs"
    assert metadata["symbols"]["crate::entry::main"]["name"] == "main"


def test_colliding_python_and_native_exports_execute(tmp_path):
    root = sources(
        tmp_path,
        {
            "left.py": "def value() -> int:\n    return 10\n",
            "right.rs": "pub fn value() -> i64 { 20 }\n",
            "main.py": """from left import value as first
from right import value as second

def main() -> None:
    left_value: int = 5
    assert first() + second() + left_value == 35
    print("py__left__value")
    return
if __name__ == "__main__":
    main()
""",
        },
    )
    result = run_project(root, tmp_path / "rust")
    assert result.returncode == 0, result.stderr
    assert result.stdout == "py__left__value\n"
    assert "pub(crate) fn value(" in (tmp_path / "rust/src/left.rs").read_text()
    assert "pub(crate) fn value(" in (tmp_path / "rust/src/right.rs").read_text()
    code = (tmp_path / "rust/src/entry.rs").read_text()
    assert "crate::left::value()" in code
    assert "crate::right::value()" in code
