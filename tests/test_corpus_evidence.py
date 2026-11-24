"""Evidence invalidation follows selected application data and transitive checker code."""

import importlib.util
import json
from pathlib import Path

import pytest


def fixture(tmp_path: Path, monkeypatch) -> tuple:
    repository = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(repository / "tools"))
    spec = importlib.util.spec_from_file_location("corpus_evidence_under_test", repository / "tools/corpus.py")
    corpus = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(corpus)
    sources = {
        "tools/corpus.py": "# verifier\n",
        "tools/corpus_checks/__init__.py": "from . import shared\n",
        "tools/corpus_checks/shared.py": "VALUE = 1\n",
        "tools/corpus_checks/selected.py": "from .nested.helper import value\nfrom .common import Application\n",
        "tools/corpus_checks/common.py": "class Application: pass\n",
        "tools/corpus_checks/nested/__init__.py": "# nested\n",
        "tools/corpus_checks/nested/helper.py": "from .. import shared\nvalue = shared.VALUE\n",
        "tools/corpus_checks/unrelated.py": "# other application\n",
        "examples/corpus/catalog.json": "{}\n",
        "examples/corpus/selected/main.py": "print('fixture')\n",
        "examples/corpus/selected/config.json": "{}\n",
        "pyproject.toml": "[project]\n",
        "py2rust/compiler/service.py": "# compiler\n",
        "py2rust/compiler/project.py": "# linker\n",
        "py2rust/compiler/frontend/mypy-source.json": "{}\n",
        "py2rust/stdlib.py": "# reference\n",
        "py2rust/compiler/service_runtime/src/lib.rs": "// runtime\n",
        "py2rust/compiler/service_runtime/Cargo.toml": "# dependencies\n",
        "py2rust/compiler/service_runtime/Cargo.lock": "# lock\n",
    }
    for name, content in sources.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    monkeypatch.setattr(corpus, "ROOT", tmp_path)
    monkeypatch.setattr(corpus, "CORPUS", tmp_path / "examples/corpus")
    monkeypatch.setattr(corpus, "__file__", str(tmp_path / "tools/corpus.py"))
    program = {"id": "035", "path": "selected", "check": "selected", "assets": ["config.json"], "minimum_sloc": 200}
    return corpus, program


def test_selected_metadata_and_transitive_sources_invalidate(tmp_path: Path, monkeypatch) -> None:
    corpus, program = fixture(tmp_path, monkeypatch)
    original = corpus.fingerprint(program)
    assert len(corpus.checker_sources("selected")) == 6
    for name in [
        "tools/corpus.py",
        "tools/corpus_checks/common.py",
        "tools/corpus_checks/shared.py",
        "tools/corpus_checks/nested/helper.py",
        "tools/corpus_checks/nested/__init__.py",
        "tools/corpus_checks/selected.py",
        "examples/corpus/selected/main.py",
        "examples/corpus/selected/config.json",
        "py2rust/compiler/service.py",
        "py2rust/compiler/project.py",
        "py2rust/compiler/frontend/mypy-source.json",
        "py2rust/stdlib.py",
        "py2rust/compiler/service_runtime/src/lib.rs",
        "py2rust/compiler/service_runtime/Cargo.toml",
        "py2rust/compiler/service_runtime/Cargo.lock",
        "pyproject.toml",
    ]:
        path = tmp_path / name
        before = path.read_bytes()
        path.write_bytes(before + b"\n")
        assert corpus.fingerprint(program) != original, name
        path.write_bytes(before)
        assert corpus.fingerprint(program) == original
    assert corpus.fingerprint(dict(program, minimum_sloc=201)) != original
    (tmp_path / "examples/corpus/selected/config.json").unlink()
    assert corpus.fingerprint(program) != original
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def test_unrelated_catalog_checker_and_reports_do_not_invalidate(tmp_path: Path, monkeypatch) -> None:
    corpus, program = fixture(tmp_path, monkeypatch)
    original = corpus.fingerprint(program)
    (tmp_path / "examples/corpus/catalog.json").write_text(json.dumps({"unrelated": "new program"}))
    (tmp_path / "tools/corpus_checks/unrelated.py").write_text("# changed unrelated checker\n")
    (tmp_path / "tools/corpus_checks/new_app.py").write_text("# added unrelated checker\n")
    (tmp_path / "examples/corpus/selected/result.json").write_text("generated report")
    assert corpus.fingerprint(program) == original
    # A newly declared helper becomes relevant, including changes through an import cycle.
    selected = tmp_path / "tools/corpus_checks/selected.py"
    selected.write_text(selected.read_text() + "import corpus_checks.new_app\n")
    changed = corpus.fingerprint(program)
    assert changed != original
    helper = tmp_path / "tools/corpus_checks/new_app.py"
    helper.write_text("import corpus_checks.selected\n")
    assert corpus.fingerprint(program) != changed
    assert len(corpus.checker_sources("selected")) == 7
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def test_absolute_package_imports_and_missing_helpers(tmp_path: Path, monkeypatch) -> None:
    corpus, _program = fixture(tmp_path, monkeypatch)
    (tmp_path / "tools/corpus_checks/selected.py").write_text(
        "from corpus_checks import common\nfrom . import missing\n"
    )
    files = corpus.checker_sources("selected")
    assert tmp_path / "tools/corpus_checks/common.py" in files
    assert tmp_path / "tools/corpus_checks/missing.py" in files
    assert tmp_path / "tools/corpus_checks/nested/helper.py" not in files
    return  # noqa: PLR1711 - explicit return required by repository guidelines


