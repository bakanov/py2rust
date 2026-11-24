"""Preview or atomically export layered configuration with provenance diagnostics."""

from configuration import Settings, load
from documents import Document, revalidate, stamp
from merging import combine, record
from model import Merged, Recorded, locations

from py2rust.stdlib import (
    Json,
    env_get,
    json_equal,
    json_string,
    path_exists,
    pretty,
    process_exit,
    sleep,
    write_text_atomic,
)


def checkpoint(label: str) -> None:
    assert env_get("MERGE_FAIL", "") != label, "injected interruption: " + label
    if env_get("MERGE_PAUSE", "") == label:
        print("PAUSED " + label)
        signal: str = env_get("MERGE_CONTINUE", "")
        for attempt in range(3000):
            if signal != "" and path_exists(signal):
                return
            sleep(0.01)
        assert False, "pause timed out"
    return


def resolve(settings: Settings) -> Json:
    value: Json = {}
    origins: dict[str, str] = {}
    events: list[Json] = []
    conflicts: list[Json] = []
    used: set[str] = set()
    layers: list[Json] = []
    for index in range(len(settings.names)):
        document: Document = settings.documents[index + 1]
        name: str = settings.names[index]
        layers.append(
            {
                "name": name,
                "present": document.present,
                "sha256": document.digest,
                "bytes": document.size,
                "nodes": document.nodes,
            }
        )
        if document.present:
            merged: Merged = combine(value, document.value, "", settings.allowed)
            value = merged.value
            recorded: Recorded = record(merged.changes, name, origins)
            origins = recorded.origins
            events.extend(recorded.events)
            conflicts.extend(recorded.conflicts)
            for permission in recorded.used:
                used.add(permission)
    assert len(locations(value, "", 0)) <= settings.max_nodes, "resolved node budget exceeded"
    unused: list[str] = []
    for permission in sorted(list(settings.allowed)):  # noqa: C414 - explicit typed-list conversion
        if permission not in used:
            unused.append(permission)
    status: str = "resolved" if len(conflicts) == 0 else "conflicted"
    resolved: Json = value if len(conflicts) == 0 else None
    provenance: Json = origins if len(conflicts) == 0 else {}
    return {
        "status": status,
        "resolved": resolved,
        "provenance": provenance,
        "events": events,
        "conflicts": conflicts,
        "layers": layers,
        "unused_type_changes": unused,
    }


def main() -> None:
    mode: str = env_get("MERGE_MODE", "preview")
    assert mode in ["preview", "apply"], "mode must be preview or apply"
    settings: Settings = load()
    before: Json = stamp(settings.output)
    checkpoint("loaded")
    report: Json = resolve(settings)
    report["mode"] = mode
    text: str = pretty(report)
    assert len(text.encode()) <= 16777216, "report exceeds 16 MiB"
    checkpoint("resolved")
    revalidate(settings.documents)
    if json_string(report["status"]) == "conflicted":
        print(text)
        process_exit(2)
    if mode == "apply":
        output: str = pretty(report["resolved"]) + "\n"
        assert len(output.encode()) <= 16777216, "export exceeds 16 MiB"
        checkpoint("before_publish")
        revalidate(settings.documents)
        assert json_equal(before, stamp(settings.output)), "output changed before publication"
        write_text_atomic(settings.output, output)
        checkpoint("after_publish")
    print(text)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


if __name__ == "__main__":
    main()
