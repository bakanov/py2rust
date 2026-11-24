"""Bounded live refresh, per-frame terminal resizing, plain fallback and signal cleanup."""

# ruff: noqa: PLR1711 - explicit returns
from documents import read
from model import text
from records import event, observe

from py2rust.stdlib import (
    Json,
    ProcessPool,
    json_array,
    json_bool,
    json_int,
    process_pool,
    process_pool_close,
    process_pool_signal,
    sleep,
    terminal_info,
    terminal_write,
)


def show(record: Json, interactive: bool) -> None:
    lines: list[str] = []
    for line in json_array(record["lines"]):
        lines.append(text(line))
    terminal_write(
        ("\x1b[H\x1b[2J" if interactive else "")
        + ("\r\n" if interactive else "\n").join(lines)
        + ("" if interactive else "\n\n")
    )
    return


def watch(path: str, config: Json) -> tuple[list[Json], Json, int]:
    signals: ProcessPool = process_pool()
    interactive: bool = json_bool(terminal_info()["ansi"])
    state: Json = None
    events: list[Json] = []
    interrupted: int = 0
    try:
        if interactive:
            terminal_write("\x1b[?1049h\x1b[?25l")
        count: int = json_int(config["refreshes"])
        for index in range(count):
            interrupted = process_pool_signal(signals)
            if interrupted != 0:
                break
            raw: bytes = b""
            readable: bool = True
            try:
                raw = read(path, 65536).data
            except Exception:  # noqa: BLE001 - a missing or changing snapshot is a recoverable observation
                readable = False
            observed: tuple[Json, str] = observe(state, raw, readable)
            state = observed[0]
            info: Json = terminal_info()
            width: int = json_int(config["columns"])
            height: int = 132
            if json_bool(info["isatty"]):
                width = min(width, max(1, json_int(info["columns"]) - 1))
            if interactive:
                height = min(height, max(1, json_int(info["rows"]) - 1))
            record: Json = event(raw, readable, state, observed[1], width, height, index + 1, count)
            events.append(record)
            show(record, interactive)
            if index + 1 < count:
                remaining: int = json_int(config["interval_ms"])
                while remaining > 0 and process_pool_signal(signals) == 0:
                    delay: int = min(remaining, 20)
                    sleep(float(delay) / 1000.0)
                    remaining = remaining - delay
        interrupted = process_pool_signal(signals)
    finally:
        try:
            if interactive:
                terminal_write("\x1b[?25h\x1b[?1049l")
        finally:
            process_pool_close(signals)
    return (events, state, interrupted)
