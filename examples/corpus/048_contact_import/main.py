"""Import contacts into a new lossless book, separating ambiguous groups for human review."""

import logging

from documents import Document, absolute, checkpoint, publish, read, unchanged
from merging import Contact, digest, group, order, summarize
from schema import Parsed, exact, parse, policy

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_bool,
    json_canonical,
    json_equal,
    json_int,
    json_loads,
    json_string,
    path_parent,
    path_resolve,
    pretty,
    process_exit,
    sha256_digest,
    sha256_new,
    sha256_update,
)


def run() -> int:
    mode: str = env_get("CONTACT_MODE", "preview")
    assert mode in ["preview", "write"], "invalid contact mode"
    path: str = absolute(env_get("CONTACT_CONFIG", "contact-job.json"), path_resolve("."))
    configuration: Document = read(path, 65536)
    documents: list[Document] = [configuration]
    config: Json = json_loads(configuration.data.decode())
    exact(config, ["inputs", "state", "output", "keys"])
    rules: list[list[str]] = policy(config["keys"])
    parent: str = path_parent(path)
    output: str = absolute(json_string(config["output"]), parent)
    records: dict[str, Json] = {}
    state_path: str = json_string(config["state"])
    if state_path != "":
        original: Document = read(absolute(state_path, parent), 8388608)
        documents.append(original)
        envelope: Json = json_loads(original.data.decode())
        exact(envelope, ["state", "sha256"])
        state: Json = envelope["state"]
        exact(state, ["version", "keys", "records"])
        assert json_int(state["version"]) == 1 and json_equal(state["keys"], rules), "state policy mismatch"
        assert json_string(envelope["sha256"]) == digest(state), "state checksum mismatch"
        rows: list[Json] = json_array(state["records"])
        assert len(rows) <= 2000, "state record limit exceeded"
        for row in rows:
            assert len(parse(row).errors) == 0, "invalid stored contact"
            variant: str = digest(row)
            assert variant not in records, "duplicate stored variant"
            records[variant] = row
    before: int = len(records)
    sources: list[Json] = []
    rejected: list[Json] = []
    inputs: list[Json] = json_array(config["inputs"])
    assert 1 <= len(inputs) <= 16, "expected 1..16 input files"
    input_bytes: int = 0
    total: int = 0
    replayed: int = 0
    for value in inputs:
        source: Document = read(absolute(json_string(value), parent), 4194304)
        input_bytes = input_bytes + len(source.data)
        assert input_bytes <= 8388608, "total input exceeds 8 MiB"
        documents.append(source)
        rows: list[Json] = json_array(json_loads(source.data.decode()))
        total = total + len(rows)
        assert total <= 2000, "import record limit exceeded"
        sources.append(
            {
                "path": source.path,
                "sha256": sha256_digest(sha256_update(sha256_new(), source.data)),
                "records": len(rows),
            }
        )
        for index in range(len(rows)):
            row: Json = rows[index]
            parsed: Parsed = parse(row)
            if len(parsed.errors) > 0:
                rejected.append({"input": len(sources), "record": index + 1, "raw": row, "errors": parsed.errors})
            else:
                variant: str = digest(row)
                if variant in records:
                    replayed = replayed + 1
                else:
                    assert len(records) < 2000, "book record limit exceeded"
                    records[variant] = row
        checkpoint("input:" + str(len(sources)))
    ordered: list[Contact] = order(records)
    groups: dict[int, list[int]] = group(ordered, rules)
    contacts: list[Json] = []
    review: list[Json] = []
    stored: list[Json] = []
    for contact in ordered:
        stored.append(contact.raw)
    for root in groups:  # noqa: PLC0206 - subset key iteration
        members: list[Contact] = []
        for index in groups[root]:
            members.append(ordered[index])
        result: Json = summarize(members)
        if json_bool(result["review"]):
            review.append(result)
        else:
            contacts.append(result)
    state: Json = {"version": 1, "keys": rules, "records": stored}
    book: str = json_canonical({"state": state, "sha256": digest(state)})
    assert len(book.encode()) <= 8388608, "book exceeds 8 MiB"
    report: Json = {
        "sources": sources,
        "input_records": total,
        "added": len(records) - before,
        "replayed": replayed,
        "rejected": len(rejected),
        "variants": len(records),
        "contacts": len(contacts),
        "review_groups": len(review),
        "state_sha256": digest(state),
    }
    files: dict[str, str] = {
        "book.json": book,
        "contacts.json": pretty(contacts) + "\n",
        "review.json": pretty(review) + "\n",
        "rejected.json": json_canonical(rejected) + "\n",
        "report.json": pretty(report) + "\n",
    }
    for name in files:  # noqa: PLC0206
        assert len(files[name].encode()) <= 16777216, "output exceeds 16 MiB"
    checkpoint("validated")
    unchanged(documents)
    if mode == "write":
        publish(output, files, documents)
    print(pretty(report))
    return 1 if len(review) > 0 or len(rejected) > 0 else 0


def main() -> None:
    code: int = 2
    try:
        code = run()
    except Exception as error:  # noqa: BLE001 - fatal CLI failures use exit 2
        logging.error(str(error))  # noqa: LOG015 - supported logging facade
    process_exit(code)
    return  # noqa: PLR1711 - explicit returns follow repository guidelines


if __name__ == "__main__":
    main()
