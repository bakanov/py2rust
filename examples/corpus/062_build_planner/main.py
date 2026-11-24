"""Read build requests, explain plans and publish a reproducible complete result bundle."""

# ruff: noqa: PLR1711, BLE001, LOG015, PLC0206 - explicit returns and recoverable errors

import logging

from documents import Document, absolute, checkpoint, present, publish, read, unchanged
from model import Graph, document, exact, load, requests
from planner import plan

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


def explain(graph: Graph, result: Json) -> str:
    lines: list[str] = ["Request " + json_canonical(result["id"]) + ": " + json_string(result["status"])]
    number: int = 0
    for layer in json_array(result["layers"]):
        number = number + 1
        lines.append("Layer " + str(number) + ":")
        for value in json_array(layer):
            name: str = json_string(value)
            lines.append("  " + json_canonical(name) + "  argv=" + json_canonical(graph.commands[name]))
    if json_string(result["status"]) == "cycle":
        lines.append("Blocked: " + json_canonical(result["blocked"]))
        lines.append("Request-to-cycle prerequisites: " + json_canonical(result["requires_path"]))
        lines.append("Cycle (target requires next): " + json_canonical(result["cycle"]))
    return "\n".join(lines) + "\n"


def run() -> int:
    mode: str = env_get("BUILD_MODE", "preview")
    assert mode in ["preview", "write"], "invalid planner mode"
    path: str = absolute(env_get("BUILD_CONFIG", "build-job.json"), path_resolve("."))
    configuration: Document = read(path, 65536)
    config: Json = json_loads(configuration.data.decode())
    exact(config, ["graph", "requests", "output"])
    base: str = path_parent(path)
    output: str = absolute(json_string(config["output"]), base)
    assert not present(output), "output directory already exists"
    source: Document = read(absolute(json_string(config["graph"]), base), 4194304)
    wanted: Document = read(absolute(json_string(config["requests"]), base), 4194304)
    documents: list[Document] = [configuration, source, wanted]
    graph: Graph = load(json_loads(source.data.decode()))
    jobs: list[Json] = requests(graph, json_loads(wanted.data.decode()))
    results: list[Json] = []
    explanations: list[str] = []
    encoded_size: int = 0
    cycles: int = 0
    for request in jobs:
        result: Json = plan(graph, request)
        encoded_size = encoded_size + len(json_canonical(result).encode())
        assert encoded_size <= 16777216, "plans exceed 16 MiB"
        results.append(result)
        explanations.append(explain(graph, result))
        if json_string(result["status"]) == "cycle":
            cycles = cycles + 1
    graph_text: str = json_canonical(document(graph)) + "\n"
    report: Json = {
        "version": 1,
        "graph": {"targets": len(graph.commands), "edges": graph.edges, "sha256": digest(graph_text)},
        "requests": len(jobs),
        "cyclic": cycles,
        "plans": results,
    }
    report_text: str = json_canonical(report) + "\n"
    explanation: str = "\n".join(explanations)
    assert len(report_text.encode()) <= 16777216 and len(explanation.encode()) <= 16777216, "report exceeds 16 MiB"
    files: dict[str, str] = {
        "graph.json": graph_text,
        "requests.json": json_canonical(jobs) + "\n",
        "plan.json": report_text,
        "plan.txt": explanation,
    }
    checksums: Json = {}
    for name in files:
        checksums[name] = {"bytes": len(files[name].encode()), "sha256": digest(files[name])}
    files["manifest.json"] = pretty({"version": 1, "files": checksums}) + "\n"
    checkpoint("validated")
    unchanged(documents)
    if mode == "write":
        publish(output, files, documents)
    print(report_text.strip())
    return 1 if cycles > 0 else 0


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
