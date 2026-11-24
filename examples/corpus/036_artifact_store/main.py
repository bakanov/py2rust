"""A standalone artifact-store command; Python is needed only to transpile it."""

from common import checkpoint, configuration, document, fields, identifier, name
from content import digest
from graph import reachable, read
from operations import collect, import_file, manifest, pin, retrieve
from repository import inventory, open_store, references

from py2rust.stdlib import (
    Json,
    env_get,
    file_lock,
    json_int,
    json_string,
    path_join,
    pretty,
    remove_file,
    sync_directory,
)


def main() -> None:
    config: Json = configuration()
    repo: str = json_string(config["repository"])
    mode: str = env_get("STORE_MODE", "list")
    assert mode in ["init", "import", "manifest", "pin", "unpin", "get", "show", "list", "gc", "verify"], "unknown mode"
    with file_lock(path_join(repo, ".store.lock")) as _lock:
        checkpoint("locked")
        open_store(config, mode == "init")
        state: dict[str, Json] = inventory(config)
        roots: dict[str, str] = references(repo, state)
        request: Json = {}
        if mode in ["import", "manifest", "pin", "unpin", "get", "show"]:
            request = document(env_get("STORE_REQUEST", "request.json"))
        result: Json = {"references": roots, "nodes": len(state) - 3}
        if mode == "import":
            result = import_file(config, state, request)
        elif mode == "manifest":
            result = manifest(config, state, roots, request)
        elif mode == "pin":
            fields(request, ["name", "manifest", "expected"])
            hashed: str = identifier(json_string(request["manifest"]))
            reachable(config, state, [hashed], None)
            pin(config, state, roots, json_string(request["name"]), hashed, json_string(request["expected"]))
            result = {"pinned": request["name"], "manifest": hashed}
        elif mode == "unpin":
            fields(request, ["name", "expected"])
            reference: str = name(json_string(request["name"]))
            assert reference in roots and roots[reference] == identifier(
                json_string(request["expected"])
            ), "reference changed"
            remove_file(path_join(repo, "refs/" + reference + ".json"))
            sync_directory(path_join(repo, "refs"))
            result = {"unpinned": reference}
        elif mode == "get":
            result = retrieve(config, state, request)
        elif mode == "show":
            fields(request, ["manifest"])
            hashed: str = identifier(json_string(request["manifest"]))
            result = {"manifest": read(repo, hashed), "reachable": reachable(config, state, [hashed], None)}
        elif mode == "gc":
            result = collect(config, state, roots)
        elif mode == "verify":
            identifiers: list[str] = []
            for key in state:
                if key.startswith("manifests/"):
                    identifiers.append(key[10:-5])
                elif key.startswith("blobs/"):
                    assert digest(path_join(repo, key), json_int(state[key]["size"])) == key[6:], "corrupt blob"
            for reference in roots:  # noqa: PLC0206 - typed key iteration
                identifiers.append(roots[reference])
            result = reachable(config, state, identifiers, None)
        print(pretty(result))
    return  # noqa: PLR1711 - explicit return required by repository guidelines


if __name__ == "__main__":
    main()
