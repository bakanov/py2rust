"""Publish only sanitized data, numeric audit counters and hashes of output files."""

# ruff: noqa: PLC0206 - explicit subset dictionary iteration
from py2rust.stdlib import (
    Json,
    json_array,
    json_canonical,
    json_int,
    sha256_digest,
    sha256_new,
    sha256_update,
)


def render(data: bytes, audit: Json) -> dict[str, bytes]:
    lines: list[str] = [
        "Structured-log redaction",
        "Records: " + str(json_int(audit["records"])),
        "Changed records: " + str(json_int(audit["changed_records"])),
        "Matches: " + str(json_int(audit["matches"])),
    ]
    for counter in json_array(audit["rules"]):
        lines.append("Rule " + str(json_int(counter["index"])) + ": " + json_canonical(counter))
    for counter in json_array(audit["targets"]):
        lines.append("Target " + str(json_int(counter["index"])) + ": " + json_canonical(counter))
    files: dict[str, bytes] = {
        "redacted.jsonl": data,
        "audit.json": (json_canonical(audit) + "\n").encode(),
        "report.txt": ("\n".join(lines) + "\n").encode(),
    }
    manifest: Json = {}
    for name in files:
        manifest[name] = {"bytes": len(files[name]), "sha256": sha256_digest(sha256_update(sha256_new(), files[name]))}
    files["manifest.json"] = (json_canonical({"version": 1, "files": manifest}) + "\n").encode()
    return files
