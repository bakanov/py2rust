"""Local projection policy requires roots and preserves effect/feature barriers."""

import pytest

from py2rust.compiler.ir import ValueType
from py2rust.compiler.place_policy import BorrowOptions, projection

ENABLED = BorrowOptions(text=True, slices=True, json=True)
DISABLED = BorrowOptions(text=False, slices=False, json=False)


@pytest.mark.parametrize(
    ("operation", "type_name", "expected"),
    [
        ("slice", "builtins.bytes", "sequence_slice"),
        ("slice", "builtins.tuple", "sequence_slice"),
        ("index", "builtins.str", "text"),
        ("index", "py2rust.stdlib.Json", "json"),
        ("json_array", "py2rust.stdlib.Json", "json_array"),
    ],
)
def test_optional_projections_require_root_and_feature(operation: str, type_name: str, expected: str) -> None:
    typ = ValueType(type_name)
    assert projection(operation, typ, options=ENABLED, stable=True) == expected
    assert projection(operation, None, options=ENABLED, stable=True) is None
    assert projection(operation, typ, options=DISABLED, stable=True) is None
    if operation != "json_array":
        assert projection(operation, typ, options=ENABLED, stable=False) is None
    return  # noqa: PLR1711


def test_projection_representation_and_unreviewed_types() -> None:
    assert projection("index", ValueType("str"), options=ENABLED, stable=True, indexed_text=True) == "indexed_text"
    assert projection("index", ValueType("str"), options=ENABLED, stable=False, indexed_text=True) is None
    assert projection("field", ValueType("app.Record"), options=DISABLED, stable=True, record=True) == "field"
    assert projection("field", ValueType("external.Record"), options=ENABLED, stable=True) is None
    assert projection("index", ValueType("external.Buffer"), options=ENABLED, stable=True) is None
    # These existing projections do not require an optional optimization. Their
    # use at a call boundary remains subject to the argument-stability policy.
    for name, kind in [("list", "sequence"), ("builtins.tuple", "sequence"), ("tuple", "tuple"), ("dict", "mapping")]:
        assert projection("index", ValueType(name), options=DISABLED, stable=False) == kind
    return  # noqa: PLR1711
