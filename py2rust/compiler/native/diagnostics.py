"""Optional native compiler phase tracing, disabled during ordinary compilation."""

from py2rust.stdlib import env_get


def trace_phase(phase: str) -> None:
    if env_get("PY2RUST_TRACE", "") == "1":
        print("py2rust:", phase)
    return
