"""Solve bounded Sudoku batches and publish reusable boards and independently checkable witnesses."""

# ruff: noqa: PLR1711, BLE001, LOG015, PLC0206 - explicit returns and subset operations

import logging

from documents import Document, absolute, checkpoint, present, publish, read, unchanged
from model import Board, document, exact, load
from solver import solve

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_canonical,
    json_int,
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


def diagnostic_text(result: Json) -> str:
    lines: list[str] = ["Board " + json_canonical(result["id"]) + ": " + json_string(result["status"])]
    lines.append(
        "Visited "
        + json_canonical(result["stats"]["visited"])
        + " of "
        + json_canonical(result["budget"])
        + " permitted nodes"
    )
    for error in json_array(result["diagnostics"]):
        lines.append(json_canonical(error))
    for index in range(len(json_array(result["solutions"]))):
        lines.append("Solution " + str(index + 1))
        for row in json_array(result["solutions"][index]):
            values: list[str] = []
            for value in json_array(row):
                values.append(json_canonical(value))
            lines.append(" ".join(values))
    return "\n".join(lines) + "\n"


def run() -> int:
    mode: str = env_get("SUDOKU_MODE", "preview")
    assert mode in ["preview", "write"], "invalid Sudoku mode"
    path: str = absolute(env_get("SUDOKU_CONFIG", "sudoku-job.json"), path_resolve("."))
    configuration: Document = read(path, 65536)
    config: Json = json_loads(configuration.data.decode())
    exact(config, ["boards", "output"])
    base: str = path_parent(path)
    output: str = absolute(json_string(config["output"]), base)
    assert not present(output), "output directory already exists"
    source: Document = read(absolute(json_string(config["boards"]), base), 1048576)
    boards: list[Board] = load(json_loads(source.data.decode()))
    counts: Json = {"invalid": 0, "unsatisfiable": 0, "unique": 0, "multiple": 0, "search_limit": 0}
    results: list[Json] = []
    records: list[str] = []
    descriptions: list[str] = []
    for board in boards:
        result: Json = solve(board)
        status: str = json_string(result["status"])
        counts[status] = json_int(counts[status]) + 1
        results.append(result)
        records.append(json_canonical(result) + "\n")
        descriptions.append(diagnostic_text(result))
    normalized: str = json_canonical(document(boards)) + "\n"
    report: Json = {"version": 1, "boards_sha256": digest(normalized), "counts": counts, "results": results}
    files: dict[str, str] = {
        "boards.json": normalized,
        "results.json": json_canonical(report) + "\n",
        "results.jsonl": "".join(records),
        "diagnostics.txt": "\n".join(descriptions),
    }
    checksums: Json = {}
    for name in files:
        assert len(files[name].encode()) <= 8388608, "output file exceeds 8 MiB"
        checksums[name] = {"bytes": len(files[name].encode()), "sha256": digest(files[name])}
    files["manifest.json"] = pretty({"version": 1, "files": checksums}) + "\n"
    documents: list[Document] = [configuration, source]
    checkpoint("validated")
    unchanged(documents)
    if mode == "write":
        publish(output, files, documents)
    print(json_canonical(report))
    return 0 if json_int(counts["unique"]) == len(boards) else 1


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
