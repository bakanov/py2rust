"""Validate a complete application's environment and publish only redacted configuration reports."""

# ruff: noqa: BLE001, LOG015, PLR1711 - generic fatal boundary and explicit returns
import logging

from documents import Document, absolute, present, publish, read
from evaluation import evaluate
from reports import bundle, describe, render
from schema import exact, load, order

from py2rust.stdlib import (
    Json,
    env_get,
    json_bool,
    json_canonical,
    json_int,
    json_loads_unique,
    json_string,
    path_parent,
    path_resolve,
    process_exit,
)


def run() -> int:
    request: Document = read(absolute(env_get("SETTINGS_CONFIG", "settings-job.json"), path_resolve(".")), 65536)
    config: Json = json_loads_unique(request.data.decode())
    exact(config, ["version", "schema", "output"])
    assert json_int(config["version"]) == 1, "unsupported request version"
    base: str = path_parent(request.path)
    output: str = absolute(json_string(config["output"]), base)
    assert not present(output), "output already exists"
    document: Document = read(absolute(json_string(config["schema"]), base), 262144)
    fields: Json = load(json_loads_unique(document.data.decode()))
    names: list[str] = order(fields)
    states: Json = evaluate(fields, names)
    report: Json = render(fields, states)
    publish(output, bundle(report, describe(fields), document.path), [request, document])
    print(json_canonical(report["summary"]))
    return 0 if json_bool(report["valid"]) else 1


def main() -> None:
    try:
        process_exit(run())
    except Exception:
        logging.error("configuration request rejected")
        process_exit(2)
    return


if __name__ == "__main__":
    main()
