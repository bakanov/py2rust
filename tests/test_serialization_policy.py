"""JSON representation policy preserves validation and numeric output."""

from pathlib import Path

import pytest

from py2rust.compiler import pipeline, service
from py2rust.compiler.ir import ValueType
from py2rust.compiler.libraries.serialization import (
    direct_output,
    select_output,
    serializable,
)

from . import test_optimization as cases
from . import test_service_canonical_json as canonical
from .test_typed_liveness import test_move_and_copy_execution as run_case


def test_representation_boundaries() -> None:
    text = ValueType("builtins.str")
    floating = ValueType("builtins.float")
    document = ValueType("py2rust.stdlib.Json")
    resource = ValueType("py2rust.stdlib.FileHandle")
    assert serializable(floating) and not direct_output(floating)
    assert not serializable(ValueType("builtins.list", (resource,)))
    assert not serializable(ValueType("app.Record"))
    assert not serializable(ValueType("builtins.dict", (ValueType("builtins.int"), text)))
    assert direct_output(ValueType("builtins.tuple", (text,)))
    assert not direct_output(ValueType("tuple"))
    assert direct_output(ValueType("tuple", (text,) * 12))
    assert not direct_output(ValueType("tuple", (text,) * 13))
    mapping = ValueType("builtins.dict", (text, floating))
    assert serializable(mapping) and not direct_output(mapping)
    assert select_output("json_canonical", document, optimize=True).helper == "json_canonical_view"
    assert select_output("json_canonical", text, optimize=True).helper == "json_canonical"
    assert select_output("pretty", text, optimize=False).helper == "pretty"
    return  # noqa: PLR1711


@pytest.mark.parametrize("optimize", [False, True])
@pytest.mark.parametrize(
    "case", [cases.test_direct_serialization_contract, cases.test_array_views_and_borrowed_serialization]
)
def test_typed_serialization_execution(tmp_path: Path, monkeypatch, optimize: bool, case) -> None:
    run_case(tmp_path, monkeypatch, optimize, case)
    return  # noqa: PLR1711


@pytest.mark.parametrize(
    "case",
    [
        canonical.test_canonical_json_float_vectors_and_roundtrip,
        canonical.test_canonical_json_numeric_spelling_and_validation,
    ],
)
def test_typed_canonical_vectors(tmp_path: Path, monkeypatch, case) -> None:
    monkeypatch.setattr(
        service.ServiceCompiler,
        "compile",
        lambda self, source: pipeline.compile_typed({"main": (tmp_path / "main.py", source)}),
    )
    case(tmp_path, "rust")
    return  # noqa: PLR1711
