"""Nonblocking child ownership, exact pipe data, scoped cleanup and signal exclusivity."""

import os
import signal
import subprocess
import time
from pathlib import Path

import pytest

from tools.corpus_checks.process_fixture import gone, ready
from tools.corpus_checks.runner_fixture import build_runner_fixture

from .test_services import program


def source_for(helper: Path, work: Path, body: str) -> str:
    return (
        """from py2rust.stdlib import (
    ProcessPool, Json, process_pool, process_pool_close, process_pool_signal, process_spawn, process_poll,
    process_signal, process_run, json_bool, json_int, json_is_null, json_string, sleep, write_text, path_exists,
    parallel_map, monotonic,
)
def drain(pool: ProcessPool, identifier: int, limit: int) -> tuple[int, bytes, bytes]:
    output: bytes = b""
    error: bytes = b""
    for index in range(10000):
        result: tuple[Json,bytes,bytes] = process_poll(pool, identifier, limit)
        assert len(result[1]) <= limit and len(result[2]) <= limit
        output = output + result[1]
        error = error + result[2]
        if json_bool(result[0]["complete"]):
            assert json_bool(result[0]["exited"])
            return (json_int(result[0]["returncode"]), output, error)
        sleep(0.001)
    assert False, "drain deadline"
    return (999, b"", b"")
def check() -> None:
"""
        + "    helper: str = "
        + repr(str(helper))
        + "\n    cwd: str = "
        + repr(str(work))
        + "\n"
        + body
        + """
    return
if __name__ == "__main__":
    check()
"""
    )


