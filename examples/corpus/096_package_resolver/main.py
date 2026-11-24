"""Resolve a local dependency graph or verify a complete lock without executing package code."""

# ruff: noqa: I001, BLE001, LOG015, PLR1711 - compact imports and application boundary
import logging
from configuration import Job, load
from documents import absolute, publish, read
from reports import digest, render
from solving import solve, verify
from py2rust.stdlib import (
    Json, env_get, json_int, json_keys, json_string, path_resolve, process_exit,
)


def evaluate(job: Job) -> Json:
    if job.mode == "resolve":
        outcome: Json = solve(
            job.packages, job.roots, json_int(job.config["max_steps"]), json_int(job.config["max_conflicts"])
        )
        outcome["errors"] = []
        if json_string(outcome["status"]) == "resolved":
            choices: dict[str, str] = {}
            for name in json_keys(outcome["selected"]):
                choices[name] = json_string(outcome["selected"][name])
            assert len(verify(job.packages, job.roots, choices)) == 0, "internal solution verification failed"
        return outcome
    errors: list[Json] = verify(job.packages, job.roots, job.choices)
    if job.lock_hash != digest(job.index.data):
        errors.append({"kind": "index_digest"})
    return {
        "status": "valid_lock" if len(errors) == 0 else "invalid_lock",
        "selected": job.choices,
        "statistics": {"states": 0, "conflicts": 0, "recorded_conflicts": 0, "pending_states": 0},
        "conflicts": [],
        "next_state": None,
        "errors": errors,
    }


def run() -> int:
    job: Job = load(read(absolute(env_get("RESOLVER_CONFIG", "resolver-job.json"), path_resolve(".")), 65536))
    outcome: Json = evaluate(job)
    publish(job.output, render(job, outcome), job.inputs)
    status: str = json_string(outcome["status"])
    print(status)
    if status == "budget_exhausted":
        return 3
    return 0 if status in ["resolved", "valid_lock"] else 1


def main() -> None:
    try:
        process_exit(run())
    except Exception as error:
        logging.error(str(error))
        process_exit(2)
    return


if __name__ == "__main__":
    main()
