"""Preview, create, verify or clean a bounded manifest-driven fixture tree."""

from actions import cleanup, create
from documents import absolute, digest, document, present
from manifest import Manifest, parse
from receipt import load, verify

from py2rust.stdlib import (
    Json,
    env_get,
    file_lock,
    json_bool,
    json_keys,
    json_string,
    path_join,
    path_parent,
    path_same,
    pretty,
)


def outside(path: str, root: str) -> str:
    result: str = absolute(path)
    assert result != root and not result.startswith(root + "/"), "control files must be outside fixture root"
    return result


def summary(body: Json) -> Json:
    created: int = 0
    for name in json_keys(body["entries"]):
        if json_bool(body["entries"][name]["owned"]) and body["entries"][name]["stamp"] is not None:
            created = created + 1
    return {
        "root": body["root"],
        "phase": body["phase"],
        "created": created,
        "bytes": body["bytes"],
        "cleanup_step": body["step"],
    }


def main() -> None:
    mode: str = env_get("FIXTURE_MODE", "preview")
    assert mode in ["preview", "create", "verify", "cleanup"], "invalid fixture mode"
    receipt_path: str = env_get("FIXTURE_RECEIPT", "fixture-receipt.json")
    source: str = env_get("FIXTURE_MANIFEST", "fixtures.json")
    body: Json = {}
    if mode in ["preview", "create"]:
        body = parse(document(source)).receipt
    else:
        body = load(receipt_path)
    root: str = json_string(body["root"])
    receipt_path = outside(receipt_path, root)
    if mode in ["preview", "create"]:
        source = outside(source, root)
        assert receipt_path != source and (
            not present(receipt_path) or not path_same(receipt_path, source)
        ), "manifest and receipt alias"
    lock: str = path_join(path_parent(root), ".py2rust-fixture-" + digest(root) + ".lock")
    assert source != lock and receipt_path != lock, "control path aliases lock"
    with file_lock(lock) as _lock:
        if mode in ["preview", "create"]:
            manifest: Manifest = parse(document(source))
            assert json_string(manifest.receipt["root"]) == root, "manifest root changed"
            body = manifest.receipt
            if mode == "create":
                body = create(manifest, receipt_path)
        else:
            body = load(receipt_path)
            assert json_string(body["root"]) == root, "receipt root changed"
            if mode == "cleanup":
                body = cleanup(body, receipt_path)
            else:
                assert json_string(body["phase"]) == "ready", "receipt is not ready"
                verify(body)
        print(pretty(body if mode == "preview" else summary(body)))
    return  # noqa: PLR1711 - explicit return required by repository guidelines


if __name__ == "__main__":
    main()
