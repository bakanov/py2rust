"""Portable index snapshots, runnable replay requests, verified locks and branch explanations."""

# ruff: noqa: I001, PLC0206 - compact imports and typed dictionary iteration
from configuration import Job
from py2rust.stdlib import (
    Json, json_array, json_canonical, json_keys, json_string, sha256_digest, sha256_new, sha256_update,
)


def digest(data: bytes) -> str:
    return sha256_digest(sha256_update(sha256_new(), data))


def render(job: Job, outcome: Json) -> dict[str, bytes]:
    status: str = json_string(outcome["status"])
    report: Json = {"version": 1, "index_sha256": digest(job.index.data), "roots": job.root_text, "outcome": outcome}
    lines: list[str] = ["Package constraint resolver: " + status]
    lines.append(
        "A conflict explains one branch; retained conflicts are not claimed to be a minimal unsatisfiable core."
    )
    lines.append(json_canonical(outcome["statistics"]))
    for name in sorted(json_keys(outcome["selected"])):
        lines.append(name + " = " + json_string(outcome["selected"][name]))
    for item in json_array(outcome["conflicts"]):
        lines.append("Conflict: " + json_canonical(item))
    for item in json_array(outcome["errors"]):
        lines.append("Lock error: " + json_canonical(item))
    files: dict[str, bytes] = {
        "index.json": job.index.data,
        "report.json": (json_canonical(report) + "\n").encode(),
        "report.txt": ("\n".join(lines) + "\n").encode(),
    }
    replay: Json = {
        "version": 1,
        "mode": "verify",
        "index": "index.json",
        "output": "replayed",
        "lock": "input-lock.json" if status == "invalid_lock" else "lock.json",
    }
    if job.mode == "resolve":
        replay = {
            "version": 1,
            "mode": "resolve",
            "index": "index.json",
            "output": "replayed",
            "roots": job.root_text,
            "max_steps": job.config["max_steps"],
            "max_conflicts": job.config["max_conflicts"],
        }
    files["replay.json"] = (json_canonical(replay) + "\n").encode()
    if status in ["resolved", "valid_lock"]:
        lock: Json = {
            "version": 1,
            "index_sha256": digest(job.index.data),
            "roots": job.root_text,
            "packages": outcome["selected"],
        }
        files["lock.json"] = (json_canonical(lock) + "\n").encode()
        files["verify.json"] = (
            json_canonical(
                {"version": 1, "mode": "verify", "index": "index.json", "output": "verified", "lock": "lock.json"}
            )
            + "\n"
        ).encode()
    elif job.mode == "verify":
        files["input-lock.json"] = job.inputs[-1].data
    manifest: Json = {}
    total: int = 0
    for name in files:
        total = total + len(files[name])
        assert total <= 4194304, "report bundle exceeds 4 MiB"
        manifest[name] = {"bytes": len(files[name]), "sha256": digest(files[name])}
    files["manifest.json"] = (json_canonical(manifest) + "\n").encode()
    return files
