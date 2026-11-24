"""Sort complete JSONL datasets under an enforced memory limit and publish an atomic bundle."""

# ruff: noqa: PLR1711, BLE001, LOG015 - explicit returns and recoverable errors

import logging

from model import Job, Run
from runs import generate, merge, run_path
from storage import (
    checkpoint,
    cleanup,
    configuration,
    initialize,
    prepare,
    present,
    stamp,
)

from py2rust.stdlib import (
    Json,
    env_get,
    file_lock,
    file_open,
    file_sync,
    file_write,
    json_equal,
    json_int,
    limit_address_space,
    mkdir_new,
    path_join,
    path_parent,
    pretty,
    process_exit,
    remove_file,
    rename_no_replace,
    sync_directory,
)


def sort(job: Job, stamps: list[Json], recovered: int, memory: int) -> Json:
    created: tuple[list[Run], Json] = generate(job, stamps)
    active: list[Run] = created[0]
    report: Json = created[1]
    identifier: int = len(active)
    report["initial_runs"] = len(active)
    passes: int = 0
    checkpoint("runs-ready")
    while len(active) > 1:
        following: list[Run] = []
        for start in range(0, len(active), job.fan_in):
            group: list[Run] = active[start : start + job.fan_in]
            if len(group) == 1:
                following.append(group[0])
            else:
                combined: Run = merge(job, group, run_path(job, identifier), False)
                identifier = identifier + 1
                following.append(combined)
                for original in group:
                    remove_file(original.path)
        active = following
        passes = passes + 1
        checkpoint("pass:" + str(passes))
    bundle: str = path_join(job.workspace, "bundle")
    mkdir_new(bundle)
    result: Run = merge(job, active, path_join(bundle, "sorted.jsonl"), True)
    assert result.count == json_int(report["rows"]), "final row count differs from input"
    report["merge_passes"] = passes
    report["output_bytes"] = result.size
    report["output_sha256"] = result.digest
    report["memory_limit_bytes"] = memory
    report["recovered_files"] = recovered
    with file_open(path_join(bundle, "report.json"), "x+b") as handle:
        file_write(handle, (pretty(report) + "\n").encode())
        file_sync(handle)
    sync_directory(bundle)
    checkpoint("ready")
    for position in range(len(job.inputs)):
        assert json_equal(stamps[position], stamp(job.inputs[position])), "input changed before publication"
    assert json_equal(job.config_stamp, stamp(job.config_path)), "configuration changed before publication"
    rename_no_replace(bundle, job.output)
    checkpoint("published")
    sync_directory(path_parent(job.output))
    return report


def run() -> None:
    job: Job = configuration()
    mode: str = env_get("SORT_MODE", "sort")
    assert mode in ["sort", "cleanup"], "invalid sorter mode"
    if mode == "sort":
        assert not present(job.output), "output already exists"
    memory: int = limit_address_space(job.memory_bytes)
    inputs: list[Json] = []
    total_bytes: int = 0
    if mode == "sort":
        for path in job.inputs:
            metadata: Json = stamp(path)
            total_bytes = total_bytes + json_int(metadata["size"])
            assert total_bytes <= 1073741824, "inputs exceed 1 GiB"
            inputs.append(metadata)
    report: Json = {}
    prepare(job)
    with file_lock(path_join(job.workspace, ".lock")) as _lock:
        initialize(job)
        recovered: int = cleanup(job)
        if mode == "cleanup":
            print(pretty({"removed_files": recovered}))
            return
        try:
            report = sort(job, inputs, recovered, memory)
        except Exception:
            cleanup(job)
            raise
        cleanup(job)
    print(pretty(report))
    return


def main() -> None:
    try:
        run()
    except Exception as error:
        logging.error(str(error))
        process_exit(2)
    return


if __name__ == "__main__":
    main()
