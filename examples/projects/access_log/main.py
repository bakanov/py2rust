"""Read a JSON Lines file and print a JSON traffic summary."""

from analysis import Summary, summarize
from py2rust.stdlib import env_get, json_dumps, read_text


def main() -> None:
    path: str = env_get("ACCESS_LOG", "sample.jsonl")
    summary: Summary = summarize(read_text(path))
    print(
        json_dumps(
            {
                "requests": summary.requests,
                "errors": summary.errors,
                "total_bytes": summary.total_bytes,
                "max_elapsed_ms": summary.max_elapsed_ms,
                "routes": summary.routes,
            }
        )
    )
    return


if __name__ == "__main__":
    main()
