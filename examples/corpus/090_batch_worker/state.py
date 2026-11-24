"""Validate saved progress independently of batch size; checksums detect accidental corruption."""

# ruff: noqa: I001, PLR1711 - compact runtime imports and explicit subset returns
from configuration import exact, integer
from jobs import summarize
from py2rust.stdlib import (
    Json,
    json_array,
    json_canonical,
    json_equal,
    json_int,
    json_is_null,
    json_keys,
    json_string,
)


def empty(binding: Json) -> Json:
    results: list[Json] = []
    return {"version": 1, "binding": binding, "completed": 0, "results": results, "summary": summarize(results)}


def validate(state: Json, binding: Json, jobs: list[Json]) -> None:
    exact(state, ["version", "binding", "completed", "results", "summary"])
    assert json_int(state["version"]) == 1 and json_equal(state["binding"], binding), "checkpoint binding mismatch"
    completed: int = integer(state["completed"], 0, len(jobs))
    results: list[Json] = json_array(state["results"])
    assert len(results) == completed, "checkpoint cursor/result mismatch"
    for index in range(completed):
        result: Json = results[index]
        exact(
            result,
            [
                "id",
                "normalized",
                "characters",
                "utf8_bytes",
                "words",
                "frequencies",
                "samples",
                "sum",
                "minimum",
                "maximum",
            ],
        )
        assert json_equal(result["id"], jobs[index]["id"]), "checkpoint job order mismatch"
        text: str = json_string(result["normalized"])
        assert len(text.encode()) <= 8192 and len(json_canonical(result).encode()) <= 32768, "saved result too large"
        assert json_int(result["characters"]) == len(text), "character count mismatch"
        assert json_int(result["utf8_bytes"]) == len(text.encode()), "byte count mismatch"
        frequencies: Json = result["frequencies"]
        counted: dict[str, int] = {}
        words: list[str] = text.split()
        for word in words:
            counted[word] = counted.get(word, 0) + 1
        assert len(json_keys(frequencies)) == len(counted), "word set mismatch"
        for word in counted:  # noqa: PLC0206 - typed dictionary key iteration in the supported subset
            assert json_int(frequencies[word]) == counted[word], "word frequency mismatch"
        assert json_int(result["words"]) == len(words), "word count mismatch"
        samples: int = integer(result["samples"], 0, 128)
        total: int = integer(result["sum"], -samples * 1000000000, samples * 1000000000)
        if samples == 0:
            assert json_is_null(result["minimum"]) and json_is_null(result["maximum"]), "empty extrema mismatch"
        else:
            low: int = integer(result["minimum"], -1000000000, 1000000000)
            high: int = integer(result["maximum"], low, 1000000000)
            assert low * samples <= total <= high * samples, "sample summary mismatch"
    assert json_equal(state["summary"], summarize(results)), "checkpoint totals mismatch"
    return


def report(state: Json) -> bytes:
    return (
        json_canonical(
            {"version": 1, "binding": state["binding"], "results": state["results"], "summary": state["summary"]}
        )
        + "\n"
    ).encode()
