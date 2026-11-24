"""Read one packing job and publish canonical inputs, package manifests and explicit rejections."""

# ruff: noqa: PLR1711, BLE001, LOG015, PLC0206 - explicit returns and subset operations

import logging

from documents import Document, absolute, checkpoint, present, publish, read, unchanged
from model import Problem, document, exact, load
from packing import plan

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
    mode: str = env_get("PARCEL_MODE", "preview")
    assert mode in ["preview", "write"], "invalid packing mode"
    path: str = absolute(env_get("PARCEL_CONFIG", "parcel-job.json"), path_resolve("."))
    configuration: Document = read(path, 65536)
    config: Json = json_loads(configuration.data.decode())
    exact(config, ["problem", "output"])
    base: str = path_parent(path)
    output: str = absolute(json_string(config["output"]), base)
    assert not present(output), "output directory already exists"
    source: Document = read(absolute(json_string(config["problem"]), base), 4194304)
    problem: Problem = load(json_loads(source.data.decode()))
    report: Json = plan(problem)
    problem_text: str = json_canonical(document(problem)) + "\n"
    report["problem_sha256"] = digest(problem_text)
    lines: list[str] = ["Status: " + json_string(report["status"]), "Totals: " + json_canonical(report["totals"])]
    packages: list[str] = []
    for parcel in json_array(report["packages"]):
        packages.append(json_canonical(parcel) + "\n")
        identifiers: list[str] = []
        for item in json_array(parcel["items"]):
            identifiers.append(json_string(item["id"]))
        lines.append(
            json_string(parcel["id"])
            + " box="
            + json_canonical(parcel["box"])
            + " destination="
            + json_canonical(parcel["destination"])
            + " items="
            + json_canonical(identifiers)
        )
    rejected: list[str] = []
    for rejection in json_array(report["rejected"]):
        rejected.append(json_canonical(rejection) + "\n")
        lines.append("Rejected " + json_canonical(rejection["item"]["id"]) + ": " + json_string(rejection["reason"]))
    files: dict[str, str] = {
        "problem.json": problem_text,
        "plan.json": json_canonical(report) + "\n",
        "packages.jsonl": "".join(packages),
        "rejected.jsonl": "".join(rejected),
        "plan.txt": "\n".join(lines) + "\n",
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
    return 0 if json_string(report["status"]) == "complete" else 1


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
