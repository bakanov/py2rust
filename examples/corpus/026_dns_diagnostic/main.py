"""Run a DNS diagnostic batch and checkpoint readable JSON/text reports."""

from lookup import lookup
from settings import configuration

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_bool,
    json_int,
    json_string,
    pretty,
    process_exit,
    write_text_atomic,
)


def publish(report: Json) -> None:
    lines: list[str] = [
        "DNS diagnostic: " + str(len(json_array(report["results"]))) + "/" + str(json_int(report["planned"]))
    ]
    for item in json_array(report["results"]):
        lines.append(
            json_string(item["name"])
            + " "
            + json_string(item["type"])
            + ": "
            + json_string(item["status"])
            + " (attempts "
            + str(json_int(item["attempts"]))
            + ")"
        )
        for answer in json_array(item["answers"]):
            lines.append("  " + json_string(answer["address"]) + " ttl=" + str(json_int(answer["ttl"])))
        if json_string(item["status"]) == "no_response":
            lines.append("  " + json_string(item["error"]))
    state: str = "partial"
    if json_bool(report["complete"]):
        state = "complete"
    lines.append("Errors: " + str(json_int(report["errors"])) + "; " + state)
    write_text_atomic(env_get("DNS_REPORT", "dns-report.json"), pretty(report))
    write_text_atomic(env_get("DNS_TEXT", "dns-report.txt"), "\n".join(lines) + "\n")
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def main() -> None:
    policy: Json = configuration()
    results: list[Json] = []
    report: Json = {
        "server": policy["host"],
        "port": policy["port"],
        "planned": len(json_array(policy["queries"])),
        "complete": False,
        "results": results,
        "errors": 0,
    }
    publish(report)
    for item in json_array(policy["queries"]):
        result: Json = lookup(item, policy)
        result["name"] = item["name"]
        result["type"] = item["type"]
        results.append(result)
        if json_string(result["status"]) != "ok":
            report["errors"] = json_int(report["errors"]) + 1
        report["results"] = results
        publish(report)
    report["complete"] = True
    publish(report)
    print(pretty(report))
    if json_int(report["errors"]) > 0:
        process_exit(1)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


if __name__ == "__main__":
    main()
