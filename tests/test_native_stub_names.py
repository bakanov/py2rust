"""Native export names cannot shadow types or private typing-stub imports."""

import os
import subprocess
from pathlib import Path

from .test_project import build, sources


def test_native_type_names_and_private_aliases(tmp_path: Path) -> None:
    root = sources(
        tmp_path,
        {
            "native.rs": """pub fn bytes(value: &[u8]) -> Vec<u8> { value.to_vec() }
pub fn str(value: &str) -> String { value.to_owned() }
pub fn int(value: i64) -> i64 { value + 1 }
pub fn list(value: Vec<i64>) -> Vec<i64> { value }
pub fn Json(value: serde_json::Value) -> serde_json::Value { value }
pub fn _py2rust_builtins() -> i64 { 4 }
pub fn _py2rust_builtins_() -> i64 { 5 }
pub fn _py2rust_json() -> i64 { 6 }
""",
            "main.py": """import native
from py2rust.stdlib import Json, json_int

def check() -> None:
    assert native.bytes(b"abc") == b"abc"
    assert native.str("héllo") == "héllo"
    assert native.int(2) == 3
    assert native.list([1, 2]) == [1, 2]
    value: Json = 7
    assert json_int(native.Json(value)) == 7
    assert native._py2rust_builtins() == 4
    assert native._py2rust_builtins_() == 5
    assert native._py2rust_json() == 6
    print("native type names passed")

if __name__ == "__main__":
    check()
""",
        },
    )
    binary = build(root, tmp_path / "rust")
    result = subprocess.run(
        [str(binary)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=10,
        env=dict(os.environ, PATH="/nonexistent", PYTHONHOME="/nonexistent", PYTHONPATH="/nonexistent"),
        check=False,
    )
    assert result.returncode == 0 and not result.stderr, result.stderr
    assert result.stdout == "native type names passed\n"
    return  # noqa: PLR1711
