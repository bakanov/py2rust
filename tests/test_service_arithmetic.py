"""Exact signed division, remainder, stable tuple sorting, and collection copies."""

import pytest
from py2rust.compiler.service import ServiceCompiler, ServiceError

from .test_services import parity, run


def test_signed_floor_and_modulo_match_python(tmp_path):
    parity(
        tmp_path,
        """
def check() -> None:
    values: list[int] = [-9223372036854775808, -100, -7, -1, 0, 1, 7, 100, 9223372036854775807]
    for left in values:
        for right in [-9223372036854775808, -7, -2, 2, 7, 9223372036854775807]:
            print(left // right, left % right)
    assert -9223372036854775808 % -1 == 0
    errors: int = 0
    try:
        value: int = 1 // 0
    except Exception:
        errors = errors + 1
    try:
        remainder: int = -1 % 0
    except Exception:
        errors = errors + 1
    assert errors == 2
    return
if __name__ == "__main__":
    check()
""",
    )


def test_floor_overflow_is_recoverable(tmp_path):
    result = run(
        tmp_path,
        """
def check() -> None:
    try:
        value: int = -9223372036854775808 // -1
    except Exception as error:
        print(str(error))
    return
if __name__ == "__main__":
    check()
""",
        "rust",
    )
    assert result.returncode == 0 and result.stdout == "integer overflow\n"


def test_collection_order_and_independent_copies(tmp_path):
    parity(
        tmp_path,
        """
from py2rust.stdlib import pretty

def check() -> None:
    ranks: list[tuple[int, str]] = [(3, "b"), (-1, "a"), (3, "a"), (3, "世界")]
    ordered: list[tuple[int, str]] = sorted(ranks)
    assert ranks[0] == (3, "b")
    ranks.sort()
    assert ranks == ordered
    ranks.reverse()
    assert ranks[0] == (3, "世界")
    counts: dict[str, int] = {"a": 1}
    duplicate: dict[str, int] = counts.copy()
    duplicate["a"] = 2
    assert counts["a"] == 1
    names: set[str] = {"a"}
    copied: set[str] = names.copy()
    copied.add("b")
    assert len(names) == 1 and len(copied) == 2
    print(pretty(ranks))
    return
if __name__ == "__main__":
    check()
""",
    )


@pytest.mark.parametrize("operation", ["sorted([1.0, 2.0])", "1.0 // 2.0", "1 % 2.0"])
def test_unsupported_numeric_ordering_is_diagnosed(operation):
    with pytest.raises(ServiceError):
        ServiceCompiler().compile(f'def check() -> None:\n    {operation}\nif __name__ == "__main__":\n    check()\n')
