"""Interoperability scripts must consume typed evidence and binaries together."""

import os
import subprocess
import sys
from pathlib import Path


def test_interoperability_scripts_select_typed_builds(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    code = """import importlib
import pathlib
import sys
sys.path.insert(0, sys.argv[1])
import corpus
checked = []
for path in sorted(pathlib.Path(sys.argv[1]).glob('check_*.py')):
    module = importlib.import_module(path.stem)
    if hasattr(module, 'BUILD'):
        assert module.BUILD == corpus.evidence_root('typed'), path.name
        assert module.BUILD != corpus.evidence_root('legacy'), path.name
        checked.append(path.name)
assert len(checked) >= 80, checked
print(len(checked))
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(root / "tools")],
        env=dict(os.environ, PY2RUST_BUILD_DIR=str(tmp_path / "build")),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return  # noqa: PLR1711
