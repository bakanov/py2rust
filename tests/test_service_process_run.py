"""Structured native process outcomes retain bounded binary prefixes and clean owned groups."""

import json
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
        "from py2rust.stdlib import Json, process_run, json_canonical, json_int, json_string, json_is_null, "
        "parallel_map, sleep, write_text, path_exists\n\ndef check() -> None:\n"
        + "    helper: str = "
        + repr(str(helper))
        + "\n    cwd: str = "
        + repr(str(work))
        + "\n"
        + body
        + '\n    return\nif __name__ == "__main__":\n    check()\n'
    )


def execute(tmp_path: Path, engine: str, body: str) -> subprocess.CompletedProcess:
    helper = build_runner_fixture(tmp_path)
    command = program(tmp_path, source_for(helper, tmp_path, body), engine)
    result = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, timeout=40, check=False)
    assert result.returncode == 0 and not result.stderr, result
    return result


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_process_run_exact_binary_exit_environment_and_arguments(tmp_path: Path, engine: str) -> None:
    result = execute(
        tmp_path,
        engine,
        """    arguments: list[str] = [helper,"copy"]
    environment: dict[str,str] = {}
    got: tuple[Json,bytes,bytes] = process_run(arguments,environment,cwd,b"hello\\x00\\xff",3000,7)
    assert got[1] == b"hello\\x00\\xff" and got[2] == b""
    assert json_string(got[0]["kind"]) == "exited" and json_int(got[0]["returncode"]) == 0
    assert json_int(got[0]["interrupt_signal"]) == 0
    got = process_run([helper,"emit","65536","65536","7"],{},cwd,b"",3000,131072)
    assert json_int(got[0]["returncode"]) == 7 and len(got[1]) == len(got[2])
    assert len(got[1]) == 65536
    for index in range(len(got[1])):
        assert got[1][index] == index % 256 and got[2][index] == 101
    got = process_run([helper,"env","ONLY"],{"ONLY":"世界 value"},cwd,b"",3000,100)
    assert got[1].decode() == "世界 value"
    got = process_run([helper,"env","HOME"],{},cwd,b"",3000,100)
    assert got[1] == b"<unset>"
    got = process_run([helper,"cwd"],{},cwd,b"",3000,4096)
    assert got[1].decode() == cwd
    got = process_run([helper,"args","a b","$HOME","*","世界"],{},cwd,b"",3000,1000)
    assert got[1].decode() == "612062\\n24484f4d45\\n2a\\ne4b896e7958c\\n"
    got = process_run([helper,"signal","15"],{},cwd,b"",3000,0)
    assert json_string(got[0]["kind"]) == "exited" and json_int(got[0]["returncode"]) == -15
    print("results passed")""",
    )
    assert result.stdout == "results passed\n"


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_process_run_timeout_prefixes_and_closed_pipes(tmp_path: Path, engine: str) -> None:
    started = time.monotonic()
    result = execute(
        tmp_path,
        engine,
        """    got: tuple[Json,bytes,bytes] = process_run(
        [helper,"prefix-hold",cwd+"/prefix.pids"],{},cwd,b"",400,100)
    assert json_string(got[0]["kind"]) == "timeout" and json_is_null(got[0]["returncode"])
    assert got[1] == b"ready\\x00\\xff" and got[2] == b"waiting"
    got = process_run([helper,"closed-hold",cwd+"/closed.pids"],{},cwd,b"input",400,0)
    assert json_string(got[0]["kind"]) == "timeout" and got[1] == b"" and got[2] == b""
    got = process_run([helper,"orphan",cwd+"/orphan.pids"],{},cwd,b"",3000,0)
    assert json_string(got[0]["kind"]) == "exited" and json_int(got[0]["returncode"]) == 0
    got = process_run([helper,"copy"],{},cwd,b"still usable",3000,12)
    assert got[1] == b"still usable"
    print("deadlines passed")""",
    )
    assert result.stdout == "deadlines passed\n"
    # Build time is separate from the child deadline; subprocess.run itself bounds hangs.
    assert time.monotonic() - started < 40
    for name in ["prefix", "closed", "orphan"]:
        gone(tmp_path / (name + ".pids"), minimum=2)


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_process_run_output_limits_preserve_full_bounded_prefix(tmp_path: Path, engine: str) -> None:
    result = execute(
        tmp_path,
        engine,
        """    limits: list[int] = [0,1,65535,65536,65537,100000]
    for limit in limits:
        got: tuple[Json,bytes,bytes] = process_run([helper,"emit","100001","0"],{},cwd,b"",3000,limit)
        assert json_string(got[0]["kind"]) == "output_limit" and json_is_null(got[0]["returncode"])
        assert len(got[1]) == limit and got[2] == b""
        for index in range(len(got[1])):
            assert got[1][index] == index % 256
    got: tuple[Json,bytes,bytes] = process_run([helper,"emit","100000","100000"],{},cwd,b"",3000,99999)
    assert json_string(got[0]["kind"]) == "output_limit" and len(got[1])+len(got[2]) == 99999
    for index in range(len(got[1])):
        assert got[1][index] == index % 256
    for byte in got[2]:
        assert byte == 101
    got = process_run([helper,"flood-hold",cwd+"/flood.pids"],{},cwd,b"",3000,1)
    assert json_string(got[0]["kind"]) == "output_limit" and got[1] == b"x"
    print("capture limits passed")""",
    )
    assert result.stdout == "capture limits passed\n"
    gone(tmp_path / "flood.pids", minimum=2)


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_process_run_spawn_errors_and_invalid_configuration(tmp_path: Path, engine: str) -> None:
    (tmp_path / "not-executable").write_text("not an executable")
    result = execute(
        tmp_path,
        engine,
        """    names: list[str] = [cwd+"/missing",cwd+"/not-executable",cwd]
    for name in names:
        got: tuple[Json,bytes,bytes] = process_run([name],{},cwd,b"",3000,100)
        assert json_string(got[0]["kind"]) == "spawn_error" and json_is_null(got[0]["returncode"])
        assert got[1] == b"" and got[2] == b""
    failures: int = 0
    for limit in [-1,16777217]:
        try:
            got: tuple[Json,bytes,bytes] = process_run([helper,"record",cwd+"/must-not-exist"],{},cwd,b"",100,limit)
        except Exception:
            failures = failures + 1
    for timeout in [0,60001]:
        try:
            got: tuple[Json,bytes,bytes] = process_run([helper,"record",cwd+"/must-not-exist"],{},cwd,b"",timeout,0)
        except Exception:
            failures = failures + 1
    try:
        got: tuple[Json,bytes,bytes] = process_run([helper,"record",cwd+"/must-not-exist"],{"BAD=NAME":"x"},cwd,b"",100,0)
    except Exception:
        failures = failures + 1
    assert failures == 5 and not path_exists(cwd+"/must-not-exist")
    print("spawn and validation passed")""",
    )
    assert result.stdout == "spawn and validation passed\n"