def execute(tmp_path: Path, engine: str, body: str) -> subprocess.CompletedProcess:
    helper = build_runner_fixture(tmp_path)
    command = program(tmp_path, source_for(helper, tmp_path, body), engine)
    result = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0 and not result.stderr, result
    return result


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_pool_concurrency_exact_bytes_and_exit_codes(tmp_path: Path, engine: str) -> None:
    result = execute(
        tmp_path,
        engine,
        """    with process_pool() as pool:
        first: int = process_spawn(pool,[helper,"emit","131073","65537","7"],{},cwd)
        second: int = process_spawn(pool,[helper,"env","ONLY"],{"ONLY":"世界"},cwd)
        third: int = process_spawn(pool,[helper,"env","HOME"],{},cwd)
        assert first < second and second < third
        # The second child can complete before the first child is drained.
        two: tuple[int,bytes,bytes] = drain(pool,second,1)
        assert two[0] == 0 and two[1].decode() == "世界" and two[2] == b""
        three: tuple[int,bytes,bytes] = drain(pool,third,3)
        assert three[1] == b"<unset>"
        one: tuple[int,bytes,bytes] = drain(pool,first,65536)
        assert one[0] == 7 and len(one[1]) == 131073 and len(one[2]) == 65537
        for index in range(len(one[1])):
            assert one[1][index] == index % 256
        for byte in one[2]:
            assert byte == 101
        identifier: int = process_spawn(pool,[helper,"copy"],{},cwd)
        empty: tuple[int,bytes,bytes] = drain(pool,identifier,10)
        assert empty[0] == 0 and empty[1] == empty[2] == b""
        identifier = process_spawn(pool,[helper,"signal","15"],{},cwd)
        empty = drain(pool,identifier,10)
        assert empty[0] == -15
        identifier = process_spawn(pool,[helper,"args","a b","$HOME","*","世界"],{},cwd)
        exact: tuple[int,bytes,bytes] = drain(pool,identifier,7)
        assert exact[1].decode() == "612062\\n24484f4d45\\n2a\\ne4b896e7958c\\n"
        identifier = process_spawn(pool,[helper,"cwd"],{},cwd)
        exact = drain(pool,identifier,7)
        assert exact[1].decode() == cwd
    print("concurrent capture passed")""",
    )
    assert result.stdout == "concurrent capture passed\n"
    return  # noqa: PLR1711 - explicit repository returns


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_pool_validation_aliases_capacity_and_signal_exclusivity(tmp_path: Path, engine: str) -> None:
    result = execute(
        tmp_path,
        engine,
        """    saved: ProcessPool = process_pool()
    errors: int = 0
    with saved as pool:
        for index in range(2):
            try:
                if index == 0:
                    process_pool()
                else:
                    process_run([helper,"copy"],{},cwd,b"",1000,0)
            except Exception as error:
                assert str(error) == "process signal ownership is already active"
                errors = errors + 1
        try:
            process_spawn(pool,[cwd+"/missing"],{},cwd)
        except Exception as error:
            assert str(error) == "process pool spawn failed"
            errors = errors + 1
        try:
            process_spawn(pool,[helper,"copy"],{"BAD=NAME":"x"},cwd)
        except Exception:
            errors = errors + 1
        children: list[int] = []
        for index in range(32):
            children.append(process_spawn(pool,[helper,"exit","0"],{},cwd))
        try:
            process_spawn(pool,[helper,"record",cwd+"/must-not-exist"],{},cwd)
        except Exception as error:
            assert str(error) == "process pool capacity exceeded"
            errors = errors + 1
        for limit in [0,65537]:
            try:
                process_poll(pool,children[0],limit)
            except Exception:
                errors = errors + 1
        try:
            process_signal(pool,children[0],2)
        except Exception:
            errors = errors + 1
        for child in children:
            result: tuple[int,bytes,bytes] = drain(pool,child,32)
            assert result[0] == 0
        try:
            process_poll(pool,children[0],1)
        except Exception as error:
            assert str(error) == "unknown process pool child"
            errors = errors + 1
        try:
            process_signal(pool,children[0],15)
        except Exception:
            errors = errors + 1
        assert not path_exists(cwd+"/must-not-exist")
    process_pool_close(saved)
    try:
        process_pool_signal(saved)
    except Exception as error:
        assert str(error) == "process pool is closed"
        errors = errors + 1
    assert errors == 11
    result: tuple[Json,bytes,bytes] = process_run([helper,"copy"],{},cwd,b"restored",1000,8)
    assert result[1] == b"restored"
    with process_pool() as next_pool:
        assert process_pool_signal(next_pool) == 0
    print("validation passed")""",
    )
    assert result.stdout == "validation passed\n"
    return  # noqa: PLR1711 - explicit repository returns


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_pool_nonblocking_lifetime_and_descendant_cleanup(tmp_path: Path, engine: str) -> None:
    result = execute(
        tmp_path,
        engine,
        """    with process_pool() as pool:
        identifier: int = process_spawn(pool,[helper,"hold",cwd+"/hold.pids"],{},cwd)
        while not path_exists(cwd+"/hold.pids"):
            sleep(0.001)
        sleep(0.05)
        started: float = monotonic()
        for index in range(100):
            got: tuple[Json,bytes,bytes] = process_poll(pool,identifier,32)
            assert not json_bool(got[0]["complete"]) and not json_bool(got[0]["exited"])
            assert json_is_null(got[0]["returncode"]) and got[1] == got[2] == b""
        assert monotonic() - started < 1.0
        process_signal(pool,identifier,15)
        sleep(0.02)
        process_signal(pool,identifier,9)
        result: tuple[int,bytes,bytes] = drain(pool,identifier,32)
        assert result[0] == -9
        identifier = process_spawn(pool,[helper,"orphan",cwd+"/orphan.pids"],{},cwd)
        result = drain(pool,identifier,32)
        assert result[0] == 0
    try:
        with process_pool() as failed:
            process_spawn(failed,[helper,"hold",cwd+"/scope.pids"],{},cwd)
            while not path_exists(cwd+"/scope.pids"):
                sleep(0.001)
            sleep(0.05)
            assert False, "intentional"
    except Exception:
        print("scope cleanup passed")""",
    )
    assert result.stdout == "scope cleanup passed\n"
    for name in ["hold", "orphan", "scope"]:
        gone(tmp_path / (name + ".pids"), minimum=2)
    return  # noqa: PLR1711 - explicit repository returns


