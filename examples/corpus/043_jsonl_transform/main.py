"""Resume one immutable JSONL input, preserving accepted rows and rejected bytes."""

from processing import run
from storage import (
    configuration,
    digest,
    guard,
    initialize,
    load,
    names,
    present,
    restore,
)

from py2rust.stdlib import (
    FileHandle,
    Json,
    Sha256,
    file_lock,
    file_open,
    json_int,
    json_string,
    line_open,
    path_join,
    path_parent,
    pretty,
    process_exit,
)


def main() -> None:
    config: Json = configuration()
    root: str = json_string(config["output"])
    lock: str = path_join(path_parent(root), ".py2rust-jsonl-" + digest(root) + ".lock")
    assert lock != json_string(config["input"]) and lock != json_string(config["_path"]), "control path aliases lock"
    with file_lock(lock) as _lock:
        state: Json = load(config) if present(root) else initialize(config)
        guard(config, state)
        paths: list[str] = names()
        with file_open(path_join(root, paths[0]), "r+b") as accepted:  # noqa: SIM117 - one scoped binding per with
            with file_open(path_join(root, paths[1]), "r+b") as quarantine:
                with file_open(path_join(root, paths[2]), "r+b") as rejected:
                    outputs: list[FileHandle] = [accepted, quarantine, rejected]
                    hashes: list[Sha256] = restore(config, state, outputs)
                    with line_open(json_string(config["input"]), json_int(state["offset"])) as reader:
                        state = run(config, state, reader, outputs, hashes)
        print(pretty(state))
        if json_string(state["phase"]) == "paused":
            process_exit(75)


if __name__ == "__main__":
    main()
