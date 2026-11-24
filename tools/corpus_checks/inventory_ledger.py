"""Accounting, replay, capacity, crash recovery and concurrent-writer acceptance for application 102."""

from __future__ import annotations

import copy
import itertools
import json
import os
import random
import select
import subprocess
from pathlib import Path

from .common import Application
from .inventory_fixture import (
    apply_model,
    balances,
    canonical,
    digest,
    event,
    new_ledger,
    record,
    sequence,
)

ITEMS = ["bolt", "nut", "washer"]


def save(path: Path, value: object) -> None:
    path.write_bytes(canonical(value))
    return  # noqa: PLR1711


def request(
    operations: list, output: str = "output", items: list[str] | None = None, revision: int | None = None
) -> dict:
    return {
        "version": 1,
        "mode": "apply",
        "store": "inventory.json",
        "output": output,
        "items": ITEMS if items is None else items,
        "expected_revision": revision,
        "operations": operations,
    }


def fixture(root: Path, operations: list | None = None, previous: dict | None = None, **options: object) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    config = request(sequence() if operations is None else operations, **options)
    save(root / "inventory-job.json", config)
    if previous is not None:
        save(root / "inventory.json", previous)
    return config


def files_at(root: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in root.iterdir() if p.is_file()}


def inspect(
    root: Path, config: dict, before: int, ledger: dict, outcomes: list[dict], raw: bytes, changed: bool
) -> dict:
    summary = {key: sum(row["status"] == key for row in outcomes) for key in ["accepted", "duplicate", "rejected"]}
    stock = balances(ledger["state"])
    report = {
        "version": 1,
        "mode": config["mode"],
        "before_revision": before,
        "revision": ledger["revision"],
        "head": ledger["head"],
        "changed_store": changed,
        "snapshot_sha256": digest(raw),
        "summary": summary,
        "balances": stock,
        "orders": ledger["state"]["orders"],
        "outcomes": outcomes,
    }
    lines = [f"Inventory ledger revision {ledger['revision']}: " + canonical(summary).decode().strip()]
    lines += [sku + ": " + canonical(row).decode().strip() for sku, row in stock.items()]
    lines += [
        "order " + name + ": " + canonical(row).decode().strip() for name, row in sorted(report["orders"].items())
    ]
    lines += [canonical(row).decode().strip() for row in outcomes]
    files = {
        "ledger.json": raw,
        "report.json": canonical(report),
        "report.txt": ("\n".join(lines) + "\n").encode(),
        "replay.json": canonical({"version": 1, "mode": "verify", "store": "ledger.json", "output": "replayed"}),
        "continue.json": canonical(
            {**request([], "continued", ledger["items"], ledger["revision"]), "store": "ledger.json"}
        ),
    }
    files["manifest.json"] = canonical(
        {name: {"bytes": len(data), "sha256": digest(data)} for name, data in files.items()}
    )
    output = root / config["output"]
    assert {p.name for p in output.iterdir()} == set(files)
    assert files_at(output) == files, root
    assert (root / config["store"]).read_bytes() == raw
    return report


def run(
    app: Application, root: Path, config: dict, previous: dict | None = None, selected: str = "inventory-job.json"
) -> tuple[dict, dict]:
    initial = new_ledger(config["items"]) if previous is None else previous
    path = root / config["store"]
    prior = path.read_bytes() if path.exists() else None
    stamp = path.stat() if prior is not None else None
    if prior is not None:
        assert canonical(json.loads(prior)) == canonical(initial)
    following, outcomes = apply_model(initial, config["operations"]) if config["mode"] == "apply" else (initial, [])
    changed = prior is None or initial["revision"] != following["revision"]
    raw = canonical(following) if changed else prior
    result = app.run(root, {"INVENTORY_CONFIG": str(root / selected)}, timeout=60)
    assert result.returncode == int(any(row["status"] == "rejected" for row in outcomes)) and not result.stderr, (
        root,
        result,
    )
    report = inspect(root, config, initial["revision"], following, outcomes, raw, changed)
    assert result.stdout == canonical(report["summary"]).decode()
    if not changed:
        assert path.stat().st_mtime_ns == stamp.st_mtime_ns and path.stat().st_ino == stamp.st_ino
    return following, report


