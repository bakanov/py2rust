"""Audit a bounded same-origin site and atomically save a machine-readable report."""

import sys

from crawl import crawl, report
from model import configuration

from py2rust.stdlib import (
    Json,
    json_bool,
    json_dumps,
    json_int,
    json_string,
    pretty,
    write_text_atomic,
)


def main() -> None:
    policy: Json = configuration()
    result: Json = report(policy, crawl(policy))
    write_text_atomic(json_string(policy["report"]), pretty(result))
    summary: Json = result["summary"]
    print(json_dumps(summary))
    if json_int(summary["broken_pages"]) > 0 or json_int(summary["broken_links"]) > 0:
        sys.exit(1)
    if not json_bool(summary["complete"]):
        sys.exit(2)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


if __name__ == "__main__":
    main()
