"""Run collection-method boundary and effect scenarios through typed emission."""

from pathlib import Path

import pytest

from py2rust.compiler import pipeline, service

from . import test_service_bytearray as buffers
from . import test_service_insert as lists


@pytest.mark.parametrize("optimize", [False, True])
@pytest.mark.parametrize(
    "case",
    [
        lists.test_insert_bounds_order_and_element_types,
        buffers.test_bytearray_invalid_values_and_indices_leave_buffer_unchanged,
    ],
)
def test_typed_collection_mutations(tmp_path: Path, monkeypatch, optimize: bool, case) -> None:
    original = service.ServiceCompiler.__init__

    def initialize(self, *args, **kwargs) -> None:
        kwargs["optimize"] = optimize
        original(self, *args, **kwargs)
        return

    monkeypatch.setattr(service.ServiceCompiler, "__init__", initialize)
    monkeypatch.setattr(
        service.ServiceCompiler,
        "compile",
        lambda self, source: pipeline.compile_typed({"main": (tmp_path / "main.py", source)}),
    )
    case(tmp_path)
    return


@pytest.mark.parametrize(
    "annotation, statement", [("list[int]", "values.insert(0, None)"), ("list[Json]", 'values.insert("bad", None)')]
)
def test_insert_json_hook_preserves_other_type_checks(tmp_path: Path, annotation: str, statement: str) -> None:
    from py2rust.compiler.frontend.mypy import FrontendError

    source = (
        "from py2rust.stdlib import Json\ndef check() -> None:\n"
        + "    values: "
        + annotation
        + " = []\n    "
        + statement
        + "\n"
    )
    path = tmp_path / "invalid.py"
    with pytest.raises(FrontendError) as caught:
        pipeline.prepare_typed({"main": (path, source)})
    assert str(path) + ":4:" in str(caught.value)
    return
