"""Parameter ABI plans preserve value semantics and runtime callback contracts."""

from pathlib import Path

import pytest

from py2rust.compiler import memory, pipeline, service
from py2rust.compiler.backend import module_emission

from . import test_service_parallel as parallel_cases
from . import test_service_records as record_cases
from .test_services import parity

SOURCE = """from dataclasses import dataclass
from py2rust.stdlib import Json, json_get, json_int, parallel_map
import heapq

@dataclass
class Record:
    values: list[int]

def inspect(record: Record, names: list[str], data: bytes) -> int:
    return len(record.values) + len(names) + len(data)

def update(record: Record) -> int:
    record.values = [1, 2]
    return len(record.values)

def indexed(values: list[list[int]]) -> int:
    values[0].append(2)
    return len(values[0])

def deleted(values: dict[str, int]) -> int:
    del values["a"]
    return len(values)

def heap(values: list[int]) -> int:
    heapq.heapify(values)
    return heapq.heappop(values)

def rebound(text: str) -> str:
    text = "changed"
    return text

def callback(value: Json) -> Json:
    return value

def run() -> None:
    print(inspect(Record([1]), ["x"], b"a"))
    print(update(Record([1])))
    print(indexed([[1]]))
    print(deleted({"a": 1, "b": 2}))
    print(heap([3, 1, 2]))
    print(rebound("original"))
    results: list[Json] = parallel_map(callback, [5, 6], 2)
    print(json_int(results[1]))
    document: Json = {"selected": 7}
    print(json_int(json_get(document, "selected", callback(document))))

if __name__ == "__main__":
    run()
"""


def forbidden_ast_policy(*args, **kwargs) -> None:
    raise AssertionError("typed parameter plan fell back to AST analysis")


def test_prepared_parameter_modes_and_legacy_equivalence(tmp_path: Path, monkeypatch) -> None:
    prepared = pipeline.prepare_typed({"main": (tmp_path / "main.py", SOURCE)})
    plans = {plan.function: plan for plan in prepared.memory.parameters}
    assert {p.mode for p in plans["main.inspect"].parameters} == {"borrow"}
    for name in ["update", "indexed", "deleted", "heap", "rebound", "callback"]:
        assert plans["main." + name].parameters[0].mode == "owned"
    assert plans["main.callback"].callback
    assert plans["main.callback"].parameters[0].reason == "callback_owned_abi"
    assert plans["main.heap"].parameters[0].reason == "heap_operation_mutates_parameter"
    current = pipeline.emit_rust(prepared)
    original_link = pipeline.linked_tree

    def old_parameters(*args, **kwargs):
        kwargs["parameter_plans"] = None
        return original_link(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(pipeline, "linked_tree", old_parameters)
        assert pipeline.emit_rust(prepared) == current
    monkeypatch.setattr(memory, "_legacy_parameter_uses", forbidden_ast_policy)
    monkeypatch.setattr(module_emission, "callback_functions", forbidden_ast_policy)
    assert pipeline.emit_rust(prepared) == current
    return  # noqa: PLR1711


def test_parameter_values_and_callbacks(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(memory, "_legacy_parameter_uses", forbidden_ast_policy)
    monkeypatch.setattr(module_emission, "callback_functions", forbidden_ast_policy)
    monkeypatch.setattr(
        service.ServiceCompiler,
        "compile",
        lambda self, source: pipeline.compile_typed({"main": (tmp_path / "main.py", source)}),
    )
    assert parity(tmp_path, SOURCE) == "3\n2\n2\n1\n1\nchanged\n6\n7\n"
    return  # noqa: PLR1711


@pytest.mark.parametrize(
    "case",
    [
        record_cases.test_record_fields_defaults_keywords_and_collections,
        record_cases.test_records_can_hold_scoped_resources,
        record_cases.test_native_records_follow_owned_value_semantics,
        parallel_cases.test_parallel_order_and_value_isolation,
        parallel_cases.test_parallel_errors_join_all_callbacks,
    ],
)
def test_record_and_worker_semantics(tmp_path: Path, monkeypatch, case) -> None:
    monkeypatch.setattr(memory, "_legacy_parameter_uses", forbidden_ast_policy)
    monkeypatch.setattr(module_emission, "callback_functions", forbidden_ast_policy)
    monkeypatch.setattr(
        service.ServiceCompiler,
        "compile",
        lambda self, source: pipeline.compile_typed({"main": (tmp_path / "main.py", source)}),
    )
    case(tmp_path)
    return  # noqa: PLR1711


@pytest.mark.parametrize(
    "source",
    [
        SOURCE.replace(
            "results: list[Json] = parallel_map(callback, [5, 6], 2)",
            "numbers: list[int] = [5, 6]\n    results: list[Json] = parallel_map(callback, numbers, 2)",
        ),
        SOURCE.replace("def callback(value: Json) -> Json:", "def callback(value: int) -> Json:"),
    ],
)
def test_callback_contracts_remain_checked(tmp_path: Path, source: str) -> None:
    from py2rust.compiler.frontend import FrontendError

    with pytest.raises(FrontendError, match="incompatible type"):
        pipeline.prepare_typed({"main": (tmp_path / "main.py", source)})
    return  # noqa: PLR1711


def test_reachable_receiver_mutation_is_owned(tmp_path: Path) -> None:
    # Field-method emission is not implemented yet, but its parameter policy must
    # still reject borrowing when a reachable receiver can be mutated.
    source = SOURCE.replace("record.values = [1, 2]", "record.values.append(2)")
    prepared = pipeline.prepare_typed({"main": (tmp_path / "main.py", source)})
    update = next(plan for plan in prepared.memory.parameters if plan.function == "main.update")
    assert update.parameters[0].mode == "owned"
    assert update.parameters[0].reason == "receiver_effects_not_readonly"
    return  # noqa: PLR1711
