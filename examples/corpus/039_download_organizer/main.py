"""Preview a download layout, then explicitly apply the reviewed plan identifier."""

from configuration import load
from guards import distinct, document, present, sidecar
from planning import preview, validate
from transaction import execute

from py2rust.stdlib import (
    Json,
    env_get,
    file_lock,
    json_string,
    path_join,
    pretty,
    write_text_atomic,
)


def main() -> None:
    mode: str = env_get("ORGANIZE_MODE", "preview")
    assert mode in ["preview", "apply"], "mode must be preview or apply"
    config_path: str = env_get("ORGANIZE_CONFIG", "organize.json")
    plan_path: str = env_get("ORGANIZE_PLAN", "organize-plan.json")
    journal: str = env_get("ORGANIZE_JOURNAL", "organize-journal.json")
    config: Json = {}
    envelope: Json = {}
    root: str = ""
    if mode == "preview":
        config = load(document(config_path))
        root = json_string(config["root"])
    else:
        envelope = document(plan_path)
        validate(envelope)
        root = json_string(envelope["plan"]["root"])
    plan_path = sidecar(plan_path, root)
    journal = sidecar(journal, root)
    paths: list[str] = [plan_path, journal]
    if mode == "preview":
        paths.append(sidecar(config_path, root))
    distinct(paths)
    with file_lock(path_join(root, ".py2rust-organize.lock")) as _lock:
        if mode == "preview":
            assert not present(journal), "keep the plan with its journal; choose fresh sidecar paths"
            envelope = preview(config)
            validate(envelope)
            encoded: str = pretty(envelope)
            assert len(encoded.encode()) <= 2097152, "plan exceeds 2 MiB"
            write_text_atomic(plan_path, encoded)
            print(encoded)
        else:
            assert env_get("ORGANIZE_APPROVE", "") == json_string(
                envelope["id"]
            ), "set ORGANIZE_APPROVE to the reviewed plan id"
            saved: Json = document(plan_path)
            validate(saved)
            assert json_string(saved["id"]) == json_string(envelope["id"]), "plan changed"
            print(pretty(execute(saved, journal)))
    return  # noqa: PLR1711 - explicit return required by repository guidelines


if __name__ == "__main__":
    main()
