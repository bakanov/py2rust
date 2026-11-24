"""Paper Plane: Python source compiled into one native Rust web server."""

from app.api import handle
from app.store import initialize

from py2rust.stdlib import env_get, json_int, json_loads, web_serve


def main() -> None:
    initialize()
    port: int = json_int(json_loads(env_get("PAPER_PLANE_PORT", "8765")))
    web_serve(env_get("PAPER_PLANE_HOST", "127.0.0.1"), port, handle)


if __name__ == "__main__":
    main()
