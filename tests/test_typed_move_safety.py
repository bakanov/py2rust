"""Prepared move safety protects resource ownership and live borrowed views."""

from pathlib import Path

import pytest

from py2rust.compiler import ir, pipeline, service
from py2rust.compiler.move_safety import analyze

from . import test_optimization as optimization
from . import test_service_recursive_records as recursive
from . import test_service_resources as resources
from .test_typed_parameters import SOURCE


def forbidden_legacy(*args, **kwargs) -> None:
    raise AssertionError("typed move safety fell back to emitter type analysis")


def test_resource_reachability_through_recursive_records() -> None:
    source = ir.Source("records.py", 1, 0)

    def record(name: str, *types: ir.ValueType) -> ir.Record:
        return ir.Record(name, tuple(ir.Field(str(i), typ, source) for i, typ in enumerate(types)), source)

    def sequence(name: str) -> ir.ValueType:
        return ir.ValueType("builtins.list", (ir.ValueType(name),))

    module = ir.Module(
        "records",
        (),
        records=(
            record("Clean", sequence("Clean"), ir.ValueType("builtins.str")),
            record("First", sequence("Second")),
            record("Second", sequence("First"), ir.ValueType("py2rust.stdlib.FileHandle")),
            record("Unknown", ir.ValueType("external.Handle")),
        ),
    )
    plan = analyze((module,))
    assert dict(plan.records) == {"Clean": True, "First": False, "Second": False, "Unknown": False}
    assert plan.permits(sequence("Clean"))
    assert not plan.permits(sequence("First"))
    assert not plan.permits(ir.ValueType("py2rust.stdlib.FileHandle"))
    return  # noqa: PLR1711


def test_prepared_move_safety_matches_legacy(tmp_path: Path, monkeypatch) -> None:
    prepared = pipeline.prepare_typed({"main": (tmp_path / "main.py", SOURCE)})
    assert dict(prepared.memory.move_safety.records) == {"main.Record": True}
    current = pipeline.emit_rust(prepared)
    original_link = pipeline.linked_tree

    def legacy(*args, **kwargs):
        kwargs["move_safety"] = None
        return original_link(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(pipeline, "linked_tree", legacy)
        assert pipeline.emit_rust(prepared) == current
    monkeypatch.setattr(service.ServiceCompiler, "_legacy_move_safe_type", forbidden_legacy)
    assert pipeline.emit_rust(prepared) == current
    return  # noqa: PLR1711


@pytest.mark.parametrize("optimize", [False, True])
@pytest.mark.parametrize(
    "case",
    [
        optimization.test_text_indexes_and_views,
        optimization.test_json_views_and_owned_escapes,
        optimization.test_sequence_views_preserve_snapshots,
        resources.test_file_scopes_and_hash_snapshots,
        recursive.test_recursive_record_collection_fields_and_traversal,
    ],
)
def test_native_moves_preserve_views_and_resources(tmp_path: Path, monkeypatch, optimize: bool, case) -> None:
    original_init = service.ServiceCompiler.__init__

    def initialize(self, *args, **kwargs) -> None:
        kwargs["optimize"] = optimize
        original_init(self, *args, **kwargs)
        return  # noqa: PLR1711

    monkeypatch.setattr(service.ServiceCompiler, "__init__", initialize)
    monkeypatch.setattr(service.ServiceCompiler, "_legacy_move_safe_type", forbidden_legacy)
    monkeypatch.setattr(
        service.ServiceCompiler,
        "compile",
        lambda self, source: pipeline.compile_typed({"main": (tmp_path / "main.py", source)}),
    )
    if case.__module__ == optimization.__name__:
        case(tmp_path, monkeypatch, optimize)
    else:
        case(tmp_path)
    return  # noqa: PLR1711
