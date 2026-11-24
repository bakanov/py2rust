"""Run an arithmetic script against a durable session, preserving state after expression errors."""

# ruff: noqa: BLE001, LOG015, PLC0206, PLR1711 - explicit returns and supported subset operations
import logging

from documents import Document, absolute, checkpoint, present, publish, read, unchanged
from evaluation import Statement, statement
from lexing import Token, identifier, tokenize

from py2rust.stdlib import (
    Json,
    env_get,
    json_canonical,
    json_int,
    json_keys,
    json_kind,
    json_loads,
    json_string,
    path_parent,
    path_resolve,
    pretty,
    process_exit,
    sha256_digest,
    sha256_new,
    sha256_update,
)


def exact(value: Json, fields: list[str]) -> None:
    assert json_keys(value) == sorted(fields), "unexpected object fields"
    return


def run() -> None:
    mode: str = env_get("CALC_MODE", "preview")
    assert mode in ["preview", "write"], "invalid calculator mode"
    config: Document = read(absolute(env_get("CALC_CONFIG", "calculator-job.json"), path_resolve(".")), 65536)
    job: Json = json_loads(config.data.decode())
    exact(job, ["state", "script", "output"])
    output: str = absolute(json_string(job["output"]), path_parent(config.path))
    assert not present(output), "output directory already exists"
    state: Document = read(absolute(json_string(job["state"]), path_parent(config.path)), 65536)
    script: Document = read(absolute(json_string(job["script"]), path_parent(config.path)), 1048576)
    initial: Json = json_loads(state.data.decode())
    exact(initial, ["version", "variables"])
    assert json_int(initial["version"]) == 1, "unsupported session version"
    names: list[str] = json_keys(initial["variables"])
    assert len(names) <= 256, "session exceeds 256 variables"
    variables: dict[str, Json] = {}
    for name in names:
        assert identifier(name), "invalid session variable name"
        value: Json = initial["variables"][name]
        assert json_kind(value) == "number", "session variables must be numbers"
        variables[name] = value
    text: str = script.data.decode().replace("\r\n", "\n")
    lines: list[str] = text.split("\n")
    assert len(lines) <= 256, "script exceeds 256 lines"
    records: list[Json] = []
    errors: int = 0
    for index in range(len(lines)):
        line: str = lines[index]
        try:
            tokens: list[Token] = tokenize(line)
            if len(tokens) > 1:
                result: Statement = statement(tokens, variables)
                if result.binding != "":
                    variables[result.binding] = result.value
                records.append(
                    {
                        "line": index + 1,
                        "source": line,
                        "status": "ok",
                        "binding": result.binding,
                        "value": result.value,
                    }
                )
        except Exception as error:
            records.append({"line": index + 1, "source": line, "status": "error", "error": str(error)})
            errors = errors + 1
    values: Json = {}
    for name in variables:
        values[name] = variables[name]
    report: Json = {"version": 1, "records": records, "errors": errors, "variables": values}
    files: dict[str, bytes] = {
        "state.json": (json_canonical({"version": 1, "variables": values}) + "\n").encode(),
        "initial-state.json": state.data,
        "script.txt": script.data,
        "report.json": (json_canonical(report) + "\n").encode(),
    }
    checksums: Json = {}
    total: int = 0
    for name in files:
        total = total + len(files[name])
        assert total <= 4194304, "exports exceed 4 MiB"
        checksums[name] = {"bytes": len(files[name]), "sha256": sha256_digest(sha256_update(sha256_new(), files[name]))}
    files["manifest.json"] = (pretty({"version": 1, "files": checksums}) + "\n").encode()
    documents: list[Document] = [config, state, script]
    checkpoint("validated")
    unchanged(documents)
    if mode == "write":
        publish(output, files, documents)
    print(json_canonical(report))
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
