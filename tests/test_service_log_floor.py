"""Logarithm domains and bounded integer rounding used by probabilistic structures."""

import math
import random
from pathlib import Path

import pytest
from py2rust.compiler.service import ServiceCompiler, ServiceError

from .test_services import parity


def test_logarithm_vectors_and_integer_floor(tmp_path: Path) -> None:
    rng = random.Random(5601)
    values = [5e-324, 1e-308, 0.001, 0.5, 1.0, 2.0, 1e308]
    values += [10 ** rng.uniform(-300, 300) for _ in range(128)]
    # Do not demand identical decimal formatting from separate libm implementations.
    assertions = "\n".join(
        f"    assert math.log({value!r}) >= {math.log(value) - 2e-12!r}\n"
        f"    assert math.log({value!r}) <= {math.log(value) + 2e-12!r}"
        for value in values
    )
    parity(
        tmp_path,
        """
import math
from py2rust.stdlib import floor, math_log
def observed(value: int) -> int:
    print(value)
    return value
def check() -> None:
    assert math.floor(observed(9223372036854775807)) == 9223372036854775807
    assert floor(-9223372036854775808) == -9223372036854775808
    for pair in [(0.0, 0), (-0.0, 0), (0.1, 0), (-0.1, -1), (1.999, 1), (-1.999, -2),
                 (9223372036854774784.0, 9223372036854774784), (-9223372036854775808.0, -9223372036854775808)]:
        assert math.floor(pair[0]) == pair[1] and floor(pair[0]) == pair[1]
    assert math.log(1) == 0.0 and math_log(1.0) == 0.0
"""
        + assertions
        + """
    return
if __name__ == "__main__":
    check()
""",
    )
    return  # noqa: PLR1711


def test_logarithm_domain_and_floor_overflow(tmp_path: Path) -> None:
    parity(
        tmp_path,
        """
import math
from py2rust.stdlib import floor, math_log
def check() -> None:
    errors: int = 0
    for value in [0.0, -0.0, -1.0, -1e308]:
        try:
            math.log(value)
        except Exception:
            errors = errors + 1
        try:
            math_log(value)
        except Exception:
            errors = errors + 1
    for value in [9223372036854775808.0, -9223372036854777856.0, 1e308]:
        try:
            floor(value)
        except Exception:
            errors = errors + 1
    assert errors == 11
    return
if __name__ == "__main__":
    check()
""",
    )
    return  # noqa: PLR1711


@pytest.mark.parametrize("expression", ["math.log()", "math.log(2.0, 10.0)", "math.log(True)", 'math.floor("1")'])
def test_math_rejects_unsupported_arguments(expression: str) -> None:
    with pytest.raises(ServiceError, match="math_log expects 1 arguments|expected Type.*float"):
        ServiceCompiler().compile(
            "import math\ndef check() -> None:\n    "
            + expression
            + '\n    return\nif __name__ == "__main__":\n    check()\n'
        )
    return  # noqa: PLR1711
