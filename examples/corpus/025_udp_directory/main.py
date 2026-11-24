"""Run the directory or its native retrying announcement/discovery client."""

from client import run_client
from config import configuration
from server import serve

from py2rust.stdlib import Json, env_get, json_int, json_loads


def main() -> None:
    mode: str = env_get("DIR_MODE", "serve")
    policy: Json = configuration(mode)
    port: int = json_int(json_loads(env_get("DIR_PORT", "8790")))
    assert port >= 0 and port <= 65535, "invalid UDP port"
    if mode == "client":
        run_client(policy, port)
    else:
        serve(policy, port)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


if __name__ == "__main__":
    main()
