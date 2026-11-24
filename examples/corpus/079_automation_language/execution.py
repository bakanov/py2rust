"""Execute lexical blocks, charging every statement and repeat iteration to a finite budget."""

# ruff: noqa: BLE001 - retain completed state and normalize errors in the execution report
from dataclasses import dataclass

from syntax import Node
from values import evaluate, scope_index

from py2rust.stdlib import Json, json_keys


@dataclass
class Outcome:
    frames: list[Json]
    emitted: list[int]
    trace: list[Json]
    steps: int
    error: str


def execute(nodes: list[Node], frames: list[Json], budget: int) -> Outcome:
    emitted: list[int] = []
    trace: list[Json] = []
    steps: int = 0
    failure: str = ""
    for node in nodes:
        try:
            assert steps < budget, node.location + "step budget exhausted"
            steps = steps + 1
            value: int = evaluate(node.children[0], frames)
            depth: int = len(frames) - 1
            if node.kind in ["let", "set"]:
                if node.kind == "set":
                    depth = scope_index(frames, node.value, node.location)
                scope: Json = frames[depth]
                if node.kind == "let":
                    assert node.value not in json_keys(scope), (
                        node.location + "variable already declared: " + node.value
                    )
                    assert len(json_keys(scope)) < 128, node.location + "scope exceeds 128 variables"
                scope[node.value] = value
                frames[depth] = scope
            elif node.kind == "emit":
                emitted.append(value)
            elif node.kind == "repeat":
                assert value >= 0, node.location + "repeat count must be nonnegative"
            trace.append(
                {"kind": node.kind, "name": node.value, "value": value, "depth": depth, "location": node.location}
            )
            if node.kind in ["if", "repeat"]:
                iterations: int = value if node.kind == "repeat" else 1
                branch: int = 2 if node.kind == "if" and value == 0 else 1
                for iteration in range(iterations):
                    if node.kind == "repeat":
                        assert steps < budget, node.location + "step budget exhausted"
                        steps = steps + 1
                        trace.append(
                            {
                                "kind": "iteration",
                                "value": iteration + 1,
                                "depth": len(frames),
                                "location": node.location,
                            }
                        )
                    frames.append({})
                    child: Outcome = execute(node.children[branch].children, frames, budget - steps)
                    frames = child.frames
                    frames.pop()
                    emitted.extend(child.emitted)
                    trace.extend(child.trace)
                    steps = steps + child.steps
                    failure = child.error
                    if failure != "":
                        break
        except Exception as error:
            failure = str(error)
            trace.append({"kind": "error", "message": failure, "location": node.location})
        if failure != "":
            break
    return Outcome(frames, emitted, trace, steps, failure)
