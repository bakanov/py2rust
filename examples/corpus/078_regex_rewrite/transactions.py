"""Publish complete backups, then replace individual files with a durable progress receipt."""

# ruff: noqa: PLR1711 - explicit subset operations
from documents import Document, present, publish, read, stamp
from planning import Plan
from rules import digest

from py2rust.stdlib import (
    Json,
    env_get,
    file_lock,
    file_open,
    file_sync,
    file_write,
    json_array,
    json_canonical,
    json_equal,
    json_int,
    json_loads,
    json_string,
    path_join,
    path_parent,
    path_set_metadata,
    path_stat,
    random_token,
    remove_file,
    replace_file,
    sync_directory,
    write_text_atomic,
)


def replace(path: str, data: bytes, mode: int, mtime: int, preserve_time: bool) -> None:
    temporary: str = path_join(path_parent(path), ".rewrite-file-" + random_token())
    try:
        with file_open(temporary, "x+b") as handle:
            file_write(handle, data)
            if not preserve_time:
                mtime = json_int(stamp(temporary)["mtime_ns"])
            path_set_metadata(temporary, mode, mtime)
            file_sync(handle)
        replace_file(temporary, path)
        sync_directory(path_parent(path))
    except Exception:
        if present(temporary):
            remove_file(temporary)
        raise
    return


def apply(plan: Plan) -> Json:
    assert json_equal(plan.config.stamp, stamp(plan.config.path)), "configuration changed"
    for change in plan.changes:
        assert json_equal(change.original.stamp, stamp(change.original.path)), "input changed"
    with file_lock(plan.backup + ".lock") as _lock:
        files: dict[str, bytes] = {}
        for index in range(len(plan.changes)):
            files[str(index) + ".before"] = plan.changes[index].original.data
            files[str(index) + ".after"] = plan.changes[index].replacement
        files["report.json"] = (json_canonical(plan.report) + "\n").encode()
        files["job.json"] = plan.config.data
        files["state.json"] = (json_canonical({"status": "prepared", "completed": 0}) + "\n").encode()
        publish(plan.backup, files)
        completed: int = 0
        try:
            for change in plan.changes:
                assert env_get("REWRITE_FAIL", "") != str(completed), "injected interruption"
                assert json_equal(
                    change.original.stamp, stamp(change.original.path)
                ), "input changed before replacement"
                if change.original.data != change.replacement:
                    replace(change.original.path, change.replacement, json_int(change.original.stamp["mode"]), 0, False)
                completed = completed + 1
                write_text_atomic(
                    path_join(plan.backup, "state.json"), json_canonical({"status": "applying", "completed": completed})
                )
        except Exception:
            write_text_atomic(
                path_join(plan.backup, "state.json"), json_canonical({"status": "interrupted", "completed": completed})
            )
            raise
        write_text_atomic(
            path_join(plan.backup, "state.json"), json_canonical({"status": "applied", "completed": completed})
        )
    return plan.report


def restore(backup: str) -> Json:
    assert json_string(path_stat(backup, False)["kind"]) == "directory", "backup must be a directory"
    with file_lock(backup + ".lock") as _lock:
        report: Json = json_loads(read(path_join(backup, "report.json"), 1048576).data.decode())
        assert json_int(report["version"]) == 1, "unsupported backup version"
        rows: list[Json] = json_array(report["files"])
        assert 1 <= len(rows) <= 64, "invalid backup file count"
        # Validate every original and current file before restoring the first file.
        originals: list[bytes] = []
        current: list[Json] = []
        for index in range(len(rows)):
            row: Json = rows[index]
            assert json_int(row["index"]) == index, "invalid backup index"
            assert 0 <= json_int(row["mode"]) <= 511, "invalid backup permissions"
            json_int(row["mtime_ns"])
            data: bytes = read(path_join(backup, str(index) + ".before"), 65536).data
            assert digest(data) == json_string(row["before_sha256"]), "corrupt backup"
            now: Document = read(json_string(row["path"]), 65536)
            hashed: str = digest(now.data)
            assert hashed in [
                json_string(row["before_sha256"]),
                json_string(row["after_sha256"]),
            ], "file changed since rewrite"
            originals.append(data)
            current.append(now.stamp)
        write_text_atomic(path_join(backup, "state.json"), json_canonical({"status": "restoring", "completed": 0}))
        for index in range(len(rows)):
            row: Json = rows[index]
            path: str = json_string(row["path"])
            assert json_equal(current[index], stamp(path)), "file changed before restore"
            replace(path, originals[index], json_int(row["mode"]), json_int(row["mtime_ns"]), True)
            write_text_atomic(
                path_join(backup, "state.json"), json_canonical({"status": "restoring", "completed": index + 1})
            )
        write_text_atomic(
            path_join(backup, "state.json"), json_canonical({"status": "restored", "completed": len(rows)})
        )
        return report
