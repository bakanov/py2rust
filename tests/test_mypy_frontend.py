"""The frontend must provide actual inferred types, not just a successful check."""

from pathlib import Path

import pytest

from py2rust.compiler.frontend import FrontendError, analyze


def test_frontend_preserves_narrowed_expression_types(tmp_path: Path) -> None:
    from mypy.nodes import NameExpr
    from mypy.types import Instance

    source = "def size(value: str | None) -> int:\n    if value is None:\n        return 0\n    return len(value)\n"
    program = analyze({"main": (tmp_path / "main.py", source)})
    uses = [
        typ
        for expression, typ in program.expression_types.items()
        if isinstance(expression, NameExpr) and expression.name == "value" and expression.line == 4
    ]
    assert len(uses) == 1
    assert isinstance(uses[0], Instance)
    assert uses[0].type.fullname == "builtins.str"
    assert program.modules["main"].tree.defs


def test_frontend_resolves_cross_module_alias(tmp_path: Path) -> None:
    from mypy.nodes import CallExpr
    from mypy.types import Instance

    program = analyze(
        {
            "helper": (tmp_path / "helper.py", "def size(value: str) -> int:\n    return len(value)\n"),
            "main": (tmp_path / "main.py", 'from helper import size as measure\nanswer = measure("abc")\n'),
        }
    )
    calls = [typ for expression, typ in program.expression_types.items() if isinstance(expression, CallExpr)]
    assert any(isinstance(typ, Instance) and typ.type.fullname == "builtins.int" for typ in calls)
    assert set(program.modules) == {"main", "helper"}


def test_frontend_rejects_invalid_return(tmp_path: Path) -> None:
    with pytest.raises(FrontendError, match="Incompatible return value type"):
        analyze({"main": (tmp_path / "main.py", 'def size() -> int:\n    return "wrong"\n')})


def test_ir_uses_inferred_local_types_and_resolved_calls(tmp_path: Path) -> None:
    from py2rust.compiler.frontend.lowering import lower
    from py2rust.compiler.ir import ValueType

    program = analyze(
        {"main": (tmp_path / "main.py", "def size(text: str) -> int:\n    count = len(text)\n    return count + 1\n")}
    )
    function = lower(program)[0].functions[0]
    assert function.name == "main.size"
    assignment, returned = function.body
    call = assignment.expressions[0]
    assert call.operation == "call" and call.value == "builtins.len"
    assert call.type == ValueType("builtins.int")
    assert call.source.line == 2
    assert returned.expressions[0].operation == "binary"
    assert returned.expressions[0].operands[0].type == ValueType("builtins.int")


def test_ir_rejects_dynamic_types(tmp_path: Path) -> None:
    from py2rust.compiler.frontend.lowering import lower

    program = analyze(
        {"main": (tmp_path / "main.py", "from typing import Any\ndef identity(value: Any) -> Any:\n    return value\n")}
    )
    with pytest.raises(FrontendError, match="concrete supported type"):
        lower(program)


def test_ir_preserves_loops_and_lazy_comparison_structure(tmp_path: Path) -> None:
    from py2rust.compiler.frontend.lowering import lower
    from py2rust.compiler.ir import ValueType

    source = """def scan(values: list[int], threshold: int) -> int:
    result = 0
    for value in values:
        if 0 < value < threshold and value != 2:
            result = result + value
        else:
            continue
    while result > 10:
        result = result - 1
        if result == 12:
            break
    return result
"""
    function = lower(analyze({"main": (tmp_path / "main.py", source)}))[0].functions[0]
    loop = function.body[1]
    assert loop.operation == "for"
    assert loop.target == "value" and loop.target_type == ValueType("builtins.int")
    condition = loop.blocks[0][0].expressions[0]
    assert condition.operation == "short_circuit"
    chain = condition.operands[0]
    assert chain.operation == "compare_chain" and chain.operators == ("<", "<")
    assert len(chain.operands) == 3
    assert function.body[2].operation == "while"


def test_ir_preserves_collection_element_types(tmp_path: Path) -> None:
    from py2rust.compiler.frontend.lowering import lower
    from py2rust.compiler.ir import ValueType

    source = """def sample() -> int:
    values = [1, 2, 3]
    mapping = {"first": values[0]}
    return mapping["first"]
"""
    function = lower(analyze({"main": (tmp_path / "main.py", source)}))[0].functions[0]
    values = function.body[0].expressions[0]
    assert values.type == ValueType("builtins.list", (ValueType("builtins.int"),))
    mapping = function.body[1].expressions[0]
    assert mapping.type == ValueType("builtins.dict", (ValueType("builtins.str"), ValueType("builtins.int")))
    assert [item.operation for item in mapping.operands] == ["literal", "index"]


def test_ir_keeps_exception_regions_and_module_entry(tmp_path: Path) -> None:
    from py2rust.compiler.frontend.lowering import lower

    source = """def choose(value: int) -> int:
    try:
        assert value > 0, "positive required"
        return value
    except Exception as error:
        raise
    finally:
        value = 0

if __name__ == "__main__":
    choose(1)
"""
    module = lower(analyze({"main": (tmp_path / "main.py", source)}))[0]
    protected = module.functions[0].body[0]
    assert protected.operation == "try"
    assert protected.blocks[0][-1].operation == "return"
    assert protected.blocks[1] == ()
    assert protected.blocks[2][0].operation == "assign"
    handler = protected.handlers[0]
    assert handler.exception == "builtins.Exception" and handler.binding == "error"
    assert handler.body[0].operation == "reraise"
    assert module.body[0].operation == "if"
    assert module.body[0].blocks[0][0].expressions[0].value == "main.choose"


