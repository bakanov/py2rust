"""Native parsing without code execution; syntax, Unicode and resource-boundary parity."""

# ruff: noqa: PLR1711 - explicit repository returns
import ast
import json
from pathlib import Path

import pytest

from py2rust.stdlib import python_statement_tree
from tools.corpus_checks.common import Application
from tools.generate_python_identifiers import generate

from .test_services import program


def parse_batch(tmp_path: Path, engine: str, sources: list[str]) -> list[dict]:
    (tmp_path / "sources.json").write_text(json.dumps(sources))
    source = """from py2rust.stdlib import Json, json_array, json_dumps, json_loads, json_string, read_text, python_statement_tree
def examine() -> None:
    for item in json_array(json_loads(read_text("sources.json"))):
        try:
            tree: Json = python_statement_tree(json_string(item))
            print(json_dumps({"tree":tree}))
        except Exception as error:
            print(json_dumps({"error":str(error)}))
    return
if __name__ == "__main__":
    examine()
"""
    app = Application(program(tmp_path, source, engine), engine)
    result = app.run(tmp_path, {}, timeout=45)
    assert result.returncode == 0 and not result.stderr, result
    rows = [json.loads(line) for line in result.stdout.splitlines()]
    assert len(rows) == len(sources)
    return rows


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_python_tree_definitions_blocks_and_locations(tmp_path: Path, engine: str) -> None:
    source = """"module doc"
@((decorate("é")))
class Café[T]:
    "class doc"
    @wrap(
       "inner")
    async def go(self, x: T) -> T:
        "function doc"
        try:
            async with context() as c:
                async for item in c:
                    def nested():
                        return item
                else:
                    pass
        except* ValueError:
            import collections.abc as abc
        else:
            from .helpers import value as v
        finally:
            assert True
if True:
    x = 1
elif False:
    x = 2
elif other:
    x = 3
else:
    x = 4
match x:
    case [a, b] if a:
        type Pair[T] = tuple[T, T]
    case _:
        raise ValueError()
"""
    sources = [source, "\ufeff" + source.replace("\n", "\r\n"), source.replace("\n", "\r")]
    rows = parse_batch(tmp_path, engine, sources)
    expected = python_statement_tree(source)
    assert all(row == {"tree": expected} for row in rows)
    nodes = expected["nodes"]
    # Independent stdlib AST source positions and decorator expression extraction.
    tree = ast.parse(source)
    for value in ast.walk(tree):
        if isinstance(value, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            found = next(node for node in nodes if node["line"] == value.lineno and node["name"] == value.name)
            assert (found["column"], found["end_line"], found["end_column"]) == (
                value.col_offset,
                value.end_lineno,
                value.end_col_offset,
            )
            assert [item["text"] for item in found["decorators"]] == [
                ast.get_source_segment(source, item) for item in value.decorator_list
            ]
    assert {node["kind"] for node in nodes} >= {"AsyncFor", "AsyncWith", "TryStar", "Match", "TypeAlias"}
    return


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_python_tree_unicode_strings_and_identifier_tables(tmp_path: Path, engine: str) -> None:
    sources = [
        "'\\N{SNOWMAN}\\N{CJK UNIFIED IDEOGRAPH-2EBF0}'\n",
        "def K(𝒇):\n    return 𝒇\n",
        "def \U0002ebf0(): pass\n",  # Unicode 15.1 CJK Extension I.
        "r'\\ud800'\n",
        "b'\\ud800'\n",
        "'\\\\ud800'\n",
        'rf"literal \\ud800 {1}"\n',
        "f\"{r'\\ud800'}\"\n",
        'f"{1:{2}}"\n',
        "'é' '😀'\n",
        '"\\U0001F600"\n',
    ]
    rows = parse_batch(tmp_path, engine, sources)
    assert rows == [{"tree": python_statement_tree(source)} for source in sources]
    assert rows[1]["tree"]["nodes"][0]["name"] == "K"
    assert (
        Path(__file__)
        .resolve()
        .parents[1]
        .joinpath("py2rust/compiler/service_runtime/src/python_identifiers.rs")
        .read_text()
        == generate()
    )
    return


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_python_tree_rejects_invalid_source_and_recovers(tmp_path: Path, engine: str) -> None:
    sources = [
        "def broken(: pass",
        "if True:\npass",
        "f(x=1,x=2)",
        "def f(x,x): pass",
        "type T[X = int] = X",
        "x = f'\\ud800'",
        "x='\\ud800'",
        "x='\\U0000dfff'",
        "rf\"{'\\ud800'}\"",
        "x='\\N{FACE WITH BAGS UNDER EYES}'",  # Unicode 16 name.
        "def \U00001c89(): pass",  # Unicode 16 identifier; must not float with lexer data.
        "x='\\N{KEYCAP DIGIT ONE}'",
        "x=\0",
        "#" + "x" * 131072,
    ]
    interleaved = [item for source in sources for item in [source, '"recovered"\n']]
    rows = parse_batch(tmp_path, engine, interleaved)
    for index in range(len(sources)):
        assert "error" in rows[2 * index], (sources[index], rows[2 * index])
        assert rows[2 * index + 1]["tree"]["nodes"][0]["string"] == "recovered"
    return


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_python_tree_resource_limits(tmp_path: Path, engine: str) -> None:
    accepted = ["#" + "x" * 131071, "pass\n" * 4096, "x=" + "(" * 128 + "0" + ")" * 128, "x=" + " + ".join(["1"] * 128)]
    rejected = [
        "pass\n" * 4097,
        "x=" + "(" * 129 + "0" + ")" * 129,
        "x=" + " + ".join(["1"] * 129),
        "x=" + "+" * 2000 + "1",
        "x=" + "+".join(["1"] * 8200),
    ]
    accepted.append("".join("    " * i + "if True:\n" for i in range(63)) + "    " * 63 + "pass\n")
    rejected.append("".join("    " * i + "if True:\n" for i in range(64)) + "    " * 64 + "pass\n")
    rows = parse_batch(tmp_path, engine, accepted + rejected + ["pass"])
    assert all("tree" in row for row in rows[: len(accepted)]), rows[: len(accepted)]
    assert all("error" in row and "limit" in row["error"] for row in rows[len(accepted) : -1]), rows[len(accepted) : -1]
    assert rows[-1]["tree"]["nodes"][0]["kind"] == "Pass"
    return