def consume(app: Application, root: Path, name: str, previous: dict) -> tuple[dict, dict]:
    config = json.loads((root / name).read_bytes())
    return run(app, root, config, previous, name)


def reject(app: Application, root: Path, reason: str = "", preserve_store: bool = True) -> None:
    store = root / "inventory.json"
    prior = store.read_bytes() if preserve_store and store.is_file() else None
    result = app.run(root, {}, timeout=10)
    assert result.returncode == 2 and result.stderr and not result.stdout, (root, result)
    assert reason in result.stderr, (reason, result)
    assert not (root / "output").exists() and not list(root.glob(".inventory-*"))
    if prior is not None:
        assert store.read_bytes() == prior
    return  # noqa: PLR1711


def semantics(app: Application, root: Path) -> dict:
    config = fixture(root / "batch")
    final, report = run(app, root / "batch", config)
    assert report["summary"] == {"accepted": 8, "duplicate": 1, "rejected": 7}
    assert final["state"]["stock"] == dict.fromkeys(ITEMS, 0)
    assert final["state"]["orders"] == {
        "orderA": {"status": "released", "items": {}},
        "orderB": {"status": "cancelled", "items": {}},
    }
    # Same sequence in separate invocations must produce the same accepted history.
    work = root / "incremental"
    previous = None
    for index, row in enumerate(sequence()):
        config = fixture(work, [row], output=f"report-{index}")
        previous, _ = run(app, work, config, previous)
    assert previous == final
    # Replaying audit history and applying an exported empty continuation preserve raw bytes and inode.
    snapshot = root / "batch/output"
    replayed, verified = consume(app, snapshot, "replay.json", final)
    continued, empty = consume(app, snapshot, "continue.json", final)
    assert replayed == continued == final and not verified["changed_store"] and not empty["changed_store"]
    # Accepted IDs remain duplicates after orders close; rejected attempts reserve no identity.
    retry = request([row["event"] for row in final["events"]], "retry", revision=final["revision"])
    save(root / "batch/inventory-job.json", retry)
    _, retried = run(app, root / "batch", retry, final)
    assert retried["summary"] == {"accepted": 0, "duplicate": 8, "rejected": 0}
    init = root / "empty-initialization"
    created, initialized = run(app, init, fixture(init, []))
    assert initialized["changed_store"] and created["revision"] == 0
    # Arbitrary request ordering does not alter accepted history or exported canonical data.
    reordered = [{k: row[k] for k in reversed(row)} for row in sequence()]
    for row in reordered:
        if isinstance(row.get("items"), dict):
            row["items"] = dict(reversed(list(row["items"].items())))
    config = fixture(root / "reordered", reordered, items=list(reversed(ITEMS)))
    other, other_report = run(app, root / "reordered", config)
    assert other == final and other_report == report
    return {
        "transactions": len(sequence()),
        "incremental_restarts": len(sequence()),
        "summary": report["summary"],
        "atomic_multi_item_failures": 3,
        "closed_order_idempotency": True,
        "rejected_ids_reusable": True,
        "empty_initialization": True,
        "snapshot_replay_and_continuation": True,
        "canonical_ordering": True,
        "final_ledger_sha256": digest(canonical(final)),
    }


