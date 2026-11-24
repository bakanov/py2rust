"""Run bounded foreground pipelines, preserving binary streams and every stage status."""

# ruff: noqa: BLE001 - per-pipeline recovery and explicit subset operations
from planning import Plan, resolve

from py2rust.stdlib import Json, process_pipeline


def shell_status(status: int) -> int:
    if status < 0:
        return 128 - status
    return status


def execute(plan: Plan) -> tuple[Json, dict[str, bytes], int]:
    records: list[Json] = []
    files: dict[str, bytes] = {}
    total: int = 0
    final_status: int = 0
    cancelled: bool = False
    for job in plan.jobs:
        if cancelled:
            records.append({"name": job.name, "state": "skipped", "status": final_status})
            continue
        status: int = 0
        commands: list[list[str]] = []
        try:
            commands = resolve(job, plan.cwd)
            environments: list[dict[str, str]] = []
            for stage in commands:
                environments.append(job.environment.copy())
            limit: int = min(plan.max_output, 33554432 - total)
            result: tuple[list[int], bytes, list[bytes]] = process_pipeline(
                commands, environments, plan.cwd, job.data, plan.timeout, limit
            )
            statuses: list[Json] = []
            for code in result[0]:
                statuses.append(code)
                if plan.pipefail and code != 0:
                    status = shell_status(code)
            if not plan.pipefail:
                status = shell_status(result[0][-1])
            stdout: str = job.name + ".stdout"
            files[stdout] = result[1]
            total = total + len(result[1])
            errors: list[Json] = []
            for index in range(len(result[2])):
                stderr: str = job.name + "." + str(index) + ".stderr"
                files[stderr] = result[2][index]
                total = total + len(result[2][index])
                errors.append(stderr)
            records.append(
                {
                    "name": job.name,
                    "state": "finished",
                    "status": status,
                    "stages": statuses,
                    "stdout": stdout,
                    "stderr": errors,
                }
            )
        except Exception as error:
            message: str = str(error)
            status = 125
            if message == "pipeline deadline exceeded":
                status = 124
            elif message == "pipeline interrupted by signal 2":
                status = 130
                cancelled = True
            elif message == "pipeline interrupted by signal 15":
                status = 143
                cancelled = True
            records.append({"name": job.name, "state": "error", "status": status, "error": message})
        final_status = status
    report: Json = {
        "version": 1,
        "jobs": records,
        "captured_bytes": total,
        "status": final_status,
        "cancelled": cancelled,
    }
    return report, files, final_status
