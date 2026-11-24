"""Versioned backup commands; the repository lock serializes all cooperating users."""

from common import (
    checkpoint,
    configuration,
    document,
    present,
    stamp,
    version_name,
    write_document,
)
from manifests import load_all
from restore import restore
from snapshot import create

from py2rust.stdlib import (
    Json,
    directory_names,
    env_get,
    file_lock,
    json_equal,
    json_string,
    mkdir_new,
    path_join,
    pretty,
    remove_file,
    sync_directory,
)


def repository(repo: str, initialize: bool) -> None:
    allowed: list[str] = [".backup.lock", "format.json", "objects", "versions", "staging"]
    for name in directory_names(repo, 10):
        assert name in allowed, "unexpected repository entry"
    if initialize:
        assert not present(path_join(repo, "format.json")), "repository is already initialized"
        for name in ["objects", "versions", "staging"]:
            path: str = path_join(repo, name)
            if not present(path):
                mkdir_new(path)
            assert len(directory_names(path, 1)) == 0, "initialization requires empty directories"
        write_document(path_join(repo, "format.json"), {"format": "py2rust-snapshot", "version": 1})
        sync_directory(repo)
    assert json_equal(
        document(path_join(repo, "format.json")), {"format": "py2rust-snapshot", "version": 1}
    ), "unknown format"
    for name in ["objects", "versions", "staging"]:
        assert json_string(stamp(path_join(repo, name))["kind"]) == "directory", "invalid repository directory"
    # A killed snapshot can leave only these private, unpublished temporary files.
    for name in directory_names(path_join(repo, "staging"), 2):
        assert name in ["object.part", "manifest.json"], "unknown staging entry"
        path: str = path_join(repo, "staging/" + name)
        assert json_string(stamp(path)["kind"]) == "file", "invalid staging entry"
        remove_file(path)
    sync_directory(path_join(repo, "staging"))
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def main() -> None:
    config: Json = configuration()
    repo: str = json_string(config["repository"])
    mode: str = env_get("BACKUP_MODE", "list")
    assert mode in ["init", "snapshot", "list", "restore"], "unknown backup mode"
    with file_lock(path_join(repo, ".backup.lock")) as _lock:
        checkpoint("locked")
        repository(repo, mode == "init")
        versions: dict[int, Json] = load_all(repo)
        result: Json = {"initialized": True}
        if mode == "snapshot":
            result = create(config, versions, version_name(env_get("BACKUP_VERSION", "")))
        elif mode == "restore":
            name: str = version_name(env_get("BACKUP_VERSION", ""))
            selected: Json = {}
            found: bool = False
            for sequence in versions:  # noqa: PLC0206 - typed key iteration
                if json_string(versions[sequence]["name"]) == name:
                    selected = versions[sequence]
                    found = True
            assert found, "version not found"
            result = restore(config, selected, env_get("BACKUP_DEST", ""))
        elif mode == "list":
            listing: list[Json] = []
            for sequence in sorted(list(versions)):  # noqa: C414 - explicit typed key snapshot
                listing.append({"name": versions[sequence]["name"], "sequence": sequence})
            result = listing
        print(pretty(result))
    return  # noqa: PLR1711 - explicit return required by repository guidelines


if __name__ == "__main__":
    main()
