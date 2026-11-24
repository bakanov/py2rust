"""Argument stability is prepared on IR, including conservative nested effects."""

from pathlib import Path

from py2rust.compiler import memory, pipeline
from py2rust.compiler.service import ServiceCompiler

from .test_services import parity

SOURCE = """from py2rust.stdlib import Json, json_get, json_int

def select(document: Json, keys: list[str]) -> Json:
    return json_get(document, "selected", len(keys))

def checked(document: Json, keys: list[str]) -> Json:
    return json_get(document, "selected", len(keys[4]))

def run() -> None:
    keys: list[str] = ["one", "two"]
    present: Json = {"selected": 7, "payload": [1, 2, 3]}
    missing: Json = {"payload": [1, 2, 3]}
    print(json_int(select(present, keys)))
    print(json_int(select(missing, keys)))
    print(len(keys))
    try:
        checked(present, keys)
    except Exception:
        print("bounds checked")
    print(json_int(present["selected"]))

if __name__ == "__main__":
    run()
"""


def test_structural_length_avoids_document_copy(tmp_path: Path, monkeypatch) -> None:
    program = pipeline.prepare_typed({"main": (tmp_path / "main.py", SOURCE)})
    after = pipeline.emit_rust(program)
    assert 'rt::json_get(document, "selected",' in after
    # Empty metadata selects the adapter's legacy expression analysis for comparison.
    original_link = pipeline.linked_tree

    def legacy_arguments(*args, **kwargs):
        kwargs["evaluation_facts"] = None
        return original_link(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(pipeline, "linked_tree", legacy_arguments)
        before = pipeline.emit_rust(program)
    assert 'rt::json_get(&((*document).clone()), "selected",' in before

    def unexpected(*args, **kwargs) -> None:
        raise AssertionError("typed argument analysis fell back to Python AST")

    monkeypatch.setattr(memory, "_legacy_argument_effects_unknown", unexpected)
    assert pipeline.emit_rust(program) == after
    assert any(expr.value == "builtins.len" and proof.stable for expr, proof in program.memory.evaluations)
    return  # noqa: PLR1711


def test_nested_effects_keep_snapshot_and_provenance(tmp_path: Path) -> None:
    source = SOURCE.replace(
        "def select(document: Json, keys: list[str]) -> Json:",
        "def mutate(keys: list[str]) -> list[str]:\n    keys.pop()\n    return keys\n\n"
        "def select(document: Json, keys: list[str]) -> Json:",
    ).replace('"selected", len(keys)', '"selected", len(mutate(keys))')
    program = pipeline.prepare_typed({"main": (tmp_path / "main.py", source)})
    assert 'rt::json_get(&((*document).clone()), "selected",' in pipeline.emit_rust(program)
    decisions = [proof for expr, proof in program.memory.evaluations if expr.value == "builtins.len"]
    blocked = [proof for proof in decisions if not proof.stable]
    assert len(blocked) == 1
    assert blocked[0].blocker.detail == "main.mutate"
    assert blocked[0].blocker.source.path == str(tmp_path / "main.py")
    return  # noqa: PLR1711


def test_argument_values_and_input_preservation(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        ServiceCompiler,
        "compile",
        lambda self, source: pipeline.compile_typed({"main": (tmp_path / "main.py", source)}),
    )
    assert parity(tmp_path, SOURCE) == "7\n2\n2\nbounds checked\n7\n"
    return  # noqa: PLR1711
