"""Plan terrain routes and atomically export canonical inputs, paths, statistics and ASCII maps."""

# ruff: noqa: PLR1711, BLE001, LOG015, PLC0206 - explicit returns and subset operations

import logging

from documents import Document, absolute, checkpoint, present, publish, read, unchanged
from model import Grid, exact, load, requests, terrain
from routing import render, solve

from py2rust.stdlib import (
    Json,
    env_get,
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
    mode: str = env_get("TERRAIN_MODE", "preview")
    assert mode in ["preview", "write"], "invalid terrain mode"
    path: str = absolute(env_get("TERRAIN_CONFIG", "terrain-job.json"), path_resolve("."))
    configuration: Document = read(path, 65536)
    config: Json = json_loads(configuration.data.decode())
    exact(config, ["grid", "terrain", "requests", "output"])
    base: str = path_parent(path)
    output: str = absolute(json_string(config["output"]), base)
    assert not present(output), "output directory already exists"
    source: Document = read(absolute(json_string(config["grid"]), base), 8192)
    rules: Document = read(absolute(json_string(config["terrain"]), base), 65536)
    queries: Document = read(absolute(json_string(config["requests"]), base), 1048576)
    costs: dict[str, int] = terrain(json_loads(rules.data.decode()))
    grid: Grid = load(source.data.decode(), costs)
    wanted: list[Json] = requests(grid, json_loads(queries.data.decode()))
    results: list[Json] = []
    pictures: list[str] = ["S=start G=goal @=start-and-goal *=path X=blocked-endpoint #=wall\n"]
    paths: list[str] = []
    counts: dict[str, int] = {"found": 0, "unreachable": 0, "blocked": 0}
    for request in wanted:
        result: Json = solve(grid, request)
        results.append(result)
        status: str = json_string(result["status"])
        counts[status] = counts[status] + 1
        pictures.append(render(grid, result))
        paths.append(json_canonical(result) + "\n")
    files: dict[str, str] = {
        "grid.txt": "\n".join(grid.rows) + "\n",
        "terrain.json": json_canonical({"version": 1, "costs": costs}) + "\n",
        "requests.json": json_canonical(wanted) + "\n",
    }
    hashes: Json = {}
    for name in files:
        hashes[name] = digest(files[name])
    report: Json = {
        "version": 1,
        "grid": {
            "width": grid.width,
            "height": len(grid.rows),
            "passable": grid.passable,
            "minimum_cost": grid.minimum,
        },
        "input_sha256": hashes,
        "queries": len(wanted),
        "counts": counts,
        "routes": results,
    }
    files["routes.json"] = json_canonical(report) + "\n"
    files["paths.jsonl"] = "".join(paths)
    files["routes.txt"] = "\n".join(pictures)
    checksums: Json = {}
    for name in files:
        assert len(files[name].encode()) <= 16777216, "output file exceeds 16 MiB"
        checksums[name] = {"bytes": len(files[name].encode()), "sha256": digest(files[name])}
    files["manifest.json"] = pretty({"version": 1, "files": checksums}) + "\n"
    documents: list[Document] = [configuration, source, rules, queries]
    checkpoint("validated")
    unchanged(documents)
    if mode == "write":
        publish(output, files, documents)
    print(json_canonical(report))
    return 0 if counts["blocked"] + counts["unreachable"] == 0 else 1


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
