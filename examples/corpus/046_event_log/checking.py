"""Scan physical JSONL records while keeping independent ID, sequence, time and state observations."""

from documents import checkpoint
from model import Code, Parsed, Stream, issue, parse

from py2rust.stdlib import (
    Json,
    Sha256,
    json_array,
    json_bool,
    json_canonical,
    json_int,
    json_string,
    line_open,
    line_read,
    pretty,
    sha256_digest,
    sha256_new,
    sha256_update,
)


def missing(numbers: list[int], first: int) -> list[Json]:
    cursor: int = first
    ranges: list[Json] = []
    for number in sorted(numbers):
        if number < cursor:
            continue
        if number > cursor:
            ranges.append({"first": cursor, "last": number - 1})
        if number == 9223372036854775807:
            break
        cursor = number + 1
    return ranges


def scan(path: str, config: Json, allowed: set[tuple[str, str]], size: int) -> Json:
    identifiers: dict[str, tuple[int, str]] = {}
    sequences: dict[tuple[str, int], int] = {}
    numbers: dict[str, list[int]] = {}
    streams: dict[str, Stream] = {}
    diagnostics: list[Json] = []
    diagnostic_bytes: int = 0
    counts: dict[str, int] = {}
    first: int = json_int(config["first_sequence"])
    states: list[Json] = json_array(config["states"])
    source_hash: Sha256 = sha256_new()
    offset: int = 0
    line: int = 0
    schema_valid: int = 0
    checked: int = 0
    global_clock: str = ""
    global_line: int = 0
    with line_open(path, 0) as reader:
        while True:
            raw: bytes = b""
            length: int = 0
            row_hash: Sha256 = sha256_new()
            oversized: bool = False
            while True:
                chunk: tuple[bytes, bool] = line_read(reader, 65536)
                length = length + len(chunk[0])
                assert offset + length <= json_int(config["max_input_bytes"]), "input grew beyond byte limit"
                row_hash = sha256_update(row_hash, chunk[0])
                source_hash = sha256_update(source_hash, chunk[0])
                if length > json_int(config["max_line_bytes"]):
                    oversized = True
                    raw = b""
                elif not oversized:
                    raw = raw + chunk[0]
                if chunk[1]:
                    break
            if length == 0:
                break
            line = line + 1
            assert line <= json_int(config["max_records"]), "record limit exceeded"
            event: Json = None
            problems: list[Json] = []
            if oversized:
                problems.append(issue(Code.OVERSIZED_RECORD, {"limit": json_int(config["max_line_bytes"])}))
            else:
                parsed: Parsed = parse(raw, states)
                event = parsed.value
                if len(parsed.errors) > 0:
                    problems.append(issue(Code.INVALID_RECORD, {"fields": parsed.errors}))
            if event is not None:
                schema_valid = schema_valid + 1
                identifier: str = json_string(event["id"])
                name: str = json_string(event["stream"])
                sequence: int = json_int(event["sequence"])
                pair: tuple[str, int] = (name, sequence)
                fingerprint: str = sha256_digest(sha256_update(sha256_new(), json_canonical(event).encode()))
                if identifier in identifiers:
                    previous: tuple[int, str] = identifiers[identifier]
                    code: Code = Code.DUPLICATE_ID if previous[1] == fingerprint else Code.CONFLICTING_ID
                    problems.append(issue(code, {"first_line": previous[0]}))
                else:
                    identifiers[identifier] = (line, fingerprint)
                    if pair in sequences:
                        problems.append(issue(Code.DUPLICATE_SEQUENCE, {"first_line": sequences[pair]}))
                    else:
                        sequences[pair] = line
                        if name not in streams:
                            assert len(streams) < json_int(config["max_streams"]), "stream limit exceeded"
                            streams[name] = Stream(
                                first - 1, 0, "", 0, json_string(config["initial_state"]), 0, line, 0
                            )
                            numbers[name] = []
                        observed: Stream = streams[name]
                        numbers[name].append(sequence)
                        if sequence < first:
                            problems.append(issue(Code.BEFORE_START, {"first": first, "actual": sequence}))
                        elif sequence < observed.high:
                            problems.append(
                                issue(Code.OUT_OF_ORDER, {"highest": observed.high, "line": observed.high_line})
                            )
                        elif sequence > observed.high and sequence - observed.high > 1:
                            problems.append(issue(Code.GAP, {"first": observed.high + 1, "last": sequence - 1}))
                        if sequence > observed.high:
                            observed.high = sequence
                            observed.high_line = line
                        moment: str = json_string(event["time"])
                        if moment < observed.clock:
                            problems.append(
                                issue(Code.STREAM_TIME, {"latest": observed.clock, "line": observed.clock_line})
                            )
                        if json_bool(config["global_time_order"]) and moment < global_clock:
                            problems.append(issue(Code.GLOBAL_TIME, {"latest": global_clock, "line": global_line}))
                        if moment > observed.clock:
                            observed.clock = moment
                            observed.clock_line = line
                        if moment > global_clock:
                            global_clock = moment
                            global_line = line
                        before: str = json_string(event["from"])
                        after: str = json_string(event["to"])
                        if before != observed.state:
                            problems.append(
                                issue(
                                    Code.STATE_MISMATCH,
                                    {"expected": observed.state, "actual": before, "line": observed.state_line},
                                )
                            )
                        if (before, after) not in allowed:
                            problems.append(issue(Code.TRANSITION, {"from": before, "to": after}))
                        observed.state = after
                        observed.state_line = line
                        observed.events = observed.events + 1
                        streams[name] = observed
                        checked = checked + 1
            if len(problems) > 0:
                for problem in problems:
                    code_name: str = json_string(problem["code"])
                    counts[code_name] = counts.get(code_name, 0) + 1
                entry: Json = {
                    "line": line,
                    "offset": offset,
                    "length": length,
                    "sha256": sha256_digest(row_hash),
                    "event": event,
                    "issues": problems,
                }
                diagnostic_bytes = diagnostic_bytes + len(pretty(entry).replace("\n", "\n    ").encode()) + 5
                assert diagnostic_bytes <= 16777216, "diagnostic report exceeds 16 MiB"
                diagnostics.append(entry)
            offset = offset + length
            checkpoint("row:" + str(line))
    assert offset == size, "input size changed during scan"
    summary: Json = {}
    for name in sorted(list(streams)):  # noqa: C414 - typed key snapshot
        observed: Stream = streams[name]
        ranges: list[Json] = missing(numbers[name], first)
        missing_count: int = 0
        for interval in ranges:
            missing_count = missing_count + (json_int(interval["last"]) - json_int(interval["first"]) + 1)
        summary[name] = {
            "checked_records": observed.events,
            "first_line": observed.first_line,
            "last_observed_state": observed.state,
            "state_line": observed.state_line,
            "highest_sequence": observed.high,
            "highest_sequence_line": observed.high_line,
            "latest_utc": observed.clock,
            "time_line": observed.clock_line,
            "missing": ranges,
            "missing_count": missing_count,
        }
    return {
        "consistent": len(diagnostics) == 0,
        "records": line,
        "schema_valid": schema_valid,
        "checked": checked,
        "invalid_records": line - schema_valid,
        "duplicate_records": schema_valid - checked,
        "input_bytes": offset,
        "input_sha256": sha256_digest(source_hash),
        "latest_utc": global_clock,
        "latest_time_line": global_line,
        "issue_counts": counts,
        "diagnostics": diagnostics,
        "streams": summary,
    }
