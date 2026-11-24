"""Read-only synchronization planning; output documents are the only writes."""

from baseline import read
from documents import checksum, load
from dry_run import simulate
from planning import plan
from trees import output_guard, scan, unchanged

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_equal,
    json_string,
    path_exists,
    pretty,
    sleep,
    write_text_atomic,
)


def main() -> None:
    config: Json = load()
    mode: str = env_get("SYNC_MODE", "plan")
    assert mode in ["plan", "baseline"], "mode must be plan or baseline"
    roots: list[str] = [json_string(config["source"]), json_string(config["destination"])]
    left: tuple[dict[str, Json], dict[str, Json], list[str]] = scan(roots[0], config)
    right: tuple[dict[str, Json], dict[str, Json], list[str]] = scan(roots[1], config)
    protected: list[str] = left[2]
    protected.extend(right[2])
    output: str = json_string(config["plan"])
    body: Json = {}
    if mode == "baseline":
        assert json_equal(left[0], right[0]), "baseline requires identical included trees"
        body = {
            "format": 1,
            "source": roots[0],
            "destination": roots[1],
            "exclude": config["exclude"],
            "entries": left[0],
        }
        body = {"id": checksum(body), "baseline": body}
        output = json_string(config["baseline"])
    else:
        base: tuple[dict[str, Json], str] = read(config)
        result: Json = plan(left[0], right[0], base[0], protected)
        simulated: dict[str, Json] = simulate(right[0], result)
        repeated: Json = plan(left[0], simulated, base[0], protected)
        assert len(json_array(repeated["operations"])) == 0, "dry run is not idempotent"
        assert json_equal(result["conflicts"], repeated["conflicts"]), "dry run changed conflicts"
        body = {
            "format": 1,
            "source": roots[0],
            "destination": roots[1],
            "baseline_id": base[1],
            "operations": result["operations"],
            "conflicts": result["conflicts"],
            "exclude": config["exclude"],
            "protected": protected,
            "source_guard": left[1],
            "destination_guard": right[1],
            "validated": True,
            "requires_revalidation": True,
        }
        body = {"id": checksum(body), "plan": body}
    if env_get("SYNC_PAUSE", "") == "scanned":
        print("PAUSED scanned")
        signal: str = env_get("SYNC_CONTINUE", "")
        for attempt in range(3000):
            if signal != "" and path_exists(signal):
                break
            sleep(0.01)
        assert signal != "" and path_exists(signal), "pause timed out"
    unchanged(roots[0], left[1])
    unchanged(roots[1], right[1])
    output_guard(output, left[1])
    output_guard(output, right[1])
    encoded: str = pretty(body)
    assert len(encoded.encode()) <= 16777216, "report exceeds 16 MiB"
    write_text_atomic(output, encoded)
    print(encoded)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


if __name__ == "__main__":
    main()
