"""A complete local IPC server and client, built from Python with no embedded interpreter."""

import sys

from client import batch
from server import serve
from settings import configuration, validate_paths

from py2rust.stdlib import env_get


def main() -> None:
    validate_paths()
    policy: dict[str, int] = configuration()
    mode: str = env_get("BUS_MODE", "serve")
    assert mode in ["serve", "client"], "mode must be serve or client"
    if mode == "client":
        if not batch(policy):
            sys.exit(2)
    else:
        serve(policy)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


if __name__ == "__main__":
    main()