@pytest.mark.parametrize("engine", ["python", "rust"])
@pytest.mark.parametrize("number", [signal.SIGINT, signal.SIGTERM])
def test_process_run_interrupt_result_cleanup_and_restoration(tmp_path: Path, engine: str, number: int) -> None:
    helper = build_runner_fixture(tmp_path)
    body = """    got: tuple[Json,bytes,bytes] = process_run([helper,"prefix-hold",cwd+"/interrupt.pids"],{},cwd,b"",10000,100)
    assert got[1] == b"ready\\x00\\xff" and got[2] == b"waiting"
    print(json_canonical(got[0]))
    got = process_run([helper,"copy"],{},cwd,b"recovered",3000,9)
    assert got[1] == b"recovered"
    write_text(cwd+"/recovered","yes")
    sleep(10.0)"""
    command = program(tmp_path, source_for(helper, tmp_path, body), engine)
    process = subprocess.Popen(command, cwd=tmp_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        ready(tmp_path / "interrupt.pids", process)
        # Readiness proves the children exist; allow the parent to consume the prefix before interrupting it.
        time.sleep(0.05)
        os.kill(process.pid, number)
        deadline = time.monotonic() + 5
        while not (tmp_path / "recovered").exists():
            assert process.poll() is None and time.monotonic() < deadline
            time.sleep(0.005)
        gone(tmp_path / "interrupt.pids", minimum=2)
        assert not Path(f"/proc/{process.pid}/task/{process.pid}/children").read_text().strip()
        process.terminate()
        output, error = process.communicate(timeout=3)
        assert process.returncode == -signal.SIGTERM and not error
        assert json.loads(output) == {"kind": "interrupted", "returncode": None, "interrupt_signal": number}
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=3)


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_process_run_repeated_failure_returns_do_not_leak(tmp_path: Path, engine: str) -> None:
    helper = build_runner_fixture(tmp_path)
    body = """    write_text(cwd+"/ready","yes")
    while not path_exists(cwd+"/continue"):
        sleep(0.01)
    for index in range(50):
        got: tuple[Json,bytes,bytes] = process_run([cwd+"/missing"],{},cwd,b"",3000,0)
        assert json_string(got[0]["kind"]) == "spawn_error"
        got = process_run([helper,"emit","4097","0"],{},cwd,b"",3000,4096)
        assert json_string(got[0]["kind"]) == "output_limit" and len(got[1]) == 4096
        got = process_run([helper,"copy"],{},cwd,b"ok",3000,2)
        assert got[1] == b"ok"
    write_text(cwd+"/finished","yes")
    sleep(10.0)"""
    command = program(tmp_path, source_for(helper, tmp_path, body), engine)
    process = subprocess.Popen(command, cwd=tmp_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:

        def wait_file(name: str) -> None:
            deadline = time.monotonic() + 20
            while not (tmp_path / name).exists():
                assert process.poll() is None and time.monotonic() < deadline
                time.sleep(0.01)
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
