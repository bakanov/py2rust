"""The program's own Unix address-space bound is real, monotone and process-local."""

import resource
import subprocess
from pathlib import Path

import pytest

from .test_services import program, run


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_address_space_limit_lowers_soft_bound_preserves_hard_and_reports_kernel_state(
    tmp_path: Path, engine: str
) -> None:
    before = resource.getrlimit(resource.RLIMIT_AS)
    result = run(
        tmp_path,
        """
from py2rust.stdlib import limit_address_space, read_text
def check() -> None:
    first: int = limit_address_space(268435456)
    assert first <= 268435456
    second: int = limit_address_space(134217728)
    assert second <= 134217728 and second <= first
    assert limit_address_space(268435456) == second
    found: bool = False
    for line in read_text("/proc/self/limits").split("\\n"):
        if line.startswith("Max address space"):
            fields: list[str] = line.split()
            assert fields[3] == str(second)
            print(fields[4])
            found = True
    assert found
    errors: int = 0
    for limit in [-1, 0, 33554431, 17179869185, 9223372036854775807]:
        try:
            limit_address_space(limit)
        except Exception:
            errors = errors + 1
    assert errors == 5
    return
if __name__ == "__main__":
    check()
""",
        engine,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == ("unlimited" if before[1] == resource.RLIM_INFINITY else str(before[1]))
    assert resource.getrlimit(resource.RLIMIT_AS) == before
    return  # noqa: PLR1711


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_address_space_limit_respects_inherited_lower_soft_bound(tmp_path: Path, engine: str) -> None:
    command = program(
        tmp_path,
        """
from py2rust.stdlib import limit_address_space
def check() -> None:
    assert limit_address_space(268435456) == 134217728
    print("inherited bound retained")
    return
if __name__ == "__main__":
    check()
""",
        engine,
    )
    result = subprocess.run(
        ["prlimit", "--as=134217728:268435456", "--", *command], capture_output=True, text=True, timeout=10, check=False
    )
    assert result.returncode == 0 and result.stdout == "inherited bound retained\n", result.stderr
    return  # noqa: PLR1711
