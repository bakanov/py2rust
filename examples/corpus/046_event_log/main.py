"""Export complete event-log diagnostics; exit 0 for consistency, 1 for findings, 2 for fatal errors."""

import logging

from checking import scan
from documents import (
    Document,
    absolute,
    checkpoint,
    present,
    publish,
    read,
    stamp,
    unchanged,
)
from model import validate_config

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_bool,
    json_canonical,
    json_int,
    json_keys,
    json_loads,
    json_string,
    path_parent,
    path_resolve,
    pretty,
    process_exit,
)


def text_report(report: Json) -> str:
    lines: list[str] = [
        "Event-log consistency report",
        "Status: " + ("consistent" if json_bool(report["consistent"]) else "inconsistent"),
        "Records: " + str(json_int(report["records"])),
        "Checked: " + str(json_int(report["checked"])),
        "Input SHA-256: " + json_string(report["input_sha256"]),
    ]
    for name in json_keys(report["streams"]):
        lines.append("Stream " + json_canonical(name) + ": " + json_canonical(report["streams"][name]))
    for record in json_array(report["diagnostics"]):
        for problem in json_array(record["issues"]):
            lines.append("Line " + str(json_int(record["line"])) + " " + json_canonical(problem))
    return "\n".join(lines) + "\n"


def run() -> int:
    mode: str = env_get("EVENT_MODE", "preview")
    assert mode in ["preview", "write"], "invalid event mode"
    path: str = absolute(env_get("EVENT_CONFIG", "event-job.json"), path_resolve("."))
    configuration: Document = read(path, 65536)
    config: Json = json_loads(configuration.data.decode())
    allowed: set[tuple[str, str]] = validate_config(config)
    parent: str = path_parent(path)
    output: str = absolute(json_string(config["output"]), parent)
    assert not present(output), "output directory already exists"
    source: str = absolute(json_string(config["input"]), parent)
    original: Document = Document(source, stamp(source), b"")
    size: int = json_int(original.stamp["size"])
    assert size <= json_int(config["max_input_bytes"]), "input byte limit exceeded"
    report: Json = scan(source, config, allowed, size)
    rendered: str = pretty(report) + "\n"
    text: str = text_report(report)
    assert len(rendered.encode()) <= 16777216 and len(text.encode()) <= 16777216, "diagnostic report exceeds 16 MiB"
    documents: list[Document] = [configuration, original]
    checkpoint("validated")
    unchanged(documents)
    if mode == "write":
        publish(output, {"report.json": rendered, "report.txt": text}, documents)
    print(rendered)
    return 0 if json_bool(report["consistent"]) else 1


def main() -> None:
    result: int = 2
    try:
        result = run()
    except Exception as error:  # noqa: BLE001 - fatal CLI errors use exit 2
        logging.error(str(error))  # noqa: LOG015 - supported logging facade
    process_exit(result)
    return  # noqa: PLR1711


if __name__ == "__main__":
    main()
