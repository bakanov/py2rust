"""Plan a batch of scheduled journeys and publish normalized inputs and readable itineraries."""

# ruff: noqa: PLR1711, BLE001, LOG015, PLC0206 - explicit returns and subset operations

import logging

from documents import Document, absolute, checkpoint, present, publish, read, unchanged
from model import Timetable, document, exact, load, requests
from routing import plan

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


def itinerary(result: Json) -> str:
    lines: list[str] = ["Journey " + json_canonical(result["id"]) + ": " + json_string(result["status"])]
    lines.append(
        json_canonical(result["from"])
        + " -> "
        + json_canonical(result["to"])
        + " after "
        + json_string(result["depart_after"])
    )
    for leg in json_array(result["legs"]):
        lines.append(
            json_canonical(leg["id"])
            + ": "
            + json_canonical(leg["from"])
            + " "
            + json_string(leg["departure"])
            + " -> "
            + json_canonical(leg["to"])
            + " "
            + json_string(leg["arrival"])
            + "; ready "
            + json_string(leg["ready_at"])
        )
    lines.append("Arrival: " + json_canonical(result["arrival"]))
    return "\n".join(lines) + "\n"


def run() -> int:
    mode: str = env_get("TIMETABLE_MODE", "preview")
    assert mode in ["preview", "write"], "invalid timetable mode"
    path: str = absolute(env_get("TIMETABLE_CONFIG", "timetable-job.json"), path_resolve("."))
    configuration: Document = read(path, 65536)
    config: Json = json_loads(configuration.data.decode())
    exact(config, ["timetable", "requests", "output"])
    base: str = path_parent(path)
    output: str = absolute(json_string(config["output"]), base)
    assert not present(output), "output directory already exists"
    source: Document = read(absolute(json_string(config["timetable"]), base), 4194304)
    queries: Document = read(absolute(json_string(config["requests"]), base), 1048576)
    timetable: Timetable = load(json_loads(source.data.decode()))
    wanted: list[Json] = requests(timetable, json_loads(queries.data.decode()))
    journeys: list[Json] = []
    rows: list[str] = []
    text: list[str] = []
    found: int = 0
    payload: int = 0
    for request in wanted:
        result: Json = plan(timetable, request)
        encoded: str = json_canonical(result) + "\n"
        payload = payload + len(encoded.encode())
        assert payload <= 8388608, "journey records exceed 8 MiB"
        journeys.append(result)
        rows.append(encoded)
        text.append(itinerary(result))
        if json_string(result["status"]) == "found":
            found = found + 1
    files: dict[str, str] = {
        "timetable.json": json_canonical(document(timetable)) + "\n",
        "requests.json": json_canonical(wanted) + "\n",
    }
    hashes: Json = {}
    for name in files:
        hashes[name] = digest(files[name])
    report: Json = {
        "version": 1,
        "input_sha256": hashes,
        "counts": {"requests": len(wanted), "found": found, "unreachable": len(wanted) - found},
        "journeys": journeys,
    }
    files["journeys.json"] = json_canonical(report) + "\n"
    files["journeys.jsonl"] = "".join(rows)
    files["itineraries.txt"] = "\n".join(text)
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
    return 0 if found == len(wanted) else 1


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
