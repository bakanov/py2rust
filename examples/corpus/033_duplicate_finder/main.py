"""Find exact duplicates and optionally export a plan for human review."""

import sys

from configuration import load
from content import checkpoint
from grouping import analyze
from reporting import plan, report
from traverse import scan

from py2rust.stdlib import (
    Json,
    json_array,
    json_bool,
    json_int,
    json_string,
    pretty,
    write_text_atomic,
)


def main() -> None:
    config: Json = load()
    walk: Json = scan(config)
    checkpoint("scanned")
    result: Json = report(walk, analyze(walk, config), config)
    encoded: str = pretty(result)
    assert len(encoded.encode()) <= json_int(config["max_report_bytes"]), "report exceeds byte limit"
    plan_text: str = pretty(plan(result))
    assert len(plan_text.encode()) <= json_int(config["max_report_bytes"]), "plan exceeds byte limit"
    write_text_atomic(json_string(config["report"]), encoded)
    if json_string(config["plan"]) != "":
        write_text_atomic(json_string(config["plan"]), plan_text)
    print(
        pretty(
            {
                "id": result["id"],
                "complete": result["complete"],
                "groups": len(json_array(result["groups"])),
                "reclaimable_logical_bytes": result["reclaimable_logical_bytes"],
            }
        )
    )
    if not json_bool(result["complete"]):
        sys.exit(2)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


if __name__ == "__main__":
    main()
