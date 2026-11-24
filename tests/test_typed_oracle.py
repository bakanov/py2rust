"""Typed memory proofs must preserve evaluation and explain conservative copies."""

from pathlib import Path

from py2rust.compiler.pipeline import compile_typed
from py2rust.compiler.service import ServiceCompiler

from .test_services import parity

SOURCE = """from py2rust.stdlib import Json, json_get, json_string

def fallback() -> Json:
    return None

def select(document: Json) -> Json:
    return json_get(document, "selected", fallback())

def run() -> None:
    document: Json = {"selected": "small", "payload": [1, 2, 3]}
    print(json_string(select(document)))

if __name__ == "__main__":
    run()
"""


def test_oracle_borrows_across_proven_calls(tmp_path: Path) -> None:
    code = compile_typed({"main": (tmp_path / "main.py", SOURCE)})
    assert 'rt::json_get(document, "selected", &(py__main__fallback()?))' in code
    transitive = SOURCE.replace(
        "def fallback() -> Json:\n    return None",
        "def fallback() -> Json:\n    return leaf()\n\ndef leaf() -> Json:\n    return None",
    )
    assert "rt::json_get(document," in compile_typed({"main": (tmp_path / "main.py", transitive)})


def test_oracle_retains_unknown_argument_effects(tmp_path: Path) -> None:
    mutating = SOURCE.replace(
        "def fallback() -> Json:\n    return None",
        "def fallback() -> Json:\n    values: list[int] = [1]\n    values.pop()\n    return None",
    )
    assert "rt::json_get(&((*document).clone())" in compile_typed({"main": (tmp_path / "main.py", mutating)})
    nested = (
        SOURCE.replace("def fallback() -> Json:", "def fallback(value: int) -> Json:")
        .replace("return json_get(document,", "values: list[int] = [1]\n    return json_get(document,")
        .replace("fallback())", "fallback(values.pop()))")
    )
    assert "rt::json_get(&((*document).clone())" in compile_typed({"main": (tmp_path / "main.py", nested)})


def test_oracle_preserves_eager_fallbacks_and_errors(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        ServiceCompiler, "compile", lambda self, source: compile_typed({"main": (tmp_path / "main.py", source)})
    )
    source = SOURCE.replace(
        "def run() -> None:",
        """def failing() -> Json:
    assert False, "fallback failed"
    return None

def noisy() -> Json:
    print("fallback evaluated")
    return None

def run() -> None:""",
    ).replace(
        "    print(json_string(select(document)))",
        """    print(json_string(select(document)))
    print(json_string(json_get(document, "selected", noisy())))
    try:
        json_get(document, "selected", failing())
    except Exception as error:
        print(str(error))
    print(json_string(document["selected"]))""",
    )
    assert parity(tmp_path, source) == "small\nfallback evaluated\nsmall\nfallback failed\nsmall\n"


def test_oracle_reports_nested_blocker_location() -> None:
    from py2rust.compiler.memory_oracle import analyze

    from py2rust.compiler import ir

    declaration = ir.Source("calls.py", 1, 0)
    call_site = ir.Source("calls.py", 3, 18)
    scalar = ir.ValueType("builtins.int")
    literal = ir.Expression("literal", scalar, declaration, value=1)
    unknown = ir.Expression("call", scalar, call_site, value="native.read")
    caller = ir.Expression("call", scalar, declaration, (unknown,), "leaf")
    leaf = ir.Function("leaf", (), scalar, (ir.Statement("return", declaration, (literal,)),), declaration)
    outer = ir.Function("outer", (), scalar, (ir.Statement("return", declaration, (caller,)),), declaration)
    plan = analyze((ir.Module("calls", (outer, leaf)),))
    assert plan.nonmutating_functions == frozenset({"leaf"})
    decision = next(item for item in plan.functions if item.function == "outer")
    assert decision.blocker is not None
    assert decision.blocker.reason == "unproven_callee"
    assert decision.blocker.detail == "native.read"
    assert decision.blocker.source == call_site


def test_prepared_ir_can_be_emitted_without_frontend_reruns(tmp_path: Path, monkeypatch) -> None:
    from py2rust.compiler import pipeline

    path = tmp_path / "main.py"
    path.write_text(SOURCE)
    prepared = pipeline.prepare_typed({"main": (path, SOURCE)})
    assert "main.fallback" in prepared.memory.nonmutating_functions
    assert prepared.modules[0].name == "main"
    expected = pipeline.emit_rust(prepared)
    path.write_text("this is no longer valid Python")

    def unexpected_analysis(*args, **kwargs) -> None:
        raise AssertionError("emission reran the frontend")

    monkeypatch.setattr(pipeline, "analyze", unexpected_analysis)
    assert pipeline.emit_rust(prepared) == expected
    assert pipeline.emit_rust(prepared) == expected
