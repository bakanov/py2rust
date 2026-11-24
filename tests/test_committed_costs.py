"""Ownership reports describe committed boundaries, not speculative receivers."""

# ruff: noqa: EXE002, PLR1711 - exFAT modes and explicit returns
from py2rust.compiler.service import ServiceCompiler

SOURCE = """
def moving(value: str) -> str:
    value = value + "!"
    return value

def copying(value: list[int]) -> int:
    value.append(1)
    saved: list[int] = value
    value.append(2)
    return len(saved) + len(value)

def materializing(value: str) -> str:
    return value

def cleanup(value: str) -> str:
    value = value + "!"
    try:
        return value
    finally:
        print(value)

if __name__ == "__main__":
    print(moving("hello"))
    print(copying([1]))
    print(materializing("hi"))
    print(cleanup("bye"))
"""


def test_committed_local_ownership_report() -> None:
    compiler = ServiceCompiler()
    compiler.collect_costs = True
    assert compiler.compile(SOURCE) == ServiceCompiler().compile(SOURCE)
    rows = [d for d in compiler.lowering_decisions if d.operation == "owned_boundary"]
    assert len(rows) == 4
    assert {(d.function, d.mode, d.reason) for d in rows} == {
        ("moving", "move", "last_use_on_all_successors"),
        ("copying", "copy", "value_live_after_use"),
        ("materializing", "materialize", "borrowed_value_requires_owned_result"),
        ("cleanup", "copy", "protected_control_flow"),
    }
    # Receiver probes for both append calls are deliberately absent.
    assert [d.line for d in rows if d.function == "copying"] == [8]
    return