def test_ir_rejects_async_instead_of_treating_it_as_synchronous(tmp_path: Path) -> None:
    from py2rust.compiler.frontend.lowering import lower

    program = analyze({"main": (tmp_path / "main.py", "async def answer() -> int:\n    return 42\n")})
    with pytest.raises(FrontendError, match="async and generator functions"):
        lower(program)


def test_ir_preserves_all_byte_literal_values(tmp_path: Path) -> None:
    from py2rust.compiler.frontend.lowering import lower

    payload = bytes(range(256))
    source = f"def payload() -> bytes:\n    return {payload!r}\n"
    module = lower(analyze({"main": (tmp_path / "main.py", source)}))[0]
    assert module.functions[0].body[0].expressions[0].value == payload


def test_ir_does_not_skip_user_defined_dataclass_methods(tmp_path: Path) -> None:
    from py2rust.compiler.frontend.lowering import lower

    source = """from dataclasses import dataclass
@dataclass
class Item:
    count: int
    def size(self) -> int:
        return self.count
"""
    program = analyze({"main": (tmp_path / "main.py", source)})
    with pytest.raises(FrontendError, match="annotated fields only"):
        lower(program)


def test_json_index_retains_nominal_type(tmp_path: Path) -> None:
    from py2rust.compiler.frontend.lowering import lower
    from py2rust.compiler.ir import ValueType
    from py2rust.compiler.libraries.stubs import sources

    source = """from py2rust.stdlib import Json

def field(document: Json) -> Json:
    return document["name"]
"""
    program = analyze({"main": (tmp_path / "main.py", source)}, stubs=sources(tmp_path / "stubs"))
    result = lower(program)[0].functions[0].body[0].expressions[0]
    assert result.operation == "json_coerce"
    assert result.operands[0].operation == "index"
    assert result.operands[0].type == ValueType("py2rust.stdlib.Json")
    assert result.type == ValueType("py2rust.stdlib.Json")


def test_json_index_rejects_float_keys(tmp_path: Path) -> None:
    from py2rust.compiler.libraries.stubs import sources

    source = """from py2rust.stdlib import Json

def field(document: Json) -> Json:
    return document[1.5]
"""
    with pytest.raises(FrontendError, match="Invalid index type"):
        analyze({"main": (tmp_path / "main.py", source)}, stubs=sources(tmp_path / "stubs"))


def test_json_assignment_is_an_explicit_typed_coercion(tmp_path: Path) -> None:
    from py2rust.compiler.frontend.lowering import lower
    from py2rust.compiler.libraries.stubs import sources

    source = """from py2rust.stdlib import Json as Document

def build() -> Document:
    result: Document = {"name": "saved", "count": 3}
    return result
"""
    program = analyze({"main": (tmp_path / "main.py", source)}, stubs=sources(tmp_path / "stubs"))
    value = lower(program)[0].functions[0].body[0].expressions[0]
    assert value.operation == "json_coerce"
    assert value.type.name == "py2rust.stdlib.Json"
    assert value.source.line == 4
    assert value.operands[0].operation == "json_object"
    assert [item.type.name for item in value.operands[0].operands] == [
        "builtins.str",
        "builtins.str",
        "builtins.str",
        "builtins.int",
    ]


def test_json_coercion_does_not_hide_unrelated_type_errors(tmp_path: Path) -> None:
    from py2rust.compiler.libraries.stubs import sources

    source = """from py2rust.stdlib import Json

def build() -> Json:
    wrong: int = "not an integer"
    result: Json = {"count": wrong}
    return result
"""
    with pytest.raises(FrontendError, match="Incompatible types in assignment"):
        analyze({"main": (tmp_path / "main.py", source)}, stubs=sources(tmp_path / "stubs"))


def test_json_null_normalization_preserves_optional_narrowing(tmp_path: Path) -> None:
    from mypy.nodes import NameExpr
    from mypy.types import Instance

    from py2rust.compiler.libraries.stubs import sources

    source = """from py2rust.stdlib import Json

def size(text: str | None) -> int:
    if text is None:
        return 0
    return len(text)
"""
    program = analyze({"main": (tmp_path / "main.py", source)}, stubs=sources(tmp_path / "stubs"))
    assert not program.json_coercions
    uses = [
        typ
        for node, typ in program.expression_types.items()
        if isinstance(node, NameExpr) and node.name == "text" and node.line == 6
    ]
    assert len(uses) == 1 and isinstance(uses[0], Instance)
    assert uses[0].type.fullname == "builtins.str"


def test_json_field_hook_preserves_optional_field_narrowing(tmp_path: Path) -> None:
    from mypy.nodes import MemberExpr
    from mypy.types import Instance

    from py2rust.compiler.libraries.stubs import sources

    source = """from dataclasses import dataclass
from py2rust.stdlib import Json
@dataclass
class Item:
    value: str | None

def size(item: Item) -> int:
    if item.value is None:
        return 0
    return len(item.value)
"""
    program = analyze({"main": (tmp_path / "main.py", source)}, stubs=sources(tmp_path / "stubs"))
    assert not program.json_coercions
    uses = [
        typ
        for node, typ in program.expression_types.items()
        if isinstance(node, MemberExpr) and node.name == "value" and node.line == 10
    ]
    assert len(uses) == 1 and isinstance(uses[0], Instance)
    assert uses[0].type.fullname == "builtins.str"


def test_frontend_does_not_write_cache_into_working_directory(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    source = "def answer() -> int:\n    return 42\n"
    program = analyze({"main": (tmp_path / "main.py", source)})
    assert "main" in program.modules
    assert not (tmp_path / ".mypy_cache").exists()
    return
