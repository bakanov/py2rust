"""Group validated records without deduplication, retaining source order inside each shard."""

from dataclasses import dataclass

from py2rust.stdlib import (
    Json,
    datetime_format,
    datetime_parse,
    json_canonical,
    json_int,
    json_kind,
    json_loads,
    json_string,
    sha256_digest,
    sha256_new,
    sha256_update,
)


@dataclass
class Partition:
    files: dict[str, str]
    manifest: Json


def digest(data: bytes) -> str:
    return sha256_digest(sha256_update(sha256_new(), data))


def partition(data: bytes, config: Json) -> Partition:
    lines: list[str] = data.decode().split("\n")
    if lines[-1] == "":
        lines.pop()
    assert len(lines) <= json_int(config["max_rows"]), "input row limit exceeded"
    content: dict[tuple[str, str], list[str]] = {}
    locations: dict[tuple[str, str], tuple[int, int]] = {}
    timestamp: str = json_string(config["timestamp_field"])
    topic_field: str = json_string(config["topic_field"])
    encoded_bytes: int = 0
    for index in range(len(lines)):
        try:
            line: str = lines[index]
            assert len(line.encode()) <= json_int(config["max_line_bytes"]), "line byte limit exceeded"
            row: Json = json_loads(line)
            assert json_kind(row) == "object", "record must be an object"
            day: str = datetime_format(datetime_parse(json_string(row[timestamp])), "%Y-%m-%d")
            topic: str = json_string(row[topic_field])
            assert 1 <= len(topic.encode()) <= 256, "topic must contain 1..256 UTF-8 bytes"
            key: tuple[str, str] = (day, topic)
            if key not in content:
                assert len(content) < json_int(config["max_shards"]), "shard count limit exceeded"
                content[key] = []
                locations[key] = (index + 1, index + 1)
            encoded: str = json_canonical(row) + "\n"
            encoded_bytes = encoded_bytes + len(encoded.encode())
            assert encoded_bytes <= 16777216, "total shard data exceeds 16 MiB"
            content[key].append(encoded)
            locations[key] = (locations[key][0], index + 1)
        except Exception as error:  # noqa: BLE001 - retain physical source line in every record error
            assert False, "line " + str(index + 1) + ": " + str(error)
    files: dict[str, str] = {}
    shards: list[Json] = []
    for key in sorted(list(content)):  # noqa: C414 - subset sorting requires a typed sequence
        filename: str = key[0] + "--" + digest(key[1].encode()) + ".jsonl"
        assert filename not in files, "shard filename collision"
        text: str = "".join(content[key])
        files[filename] = text
        shards.append(
            {
                "date": key[0],
                "topic": key[1],
                "file": filename,
                "rows": len(content[key]),
                "bytes": len(text.encode()),
                "sha256": digest(text.encode()),
                "first_line": locations[key][0],
                "last_line": locations[key][1],
            }
        )
    manifest: Json = {
        "version": 1,
        "input_sha256": digest(data),
        "input_bytes": len(data),
        "rows": len(lines),
        "shard_bytes": encoded_bytes,
        "timestamp_field": timestamp,
        "topic_field": topic_field,
        "shards": shards,
    }
    return Partition(files, manifest)
