"""A complete process/network benchmark and replayable report-comparison application."""
# ruff: noqa: I001, BLE001, LOG015, PLC0206, PLR1711 - compact imports and explicit boundary
import logging
from analysis import checked, compare, statistics
from documents import Document, absolute, present, publish, read
from execution import attempt
from model import command, digest, exact, integer, suite
from workers import worker
from py2rust.stdlib import (
    Json, env_get, json_array, json_canonical, json_int, json_loads_unique, json_string, path_parent,
    path_resolve, process_exit,
)


def encoded(value: Json) -> bytes:
    return (json_canonical(value) + "\n").encode()


def benchmark(config: Json) -> Json:
    cases: list[Json] = json_array(config["cases"])
    repetitions: int = integer(config["repetitions"], 1, 4)
    suite(cases, repetitions)
    runs: list[Json] = []
    interrupted: bool = False
    for case in cases:
        for trial in range(1, repetitions + 1):
            row: Json = attempt(case, trial, config["sender"], config["receiver"])
            runs.append(row)
            interrupted = json_string(row["status"]) == "interrupted"
            if interrupted:
                break
        if interrupted:
            break
    return {"version": 1, "kind": "benchmark", "cases": cases, "repetitions": repetitions,
            "workers": {"sender": config["sender"]["argv"], "receiver": config["receiver"]["argv"]},
            "runs": runs, "statistics": statistics(cases, runs, repetitions)}


def run() -> int:
    document: Document = read(absolute(env_get("TRANSFER_CONFIG", "transfer-job.json"), path_resolve(".")), 65536)
    config: Json = json_loads_unique(document.data.decode())
    assert json_int(config["version"]) == 1, "unsupported request version"
    base: str = path_parent(document.path)
    output: str = absolute(json_string(config["output"]), base)
    assert not present(output), "output already exists"
    mode: str = json_string(config["mode"])
    assert mode in ["benchmark", "compare"], "unknown mode"
    inputs: list[Document] = [document]
    files: dict[str, bytes] = {}
    report: Json = {"version": 1, "kind": "comparison"}
    code: int = 0
    if mode == "benchmark":
        exact(config, ["version", "mode", "output", "cases", "repetitions", "sender", "receiver"])
        config["sender"] = command(config["sender"], base)
        config["receiver"] = command(config["receiver"], base)
        report = benchmark(config)
        checked(report)
        for row in json_array(report["runs"]):
            if json_string(row["status"]) != "ok":
                code = 130 if json_string(row["status"]) == "interrupted" else 1
    else:
        exact(config, ["version", "mode", "output", "baseline", "candidate"])
        baseline: Document = read(absolute(json_string(config["baseline"]), base), 1048576)
        candidate: Document = read(absolute(json_string(config["candidate"]), base), 1048576)
        inputs.append(baseline)
        inputs.append(candidate)
        report["baseline_sha256"] = digest(baseline.data)
        report["candidate_sha256"] = digest(candidate.data)
        report["rows"] = compare(json_loads_unique(baseline.data.decode()), json_loads_unique(candidate.data.decode()))
        files["baseline.json"] = baseline.data
        files["candidate.json"] = candidate.data
        config["baseline"] = "baseline.json"
        config["candidate"] = "candidate.json"
    files["report.json"] = encoded(report)
    assert len(files["report.json"]) <= 1048576, "report byte budget exceeded"
    lines: list[str] = ["Transfer " + mode]
    if mode == "benchmark":
        for case in json_array(report["cases"]):
            name: str = json_string(case["id"])
            lines.append(name + ": " + json_canonical(report["statistics"][name]))
        for row in json_array(report["runs"]):
            if json_string(row["status"]) != "ok":
                lines.append(json_string(row["case"]) + ": " + json_string(row["phase"]) + ": " +
                             json_string(row["error"]))
    else:
        for row in json_array(report["rows"]):
            lines.append(json_canonical(row))
    files["report.txt"] = ("\n".join(lines) + "\n").encode()
    config["output"] = "replayed"
    files["replay.json"] = encoded(config)
    manifest: Json = {}
    for name in files:
        manifest[name] = {"bytes": len(files[name]), "sha256": digest(files[name])}
    files["manifest.json"] = encoded(manifest)
    publish(output, files, inputs)
    print("completed " + mode)
    return code


def main() -> None:
    try:
        role: str = env_get("TRANSFER_ROLE", "run")
        assert role in ["run", "sender", "receiver"], "unknown worker role"
        if role == "run":
            process_exit(run())
        worker(role)
    except Exception as error:
        logging.error(str(error))
        process_exit(2)
    return


if __name__ == "__main__":
    main()
