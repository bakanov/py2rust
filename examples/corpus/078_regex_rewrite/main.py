"""Preview, apply or restore a bounded batch of literal regex replacements."""

# ruff: noqa: BLE001, LOG015, PLR1711 - boundary errors and explicit return
import logging

from documents import Document, absolute, read
from planning import Plan, prepare
from transactions import apply, restore

from py2rust.stdlib import Json, env_get, json_canonical, path_resolve, process_exit


def run() -> Json:
    mode: str = env_get("REWRITE_MODE", "preview")
    assert mode in ["preview", "apply", "restore"], "invalid rewrite mode"
    if mode == "restore":
        backup: str = absolute(env_get("REWRITE_BACKUP", ""), path_resolve("."))
        return {"mode": mode, "report": restore(backup)}
    config: Document = read(absolute(env_get("REWRITE_CONFIG", "rewrite-job.json"), path_resolve(".")), 1048576)
    plan: Plan = prepare(config, mode == "apply")
    report: Json = plan.report
    if mode == "apply":
        report = apply(plan)
    return {"mode": mode, "report": report}


def main() -> None:
    status: int = 0
    try:
        print(json_canonical(run()))
    except Exception as error:
        logging.error(str(error))
        status = 2
    process_exit(status)
    return


if __name__ == "__main__":
    main()
