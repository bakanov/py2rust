"""Audit module changes and atomically export reusable graphs and impact explanations."""

# ruff: noqa: PLR1711, BLE001, LOG015, PLC0206 - explicit returns and subset operations

import logging

from analysis import Partition, describe, impact, partition
from documents import Document, absolute, checkpoint, present, publish, read, unchanged
from model import Graph, document, exact, load, requests

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


def summary(result: Json) -> str:
    lines: list[str] = ["Change " + json_canonical(result["id"]) + ": " + json_canonical(result["changed"])]
    for explanation in json_array(result["explanations"]):
        lines.append(json_canonical(explanation["module"]) + " depends through " + json_canonical(explanation["path"]))
    lines.append("Unaffected: " + json_canonical(result["unaffected"]))
    return "\n".join(lines) + "\n"


def run() -> int:
    mode: str = env_get("IMPACT_MODE", "preview")
    assert mode in ["preview", "write"], "invalid impact mode"
    path: str = absolute(env_get("IMPACT_CONFIG", "impact-job.json"), path_resolve("."))
    configuration: Document = read(path, 65536)
    config: Json = json_loads(configuration.data.decode())
    exact(config, ["graph", "requests", "output"])
    base: str = path_parent(path)
    output: str = absolute(json_string(config["output"]), base)
    assert not present(output), "output directory already exists"
    source: Document = read(absolute(json_string(config["graph"]), base), 4194304)
    queries: Document = read(absolute(json_string(config["requests"]), base), 4194304)
    graph: Graph = load(json_loads(source.data.decode()))
    wanted: list[Json] = requests(graph, json_loads(queries.data.decode()))
    components: Partition = partition(graph)
    structure: Json = describe(graph, components)
    results: list[Json] = []
    rows: list[str] = []
    text: list[str] = []
    explanation_bytes: int = 0
    for request in wanted:
        result: Json = impact(graph, components, request)
        encoded: str = json_canonical(result) + "\n"
        explanation_bytes = explanation_bytes + len(encoded.encode())
        assert explanation_bytes <= 8388608, "impact explanations exceed 8 MiB"
        results.append(result)
        rows.append(encoded)
        text.append(summary(result))
    files: dict[str, str] = {
        "graph.json": json_canonical(document(graph)) + "\n",
        "requests.json": json_canonical(wanted) + "\n",
    }
    hashes: Json = {}
    for name in files:
        hashes[name] = digest(files[name])
    report: Json = {
        "version": 1,
        "input_sha256": hashes,
        "structure": structure,
        "requests": len(wanted),
        "impacts": results,
    }
    files["impact.json"] = json_canonical(report) + "\n"
    files["impacts.jsonl"] = "".join(rows)
    files["impact.txt"] = "\n".join(text)
    checksums: Json = {}
    for name in files:
        assert len(files[name].encode()) <= 16777216, "output file exceeds 16 MiB"
        checksums[name] = {"bytes": len(files[name].encode()), "sha256": digest(files[name])}
    files["manifest.json"] = pretty({"version": 1, "files": checksums}) + "\n"
    documents: list[Document] = [configuration, source, queries]
    checkpoint("validated")
    unchanged(documents)
    if mode == "write":
        publish(output, files, documents)
    print(json_canonical(report))
    return 0


def main() -> None:
    try:
        process_exit(run())
    except Exception as error:
        logging.error(str(error))
        process_exit(2)
    return


if __name__ == "__main__":
    main()
