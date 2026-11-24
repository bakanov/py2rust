"""Solve one bounded staffing problem and atomically publish a reusable schedule bundle."""

# ruff: noqa: PLR1711, BLE001, LOG015, PLC0206 - explicit returns and subset operations

import logging

from documents import Document, absolute, checkpoint, present, publish, read, unchanged
from model import Problem, document, exact, load
from solver import solve

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_canonical,
    json_loads,
    json_string,
    path_parent,
    path_resolve,
    pretty,
    process_exit,
    sha256_digest,
    sha256_new,
    sha256_update,
)


def digest(text: str) -> str:
    return sha256_digest(sha256_update(sha256_new(), text.encode()))


def run() -> int:
    mode: str = env_get("SHIFT_MODE", "preview")
    assert mode in ["preview", "write"], "invalid scheduler mode"
    path: str = absolute(env_get("SHIFT_CONFIG", "shift-job.json"), path_resolve("."))
    configuration: Document = read(path, 65536)
    config: Json = json_loads(configuration.data.decode())
    exact(config, ["problem", "output"])
    base: str = path_parent(path)
    output: str = absolute(json_string(config["output"]), base)
    assert not present(output), "output directory already exists"
    source: Document = read(absolute(json_string(config["problem"]), base), 1048576)
    problem: Problem = load(json_loads(source.data.decode()))
    report: Json = solve(problem)
    problem_text: str = json_canonical(document(problem)) + "\n"
    report["problem_sha256"] = digest(problem_text)
    lines: list[str] = ["Status: " + json_string(report["status"]), "Score: " + json_canonical(report["score"])]
    for assignment in json_array(report["schedule"]):
        lines.append(json_canonical(assignment["shift"]) + ": " + json_canonical(assignment["workers"]))
    if json_string(report["status"]) in ["unsatisfiable", "search_limit"]:
        lines.append("Individual eligibility shortages: " + json_canonical(report["shortages"]))
        lines.append("Diagnostic partial assignment: " + json_canonical(report["diagnostic_prefix"]))
        lines.append("Next-shift constraints at that prefix: " + json_canonical(report["frontier"]))
    files: dict[str, str] = {
        "problem.json": problem_text,
        "schedule.json": json_canonical(report) + "\n",
        "schedule.txt": "\n".join(lines) + "\n",
    }
    checksums: Json = {}
    for name in files:
        checksums[name] = {"bytes": len(files[name].encode()), "sha256": digest(files[name])}
    files["manifest.json"] = pretty({"version": 1, "files": checksums}) + "\n"
    documents: list[Document] = [configuration, source]
    checkpoint("validated")
    unchanged(documents)
    if mode == "write":
        publish(output, files, documents)
    print(json_canonical(report))
    return 0 if json_string(report["status"]) == "optimal" else 1


def main() -> None:
    try:
        status: int = run()
        if status != 0:
            process_exit(status)
    except Exception as error:
        logging.error(str(error))
        process_exit(2)
    return


if __name__ == "__main__":
    main()