def generated(app: Application, root: Path) -> dict:
    rng = random.Random(102)
    work = root / "mixed"
    config = fixture(work, [event("initial", "receive", dict.fromkeys(ITEMS, 100))])
    previous, _ = run(app, work, config)
    counts = {"accepted": 1, "duplicate": 0, "rejected": 0}
    for batch in range(12):
        operations = []
        for index in range(24):
            kind = rng.choice(["receive", "reserve", "release", "cancel", "reconcile"])
            order = "order" + str(rng.randrange(35)) if kind in {"reserve", "release", "cancel"} else None
            quantities = {sku: rng.randrange(1, 25) for sku in rng.sample(ITEMS, rng.randrange(1, 4))}
            operations.append(event(f"b{batch}_{index}", kind, quantities, order))
        if batch % 2 == 0:
            operations.append(copy.deepcopy(rng.choice(previous["events"])["event"]))
        config = fixture(work, operations, output=f"batch-{batch}", revision=previous["revision"])
        previous, report = run(app, work, config, previous)
        for key in counts:
            counts[key] += report["summary"][key]
    assert all(value > 0 for value in counts.values())
    return {
        "seed": 102,
        "batches": 12,
        "attempts": sum(counts.values()),
        "summary": counts,
        "invariants_checked_after_each_event": True,
        "ledger_sha256": digest(canonical(previous)),
    }


def invalid(app: Application, root: Path) -> dict:
    bad = [None, [], "text", 1, True, {}, {"id": "missing"}, {"op": "receive"}]
    for key, values in {
        "id": [None, False, 1, "", "1start", "x" * 33, "x\n", "a/b", "λ"],
        "op": [None, False, 1, "unknown"],
        "items": [None, [], 1, {}, {"unknown": 1}],
    }.items():
        bad += [{**event("bad", "receive", {"bolt": 1}), key: value} for value in values]
    bad += [event("bad", "receive", {"bolt": value}) for value in [None, True, 1.0, "1", -1, 0, 10**9 + 1]]
    bad += [event("bad", "reserve", {"bolt": 1}, value) for value in ["", "x" * 33, 1]]
    bad += [{**event("bad", "receive", {"bolt": 1}), "extra": 1}, {"id": "bad", "op": "receive"}]
    bad += [event("bad", "release", {"bolt": 1}, "missing"), event("bad", "cancel", order="missing")]
    config = fixture(root / "operations", [event("initial", "receive", dict.fromkeys(ITEMS, 5)), *bad])
    final, report = run(app, root / "operations", config)
    assert report["summary"] == {"accepted": 1, "duplicate": 0, "rejected": len(bad)}
    malformed = []
    base = request([])
    for key, values in {
        "version": [False, 1.0, 2],
        "mode": [None, "other"],
        "items": [[], ["bolt", "bolt"], ["bad!"], [1]],
        "operations": [None, {}, "x"],
        "expected_revision": [-1, True, 0.0, 1, 513],
        "store": ["", "inventory-job.json", "inventory.json.lock"],
        "output": ["", "inventory.json", "inventory.json.lock"],
    }.items():
        for value in values:
            # The .lock store value is a valid different store; test request alias separately below.
            if key == "store" and value == "inventory.json.lock":
                continue
            malformed.append({**base, key: value})
    malformed.extend([{**base, "extra": 1}, {k: v for k, v in base.items() if k != "expected_revision"}])
    malformed.append({"version": 1, "mode": "verify", "store": "inventory.json", "output": "output"})
    for index, config in enumerate(malformed):
        work = root / f"request-{index}"
        fixture(work, [])
        save(work / "inventory-job.json", config)
        reject(app, work)
    # Parser-level errors never initialize a ledger or return per-operation outcomes.
    malformed_json = [
        b"",
        b"{}{}",
        b'{"version":1,"version":1}',
        b"[]",
        b"null",
        b"\xff",
        b"[NaN]",
        b"[9223372036854775808]",
        b'"\\ud800"',
        b"[" * 66 + b"0" + b"]" * 66,
    ]
    for index, raw in enumerate(malformed_json):
        work = root / f"json-{index}"
        fixture(work, [])
        (work / "inventory-job.json").write_bytes(raw)
        reject(app, work)
    # Corrupt every stored layer, including numerically equal non-integer cache values.
    seed, _ = apply_model(
        new_ledger(ITEMS),
        [event("receipt", "receive", dict.fromkeys(ITEMS, 10)), event("hold", "reserve", {"bolt": 3}, "order")],
    )
    mutations = []
    for path, value in [
        (("version",), True),
        (("version",), 1.0),
        (("revision",), 2.0),
        (("revision",), 1),
        (("head",), "0" * 64),
        (("items",), list(reversed(ITEMS))),
        (("extra",), True),
        (("state", "stock", "bolt"), 10.0),
        (("state", "stock", "bolt"), True),
        (("state", "orders", "order", "items", "bolt"), 3.0),
        (("state", "orders", "order", "status"), "cancelled"),
        (("events", 0, "sequence"), 1.0),
        (("events", 0, "sequence"), True),
        (("events", 0, "previous"), "wrong"),
        (("events", 0, "state_sha256"), "wrong"),
        (("events", 0, "hash"), "wrong"),
        (("events", 0, "event", "items", "bolt"), 11),
        (("events", 0, "event", "items", "bolt"), 10.0),
        (("events", 0, "extra"), True),
    ]:
        value_ledger = copy.deepcopy(seed)
        node = value_ledger
        for part in path[:-1]:
            node = node[part]
        node[path[-1]] = value
        mutations.append(value_ledger)
    duplicate = copy.deepcopy(seed)
    duplicate["events"][1]["event"] = duplicate["events"][0]["event"]
    mutations.append(duplicate)
    # A recomputed chain does not excuse an impossible oversubscribed reservation.
    forged = copy.deepcopy(seed)
    forged["events"][1]["event"]["items"]["bolt"] = 11
    forged["state"]["orders"]["order"]["items"]["bolt"] = 11
    forged["events"][1] = record(2, forged["events"][0]["hash"], forged["events"][1]["event"], forged["state"])
    forged["head"] = forged["events"][1]["hash"]
    mutations.append(forged)
    for index, ledger in enumerate(mutations):
        work = root / f"tamper-{index}"
        fixture(work, [], ledger)
        reject(app, work)
    for index, raw in enumerate(malformed_json):
        work = root / f"ledger-json-{index}"
        fixture(work, [])
        (work / "inventory.json").write_bytes(raw)
        reject(app, work)
    assert final["revision"] == 1
    return {
        "rejected_operations": len(bad),
        "invalid_requests": len(malformed),
        "invalid_json_per_input": len(malformed_json),
        "tampered_ledgers": len(mutations),
        "strict_cached_integer_types": True,
        "recomputed_invalid_history_rejected": True,
    }


