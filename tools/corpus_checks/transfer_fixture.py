"""Independent byte, statistics and comparison oracles; external native failure fixtures."""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import statistics
import subprocess
from pathlib import Path


def canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def case(name: str = "sample", size: int = 257, seed: int = 17, **changes: int) -> dict:
    return {"id": name, "size": size, "seed": seed, "send_chunk": 7, "receive_chunk": 11, "timeout_ms": 3000} | changes


def payload(row: dict) -> bytes:
    return bytes((offset * 31 + row["seed"]) % 256 for offset in range(row["size"]))


def worker(row: dict, role: str, elapsed: int = 1) -> dict:
    return {"version": 1, "role": role, "bytes": row["size"], "sha256": digest(payload(row)), "elapsed_us": elapsed}


def aggregates(cases: list[dict], runs: list[dict], repetitions: int) -> dict:
    output = {}
    for row in cases:
        good = [r for r in runs if r["case"] == row["id"] and r["status"] == "ok"]
        times = {
            "wall_us": [r["wall_us"] for r in good],
            "sender_us": [r["sender"]["elapsed_us"] for r in good],
            "receiver_us": [r["receiver"]["elapsed_us"] for r in good],
        }
        result = {"successful": len(good), "requested": repetitions}
        result.update({name: int(statistics.median(values)) if values else None for name, values in times.items()})
        for role in ["sender", "receiver"]:
            duration = result[role + "_us"]
            result[role + "_Bps"] = row["size"] * 1_000_000 // duration if duration is not None else None
        output[row["id"]] = result
    return output


def recorded(cases: list[dict] | None = None, times: list[int] | None = None) -> dict:
    cases = copy.deepcopy(cases if cases is not None else [case()])
    times = [301, 100, 500, 300] if times is None else times
    runs = []
    for row in cases:
        for trial, elapsed in enumerate(times, 1):
            runs.append(
                {
                    "case": row["id"],
                    "trial": trial,
                    "status": "ok",
                    "phase": "reports",
                    "error": "",
                    "sender": worker(row, "sender", elapsed // 2),
                    "receiver": worker(row, "receiver", elapsed // 3),
                    "wall_us": elapsed,
                }
            )
    return {
        "version": 1,
        "kind": "benchmark",
        "cases": cases,
        "repetitions": len(times),
        "workers": {"sender": ["/independent/sender"], "receiver": ["/independent/receiver"]},
        "runs": runs,
        "statistics": aggregates(cases, runs, len(times)),
    }


def comparison(before: dict, after: dict) -> list[dict]:
    first = {row["id"]: row for row in before["cases"]}
    second = {row["id"]: row for row in after["cases"]}
    old = aggregates(before["cases"], before["runs"], before["repetitions"])
    new = aggregates(after["cases"], after["runs"], after["repetitions"])
    rows = []
    for name in sorted(first.keys() | second.keys()):
        change = None
        if name not in first:
            status = "missing_baseline"
        elif name not in second:
            status = "missing_candidate"
        elif first[name] != second[name]:
            status = "incompatible"
        elif old[name]["successful"] != old[name]["requested"] or new[name]["successful"] != new[name]["requested"]:
            status = "unavailable"
        else:
            status = "comparable"
            change = (new[name]["wall_us"] - old[name]["wall_us"]) * 1_000_000 // old[name]["wall_us"]
        rows.append(
            {
                "case": name,
                "status": status,
                "wall_change_ppm": change,
                "baseline": old.get(name),
                "candidate": new.get(name),
            }
        )
    return rows


SOURCE = r"""
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
int main(int argc, char **argv) {
    if (argc != 5) return 119;
    fputs(argv[1], stdout); fflush(stdout);
    fputs(argv[2], stderr); fflush(stderr);
    long ms = strtol(argv[3], NULL, 10);
    struct timespec delay = {ms/1000, (ms%1000)*1000000};
    nanosleep(&delay, NULL);
    return atoi(argv[4]);
}
"""


def build_reporter(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    source = root / "reporter.c"
    binary = root / "reporter"
    source.write_text(SOURCE)
    compiler = shutil.which("cc")
    assert compiler is not None
    subprocess.run(
        [compiler, "-std=c11", "-Wall", "-Wextra", "-Werror", "-O2", str(source), "-o", str(binary)],
        check=True,
        capture_output=True,
    )
    return binary.resolve()
