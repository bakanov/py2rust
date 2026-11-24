"""The frontend builder must reject changed source before executing build hooks."""

from pathlib import Path

import pytest

from tools import build_frontend_wheel as builder


def fixture_source(root: Path) -> Path:
    root.mkdir()
    for name in builder.BUILD_FILES:
        (root / name).write_text(name)
    for package in ("mypy", "mypyc"):
        (root / package).mkdir()
        (root / package / "__init__.py").write_text("")
    return root


def test_frontend_digest_ignores_cache_but_detects_source_changes(tmp_path: Path) -> None:
    root = fixture_source(tmp_path / "source")
    before = builder.source_digest(root, builder.source_files(root))
    cache = root / "mypy/__pycache__"
    cache.mkdir()
    (cache / "module.pyc").write_bytes(b"disposable")
    assert builder.source_digest(root, builder.source_files(root)) == before
    (root / "mypy/__init__.py").write_text("changed = True\n")
    assert builder.source_digest(root, builder.source_files(root)) != before


def test_frontend_builder_rejects_unreviewed_source_before_build(tmp_path: Path, monkeypatch) -> None:
    root = fixture_source(tmp_path / "source")

    def forbidden_build(*args, **kwargs) -> None:
        raise AssertionError("build hook executed for unreviewed source")

    monkeypatch.setattr(builder.subprocess, "run", forbidden_build)
    with pytest.raises(ValueError, match="differs from the reviewed snapshot"):
        builder.build(root, tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_frontend_builder_rejects_compiled_input(tmp_path: Path) -> None:
    root = fixture_source(tmp_path / "source")
    (root / "mypy/nodes.so").write_bytes(b"not a pure Python visitor")
    with pytest.raises(ValueError, match="compiled frontend input"):
        builder.source_files(root)


def test_frontend_builder_keeps_output_outside_supplied_source(tmp_path: Path) -> None:
    root = fixture_source(tmp_path / "source")
    with pytest.raises(ValueError, match="outside the supplied mypy source"):
        builder.build(root, root / "wheels")
    assert not (root / "wheels").exists()


def test_frontend_fetch_uses_pinned_revision(tmp_path: Path, monkeypatch) -> None:
    import io
    import json
    import zipfile

    revision = "a" * 40
    contract = tmp_path / "contract.json"
    contract.write_text(json.dumps({"upstream_revision": revision}))
    monkeypatch.setattr(builder, "CONTRACT", contract)
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr(f"mypy-{revision}/mypy/__init__.py", "# reviewed source\n")

    def download(url: str, timeout: int) -> io.BytesIO:
        assert url == f"https://codeload.github.com/python/mypy/zip/{revision}"
        assert timeout > 0
        return io.BytesIO(payload.getvalue())

    monkeypatch.setattr(builder, "urlopen", download)
    source = builder.fetch_source(tmp_path)
    assert (source / "mypy/__init__.py").read_text() == "# reviewed source\n"
    return


def test_frontend_fetch_rejects_paths_outside_source(tmp_path: Path, monkeypatch) -> None:
    import io
    import json
    import zipfile

    contract = tmp_path / "contract.json"
    contract.write_text(json.dumps({"upstream_revision": "a" * 40}))
    monkeypatch.setattr(builder, "CONTRACT", contract)
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr("../outside.py", "unexpected")
    monkeypatch.setattr(builder, "urlopen", lambda *args, **kwargs: io.BytesIO(payload.getvalue()))
    with pytest.raises(ValueError, match="unexpected path"):
        builder.fetch_source(tmp_path)
    assert not (tmp_path.parent / "outside.py").exists()
    return
