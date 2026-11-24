"""Signed bit patterns and Python shift behavior within the i64 subset."""

from pathlib import Path

import pytest
from py2rust.compiler.service import ServiceCompiler, ServiceError

from .test_services import parity, run


def test_bitwise_signed_limits_and_evaluation_order(tmp_path: Path) -> None:
    parity(
        tmp_path,
        """
def operand(value: int) -> int:
    print(value)
    return value
def check() -> None:
    values: list[int] = [-9223372036854775808, -65536, -1, 0, 1, 255, 65535, 9223372036854775807]
    for left in values:
        print(~left)
        for right in values:
            print(left & right, left | right, left ^ right)
        for count in [0, 1, 16, 62, 63, 64, 1000, 9223372036854775807]:
            print(left >> count)
    for count in [0, 1, 10, 62]:
        print(1 << count, -1 << count)
    assert -1 << 63 == -9223372036854775808
    assert 0 << 9223372036854775807 == 0
    assert operand(3) & operand(5) == 1
    assert operand(2) << operand(3) == 16
    assert ~operand(2) == -3
    return
if __name__ == "__main__":
    check()
""",
    )
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def test_checked_shift_helpers_match_reference(tmp_path: Path) -> None:
    parity(
        tmp_path,
        """
from py2rust.stdlib import int_lshift, int_rshift
def check() -> None:
    errors: int = 0
    for pair in [(1, 63), (-2, 63), (1, 64), (1, 9223372036854775807), (0, -1), (1, -9223372036854775808)]:
        try:
            int_lshift(pair[0], pair[1])
        except Exception as error:
            print(str(error))
            errors = errors + 1
    for count in [-1, -9223372036854775808]:
        try:
            int_rshift(0, count)
        except Exception as error:
            print(str(error))
            errors = errors + 1
    assert errors == 8
    assert int_lshift(-1, 63) == -9223372036854775808
    assert int_lshift(0, 9223372036854775807) == 0
    assert int_rshift(-9223372036854775808, 9223372036854775807) == -1
    assert int_rshift(9223372036854775807, 64) == 0
    return
if __name__ == "__main__":
    check()
""",
    )
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def test_shift_operator_failures_are_recoverable(tmp_path: Path) -> None:
    result = run(
        tmp_path,
        """
def check() -> None:
    errors: int = 0
    for count in [63, 64, 9223372036854775807, -1]:
        try:
            value: int = 1 << count
        except Exception:
            errors = errors + 1
    try:
        value: int = 1 >> -1
    except Exception:
        errors = errors + 1
    assert errors == 5
    print("checked operators")
    return
if __name__ == "__main__":
    check()
""",
        "rust",
    )
    assert result.returncode == 0 and result.stdout == "checked operators\n", result.stderr
    return  # noqa: PLR1711 - explicit return required by repository guidelines


@pytest.mark.parametrize("expression", ["1 & True", "1.0 | 2.0", "True ^ False", "1 << 1.0", "~True"])
def test_bitwise_rejects_non_integer_operands(expression: str) -> None:
    with pytest.raises(ServiceError, match="unsupported (arithmetic combination|unary operator)"):
        ServiceCompiler().compile(
            "def check() -> None:\n    print(" + expression + ')\n    return\nif __name__ == "__main__":\n    check()\n'
        )
    return  # noqa: PLR1711 - explicit return required by repository guidelines
