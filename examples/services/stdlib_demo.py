import logging
import time
from enum import Enum

from py2rust.stdlib import (
    DateTime,
    Json,
    datetime_add_seconds,
    datetime_iso,
    datetime_parse,
    json_dumps,
    json_int,
    json_loads,
    list_dir,
    log_configure,
    mkdir_all,
    path_join,
    pretty,
    read_text,
    regex_findall,
    write_text,
)


class State(Enum):
    READY = "ready"
    DONE = "done"


def run() -> None:
    log_configure(logging.INFO)
    start: float = time.monotonic()
    state: State = State.READY
    label: str = "  Hello 世界  ".strip()
    words: list[str] = label.split()
    words.append("service")
    labels: set[str] = {"http", "json"}
    labels.add("rust")
    counts: dict[str, int] = {"labels": len(labels), "words": len(words)}
    identity: tuple[int, str] = (1, state.value)
    stamp: DateTime = datetime_parse("2024-02-29T23:59:59Z")
    stamp = datetime_add_seconds(stamp, 1)
    tokens: list[str] = regex_findall(r"[a-z]+", "http/1 json/2")
    report: Json = {
        "title": " / ".join(words),
        "counts": counts,
        "identity": identity,
        "timestamp": datetime_iso(stamp),
        "tokens": tokens,
    }
    directory: str = "build/service-demo-output"
    mkdir_all(directory)
    output: str = path_join(directory, "report.json")
    write_text(output, json_dumps(report))
    loaded: Json = json_loads(read_text(output))
    assert json_int(loaded["counts"]["labels"]) == 3
    assert "report.json" in list_dir(directory)
    time.sleep(0.001)
    assert time.monotonic() >= start
    state = State.DONE
    logging.info(state.value + ": " + output)  # noqa: LOG015
    print(pretty(loaded))


if __name__ == "__main__":
    run()
