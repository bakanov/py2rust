"""Export original, compact continuation, full rewind and fresh-layout programs with real requests."""

# ruff: noqa: PLC0206 - subset dictionary iteration
from model import display, parse, text

from py2rust.stdlib import (
    Json,
    json_array,
    json_canonical,
    sha256_digest,
    sha256_new,
    sha256_update,
)


def encoded(value: Json) -> bytes:
    return (json_canonical(value) + "\n").encode()


def digest(data: bytes) -> str:
    return sha256_digest(sha256_update(sha256_new(), data))


def summary(results: Json) -> Json:
    return results["summary"]


def program(title: Json, grid: Json, commands: list[str]) -> Json:
    result: Json = {"version": 1, "title": title, "grid": grid, "commands": commands}
    parse(result)
    return result


def request(mode: str, source: str, output: str) -> bytes:
    return encoded({"version": 1, "mode": mode, "input": source, "output": output})


def bundle(mode: str, source: Json, results: Json) -> dict[str, bytes]:
    archive: bytes = encoded({"version": 1, "source": source, "results": results})
    active: list[str] = []
    for value in json_array(results["active_commands"]):
        active.append(text(value))
    rewind: list[str] = active.copy()
    for index in range(len(active)):
        rewind.append("undo")
    lines: list[str] = [display(text(source["title"])), json_canonical(summary(results)), ""]
    for value in json_array(results["final"]["grid"]):
        lines.append(text(value))
    files: dict[str, bytes] = {
        "archive.json": archive,
        "program.json": encoded(source),
        "trace.json": encoded(results["trace"]),
        "continuation.json": encoded(program(source["title"], source["grid"], active)),
        "rewind.json": encoded(program(source["title"], source["grid"], rewind)),
        "layout.json": encoded(program(source["title"], results["final"]["grid"], [])),
        "layout.txt": ("\n".join(lines) + "\n").encode(),
        "report.json": encoded(
            {"version": 1, "mode": mode, "summary": summary(results), "archive_sha256": digest(archive)}
        ),
        "replay.json": request("verify", "archive.json", "replayed"),
        "simulate.json": request("simulate", "program.json", "simulated"),
        "continue-job.json": request("simulate", "continuation.json", "continued"),
        "rewind-job.json": request("simulate", "rewind.json", "rewound"),
        "restart-job.json": request("simulate", "layout.json", "restarted"),
    }
    manifest: Json = {}
    for name in files:
        assert len(files[name]) <= 16777216, "export byte limit"
        manifest[name] = {"bytes": len(files[name]), "sha256": digest(files[name])}
    files["manifest.json"] = encoded(manifest)
    return files
