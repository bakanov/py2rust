"""A standalone multi-module caller can catch native boundary failures and keep calling Rust."""

import os
import subprocess
from pathlib import Path

from .test_project import build, sources


def test_native_failures_are_local_across_python_modules(tmp_path: Path) -> None:
    root = sources(
        tmp_path,
        {
            "native.rs": """
pub fn small(n: u8) -> i64 { n as i64 }
pub fn wide() -> u128 { u128::MAX }
pub fn nested() -> (Vec<f64>, (String, f64)) { (vec![1.0], ("x".into(), f64::INFINITY)) }
pub fn rejected() -> Result<i64, String> { Err("adapter rejected".into()) }
pub fn bytes(value: &[u8]) -> Vec<u8> { value.iter().rev().copied().collect() }
""",
            "calls.py": """
from native import small, wide, nested, rejected, bytes

def attempt(kind: str) -> str:
    try:
        if kind == "argument":
            small(256)
        elif kind == "return":
            wide()
        elif kind == "nested":
            nested()
        else:
            rejected()
    except Exception as error:
        assert small(7) == 7
        assert bytes(b"\\x00\\xff") == b"\\xff\\x00"
        return str(error)
    return "unexpected success"
""",
            "main.py": """
from calls import attempt

def main() -> None:
    for kind in ["argument", "return", "nested", "result"]:
        print(kind + ": " + attempt(kind))
    print("continued after every error")
    return

if __name__ == "__main__":
    main()
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
        check=False,
        env=dict(os.environ, PATH="/nonexistent", PYTHONHOME="/nonexistent", PYTHONPATH="/nonexistent"),
    )
    assert result.returncode == 0 and not result.stderr, result.stderr
    assert result.stdout.splitlines() == [
        "argument: out of range integral type conversion attempted",
        "return: out of range integral type conversion attempted",
        "nested: non-finite floating point result",
        "result: adapter rejected",
        "continued after every error",
    ]
    return  # noqa: PLR1711
