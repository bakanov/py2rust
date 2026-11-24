"""Lossless production IR transport and native rejection of malformed graphs."""

import copy
import json
from dataclasses import replace
from pathlib import Path

import pytest

from py2rust.compiler import ir, pipeline, service
from py2rust.compiler.ir_exchange import from_document, to_document
from py2rust.compiler.native import ir_schema

from .test_services import program


def fixture_module() -> ir.Module:
    source = ir.Source("source.py", 1, 0)
    integer = ir.ValueType("builtins.int")
    expressions = tuple(
        ir.Expression("literal", integer, source, value=value)
        for value in [None, True, 2**63, -0.0, b"\x00\xff", "世界"]
    )
    statement = ir.Statement(
        "try",
        source,
        expressions,
        ((ir.Statement("pass", source),),),
        "target",
        integer,
        (ir.Handler("Exception", "error", (ir.Statement("pass", source),), source),),
        True,
    )
    function = ir.Function("main.f", (ir.Parameter("arg", integer),), integer, (statement,), source)
    field = ir.Field("value", integer, source, expressions[2])
    return ir.Module(
        "main",
        (function,),
        (statement,),
        (ir.Record("main.Record", (field,), source),),
        (ir.Enum("main.Enum", (("ONE", expressions[2]),), source),),
    )


def test_every_ir_field_round_trips() -> None:
    modules = (fixture_module(),)
    document = to_document(modules, "main")
    restored, entry = from_document(json.loads(json.dumps(document)))
    assert restored == modules
    assert entry == "main"
    assert json.dumps(to_document(restored, entry), sort_keys=True) == json.dumps(document, sort_keys=True)
    return


def test_prepared_program_emission_survives_ir_transport(tmp_path: Path) -> None:
    source = "def twice(value: int) -> int:\n    return value * 2\n\nif __name__ == '__main__':\n    print(twice(21))\n"
    prepared = pipeline.prepare_typed({"main": (tmp_path / "main.py", source)})
    modules, entry = from_document(to_document(prepared.modules, prepared.entry))
    restored = replace(prepared, modules=modules, entry=entry)
    assert pipeline.emit_program(restored).code == pipeline.emit_program(prepared).code
    return


def documents() -> list[dict]:
    valid = to_document((fixture_module(),), "main")
    cases = [valid]
    version = copy.deepcopy(valid)
    version["format"] = 2
    cases.append(version)
    forward = copy.deepcopy(valid)
    forward["nodes"][0] = {"kind": "ValueType", "name": "bad", "arguments": [0]}
    cases.append(forward)
    wrong_root = copy.deepcopy(valid)
    wrong_root["modules"] = [0]
    cases.append(wrong_root)
    extra = copy.deepcopy(valid)
    extra["nodes"][0]["extra"] = True
    cases.append(extra)
    literal = copy.deepcopy(valid)
    expression = next(row for row in literal["nodes"] if row["kind"] == "Expression")
    expression["value"] = {"kind": "int", "text": "1;panic!()"}
    cases.append(literal)
    return cases


@pytest.mark.parametrize("document", documents()[1:])
def test_malformed_graph_rejected(document: dict) -> None:
    with pytest.raises((AssertionError, ValueError, KeyError)):
        from_document(document)
    return


def test_production_schema_runs_natively(tmp_path: Path, monkeypatch) -> None:
    import os
    import subprocess

    rule_path = tmp_path / "ir_schema.py"
    rule_source = Path(ir_schema.__file__).read_text()
    rule_path.write_text(rule_source)
    source = """from py2rust.stdlib import Json, json_loads, json_array
from ir_schema import validate_document

def run() -> None:
    cases: list[Json] = json_array(json_loads(PAYLOAD))
    for document in cases:
        try:
            names: list[str] = validate_document(document)
            print("accepted " + ",".join(names))
        except Exception:
            print("rejected")

if __name__ == "__main__":
    run()
""".replace("PAYLOAD", repr(json.dumps(documents(), ensure_ascii=False)))
    monkeypatch.setattr(
        service.ServiceCompiler,
        "compile",
        lambda self, text: pipeline.compile_typed(
            {"main": (tmp_path / "main.py", text), "ir_schema": (rule_path, rule_source)}
        ),
    )
    reference = subprocess.run(program(tmp_path, source, "python"), capture_output=True, text=True, check=True)
    binary = program(tmp_path, source, "rust")
    native = subprocess.run(
        binary,
        env=dict(os.environ, PATH="/nonexistent", PYTHONHOME="/nonexistent", PYTHONPATH="/nonexistent"),
        capture_output=True,
        text=True,
        check=True,
    )
    assert native.stdout == reference.stdout == "accepted main\n" + "rejected\n" * 5
    return
