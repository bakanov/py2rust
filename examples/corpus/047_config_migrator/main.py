"""Upgrade a local configuration, preserving exact original bytes and recovery evidence."""

from transaction import execute, rollback

from py2rust.stdlib import Json, env_get, path_resolve, pretty


def main() -> None:
    mode: str = env_get("MIGRATE_MODE", "preview")
    assert mode in ["preview", "apply", "rollback"], "mode must be preview, apply or rollback"
    # Canonicalize once: sidecars stay beside the actual configuration file.
    path: str = path_resolve(env_get("MIGRATE_FILE", "settings.json"))
    if mode == "rollback":
        print(pretty(rollback(path)))
        return
    report: Json = execute(path, mode == "preview")
    print(pretty(report))
    return


if __name__ == "__main__":
    main()
