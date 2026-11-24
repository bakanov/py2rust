"""Inspect a bounded directory tree and atomically publish a readable JSON manifest."""

import sys

from configuration import load
from reporting import summarize, text_summary
from traverse import walk

from py2rust.stdlib import (
    Json,
    json_bool,
    json_int,
    json_string,
    pretty,
    write_text_atomic,
)


def main() -> None:
    config: Json = load()
    report: Json = summarize(walk(config), config)
    encoded: str = pretty(report)
    assert len(encoded.encode()) <= json_int(config["max_report_bytes"]), "report exceeds byte limit"
    write_text_atomic(json_string(config["output"]), encoded)
    print(text_summary(report))
    if not json_bool(report["complete"]):
        sys.exit(2)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


if __name__ == "__main__":
    main()
