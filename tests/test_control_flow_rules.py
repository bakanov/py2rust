"""Prepared control-flow emission does not parse temporary Rust fragments."""

from pathlib import Path

from py2rust.compiler import pipeline, rust_ast

SOURCE = """def choose(flag: bool) -> str:
    if flag:
        return "chosen"
    else:
        return "other"

def run() -> None:
    count: int = 0
    while count < 2:
        try:
            assert choose(True) == "chosen"
            count = count + 1
        except Exception:
            raise
        finally:
            print(count)
    return

if __name__ == "__main__":
    run()
"""


def test_prepared_emission_avoids_fragment_parser(tmp_path: Path, monkeypatch) -> None:
    prepared = pipeline.prepare_typed({"main": (tmp_path / "main.py", SOURCE)})
    expected = pipeline.emit_rust(prepared)

    def forbidden_parser():
        raise AssertionError("portable control-flow rendering attempted a Rust fragment parse")

    monkeypatch.setattr(rust_ast, "_load_tree_sitter_rust", forbidden_parser)
    assert pipeline.emit_rust(prepared) == expected
    return