@pytest.mark.parametrize(
    "source", ["__import__('hidden')", "import importlib", "from importlib import import_module as load"]
)
def test_dynamic_checker_imports_need_explicit_dependencies(tmp_path: Path, monkeypatch, source: str) -> None:
    corpus, _program = fixture(tmp_path, monkeypatch)
    (tmp_path / "tools/corpus_checks/selected.py").write_text(source)
    with pytest.raises(ValueError, match="static imports"):
        corpus.checker_sources("selected")
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def native_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple:
    from types import SimpleNamespace

    corpus, program = fixture(tmp_path, monkeypatch)
    program.update(id="094", native_adapters=sorted(corpus.NATIVE_FIXTURES["094"]))
    root = corpus.CORPUS / program["path"]
    modules = {"main": SimpleNamespace(path=root / "main.py", tree=object())}
    for name in program["native_adapters"]:
        path = root / name
        path.write_text("pub fn value() -> i64 { 1 }\n")
        modules[path.stem] = SimpleNamespace(path=path, tree=None)
    return corpus, program, SimpleNamespace(modules=modules)


def test_declared_native_fixtures_and_python_coverage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import hashlib

    corpus, program, project = native_fixture(tmp_path, monkeypatch)
    evidence = corpus.validate_project_sources(program, project)
    assert set(evidence) == set(program["native_adapters"])
    for name, digest in evidence.items():
        assert digest == hashlib.sha256((corpus.CORPUS / program["path"] / name).read_bytes()).hexdigest()
    project.modules.pop("main")
    with pytest.raises(AssertionError, match="untranspiled Python"):
        corpus.validate_project_sources(program, project)
    return  # noqa: PLR1711


@pytest.mark.parametrize("change", ["wrong_id", "no_declaration", "duplicate", "extra", "missing", "unlinked", "alias"])
def test_native_inventory_cannot_silently_bypass_python_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    corpus, program, project = native_fixture(tmp_path, monkeypatch)
    root = corpus.CORPUS / program["path"]
    if change == "wrong_id":
        program["id"] = "093"
    elif change == "no_declaration":
        program.pop("native_adapters")
    elif change == "duplicate":
        program["native_adapters"].append(program["native_adapters"][0])
    elif change == "extra":
        (root / "hidden_policy.rs").write_text("// not declared\n")
    elif change == "missing":
        (root / program["native_adapters"][0]).unlink()
    elif change == "unlinked":
        project.modules.pop("native_numbers")
    else:
        target = root / "native_numbers.rs"
        target.unlink()
        target.symlink_to(root / "native_text.rs")
    with pytest.raises(AssertionError):
        corpus.validate_project_sources(program, project)
    return  # noqa: PLR1711


def test_native_and_reference_shim_sources_invalidate_proof(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    corpus, program, _project = native_fixture(tmp_path, monkeypatch)
    base = tmp_path / "tools/corpus_checks/native_reference"
    base.mkdir()
    files = {
        "__init__.py": "# explicit reference fixtures\n",
        "runner.py": "from . import native_numbers, native_text, native_values\n",
        "native_numbers.py": "VALUE = 1\n",
        "native_text.py": "VALUE = 2\n",
        "native_values.py": "VALUE = 3\n",
    }
    for name, text in files.items():
        (base / name).write_text(text)
    selected = tmp_path / "tools/corpus_checks/selected.py"
    selected.write_text(selected.read_text() + "from .native_reference import runner\n")
    original = corpus.fingerprint(program)
    for path in [*(base / name for name in files), *corpus.native_source_files(program)]:
        before = path.read_bytes()
        path.write_bytes(before + b"\n")
        assert corpus.fingerprint(program) != original, path
        path.write_bytes(before)
        assert corpus.fingerprint(program) == original
    command = corpus.reference_command(program)
    assert command[-2:] == [str(base / "runner.py"), str(corpus.CORPUS / program["path"] / "main.py")]
    program.pop("native_adapters")
    assert len(corpus.reference_command(program)) == 3
    return  # noqa: PLR1711


def test_frontend_identity_and_nested_compiler_sources_invalidate_evidence(tmp_path: Path, monkeypatch) -> None:
    corpus, program = fixture(tmp_path, monkeypatch)
    assert corpus.fingerprint(program, "typed") != corpus.fingerprint(program, "legacy")
    assert corpus.evidence_root("typed") != corpus.evidence_root("legacy")
    source = tmp_path / "py2rust/compiler/frontend/lowering.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("# typed lowering\n")
    before = corpus.fingerprint(program, "typed")
    source.write_text("# changed typed lowering\n")
    assert corpus.fingerprint(program, "typed") != before


def test_typed_frontend_dependency_changes_invalidate_evidence(tmp_path: Path, monkeypatch) -> None:
    corpus, program = fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(corpus, "typed_dependency_fingerprint", lambda: "first-version")
    original = corpus.fingerprint(program, "typed")
    legacy = corpus.fingerprint(program, "legacy")
    monkeypatch.setattr(corpus, "typed_dependency_fingerprint", lambda: "second-version")
    assert corpus.fingerprint(program, "typed") != original
    assert corpus.fingerprint(program, "legacy") == legacy
