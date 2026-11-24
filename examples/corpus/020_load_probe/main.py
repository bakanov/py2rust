"""Execute a finite HTTP schedule; publish results only after every worker has joined."""

import sys

from config import configuration, lookup
from report import csv, result
from worker import elapsed, perform

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_dumps,
    json_int,
    json_string,
    monotonic,
    parallel_map,
    path_exists,
    path_is_symlink,
    path_join,
    path_name,
    path_parent,
    path_resolve,
    path_same,
    pretty,
    write_text_atomic,
)


def output_path() -> str:
    return env_get("LOAD_REPORT", "load-report.json")


def validate_paths() -> None:
    paths: list[str] = [output_path(), output_path() + ".csv", env_get("LOAD_CONFIG", "load.json")]
    for name in ["LOAD_CANCEL", "LOAD_CA"]:
        path: str = env_get(name, "")
        if path != "":
            paths.append(path)
    canonical: list[str] = []
    for index in range(len(paths)):
        value: str = paths[index]
        if index < 2:
            assert not path_is_symlink(value), "report outputs must not be symlinks"
        normalized: str = path_join(path_resolve(path_parent(value)), path_name(value))
        assert normalized not in canonical, "report, configuration or cancellation paths overlap"
        canonical.append(normalized)
        for previous in range(index):
            if path_exists(value) and path_exists(paths[previous]):
                assert not path_same(value, paths[previous]), "report, configuration or cancellation paths alias"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def main() -> None:
    validate_paths()
    policy: Json = configuration()
    jobs: list[Json] = json_array(policy["jobs"])
    write_text_atomic(output_path(), pretty({"format": 1, "phase": "running", "plan": jobs}))
    tasks: list[Json] = []
    for job in jobs:
        tasks.append(
            {
                "job": job,
                "target": lookup(policy, json_string(job["target"])),
                "origin": 0.0,
                "duration_ms": policy["duration_ms"],
                "max_lag_ms": policy["max_lag_ms"],
                "timeout_ms": policy["timeout_ms"],
                "max_body": policy["max_body"],
                "cancel_file": env_get("LOAD_CANCEL", ""),
                "ca_file": env_get("LOAD_CA", ""),
            }
        )
    began: float = monotonic()
    for index in range(len(tasks)):
        task: Json = tasks[index]
        task["origin"] = began
        tasks[index] = task
    samples: list[Json] = parallel_map(perform, tasks, json_int(policy["concurrency"]))
    report: Json = result(policy, samples, elapsed(began))
    assert len(samples) == len(jobs), "worker results are missing"
    validate_paths()
    write_text_atomic(output_path() + ".csv", csv(samples))
    write_text_atomic(output_path(), pretty(report))
    print(json_dumps(report["overall"]["counts"]))
    state: str = json_string(report["status"])
    if state == "incomplete":
        sys.exit(2)
    if state == "failed":
        sys.exit(1)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


if __name__ == "__main__":
    main()
