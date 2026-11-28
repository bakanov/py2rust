"""CLI actions must use the selected frontend and report its actual decisions."""

import json
import sys
from pathlib import Path

import pytest

from py2rust.compiler import pipeline
from py2rust.compiler.project import Project, main

SOURCE = """from py2rust.stdlib import Json, json_get, json_string

def fallback() -> Json:
    return None

def select(document: Json) -> Json:
    return json_get(document, "selected", fallback())

if __name__ == "__main__":
    print(json_string(select({"selected": "small"})))
"""


@pytest.mark.parametrize("frontend_args", [[], ["--frontend", "typed"]], ids=["default", "explicit"])
def test_typed_explain_matches_emission_and_reports_oracle(
    tmp_path: Path, monkeypatch, capsys, frontend_args: list[str]
) -> None:
    path = tmp_path / "main.py"
    path.write_text(SOURCE)
    prepared = pipeline.prepare_typed({"main": (path, SOURCE)})
    assert pipeline.emit_program(prepared, explain=True).code == pipeline.emit_rust(prepared)

    def legacy_forbidden(*args, **kwargs) -> None:
        raise AssertionError("typed CLI invoked legacy compilation")

    monkeypatch.setattr(Project, "compile", legacy_forbidden)
    monkeypatch.setattr(
        sys, "argv", ["py2rust", "explain", str(tmp_path), *frontend_args, "--function", "main.py:fallback"]
    )
    assert main() == 0
    report = json.loads(capsys.readouterr().out)
    assert report["frontend"] == "typed"
    assert len(report["functions"]) == 1
    row = report["functions"][0]
    assert row["selector"] == "main.py:fallback"
    assert row["memory_oracle"]["nonmutating"] is True
    assert row["memory_oracle"]["blocker"] is None
    assert row["memory_oracle"]["source"]["path"] == str(path)


@pytest.mark.parametrize("frontend_args", [[], ["--frontend", "typed"]], ids=["default", "explicit"])
def test_typed_cli_packages_selected_frontend(tmp_path: Path, monkeypatch, capsys, frontend_args: list[str]) -> None:
    (tmp_path / "main.py").write_text(SOURCE)
    output = tmp_path / "generated"

    def legacy_forbidden(*args, **kwargs) -> None:
        raise AssertionError("typed CLI invoked legacy compilation")

    monkeypatch.setattr(Project, "compile", legacy_forbidden)
    monkeypatch.setattr(sys, "argv", ["py2rust", "transpile", str(tmp_path), *frontend_args, "-o", str(output)])
    assert main() == 0
    assert capsys.readouterr().out.strip() == str(output)
    from py2rust.compiler.project import MARKER

    assert json.loads((output / MARKER).read_text())["frontend"] == "typed"
    assert "rt::json_get(document," in (output / "src/entry.rs").read_text()


def test_typed_explain_enforces_unknown_native_effect_gate(tmp_path: Path, monkeypatch, capsys) -> None:
    (tmp_path / "native.rs").write_text("pub fn answer() -> i64 { 42 }\n")
    (tmp_path / "main.py").write_text("""from native import answer

def run() -> int:
    return answer()

if __name__ == "__main__":
    print(run())
""")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "py2rust",
            "explain",
            str(tmp_path),
            "--frontend",
            "typed",
            "--function",
            "main.py:run",
            "--deny",
            "unknown-effects",
        ],
    )
    assert main() == 2
    report = json.loads(capsys.readouterr().out)
    assert report["violations"][0]["check"] == "unknown-effects"
    decision = report["functions"][0]["memory_oracle"]
    assert decision["nonmutating"] is False
    assert decision["blocker"]["detail"] == "native_call"
    assert decision["blocker"]["source"]["line"] == 4


def test_service_cli_defaults_to_typed(tmp_path: Path, monkeypatch) -> None:
    from py2rust.compiler import service, service_cli
    from py2rust.compiler.project import MARKER

    source = tmp_path / "main.py"
    source.write_text(SOURCE)
    output = tmp_path / "generated"

    def legacy_forbidden(*args, **kwargs) -> None:
        raise AssertionError("default service CLI invoked legacy compilation")

    monkeypatch.setattr(Project, "compile", legacy_forbidden)
    monkeypatch.setattr(service_cli, "create_service_project", legacy_forbidden)
    monkeypatch.setattr(sys, "argv", ["py2rust-service", str(source), "-o", str(output)])
    assert service.main() == 0
    assert json.loads((output / MARKER).read_text())["frontend"] == "typed"
