"""Preview a naming plan; explicitly approve its digest to apply or reverse it."""

from checks import document, present
from planning import load, preview
from transaction import execute

from py2rust.stdlib import (
    Json,
    env_get,
    file_lock,
    json_string,
    path_is_symlink,
    path_join,
    path_name,
    path_parent,
    path_resolve,
    path_same,
    path_stat,
    pretty,
    write_text_atomic,
)


def sidecar(path: str, root: str) -> str:
    assert not path_is_symlink(path), "sidecar cannot be a symlink"
    result: str = path_join(path_resolve(path_parent(path)), path_name(path))
    assert root != "/" and result != root and not result.startswith(root + "/"), "sidecars must be outside root"
    if present(result):
        assert json_string(path_stat(result, False)["kind"]) == "file", "sidecar must be regular"
    return result


def distinct(paths: list[str]) -> None:
    for left in range(len(paths)):
        for right in range(left + 1, len(paths)):
            assert paths[left] != paths[right], "sidecar paths overlap"
            if present(paths[left]) and present(paths[right]):
                assert not path_same(paths[left], paths[right]), "sidecar files alias"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def main() -> None:
    mode: str = env_get("RENAME_MODE", "preview")
    assert mode in ["preview", "apply", "reverse"], "mode must be preview, apply or reverse"
    plan_path: str = env_get("RENAME_PLAN", "rename-plan.json")
    journal_path: str = env_get("RENAME_JOURNAL", "rename-journal.json")
    envelope: Json = {}
    root: str = ""
    encoded: str = ""
    if mode == "preview":
        config_path: str = env_get("RENAME_CONFIG", "rename.json")
        raw: Json = document(config_path, 65536)
        root = path_resolve(json_string(raw["root"]))
        plan_path = sidecar(plan_path, root)
        journal_path = sidecar(journal_path, root)
        distinct([plan_path, journal_path, sidecar(config_path, root)])
        assert not present(journal_path), "keep the existing plan with its journal; select fresh sidecar paths"
        with file_lock(path_join(root, ".py2rust-rename.lock")) as _lock:
            envelope = preview(raw)
            encoded = pretty(envelope)
            assert len(encoded.encode()) <= 2097152, "plan exceeds 2 MiB"
            write_text_atomic(plan_path, encoded)
        print(encoded)
    else:
        envelope = load(plan_path)
        root = json_string(envelope["plan"]["root"])
        plan_path = sidecar(plan_path, root)
        journal_path = sidecar(journal_path, root)
        distinct([plan_path, journal_path])
        assert env_get("RENAME_APPROVE", "") == json_string(
            envelope["id"]
        ), "set RENAME_APPROVE to the reviewed plan id"
        with file_lock(path_join(root, ".py2rust-rename.lock")) as _lock:
            # Revalidate after acquiring the root-wide lock.
            assert json_string(load(plan_path)["id"]) == json_string(envelope["id"]), "plan changed"
            print(pretty(execute(envelope, journal_path, mode == "reverse")))
    return  # noqa: PLR1711 - explicit return required by repository guidelines


if __name__ == "__main__":
    main()
