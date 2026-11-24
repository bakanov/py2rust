"""Readable balances, retained order states, accepted audit history and portable snapshot continuation."""

# ruff: noqa: PLC0206 - explicit iteration
from ledger import digest, encoded
from model import balances

from py2rust.stdlib import (
    Json,
    json_canonical,
    json_int,
    json_keys,
    json_string,
)


def bundle(mode: str, before: int, ledger: Json, outcomes: list[Json], data: bytes, changed: bool) -> dict[str, bytes]:
    counts: Json = {"accepted": 0, "duplicate": 0, "rejected": 0}
    for row in outcomes:
        status: str = json_string(row["status"])
        counts[status] = json_int(counts[status]) + 1
    stock: Json = balances(ledger["state"])
    report: Json = {
        "version": 1,
        "mode": mode,
        "before_revision": before,
        "revision": ledger["revision"],
        "head": ledger["head"],
        "changed_store": changed,
        "snapshot_sha256": digest(data),
        "summary": counts,
        "balances": stock,
        "orders": ledger["state"]["orders"],
        "outcomes": outcomes,
    }
    lines: list[str] = [
        "Inventory ledger revision " + str(json_int(ledger["revision"])) + ": " + json_canonical(counts)
    ]
    for item in sorted(json_keys(stock)):
        lines.append(item + ": " + json_canonical(stock[item]))
    for name in sorted(json_keys(ledger["state"]["orders"])):
        lines.append("order " + name + ": " + json_canonical(ledger["state"]["orders"][name]))
    for row in outcomes:
        lines.append(json_canonical(row))
    files: dict[str, bytes] = {
        "ledger.json": data,
        "report.json": encoded(report),
        "report.txt": ("\n".join(lines) + "\n").encode(),
        "replay.json": encoded({"version": 1, "mode": "verify", "store": "ledger.json", "output": "replayed"}),
        "continue.json": encoded(
            {
                "version": 1,
                "mode": "apply",
                "store": "ledger.json",
                "output": "continued",
                "items": ledger["items"],
                "expected_revision": ledger["revision"],
                "operations": [],
            }
        ),
    }
    manifest: Json = {}
    for name in files:
        assert len(files[name]) <= 2097152, "output document budget exceeded"
        manifest[name] = {"bytes": len(files[name]), "sha256": digest(files[name])}
    files["manifest.json"] = encoded(manifest)
    return files
