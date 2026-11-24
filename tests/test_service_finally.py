"""Cleanup execution, return/error replacement, nested active errors and invalid loop jumps."""

from pathlib import Path

import pytest
from py2rust.compiler.service import ServiceCompiler, ServiceError

from .test_services import parity


def test_finally_cleanup_and_pending_returns(tmp_path: Path) -> None:
    assert (
        parity(
            tmp_path,
            """from py2rust.stdlib import write_text, read_text

def choose(value: int) -> int:
    try:
        if value == 1:
            return 10
        assert value != 2, "protected"
        return 30
    finally:
        write_text("cleanup", str(value))
        if value == 3:
            return 40

def handler(value: int) -> int:
    try:
        assert value != 0, "caught"
    except Exception:
        return 20
    else:
        return 30
    finally:
        write_text("cleanup", "handler")

def run() -> None:
    assert choose(1) == 10
    assert read_text("cleanup") == "1"
    try:
        choose(2)
    except Exception as error:
        assert str(error) == "protected"
    assert read_text("cleanup") == "2"
    assert choose(3) == 40
    assert handler(0) == 20
    assert handler(1) == 30
    assert read_text("cleanup") == "handler"
    print("pending returns and cleanup")
    return
if __name__ == "__main__":
    run()
""",
        )
        == "pending returns and cleanup\n"
    )
    return  # noqa: PLR1711


def test_finally_exception_precedence_and_bare_raise(tmp_path: Path) -> None:
    assert (
        parity(
            tmp_path,
            """
def suppress() -> int:
    try:
        assert False, "pending"
    finally:
        return 7

def run() -> None:
    assert suppress() == 7
    try:
        try:
            assert False, "old"
        finally:
            assert False, "new"
    except Exception as error:
        assert str(error) == "new"
    try:
        try:
            return
        finally:
            assert False, "overrides return"
    except Exception as error:
        assert str(error) == "overrides return"
    try:
        try:
            assert False, "pending error"
        finally:
            try:
                assert False, "inner"
            except Exception:
                pass
            raise
    except Exception as error:
        assert str(error) == "pending error"
    try:
        assert False, "outer handler"
    except Exception:
        try:
            try:
                pass
            finally:
                raise
        except Exception as error:
            assert str(error) == "outer handler"
    try:
        try:
            pass
        finally:
            raise
    except Exception as error:
        assert str(error) == "No active exception to reraise"
    print("exception precedence")
    return
if __name__ == "__main__":
    run()
""",
        )
        == "exception precedence\n"
    )
    return  # noqa: PLR1711


def test_finally_nested_order_and_loop_local_jumps(tmp_path: Path) -> None:
    assert (
        parity(
            tmp_path,
            """from py2rust.stdlib import read_text, write_text

def nested() -> int:
    try:
        try:
            return 8
        finally:
            write_text("trace", "inner")
    finally:
        write_text("trace", read_text("trace") + " outer")

def run() -> None:
    assert nested() == 8
    assert read_text("trace") == "inner outer"
    value: int = 0
    try:
        for index in range(5):
            if index == 0:
                continue
            try:
                assert False, "inside"
            except Exception:
                if index == 3:
                    break
            value = value + index
    finally:
        for index in range(4):
            if index == 2:
                break
            value = value + 10
    assert value == 23
    try:
        try:
            pass
        except Exception:
            value = 1000
        else:
            assert False, "else failed"
        finally:
            value = value + 1
    except Exception as error:
        assert str(error) == "else failed"
    assert value == 24
    print("nested cleanup and loop-local control")
    return
if __name__ == "__main__":
    run()
""",
        )
        == "nested cleanup and loop-local control\n"
    )
    return  # noqa: PLR1711


@pytest.mark.parametrize(
    "body",
    [
        "try:\n    break\nfinally:\n    pass",
        "try:\n    pass\nfinally:\n    continue",
        "try:\n    pass\nexcept Exception:\n    break\nfinally:\n    pass",
        "try:\n    try:\n        pass\n    except Exception:\n        break\nfinally:\n    pass",
    ],
)
def test_finally_outer_loop_jumps_rejected(body: str) -> None:
    source = "def run() -> None:\n    while True:\n" + "\n".join("        " + line for line in body.splitlines())
    source += "\nif __name__ == '__main__':\n    run()\n"
    with pytest.raises(ServiceError, match="break/continue across a try boundary"):
        ServiceCompiler().compile(source)
    return  # noqa: PLR1711
