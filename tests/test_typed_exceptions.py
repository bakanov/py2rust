"""Typed exception decisions precede emission and preserve full-program behavior."""

from pathlib import Path

import pytest

from py2rust.compiler import exceptions, pipeline, service
from py2rust.compiler.exception_policy import ExceptionPolicyError

from . import test_service_finally as legacy_cases
from . import test_service_resources as resource_cases


def no_ast_policy(*args, **kwargs) -> None:
    raise AssertionError("typed emission reanalyzed exception policy through Python AST")


@pytest.mark.parametrize(
    "case",
    [
        legacy_cases.test_finally_cleanup_and_pending_returns,
        legacy_cases.test_finally_exception_precedence_and_bare_raise,
        legacy_cases.test_finally_nested_order_and_loop_local_jumps,
        resource_cases.test_file_scopes_and_hash_snapshots,
        resource_cases.test_file_validation_and_closed_aliases,
    ],
)
def test_typed_exception_behavior_without_ast_policy(tmp_path: Path, monkeypatch, case) -> None:
    monkeypatch.setattr(exceptions, "_always_returns_ast", no_ast_policy)
    monkeypatch.setattr(service, "invalid_try_jump", no_ast_policy)
    monkeypatch.setattr(
        service.ServiceCompiler,
        "compile",
        lambda self, source: pipeline.compile_typed({"main": (tmp_path / "main.py", source)}),
    )
    case(tmp_path)
    return  # noqa: PLR1711


@pytest.mark.parametrize(
    "body",
    [
        "try:\n    break\nfinally:\n    pass",
        "try:\n    pass\nfinally:\n    continue",
        "try:\n    pass\nexcept Exception:\n    break\nfinally:\n    pass",
        "try:\n    try:\n        pass\n    except Exception:\n        break\nfinally:\n    pass",
        "try:\n    continue\nexcept Exception:\n    pass",
    ],
)
def test_invalid_jumps_rejected_before_emission(tmp_path: Path, body: str, monkeypatch) -> None:
    monkeypatch.setattr(pipeline, "emit_program", no_ast_policy)
    source = "def run() -> None:\n    while True:\n" + "\n".join("        " + line for line in body.splitlines())
    source += "\nif __name__ == '__main__':\n    run()\n"
    with pytest.raises(ExceptionPolicyError, match="break/continue across a try boundary") as error:
        pipeline.compile_typed({"main": (tmp_path / "main.py", source)})
    assert error.value.filename == str(tmp_path / "main.py")
    assert error.value.lineno == next(
        line for line, text in enumerate(source.splitlines(), 1) if text.strip() in {"break", "continue"}
    )
    return  # noqa: PLR1711


def test_prepared_exception_plan_is_reused(tmp_path: Path, monkeypatch) -> None:
    from py2rust.compiler import exception_policy

    source = """def choice(value: int) -> int:
    try:
        return value
    finally:
        if value == 2:
            return 3

if __name__ == "__main__":
    print(choice(2))
"""
    program = pipeline.prepare_typed({"main": (tmp_path / "main.py", source)})
    protected = [flow.protected for _, flow in program.exceptions.statements if flow.protected]
    assert len(protected) == 1
    assert protected[0].body_terminates
    assert not protected[0].cleanup_terminates
    assert protected[0].statement_terminates
    expected = pipeline.emit_rust(program)
    # Compare the new IR proof against the prior AST decisions on identical input.
    import ast

    tree = pipeline.linked_tree(program.modules, program.entry, exception_facts=program.exceptions.facts())
    for node in ast.walk(tree):
        if hasattr(node, "py2rust_flow"):
            del node.py2rust_flow
    assert service.ServiceCompiler().compile_tree(tree) == expected
    monkeypatch.setattr(exception_policy, "analyze", no_ast_policy)
    monkeypatch.setattr(exceptions, "_always_returns_ast", no_ast_policy)
    monkeypatch.setattr(service, "invalid_try_jump", no_ast_policy)
    assert pipeline.emit_rust(program) == expected
    return  # noqa: PLR1711


def test_project_reports_exception_policy_source(tmp_path: Path) -> None:
    from py2rust.compiler.project import create_project

    source = "def run() -> None:\n    while True:\n        try:\n            break\n        finally:\n            pass\nrun()\n"
    (tmp_path / "main.py").write_text(source)
    output = tmp_path / "rust"
    with pytest.raises(service.ServiceError, match="break/continue across a try boundary") as error:
        create_project(tmp_path, output)
    assert error.value.filename == str(tmp_path / "main.py")
    assert error.value.lineno == 4
    assert not output.exists()
    return  # noqa: PLR1711
