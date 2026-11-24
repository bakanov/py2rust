"""Module-scope declarations and uses must share resolved symbol identities."""

from pathlib import Path

from py2rust.compiler.pipeline import compile_typed
from py2rust.compiler.service import ServiceCompiler

from .test_services import parity


def test_main_guard_bindings_and_resources(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        ServiceCompiler, "compile", lambda self, source: compile_typed({"main": (tmp_path / "main.py", source)})
    )
    source = """from py2rust.stdlib import Json, json_kind, file_open, file_write, file_read

if __name__ == "__main__":
    value: Json = {"message": "hello"}
    print(json_kind(value))
    with file_open("guard-data.bin", "w+b") as output:
        file_write(output, b"saved")
    with file_open("guard-data.bin", "rb") as input_file:
        print(file_read(input_file, 5).decode("utf-8"))
    for index in range(3):
        print(index)
    try:
        assert False, "guard error"
    except Exception as error:
        print(str(error))
"""
    assert parity(tmp_path, source) == "object\nsaved\n0\n1\n2\nguard error\n"
    assert (tmp_path / "guard-data.bin").read_bytes() == b"saved"


def test_entry_statements_preserve_order_and_bindings(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        ServiceCompiler, "compile", lambda self, source: compile_typed({"main": (tmp_path / "main.py", source)})
    )
    source = """LIMIT: int = 4

def limit() -> int:
    return LIMIT

value = limit()
print(value)
if __name__ == "__main__":
    value = value + 1
    print(value)
value = value + 1
print(value)
"""
    assert parity(tmp_path, source) == "4\n5\n6\n"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def test_local_library_constants_and_intrinsics_keep_project_meaning(tmp_path: Path) -> None:
    from .test_project import run_project, sources

    root = sources(
        tmp_path,
        {
            "main.py": "import logging\nfrom logging import INFO\nimport heapq\nprint(logging.INFO)\nprint(INFO)\nprint(heapq.heappop(2))\n",
            "logging.py": "INFO: int = 777\n",
            "heapq.py": "def heappop(value: int) -> int:\n    return value + 40\n",
        },
    )
    result = run_project(root, tmp_path / "rust")
    assert result.returncode == 0, result.stderr
    assert result.stdout == "777\n777\n42\n"
    return  # noqa: PLR1711 - explicit return required by repository guidelines
