"""Library contracts and typed policies must not load the legacy AST backend."""

import subprocess
import sys

import pytest


@pytest.mark.parametrize(
    "module",
    [
        "argument_policy",
        "library_contracts",
        "libraries.method_effects",
        "parameter_policy",
    ],
)
def test_independent_policy_import(module: str) -> None:
    code = f"""import importlib
import sys
importlib.import_module('py2rust.compiler.{module}')
for name in ('memory', 'service', 'optimization', 'backend.legacy_adapter'):
    assert 'py2rust.compiler.' + name not in sys.modules, name
"""
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    return  # noqa: PLR1711
