"""Hash-bound edits, independent application verification and portable source/report bundles."""

# ruff: noqa: I001, PLC0206 - compact imports and typed dictionary iteration
from configuration import Job
from headers import analyze
from py2rust.stdlib import (
    Json, base64_decode, json_array, json_bool, json_canonical, json_equal, json_int, json_string, sha256_digest,
    sha256_new, sha256_update,
)


def digest(data: bytes) -> str:
    return sha256_digest(sha256_update(sha256_new(), data))


def encoded(value: Json) -> bytes:
    return (json_canonical(value) + "\n").encode()


def edited(data: bytes, edit: Json) -> bytes:
    if edit is None:
        return data
    start: int = json_int(edit["start"])
    end: int = json_int(edit["end"])
    assert 0 <= start <= end <= len(data), "invalid generated edit span"
    assert data[start:end] == base64_decode(json_string(edit["removed"])), "removed bytes do not match"
    return data[:start] + base64_decode(json_string(edit["replacement"])) + data[end:]


def build(job: Job) -> tuple[dict[str, bytes], Json]:
    files: dict[str, bytes] = {}
    rows: list[Json] = []
    patches: list[Json] = []
    replay_files: list[Json] = []
    corrected_files: list[Json] = []
    grouped: dict[str, list[Json]] = {}
    violations: int = 0
    remaining: int = 0
    changed: int = 0
    manual: int = 0
    corrected_bytes: int = 0
    offset: int = 1 if job.mode == "check" else 2
    for index in range(len(job.entries)):
        entry: Json = job.entries[index]
        name: str = json_string(entry["name"])
        style: str = json_string(entry["style"])
        data: bytes = job.inputs[index + offset].data
        analysis: Json = analyze(data, style, job.policy)
        after: bytes = edited(data, analysis["edit"])
        corrected_bytes = corrected_bytes + len(after)
        assert len(after) <= 65536 and corrected_bytes <= 1048576, "corrected source byte budget exceeded"
        before_hash: str = digest(data)
        after_hash: str = digest(after)
        if job.mode == "apply":
            assert json_string(entry["before_sha256"]) == before_hash, "source hash changed: " + name
            assert json_string(entry["after_sha256"]) == after_hash, "result hash mismatch: " + name
            assert json_equal(entry["edit"], analysis["edit"]), "edit differs from declared header policy: " + name
            files["files/" + name] = after
        rechecked: Json = analyze(after, style, job.policy)
        if not json_bool(analysis["manual"]):
            assert len(json_array(rechecked["issues"])) == 0, "generated header did not pass recheck"
        findings: list[Json] = json_array(analysis["issues"])
        left: list[Json] = json_array(rechecked["issues"]) if job.mode == "apply" else findings
        violations = violations + len(findings)
        remaining = remaining + len(left)
        changed = changed + (1 if after != data else 0)
        manual = manual + (1 if json_bool(analysis["manual"]) else 0)
        for item in findings:
            kind: str = json_string(item["kind"])
            if kind not in grouped:
                grouped[kind] = []
            grouped[kind].append({"file": name, "line": item["line"]})
        rows.append(
            {
                "name": name,
                "issues": findings,
                "remaining": left,
                "manual": analysis["manual"],
                "before_sha256": before_hash,
                "after_sha256": after_hash,
            }
        )
        files["sources/" + name] = data
        patches.append(
            {
                "name": name,
                "path": "sources/" + name,
                "style": style,
                "before_sha256": before_hash,
                "after_sha256": after_hash,
                "edit": analysis["edit"],
            }
        )
        replay_files.append({"name": name, "path": "sources/" + name, "style": style})
        corrected_files.append({"name": name, "path": "files/" + name, "style": style})
    summary: Json = {
        "files": len(rows),
        "violations": violations,
        "remaining": remaining,
        "changed_files": changed,
        "manual_files": manual,
    }
    report: Json = {
        "version": 1,
        "mode": job.mode,
        "policy": job.policy,
        "files": rows,
        "groups": grouped,
        "summary": summary,
    }
    files["report.json"] = encoded(report)
    lines: list[str] = ["Source header check: " + json_canonical(summary)]
    for row in rows:
        for item in json_array(row["issues"]):
            lines.append(
                json_string(row["name"]) + ":" + str(json_int(item["line"])) + ": " + json_string(item["kind"])
            )
    files["report.txt"] = ("\n".join(lines) + "\n").encode()
    files["patches.json"] = encoded({"version": 1, "policy": job.policy, "files": patches})
    files["apply.json"] = encoded({"version": 1, "mode": "apply", "output": "applied", "patches": "patches.json"})
    files["replay.json"] = encoded(
        {"version": 1, "mode": "check", "output": "replayed", "policy": job.policy, "files": replay_files}
    )
    if job.mode == "apply":
        files["recheck.json"] = encoded(
            {"version": 1, "mode": "check", "output": "rechecked", "policy": job.policy, "files": corrected_files}
        )
    manifest: Json = {}
    total: int = 0
    for name in files:
        total = total + len(files[name])
        assert total <= 8388608, "report byte budget exceeded"
        manifest[name] = {"bytes": len(files[name]), "sha256": digest(files[name])}
    files["manifest.json"] = encoded(manifest)
    return (files, summary)