def limits(app: Application, root: Path) -> dict:
    many = ["sku" + str(i) for i in range(32)]
    work = root / "items-and-quantity"
    config = fixture(
        work,
        [
            event("max", "receive", dict.fromkeys(many, 10**9)),
            event("overflow", "receive", {many[0]: 1}),
            event("all", "reserve", dict.fromkeys(many, 10**9), "o" * 32),
            event("under", "reconcile", {many[0]: 10**9 - 1}),
            event("free", "cancel", order="o" * 32),
            event("zero", "reconcile", dict.fromkeys(many, 0)),
        ],
        items=many,
    )
    _, report = run(app, work, config)
    assert report["summary"] == {"accepted": 4, "duplicate": 0, "rejected": 2}
    work = root / "order-count"
    config = fixture(work, [event("stock", "receive", {"bolt": 128})])
    previous, _ = run(app, work, config)
    config = fixture(work, [event(f"r{i}", "reserve", {"bolt": 1}, f"o{i}") for i in range(128)], output="orders")
    previous, _ = run(app, work, config, previous)
    config = fixture(
        work,
        [event("closed", "cancel", order="o0"), event("over", "reserve", {"bolt": 1}, "new")],
        output="closed-counts",
    )
    previous, report = run(app, work, config, previous)
    assert report["summary"] == {"accepted": 1, "duplicate": 0, "rejected": 1}
    work = root / "event-count"
    previous = None
    for batch in range(4):
        config = fixture(
            work, [event(f"e{batch}_{i}", "reconcile", {"bolt": i % 2}) for i in range(128)], output=f"batch-{batch}"
        )
        previous, _ = run(app, work, config, previous)
    config = fixture(work, [event("over", "receive", {"bolt": 1}), previous["events"][0]["event"]], output="full")
    previous, report = run(app, work, config, previous)
    assert previous["revision"] == 512 and report["summary"] == {"accepted": 0, "duplicate": 1, "rejected": 1}
    # Exact input boundaries and existing raw JSON padding survive an empty batch and replay.
    work = root / "byte-boundaries"
    config = fixture(work, [], new_ledger(ITEMS))
    (work / "inventory-job.json").write_bytes((work / "inventory-job.json").read_bytes().ljust(262144, b" "))
    (work / "inventory.json").write_bytes((work / "inventory.json").read_bytes().ljust(2097152, b" "))
    previous, _ = run(app, work, config, new_ledger(ITEMS))
    consume(app, work / "output", "replay.json", previous)
    for index, (key, value) in enumerate(
        [("items", many + ["extra"]), ("operations", [event(f"e{i}", "receive", {"bolt": 1}) for i in range(129)])]
    ):
        work = root / f"over-count-{index}"
        config = fixture(work, [])
        config[key] = value
        save(work / "inventory-job.json", config)
        reject(app, work)
    for name, size in [("inventory-job.json", 262144), ("inventory.json", 2097152)]:
        work = root / ("over-" + name)
        fixture(work, [], new_ledger(ITEMS))
        path = work / name
        path.write_bytes(path.read_bytes().ljust(size + 1, b" "))
        reject(app, work)
    return {
        "items": 32,
        "quantity": 10**9,
        "identifier_characters": 32,
        "retained_orders": 128,
        "batch_operations": 128,
        "accepted_events": 512,
        "request_bytes": 262144,
        "ledger_bytes": 2097152,
        "duplicates_at_history_capacity": True,
        "closed_orders_count_toward_limit": True,
        "raw_snapshot_preserved_at_byte_limit": True,
    }


