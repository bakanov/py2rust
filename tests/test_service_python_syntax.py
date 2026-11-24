"""Native compiler syntax exchange matches the Python reference on selected sources."""

import json
from pathlib import Path

from py2rust.stdlib import python_syntax_tree
from tools.corpus_checks.common import Application

from .test_services import program


def test_compiler_syntax_exchange(tmp_path: Path) -> None:
    samples = [
        "from typing import Any as Value\nfrom . import thing\ndef twice(x: int) -> int:\n    return x * 2\n",
        "x: list[int] = [1, 2]\nfor item in x[1:]:\n    if item > 0:\n        print(item)\n    elif item == 0:\n        break\n    else:\n        continue\n",
        'value = {"世界": b"abc", "flag": True, "none": None}\nassert 1 < 2 <= 3 and not False\nx = foo(1, key="é").name\n',
        '@dataclass\nclass Item:\n    name: str = ""\n\ndef use(x: Item) -> str:\n    return x.name if True else ""\n',
        "def f(x: int = 3) -> int:\n    x += 1\n    while x > 0:\n        x = x - 1\n    return x\n",
    ]
    compiler = Path(__file__).resolve().parents[1] / "py2rust/compiler"
    for relative in ["native/emitter.py", "native/ir_schema.py", "rules/numeric.py"]:
        samples.append((compiler / relative).read_text())
    samples.append("@decorator\ndef\tf(x: int) -> int:\n    return x\n")
    (tmp_path / "sources.json").write_text(json.dumps(samples))
    driver = """from py2rust.stdlib import json_array, json_loads, json_string, json_dumps, read_text, python_syntax_tree

def run() -> None:
    for source in json_array(json_loads(read_text("sources.json"))):
        print(json_dumps(python_syntax_tree(json_string(source))))

if __name__ == "__main__":
    run()
"""
    app = Application(program(tmp_path, driver, "rust"), "rust")
    result = app.run(tmp_path, {}, timeout=45)
    assert result.returncode == 0, result.stderr
    assert [json.loads(line) for line in result.stdout.splitlines()] == [python_syntax_tree(s) for s in samples]
    return  # noqa: PLR1711 - explicit repository return


def test_compiler_syntax_rejects_unsupported_and_invalid_input(tmp_path: Path) -> None:
    samples = ["value = lambda: 1\n", "async def f() -> None:\n    pass\n", "x = (\n", "x = '\\ud800'\n"]
    (tmp_path / "sources.json").write_text(json.dumps(samples))
    driver = """from py2rust.stdlib import json_array, json_loads, json_string, read_text, python_syntax_tree

def run() -> None:
    for source in json_array(json_loads(read_text("sources.json"))):
        try:
            python_syntax_tree(json_string(source))
            print("unexpected success")
        except Exception as error:
            print(str(error))

if __name__ == "__main__":
    run()
"""
    app = Application(program(tmp_path, driver, "rust"), "rust")
    result = app.run(tmp_path, {}, timeout=45)
    assert result.returncode == 0, result.stderr
    messages = result.stdout.splitlines()
    assert len(messages) == len(samples)
    assert messages[0] == "unsupported compiler syntax at 1:8"
    assert messages[1] == "unsupported compiler syntax at 1:0"
    assert "python syntax error" in messages[2]
    assert "Unicode scalar values" in messages[3]
    return  # noqa: PLR1711 - explicit repository return
