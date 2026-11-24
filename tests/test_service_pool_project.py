"""A process-pool handle crosses ordinary Python module imports in a complete native project."""

import os
import subprocess
from pathlib import Path

from .test_project import build, sources


def test_project_process_pool_annotation_and_scoped_lifetime(tmp_path: Path) -> None:
    root = sources(
        tmp_path,
        {
            "child.py": """from py2rust.stdlib import ProcessPool, Json, process_spawn, process_poll, json_bool, json_int, sleep

def run(pool: ProcessPool) -> bytes:
    identifier: int = process_spawn(pool, ["/usr/bin/printf", "module import"], {}, "/")
    output: bytes = b""
    for index in range(1000):
        result: tuple[Json, bytes, bytes] = process_poll(pool, identifier, 5)
        output = output + result[1]
        if json_bool(result[0]["complete"]):
            assert json_int(result[0]["returncode"]) == 0
            return output
        sleep(0.001)
    assert False, "child deadline"
    return b""
""",
            "main.py": """from child import run
from py2rust.stdlib import process_pool

def main() -> None:
    with process_pool() as pool:
        assert run(pool) == b"module import"
    print("project pool passed")
    return
if __name__ == "__main__":
    main()
""",
        },
    )
    binary = build(root, tmp_path / "rust")
    result = subprocess.run(
        [str(binary)],
        cwd=root,
        env=dict(os.environ, PATH="/nonexistent", PYTHONHOME="/nonexistent", PYTHONPATH="/nonexistent"),
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0 and result.stdout == "project pool passed\n" and not result.stderr
    return  # noqa: PLR1711 - explicit repository returns