@pytest.mark.parametrize("engine", ["python", "rust"])
@pytest.mark.parametrize("number", [signal.SIGINT, signal.SIGTERM])
def test_pool_parent_interrupt_and_handler_restoration(tmp_path: Path, engine: str, number: int) -> None:
    helper = build_runner_fixture(tmp_path)
    body = """    with process_pool() as pool:
        process_spawn(pool,[helper,"hold",cwd+"/interrupt.pids"],{},cwd)
        while process_pool_signal(pool) == 0:
            sleep(0.005)
        print(process_pool_signal(pool))
        try:
            process_spawn(pool,[helper,"record",cwd+"/must-not-exist"],{},cwd)
        except Exception as error:
            assert str(error) == "process pool is interrupted"
        assert not path_exists(cwd+"/must-not-exist")
    with process_pool() as recovered:
        assert process_pool_signal(recovered) == 0
    write_text(cwd+"/recovered","yes")
    sleep(10.0)"""
    command = program(tmp_path, source_for(helper, tmp_path, body), engine)
    process = subprocess.Popen(command, cwd=tmp_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        ready(tmp_path / "interrupt.pids", process)
        os.kill(process.pid, number)
        deadline = time.monotonic() + 5
        while not (tmp_path / "recovered").exists():
            assert process.poll() is None and time.monotonic() < deadline
            time.sleep(0.005)
        gone(tmp_path / "interrupt.pids", minimum=2)
        assert not Path(f"/proc/{process.pid}/task/{process.pid}/children").read_text().strip()
        process.terminate()
        output, error = process.communicate(timeout=3)
        assert process.returncode == -signal.SIGTERM and not error and output == str(number) + "\n"
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=3)
    return  # noqa: PLR1711 - explicit repository returns


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_pool_thread_disposition_repeated_scopes_and_no_leaks(tmp_path: Path, engine: str) -> None:
    helper = build_runner_fixture(tmp_path)
    body = """    if env_get("CHLD_TEST", "") == "yes":
        try:
            process_pool()
        except Exception as error:
            assert str(error) == "pipeline requires the default SIGCHLD disposition"
            print("disposition rejected")
        return
    results: list[Json] = parallel_map(worker,[0],1)
    assert json_string(results[0]) == "pipeline requires the main thread"
    write_text(cwd+"/ready","yes")
    while not path_exists(cwd+"/continue"):
        sleep(0.005)
    for index in range(50):
        with process_pool() as pool:
            try:
                process_spawn(pool,[cwd+"/missing"],{},cwd)
            except Exception:
                pass
            identifier: int = process_spawn(pool,[helper,"exit","0"],{},cwd)
            got: tuple[int,bytes,bytes] = drain(pool,identifier,32)
            assert got[0] == 0
        early(helper,cwd)
    write_text(cwd+"/finished","yes")
    sleep(10.0)"""
    prefix = """from py2rust.stdlib import env_get

def worker(item: Json) -> Json:
    try:
        process_pool()
    except Exception as error:
        return str(error)
    return "unexpected success"
def early(helper: str, cwd: str) -> None:
    with process_pool() as pool:
        process_spawn(pool,[helper,"exit","0"],{},cwd)
        return
"""
    source = source_for(helper, tmp_path, body).replace("def check()", prefix + "\ndef check()")
    command = program(tmp_path, source, engine)
    rejected = subprocess.run(
        [str(helper), "ignore-chld", *command],
        env=dict(os.environ, CHLD_TEST="yes"),
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert rejected.returncode == 0 and rejected.stdout == "disposition rejected\n" and not rejected.stderr
    process = subprocess.Popen(command, cwd=tmp_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:

        def wait_file(name: str) -> None:
            deadline = time.monotonic() + 20
            while not (tmp_path / name).exists():
                assert process.poll() is None and time.monotonic() < deadline
                time.sleep(0.005)
            return  # noqa: PLR1711 - explicit repository returns

        wait_file("ready")
        before = len(list(Path(f"/proc/{process.pid}/fd").iterdir()))
        (tmp_path / "continue").touch()
        wait_file("finished")
        assert len(list(Path(f"/proc/{process.pid}/fd").iterdir())) == before
        assert not Path(f"/proc/{process.pid}/task/{process.pid}/children").read_text().strip()
        process.terminate()
        output, error = process.communicate(timeout=3)
        assert process.returncode == -signal.SIGTERM and not output and not error
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=3)
    return  # noqa: PLR1711 - explicit repository returns