def paused(app: Application, root: Path, stage: str, release: Path | None = None) -> tuple[subprocess.Popen, Path]:
    release = root / "release" if release is None else release
    process = subprocess.Popen(
        app.command,
        cwd=root,
        env=app.environment({"INVENTORY_PAUSE": stage, "INVENTORY_RELEASE": str(release), "PYTHONUNBUFFERED": "1"}),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert select.select([process.stdout], [], [], 10)[0], (root, "readiness timeout")
        assert process.stdout.readline() == "PAUSED " + stage + "\n", (root, process.communicate(timeout=5))
    except BaseException:
        stop(process)
        raise
    return process, release


def stop(process: subprocess.Popen) -> None:
    if process.poll() is None:
        process.kill()
    process.communicate(timeout=5)
    process.stdout.close()
    process.stderr.close()
    return  # noqa: PLR1711


def publication(app: Application, root: Path) -> dict:
    seed, _ = apply_model(new_ledger(ITEMS), [event("old", "receive", {"bolt": 10})])
    operations = [event("more", "receive", {"bolt": 5}), event("hold", "reserve", {"bolt": 4}, "order")]
    # Both initial creation and replacement exercise caught failures and abrupt termination.
    for existing, stage, kill in itertools.product(
        [False, True], ["locked", "prepared", "committed", "published"], [False, True]
    ):
        work = root / f"{'existing' if existing else 'new'}-{stage}-{'kill' if kill else 'fault'}"
        initial = seed if existing else new_ledger(ITEMS)
        config = fixture(work, operations, seed if existing else None)
        expected, outcomes = apply_model(initial, operations)
        committed = stage in {"committed", "published"}
        if kill:
            process, _ = paused(app, work, stage)
            try:
                process.kill()
                process.communicate(timeout=5)
                assert process.returncode == -9
            finally:
                stop(process)
        else:
            result = app.run(work, {"INVENTORY_FAULT": stage})
            assert result.returncode == 2 and result.stderr and not result.stdout, (work, result)
            assert not list(work.glob(".inventory-*"))
        store = work / "inventory.json"
        assert store.exists() == (existing or committed)
        if store.exists():
            assert store.read_bytes() == canonical(expected if committed else initial)
        assert (work / "output").exists() == (stage == "published")
        if stage == "published":
            inspect(work, config, initial["revision"], expected, outcomes, canonical(expected), True)
        hidden = sorted(p.name for p in work.glob(".inventory-*"))
        if kill:
            assert len(hidden) == {"locked": 0, "prepared": 2, "committed": 1, "published": 0}[stage]
        inode = (work / "inventory.json.lock").stat().st_ino
        retry = {**config, "output": "retry"}
        save(work / "inventory-job.json", retry)
        following, report = run(app, work, retry, expected if committed else initial)
        assert following == expected
        assert report["summary"] == {
            "accepted": 0 if committed else 2,
            "duplicate": 2 if committed else 0,
            "rejected": 0,
        }
        assert (work / "inventory.json.lock").stat().st_ino == inode
        assert sorted(p.name for p in work.glob(".inventory-*")) == hidden
    # A stale optimistic revision is fatal even when all operation IDs were already committed.
    work = root / "stale-revision-after-commit"
    config = fixture(work, operations, seed, revision=seed["revision"])
    result = app.run(work, {"INVENTORY_FAULT": "committed"})
    assert result.returncode == 2
    reject(app, work, "revision conflict")
    return {
        "caught_faults": 8,
        "hard_kills": 8,
        "initial_and_existing_store": True,
        "whole_batch_commit": True,
        "committed_retry_idempotent": True,
        "uncommitted_retry_applies_once": True,
        "complete_or_absent_report": True,
        "stable_lock_inode": True,
        "hard_kill_staging_retained": True,
        "stale_revision_after_commit_rejected": True,
    }


def races(app: Application, root: Path) -> dict:
    seed, _ = apply_model(new_ledger(ITEMS), [event("old", "receive", {"bolt": 10})])
    operations = [event("more", "receive", {"bolt": 5})]
    for mutation in ["request", "store", "new-store", "output-before", "output-after", "store-permission"]:
        work = root / mutation
        existing = mutation != "new-store"
        config = fixture(work, operations, seed if existing else None)
        stage = "committed" if mutation == "output-after" else "prepared"
        process, release = paused(app, work, stage, root / ("release-" + mutation))
        try:
            if mutation == "request":
                with (work / "inventory-job.json").open("ab") as stream:
                    stream.write(b" ")
            elif mutation == "store":
                with (work / "inventory.json").open("ab") as stream:
                    stream.write(b" ")
            elif mutation == "new-store":
                save(work / "inventory.json", seed)
            elif mutation.startswith("output"):
                (work / "output").mkdir()
                (work / "output/keep").write_text("competitor")
            else:
                # Fails rename after staging, outside the per-operation rejection boundary.
                work.chmod(0o500)
            expected = (work / "inventory.json").read_bytes()
            release.touch()
            stdout, stderr = process.communicate(timeout=10)
            assert process.returncode == 2 and stderr and not stdout, (mutation, stdout, stderr)
            assert (work / "inventory.json").read_bytes() == expected
            if mutation.startswith("output"):
                assert {p.name for p in (work / "output").iterdir()} == {"keep"}
                assert (work / "output/keep").read_text() == "competitor"
            else:
                assert not (work / "output").exists()
            if mutation != "store-permission":
                assert not list(work.glob(".inventory-*"))
            if mutation == "output-after":
                committed, _ = apply_model(seed, operations)
                assert expected == canonical(committed)
                retry = {**config, "output": "recovered"}
                save(work / "inventory-job.json", retry)
                _, report = run(app, work, retry, committed)
                assert report["summary"]["duplicate"] == 1
        finally:
            work.chmod(0o700)
            stop(process)
    # The same lock serializes writers and verifiers; after process death the kernel releases it.
    for mode, terminate in itertools.product(["apply", "verify"], [False, True]):
        work = root / f"lock-{mode}-{terminate}"
        fixture(work, operations, seed)
        first, release = paused(app, work, "locked")
        inode = (work / "inventory.json.lock").stat().st_ino
        second_config = request([event("second", "receive", {"bolt": 1})], "second")
        if mode == "verify":
            second_config = {"version": 1, "mode": "verify", "store": "inventory.json", "output": "second"}
        save(work / "second.json", second_config)
        try:
            failed = app.run(work, {"INVENTORY_CONFIG": str(work / "second.json")})
            assert failed.returncode == 2 and failed.stderr and not failed.stdout
            assert (work / "inventory.json").read_bytes() == canonical(seed) and not (work / "second").exists()
            if terminate:
                first.kill()
                first.communicate(timeout=5)
                previous = seed
            else:
                release.touch()
                stdout, stderr = first.communicate(timeout=10)
                assert first.returncode == 0 and not stderr and stdout
                previous, _ = apply_model(seed, operations)
            run(app, work, second_config, previous, "second.json")
            assert (work / "inventory.json.lock").stat().st_ino == inode
        finally:
            stop(first)
    return {
        "input_output_and_permission_races": 6,
        "writer_and_verifier_lock_cases": 4,
        "competing_output_preserved": True,
        "post_commit_report_failure_recoverable": True,
        "lock_released_after_process_death": True,
        "persistence_failure_aborts_request": True,
    }


def filesystem(app: Application, root: Path) -> dict:
    count = 0
    seed = new_ledger(ITEMS)
    for name, kind in itertools.product(
        ["inventory-job.json", "inventory.json", "inventory.json.lock"],
        ["symlink", "hardlink", "fifo", "directory", "unreadable"],
    ):
        work = root / str(count)
        fixture(work, [], seed)
        (work / "inventory.json.lock").touch()
        path = work / name
        raw = path.read_bytes()
        path.unlink()
        target = work / "target"
        target.write_bytes(raw)
        if kind == "symlink":
            path.symlink_to(target)
        elif kind == "hardlink":
            os.link(target, path)
        elif kind == "fifo":
            os.mkfifo(path)
        elif kind == "directory":
            path.mkdir()
        else:
            path.write_bytes(raw)
            path.chmod(0)
        try:
            reject(app, work, preserve_store=False)
            assert target.read_bytes() == raw
        finally:
            if kind == "unreadable":
                path.chmod(0o600)
        count += 1
    for kind in ["file", "directory", "symlink", "permission"]:
        work = root / str(count)
        fixture(work, [event("r", "receive", {"bolt": 1})], seed)
        output = work / "output"
        if kind == "file":
            output.write_text("keep")
        elif kind == "directory":
            output.mkdir()
        elif kind == "symlink":
            output.symlink_to(work / "inventory.json")
        else:
            work.chmod(0o500)
        try:
            result = app.run(work, {})
            assert result.returncode == 2 and result.stderr and not result.stdout
            assert (work / "inventory.json").read_bytes() == canonical(seed)
            if kind == "file":
                assert output.read_text() == "keep"
            elif kind == "directory":
                assert not list(output.iterdir())
            elif kind == "symlink":
                assert output.is_symlink()
            else:
                assert not output.exists()
        finally:
            work.chmod(0o700)
        count += 1
    # The request itself cannot alias the lock, even if its contents would be a valid request.
    work = root / "request-is-lock"
    config = fixture(work, [])
    config["store"] = "inventory-job"
    save(work / "inventory-job.lock", config)
    result = app.run(work, {"INVENTORY_CONFIG": str(work / "inventory-job.lock")})
    assert result.returncode == 2 and "paths must be distinct" in result.stderr
    assert not (work / "inventory-job").exists()
    return {"guarded_paths_and_permissions": count, "request_lock_alias_rejected": True}


def check(app: Application, directory: Path) -> dict:
    observations = {}
    for name, test in [
        ("semantics", semantics),
        ("generated", generated),
        ("invalid", invalid),
        ("limits", limits),
        ("publication", publication),
        ("races", races),
        ("filesystem", filesystem),
    ]:
        observations[name] = test(app, directory / name)
        print(app.engine + " inventory ledger " + name + ": passed", flush=True)
    return observations
