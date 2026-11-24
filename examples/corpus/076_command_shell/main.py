"""A batch command shell with a reviewable plan and lossless binary capture bundles."""

# ruff: noqa: BLE001, LOG015, PLR1711, PLC0206 - top-level errors and explicit subset operations
import logging

from documents import Document, absolute, publish, read
from execution import execute
from planning import Plan, load, resolve

from py2rust.stdlib import (
    Json,
    env_get,
    json_canonical,
    json_loads,
    path_resolve,
    process_exit,
    sha256_digest,
    sha256_new,
    sha256_update,
)


def run() -> int:
    mode: str = env_get("SHELL_MODE", "plan")
    assert mode in ["plan", "run"], "invalid shell mode"
    config: Document = read(absolute(env_get("SHELL_CONFIG", "shell-job.json"), path_resolve(".")), 1048576)
    plan: Plan = load(config, json_loads(config.data.decode()))
    if mode == "plan":
        jobs: list[Json] = []
        for job in plan.jobs:
            stages: list[Json] = []
            commands: list[list[str]] = resolve(job, plan.cwd)
            for arguments in commands:
                words: list[Json] = []
                for word in arguments:
                    words.append(word)  # noqa: PERF402 - explicit str to Json conversion
                stages.append(words)
            variables: Json = {}
            for name in job.environment:
                variables[name] = job.environment[name]
            jobs.append({"name": job.name, "argv": stages, "environment": variables, "input_bytes": len(job.data)})
        print(json_canonical({"version": 1, "cwd": plan.cwd, "jobs": jobs}))
        return 0
    result: tuple[Json, dict[str, bytes], int] = execute(plan)
    report: Json = result[0]
    files: dict[str, bytes] = result[1]
    files["report.json"] = (json_canonical(report) + "\n").encode()
    files["job.json"] = config.data
    checksums: Json = {}
    for name in files:
        checksums[name] = {"bytes": len(files[name]), "sha256": sha256_digest(sha256_update(sha256_new(), files[name]))}
    files["manifest.json"] = (json_canonical({"version": 1, "files": checksums}) + "\n").encode()
    publish(plan.output, files)
    print(json_canonical(report))
    return result[2]


def main() -> None:
    status: int = 2
    try:
        status = run()
    except Exception as error:
        logging.error(str(error))
    process_exit(status)
    return


if __name__ == "__main__":
    main()
