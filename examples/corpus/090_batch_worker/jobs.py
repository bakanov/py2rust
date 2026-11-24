"""Pure transformations: NFC/casefold text, whitespace words and exact integer statistics."""

# ruff: noqa: I001 - compact runtime imports
import unicodedata
from py2rust.stdlib import Json, json_array, json_canonical, json_int, json_string


def transform(job: Json) -> Json:
    text: str = unicodedata.normalize("NFC", unicodedata.normalize("NFC", json_string(job["text"])).casefold())
    assert len(text.encode()) <= 8192, "normalized text byte limit exceeded"
    frequencies: dict[str, int] = {}
    words: list[str] = text.split()
    for word in words:
        frequencies[word] = frequencies.get(word, 0) + 1
    values: list[Json] = json_array(job["values"])
    total: int = 0
    minimum: Json = None
    maximum: Json = None
    for index in range(len(values)):
        sample: int = json_int(values[index])
        total = total + sample
        if index == 0:
            minimum = sample
            maximum = sample
        else:
            minimum = min(json_int(minimum), sample)
            maximum = max(json_int(maximum), sample)
    result: Json = {
        "id": job["id"],
        "normalized": text,
        "characters": len(text),
        "utf8_bytes": len(text.encode()),
        "words": len(words),
        "frequencies": frequencies,
        "samples": len(values),
        "sum": total,
        "minimum": minimum,
        "maximum": maximum,
    }
    assert len(json_canonical(result).encode()) <= 32768, "result byte limit exceeded"
    return result


def summarize(results: list[Json]) -> Json:
    summary: Json = {"jobs": len(results), "characters": 0, "utf8_bytes": 0, "words": 0, "samples": 0, "sum": 0}
    for result in results:
        for name in ["characters", "utf8_bytes", "words", "samples", "sum"]:
            summary[name] = json_int(summary[name]) + json_int(result[name])
    return summary
