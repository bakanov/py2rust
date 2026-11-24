"""Independent content hashes, manifest reachability and real interruption fixtures."""

from __future__ import annotations

import hashlib
import json
import os
import random
import selectors
import subprocess
from pathlib import Path

from .canonical_json import canonical
from .common import Application


def hashed(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def setup(directory: Path) -> tuple[Path, dict]:
    directory.mkdir(parents=True)
    repo = directory / "store"
    repo.mkdir()
    config = {"repository": str(repo), "max_nodes": 10000, "max_bytes": 1073741824, "max_blob_bytes": 536870912}
    (directory / "store.json").write_text(json.dumps(config))
    return repo, config


def invoke(app: Application, work: Path, mode: str, request: dict | None = None, **settings: str) -> dict:
    if request is not None:
        (work / "request.json").write_text(json.dumps(request))
    result = app.run(work, dict(STORE_MODE=mode, **settings), timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def fail(app: Application, work: Path, mode: str, request: dict | None = None, **settings: str) -> None:
    if request is not None:
        (work / "request.json").write_text(json.dumps(request))
    result = app.run(work, dict(STORE_MODE=mode, **settings), timeout=30)
    assert result.returncode != 0, result.stdout
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def imported(app: Application, work: Path, name: str, data: bytes) -> dict:
    path = work / name
    path.write_bytes(data)
    before = path.stat()
    value = invoke(app, work, "import", {"path": str(path)})
    assert value["digest"] == hashed(data) and value["size"] == len(data)
    blob = work / "store/blobs" / value["digest"]
    assert blob.read_bytes() == data and blob.stat().st_ino != before.st_ino
    after = path.stat()
    assert (before.st_size, before.st_mtime_ns, before.st_ctime_ns, before.st_nlink) == (
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
        after.st_nlink,
    )
    return {"digest": value["digest"], "size": len(data)}


def attach(
    app: Application,
    work: Path,
    files: dict,
    includes: list[str],
    name: str = "",
    expected: str = "-",
    metadata: dict | None = None,
) -> str:
    value = invoke(
        app,
        work,
        "manifest",
        {"name": name, "expected": expected, "files": files, "includes": includes, "metadata": metadata or {}},
    )
    body = {"version": 1, "files": files, "includes": sorted(includes), "metadata": metadata or {}}
    identifier = hashed(canonical(body))
    assert value == {"manifest": identifier, "name": name}
    assert (work / "store/manifests" / (identifier + ".json")).read_bytes() == canonical(body)
    return identifier


def oracle(repo: Path) -> tuple[set[str], set[str]]:
    manifests: set[str] = set()
    blobs: set[str] = set()

    def visit(identifier: str) -> None:
        if identifier in manifests:
            return
        manifests.add(identifier)
        path = repo / "manifests" / (identifier + ".json")
        body = json.loads(path.read_bytes())
        assert hashed(canonical(body)) == identifier
        for row in body["files"].values():
            data = (repo / "blobs" / row["digest"]).read_bytes()
            assert len(data) == row["size"] and hashed(data) == row["digest"]
            blobs.add(row["digest"])
        for child in body["includes"]:
            visit(child)
        return

    for path in (repo / "refs").iterdir():
        visit(json.loads(path.read_bytes())["manifest"])
    return manifests, blobs


def collected(app: Application, work: Path) -> dict:
    repo = work / "store"
    live_manifests, live_blobs = oracle(repo)
    before = {str(path.relative_to(repo)) for folder in ["blobs", "manifests"] for path in (repo / folder).iterdir()}
    expected = {"blobs/" + value for value in live_blobs} | {"manifests/" + value + ".json" for value in live_manifests}
    result = invoke(app, work, "gc")
    assert result == {
        "removed": sorted(before - expected),
        "live": {"manifests": sorted(live_manifests), "blobs": sorted(live_blobs)},
    }
    actual = {str(path.relative_to(repo)) for folder in ["blobs", "manifests"] for path in (repo / folder).iterdir()}
    assert actual == expected
    return result


def snapshot(repo: Path) -> dict:
    result = {}
    for folder in ["blobs", "manifests", "refs"]:
        for path in (repo / folder).iterdir():
            info = path.lstat()
            data = os.readlink(path).encode() if path.is_symlink() else path.read_bytes()
            result[str(path.relative_to(repo))] = (info.st_ino, info.st_mode, info.st_mtime_ns, info.st_ctime_ns, data)
    return result


def pause(app: Application, work: Path, mode: str, request: dict | None, label: str, action) -> None:
    if request is not None:
        (work / "request.json").write_text(json.dumps(request))
    signal = work / "continue"
    signal.unlink(missing_ok=True)
    process = subprocess.Popen(
        app.command,
        cwd=work,
        env=app.environment({"STORE_MODE": mode, "STORE_PAUSE": label, "STORE_CONTINUE": str(signal)}),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            assert selector.select(10), "expected pause was not reached"
            assert process.stdout.readline().strip() == "PAUSED " + label
        action(process, signal)
        stdout, stderr = process.communicate(timeout=20)
        assert process.returncode != 0, stdout + stderr
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        process.stdout.close()
        process.stderr.close()
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def kill(process, _signal: Path) -> None:
    process.kill()
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def check(app: Application, directory: Path) -> dict:
    repo, config = setup(directory / "graph")
    work = repo.parent
    assert invoke(app, work, "init") == {"references": {}, "nodes": 0}
    first = imported(app, work, "first.bin", b"\x00\xff\xfeCRLF\r\n" * 7001)
    empty = imported(app, work, "empty", b"")
    text = imported(app, work, "text", "Заметка 😀\n".encode())
    old = snapshot(repo)
    assert invoke(app, work, "import", {"path": str(work / "first.bin")}) == dict(first, created=False)
    assert snapshot(repo) == old
    duplicate = work / "duplicate"
    duplicate.write_bytes((work / "first.bin").read_bytes())
    assert invoke(app, work, "import", {"path": str(duplicate)})["created"] is False
    (work / "first.bin").write_bytes(b"changed original")
    assert (repo / "blobs" / first["digest"]).read_bytes() == b"\x00\xff\xfeCRLF\r\n" * 7001
    leaf = attach(
        app,
        work,
        {"data/世界.bin": first, "empty": empty},
        [],
        "leaf",
        metadata={"title": "shared 😀", "numeric": [0.1, 1e-7, 5e-324, -0.0, 1.7976931348623157e308]},
    )
    middle = attach(app, work, {"README": text}, [leaf])
    root = attach(app, work, {}, [middle, leaf], "release")
    assert attach(app, work, {}, [leaf, middle]) == root, "dependency order changed canonical ID"
    invoke(app, work, "pin", {"name": "archive", "manifest": root, "expected": "-"})
    live = invoke(app, work, "show", {"manifest": root})
    assert set(live["reachable"]["manifests"]) == {root, middle, leaf}
    assert set(live["reachable"]["blobs"]) == {first["digest"], empty["digest"], text["digest"]}
    assert collected(app, work)["removed"] == []
    for blob in [first, empty, text]:
        target = work / (blob["digest"] + ".download")
        assert invoke(app, work, "get", {"digest": blob["digest"], "destination": str(target)}) == blob
        assert hashed(target.read_bytes()) == blob["digest"]
        fail(app, work, "get", {"digest": blob["digest"], "destination": str(target)})
    old = snapshot(repo)
    fail(app, work, "pin", {"name": "release", "manifest": leaf, "expected": "-"})
    fail(app, work, "unpin", {"name": "release", "expected": leaf})
    assert snapshot(repo) == old
    invoke(app, work, "unpin", {"name": "leaf", "expected": leaf})
    assert collected(app, work)["removed"] == []
    replacement = attach(app, work, {"only-empty": empty}, [], "release", root)
    assert invoke(app, work, "list")["references"] == {"archive": root, "release": replacement}
    assert collected(app, work)["removed"] == []
    invoke(app, work, "unpin", {"name": "archive", "expected": root})
    removed = collected(app, work)["removed"]
    assert len(removed) == 5 and (repo / "blobs" / empty["digest"]).exists()
    assert collected(app, work)["removed"] == []
    invoke(app, work, "verify")

    # Reachability in a deterministic generated DAG, including many shared dependencies.
    dag_repo, _dag_config = setup(directory / "dag")
    current = dag_repo.parent
    invoke(app, current, "init")
    blobs = [imported(app, current, f"data-{index}", bytes([index]) * (index + 1)) for index in range(12)]
    manifests = []
    rng = random.Random(361)
    for index in range(40):
        dependencies = rng.sample(manifests, min(len(manifests), index % 4))
        files = {f"artifact-{index}": blobs[index % len(blobs)]}
        manifests.append(attach(app, current, files, dependencies, metadata={"index": index}))
    for index in [14, 27, 39]:
        invoke(app, current, "pin", {"name": f"root-{index}", "manifest": manifests[index], "expected": "-"})
    expected_manifests, expected_blobs = oracle(dag_repo)
    assert len(expected_manifests) > 10 and len(expected_blobs) > 5
    collected(app, current)
    for index in [14, 27, 39]:
        invoke(app, current, "unpin", {"name": f"root-{index}", "expected": manifests[index]})
    collected(app, current)
    assert invoke(app, current, "list") == {"references": {}, "nodes": 0}

    # Invalid reachable state blocks collection before any garbage is deleted.
    garbage = imported(app, work, "garbage", b"unreferenced garbage")
    live_blob = repo / "blobs" / empty["digest"]
    manifest_path = repo / "manifests" / (replacement + ".json")
    reference_path = repo / "refs/release.json"
    for target, data in [
        (live_blob, b"wrong"),
        (manifest_path, b"{}"),
        (reference_path, b"{}"),
        (reference_path, canonical({"manifest": "f" * 64})),
    ]:
        saved = target.read_bytes()
        target.write_bytes(data)
        before = snapshot(repo)
        fail(app, work, "gc")
        assert snapshot(repo) == before
        target.write_bytes(saved)
    saved = live_blob.read_bytes()
    live_blob.unlink()
    before = snapshot(repo)
    fail(app, work, "gc")
    assert snapshot(repo) == before
    live_blob.write_bytes(saved)
    (repo / "blobs" / garbage["digest"]).write_bytes(b"corrupt unreachable object")
    (repo / "manifests" / (("f" * 64) + ".json")).write_bytes(b'{"broken":true}')
    fail(app, work, "verify")
    assert ("blobs/" + garbage["digest"]) in collected(app, work)["removed"]

    # All schema failures leave named roots and already published objects intact.
    invalid_requests = [
        ("manifest", {"name": "bad", "expected": "-", "files": {"../escape": empty}, "includes": [], "metadata": {}}),
        (
            "manifest",
            {"name": "bad", "expected": "-", "files": {"x": dict(empty, size=True)}, "includes": [], "metadata": {}},
        ),
        (
            "manifest",
            {"name": "bad", "expected": "-", "files": {}, "includes": [replacement, replacement], "metadata": {}},
        ),
        ("manifest", {"name": "bad", "expected": "-", "files": {}, "includes": ["f" * 64], "metadata": {}}),
        (
            "manifest",
            {"name": "bad", "expected": "-", "files": {"x": dict(empty, size=1)}, "includes": [], "metadata": {}},
        ),
        ("manifest", {"name": "bad", "expected": "-", "files": {}, "includes": [], "metadata": []}),
        ("manifest", {"name": "../bad", "expected": "-", "files": {}, "includes": [], "metadata": {}}),
        ("pin", {"name": "missing", "manifest": "f" * 64, "expected": "-"}),
        ("pin", {"name": "bad name", "manifest": replacement, "expected": "-"}),
        ("pin", {"name": "fresh", "manifest": replacement, "expected": "wrong"}),
        ("get", {"digest": "../escape", "destination": str(work / "bad")}),
        ("get", {"digest": empty["digest"], "destination": str(repo / "export")}),
        ("import", {"path": str(live_blob)}),
        ("show", {"manifest": "0" * 64}),
    ]
    for mode, request in invalid_requests:
        before = snapshot(repo)
        fail(app, work, mode, request)
        assert snapshot(repo) == before
    (work / "source-link").symlink_to(work / "text")
    os.mkfifo(work / "pipe")
    for source in ["source-link", "pipe", "store", "absent"]:
        fail(app, work, "import", {"path": str(work / source)})
    (work / "destination-link").symlink_to("missing")
    fail(app, work, "get", {"digest": empty["digest"], "destination": str(work / "destination-link")})

    # Known interruption points distinguish unpublished objects from committed roots.
    for label in ["manifest_staged", "manifest_published", "ref_staged", "ref_published"]:
        interrupted_repo, _config = setup(directory / ("fail-" + label))
        current = interrupted_repo.parent
        invoke(app, current, "init")
        blob = imported(app, current, "input", b"old and new share this blob")
        previous = attach(app, current, {"old": blob}, [], "live")
        request = {"name": "live", "expected": previous, "files": {"new": blob}, "includes": [], "metadata": {}}
        fail(app, current, "manifest", request, STORE_FAIL=label)
        selected = invoke(app, current, "list")["references"]["live"]
        assert (selected == previous) == (label != "ref_published")
        invoke(app, current, "show", {"manifest": selected})
        assert list((interrupted_repo / "staging").iterdir()) == []
        collected(app, current)
        invoke(app, current, "verify")

    for label in ["blob_staged", "blob_published"]:
        interrupted_repo, _config = setup(directory / ("fail-" + label))
        current = interrupted_repo.parent
        invoke(app, current, "init")
        (current / "data").write_bytes(b"interrupted blob")
        fail(app, current, "import", {"path": str(current / "data")}, STORE_FAIL=label)
        listing = invoke(app, current, "list")
        assert listing["nodes"] == (1 if label == "blob_published" else 0)
        assert list((interrupted_repo / "staging").iterdir()) == []
        invoke(app, current, "import", {"path": str(current / "data")})
        collected(app, current)

    for label in ["manifest_staged", "ref_staged", "ref_published"]:
        interrupted_repo, _config = setup(directory / ("kill-" + label))
        current = interrupted_repo.parent
        invoke(app, current, "init")
        blob = imported(app, current, "data", b"durable root")
        previous = attach(app, current, {"old": blob}, [], "live")
        request = {"name": "live", "expected": previous, "files": {"new": blob}, "includes": [], "metadata": {}}
        pause(app, current, "manifest", request, label, kill)
        selected = invoke(app, current, "list")["references"]["live"]
        assert (selected == previous) == (label != "ref_published")
        collected(app, current)
        invoke(app, current, "show", {"manifest": selected})

    for exists in [False, True]:
        changed_repo, _config = setup(directory / ("changed-" + str(exists)))
        current = changed_repo.parent
        invoke(app, current, "init")
        path = current / "source"
        path.write_bytes(b"before")
        if exists:
            invoke(app, current, "import", {"path": str(path)})
        old_state = snapshot(changed_repo)

        def change(process, signal: Path, path=path, current=current) -> None:
            fail(app, current, "list")  # The first process still owns the repository lock.
            original = path.stat()
            path.write_bytes(b"after!")
            os.utime(path, ns=(original.st_atime_ns, original.st_mtime_ns))
            signal.touch()
            return  # noqa: PLR1711 - explicit return required by repository guidelines

        pause(app, current, "import", {"path": str(path)}, "import_hashed", change)
        assert snapshot(changed_repo) == old_state
        invoke(app, current, "list")

    # Changing the store after marking is caught before deletion, even outside the advisory lock.
    stray = imported(app, work, "stray", b"keep until collection finishes")
    old_state = snapshot(repo)

    def tamper(process, signal: Path) -> None:
        (repo / "refs/extra.json").write_bytes(canonical({"manifest": replacement}))
        signal.touch()
        return  # noqa: PLR1711 - explicit return required by repository guidelines

    pause(app, work, "gc", None, "gc_marked", tamper)
    assert (repo / "blobs" / stray["digest"]).exists()
    (repo / "refs/extra.json").unlink()
    assert snapshot(repo) == old_state
    fail(app, work, "gc", STORE_FAIL="gc_removed")
    collected(app, work)
    assert invoke(app, work, "show", {"manifest": replacement})["reachable"]["blobs"] == [empty["digest"]]

    # Real publication failures preserve the old reference; the next collection removes only orphans.
    for blocked in ["staging", "manifests", "refs"]:
        current_repo, _config = setup(directory / ("permission-" + blocked))
        current = current_repo.parent
        invoke(app, current, "init")
        blob = imported(app, current, "data", b"permission test")
        previous = attach(app, current, {"old": blob}, [], "live")
        (current_repo / blocked).chmod(0o500)
        try:
            fail(
                app,
                current,
                "manifest",
                {"name": "live", "expected": previous, "files": {"new": blob}, "includes": [], "metadata": {}},
            )
        finally:
            (current_repo / blocked).chmod(0o700)
        assert invoke(app, current, "list")["references"]["live"] == previous
        collected(app, current)

    # A stopped/corrupt retrieval never publishes its destination or follows a dangling target.
    for corruption in [False, True]:
        target = work / ("get-failed-" + str(corruption))
        saved = live_blob.read_bytes()
        if corruption:
            live_blob.write_bytes(b"corrupt")
        fail(app, work, "get", {"digest": empty["digest"], "destination": str(target)}, STORE_FAIL="get_staged")
        assert not target.exists() and (work / ("." + target.name + ".artifact-incomplete")).exists()
        live_blob.write_bytes(saved)
        fail(app, work, "get", {"digest": empty["digest"], "destination": str(target)})

    # Bounds and namespace protection.
    for key, values in {
        "max_nodes": [0, 1, 10001, True],
        "max_bytes": [0, 1, True],
        "max_blob_bytes": [0, True],
    }.items():
        for value in values:
            (work / "store.json").write_text(json.dumps(dict(config, **{key: value})))
            fail(app, work, "verify")
    (work / "store.json").write_text(json.dumps(config))
    (repo / "blobs" / ("f" * 64)).symlink_to(work / "text")
    before = snapshot(repo)
    fail(app, work, "gc")
    assert snapshot(repo) == before
    (repo / "blobs" / ("f" * 64)).unlink()
    (repo / "staging/unknown").write_bytes(b"must not be silently removed")
    fail(app, work, "list")
    assert (repo / "staging/unknown").read_bytes() == b"must not be silently removed"
    (repo / "staging/unknown").unlink()

    # Exact capacity boundaries and a failed reference publication leave collectable orphans.
    bounded_repo, bounded_config = setup(directory / "capacity")
    current = bounded_repo.parent
    bounded_config.update(max_nodes=1, max_bytes=16, max_blob_bytes=16)
    (current / "store.json").write_text(json.dumps(bounded_config))
    invoke(app, current, "init")
    sixteen = imported(app, current, "sixteen", b"a" * 16)
    assert invoke(app, current, "import", {"path": str(current / "sixteen")})["created"] is False
    for length in [1, 17]:
        (current / "additional").write_bytes(b"b" * length)
        before = snapshot(bounded_repo)
        fail(app, current, "import", {"path": str(current / "additional")})
        assert snapshot(bounded_repo) == before
    bounded_config["max_nodes"] = 2
    (current / "store.json").write_text(json.dumps(bounded_config))
    (current / "additional").write_bytes(b"b")
    fail(app, current, "import", {"path": str(current / "additional")})
    zero = imported(app, current, "zero", b"")
    body = {"version": 1, "files": {"sixteen": sixteen, "zero": zero}, "includes": [], "metadata": {}}
    manifest_id = hashed(canonical(body))
    exact_bytes = 16 + len(canonical(body)) + len(canonical({"manifest": manifest_id}))
    bounded_config.update(max_nodes=3, max_bytes=exact_bytes)
    (current / "store.json").write_text(json.dumps(bounded_config))
    request = {"name": "exact", "expected": "-", "files": body["files"], "includes": [], "metadata": {}}
    fail(app, current, "manifest", request)
    assert invoke(app, current, "list") == {"references": {}, "nodes": 3}
    bounded_config["max_nodes"] = 4
    (current / "store.json").write_text(json.dumps(bounded_config))
    assert invoke(app, current, "manifest", request)["manifest"] == manifest_id
    assert (
        sum(p.stat().st_size for folder in ["blobs", "manifests", "refs"] for p in (bounded_repo / folder).iterdir())
        == exact_bytes
    )
    assert collected(app, current)["removed"] == []
    bounded_config["max_nodes"] = 5
    (current / "store.json").write_text(json.dumps(bounded_config))
    fail(app, current, "import", {"path": str(current / "additional")})
    invoke(app, current, "verify")

    # Large import, deduplication and retrieval must fit in a process smaller than the blob.
    large_repo, _config = setup(directory / "large")
    current = large_repo.parent
    source = current / "large.bin"
    size = 160 * 1024 * 1024 + 43
    with source.open("wb") as stream:
        stream.write(b"header")
        stream.seek(size - 4)
        stream.write(b"tail")
    expected_hash = hashlib.sha256()
    with source.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            expected_hash.update(chunk)
    invoke(app, current, "init")
    limited = Application(["/usr/bin/prlimit", "--as=134217728", "--", *app.command], app.engine)
    value = invoke(limited, current, "import", {"path": str(source)})
    assert value == {"digest": expected_hash.hexdigest(), "size": size, "created": True}
    assert invoke(limited, current, "import", {"path": str(source)})["created"] is False
    root = attach(limited, current, {"large": {"digest": value["digest"], "size": size}}, [], "large")
    assert invoke(limited, current, "gc")["removed"] == []
    target = current / "retrieved"
    invoke(limited, current, "get", {"digest": value["digest"], "destination": str(target)})
    actual_hash = hashlib.sha256()
    with target.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            actual_hash.update(chunk)
    assert actual_hash.hexdigest() == expected_hash.hexdigest() and target.stat().st_size == size
    assert invoke(limited, current, "show", {"manifest": root})["reachable"]["blobs"] == [value["digest"]]
    target.unlink()
    source.unlink()
    (large_repo / "blobs" / value["digest"]).unlink()
    return {
        "canonical_manifests": "dependency order independent; Unicode metadata and artifact aliases",
        "reachability": "shared blobs and transitive/diamond dependencies",
        "dag_manifests": 40,
        "dag_live_manifests": len(expected_manifests),
        "dag_live_blobs": len(expected_blobs),
        "publication_failures": 6,
        "killed_publications": 3,
        "changed_sources": 2,
        "corrupt_reachable_cases": 5,
        "invalid_requests": len(invalid_requests) + 5,
        "filesystem_failures": 3,
        "retrieval_failures": 2,
        "changed_graph": "collection aborted",
        "large_blob_bytes": size,
        "address_space_bytes": 134217728,
    }
