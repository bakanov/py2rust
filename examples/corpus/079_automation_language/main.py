"""Compile a tiny program to an AST, execute it, and publish a portable replay bundle."""

# ruff: noqa: BLE001, LOG015, PLR1711 - boundary errors and explicit return
import logging

from documents import Document, absolute, present, publish, read, stamp
from execution import Outcome, execute
from lexing import Token, tokenize
from syntax import Node, block, describe

from py2rust.stdlib import (
    Json,
    env_get,
    json_canonical,
    json_equal,
    json_int,
    json_keys,
    json_loads,
    json_string,
    path_parent,
    path_resolve,
    process_exit,
)


def run() -> int:
    config: Document = read(absolute(env_get("AUTOMATION_CONFIG", "automation-job.json"), path_resolve(".")), 65536)
    value: Json = json_loads(config.data.decode())
    assert sorted(json_keys(value)) == ["output", "program", "steps", "version"], "invalid job fields"
    assert json_int(value["version"]) == 1, "unsupported job version"
    budget: int = json_int(value["steps"])
    assert 0 <= budget <= 10000, "step budget must be 0..10000"
    output: str = absolute(json_string(value["output"]), path_parent(config.path))
    assert not present(output), "output already exists"
    program: Document = read(absolute(json_string(value["program"]), path_parent(config.path)), 32768)
    tokens: list[Token] = tokenize(program.data.decode())
    tree: Node = block(tokens, 0, 0, False).node
    result: Outcome = execute(tree.children, [{}], budget)
    report: Json = {
        "version": 1,
        "status": "ok" if result.error == "" else "error",
        "error": result.error,
        "steps": result.steps,
        "variables": result.frames[0],
        "emitted": result.emitted,
        "trace": result.trace,
    }
    files: dict[str, bytes] = {
        "program.auto": program.data,
        "ast.json": (json_canonical(describe(tree)) + "\n").encode(),
        "report.json": (json_canonical(report) + "\n").encode(),
        "job.json": (
            json_canonical({"version": 1, "program": "program.auto", "steps": budget, "output": "replayed"}) + "\n"
        ).encode(),
    }
    assert len(files["ast.json"]) <= 1048576 and len(files["report.json"]) <= 2097152, "result byte limit exceeded"
    assert json_equal(program.stamp, stamp(program.path)) and json_equal(
        config.stamp, stamp(config.path)
    ), "input changed"
    publish(output, files)
    print(json_canonical(report))
    return 0 if result.error == "" else 1


def main() -> None:
    status: int = 2
    try:
        status = run()
    except Exception as error:
        logging.error(str(error))
    process_exit(status)
    return


if __name__ == "__main__":
    main()
