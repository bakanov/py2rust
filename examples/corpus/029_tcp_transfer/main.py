"""One complete project provides both the receiver and the resumable native sender."""

from model import configuration
from receiver import serve
from sender import send

from py2rust.stdlib import env_get, pretty


def main() -> None:
    policy: dict[str, int] = configuration()
    mode: str = env_get("XFER_MODE", "receive")
    assert mode in ["send", "receive"], "mode must be send or receive"
    if mode == "send":
        print(pretty(send(policy)))
    else:
        serve(policy)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


if __name__ == "__main__":
    main()
