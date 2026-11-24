"""Concurrent native pipelines, binary streams, limits, signals and owned-child cleanup."""

# ruff: noqa: PLR1711 - explicit repository returns
import os
import signal
import subprocess
from pathlib import Path

import pytest

from tools.corpus_checks.process_fixture import build_fixture, gone, ready

from .test_services import program


def source_for(helper: Path, work: Path, body: str) -> str:
    return (
        """from py2rust.stdlib import process_pipeline, json_dumps, sleep, parallel_map, Json

def check() -> None:
    helper: str = """
        + repr(str(helper))
        + """
    cwd: str = """
        + repr(str(work))
        + """
"""
        + body
        + """
    return
if __name__ == "__main__":
    check()
"""
    )


def run_case(tmp_path: Path, engine: str, body: str) -> subprocess.CompletedProcess:
    helper = build_fixture(tmp_path)
    command = program(tmp_path, source_for(helper, tmp_path, body), engine)
    result = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0 and not result.stderr, result
    return result


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_pipeline_arguments_bytes_and_real_concurrency(tmp_path: Path, engine: str) -> None:
    result = run_case(
        tmp_path,
        engine,
        """    commands: list[list[str]] = [[helper,"args","","a b","quote'\\\"","世界😀","$HOME","*"]]
    environments: list[dict[str,str]] = [{}]
    got: tuple[list[int], bytes, list[bytes]] = process_pipeline(commands,environments,cwd,b"",3000,1000)
    assert got[0] == [0] and got[2] == [b""]
    print(got[1].decode())
    commands = [[helper,"emit","1048576","131072"],[helper,"copy"],[helper,"copy"]]
    environments = [{},{},{}]
    got = process_pipeline(commands,environments,cwd,b"",3000,1179648)
    assert got[0] == [0,0,0] and len(got[1]) == 1048576
    assert len(got[2][0]) == 131072 and got[2][1] == b"" and got[2][2] == b""
    for index in range(len(got[1])):
        assert got[1][index] == index % 256
    commands = [[helper,"copy"],[helper,"upper"]]
    environments = [{},{}]
    data: bytes = b""
    for index in range(10000):
        data = data + b"aBc\\x00\\xff"
    got = process_pipeline(commands,environments,cwd,data,3000,50000)
    assert got[0] == [0,0] and len(got[1]) == 50000
    assert got[1][:5] == b"ABC\\x00\\xff" and got[1][-5:] == b"ABC\\x00\\xff"
    print("concurrent binary streams passed")""",
    )
    assert result.stdout.splitlines() == [
        "",
        "612062",
        "71756f74652722",
        "e4b896e7958cf09f9880",
        "24484f4d45",
        "2a",
        "",
        "concurrent binary streams passed",
    ]
    return


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_pipeline_environments_statuses_and_early_reader(tmp_path: Path, engine: str) -> None:
    run_case(
        tmp_path,
        engine,
        '''    commands: list[list[str]] = [[helper,"env","ONLY"]]
    environments: list[dict[str,str]] = [{"ONLY":"世界 value"}]
    got: tuple[list[int],bytes,list[bytes]] = process_pipeline(commands,environments,cwd,b"",3000,1000)
    assert got[1].decode() == "世界 value"
    commands = [[helper,"env","HOME"]]
    got = process_pipeline(commands,environments,cwd,b"",3000,1000)
    assert got[1] == b"<unset>"
    commands = [[helper,"cwd"]]
    got = process_pipeline(commands,environments,cwd,b"",3000,4096)
    assert got[1].decode() == cwd
    commands = [[helper,"exit","7"],[helper,"exit","0"]]
    environments = [{},{}]
    got = process_pipeline(commands,environments,cwd,b"input can be ignored",3000,0)
    assert got[0] == [7,0] and got[1] == b"" and got[2] == [b"",b""]
    commands = [[helper,"signal","15"]]
    environments = [{}]
    got = process_pipeline(commands,environments,cwd,b"",3000,0)
    assert got[0] == [-15]
    commands = [[helper,"emit","1048576","0"],[helper,"take","16"]]
    environments = [{},{}]
    got = process_pipeline(commands,environments,cwd,b"",3000,16)
    assert got[0] == [-13,0] and len(got[1]) == 16
    commands = [[helper,"copy"],[helper,"copy"],[helper,"copy"],[helper,"copy"],[helper,"copy"],[helper,"copy"],[helper,"copy"],[helper,"copy"]]
    environments = [{},{},{},{},{},{},{},{}]
    got = process_pipeline(commands,environments,cwd,b"eight",3000,5)
    assert got[0] == [0,0,0,0,0,0,0,0] and got[1] == b"eight"''',
    )
    return


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_pipeline_cleanup_on_limits_spawn_failure_and_orphans(tmp_path: Path, engine: str) -> None:
    result = run_case(
        tmp_path,
        engine,
        '''    environments: list[dict[str,str]] = [{}]
    commands: list[list[str]] = [[helper,"hold",cwd+"/timeout.pids"]]
    try:
        got: tuple[list[int],bytes,list[bytes]] = process_pipeline(commands,environments,cwd,b"",200,100)
    except Exception as error:
        assert str(error) == "pipeline deadline exceeded"
        print("timeout recovered")
    commands = [[helper,"emit","500000","500000"]]
    try:
        got: tuple[list[int],bytes,list[bytes]] = process_pipeline(commands,environments,cwd,b"",3000,999999)
    except Exception as error:
        assert str(error) == "pipeline output limit exceeded"
        print("output recovered")
    commands = [[helper,"hold",cwd+"/spawn.pids"],[cwd+"/nonexistent"]]
    environments = [{},{}]
    try:
        got: tuple[list[int],bytes,list[bytes]] = process_pipeline(commands,environments,cwd,b"",3000,100)
    except Exception as error:
        assert str(error) == "pipeline spawn failed at stage 1"
        print("spawn recovered")
    commands = [[helper,"orphan",cwd+"/orphan.pids"]]
    environments = [{}]
    got: tuple[list[int],bytes,list[bytes]] = process_pipeline(commands,environments,cwd,b"",3000,0)
    assert got[0] == [0]
    print("orphan cleaned")
    commands = [[helper,"copy"]]
    for index in range(40):
        got = process_pipeline(commands,environments,cwd,b"after failure",3000,13)
        assert got[1] == b"after failure"''',
    )
    assert result.stdout.splitlines() == ["timeout recovered", "output recovered", "spawn recovered", "orphan cleaned"]
    gone(tmp_path / "timeout.pids", minimum=2)
    gone(tmp_path / "spawn.pids")
    gone(tmp_path / "orphan.pids", minimum=2)
    return


@pytest.mark.parametrize("engine", ["python", "rust"])
@pytest.mark.parametrize("number", [signal.SIGINT, signal.SIGTERM])
def test_pipeline_interrupt_cleans_groups_and_recovers(tmp_path: Path, engine: str, number: int) -> None:
    helper = build_fixture(tmp_path)
    body = """    commands: list[list[str]] = [[helper,"hold",cwd+"/interrupt.pids"]]
    environments: list[dict[str,str]] = [{}]
    try:
        got: tuple[list[int],bytes,list[bytes]] = process_pipeline(commands,environments,cwd,b"",10000,0)
    except Exception as error:
        print(str(error))
    commands = [[helper,"args","recovered"]]
    got: tuple[list[int],bytes,list[bytes]] = process_pipeline(commands,environments,cwd,b"",3000,100)
    assert got[0] == [0]
    print(got[1].decode())"""
    command = program(tmp_path, source_for(helper, tmp_path, body), engine)
    process = subprocess.Popen(command, cwd=tmp_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        ready(tmp_path / "interrupt.pids", process)
        os.kill(process.pid, number)
        output, error = process.communicate(timeout=5)
        assert process.returncode == 0 and not error
        assert output.splitlines() == [f"pipeline interrupted by signal {number}", "7265636f7665726564", ""]
        gone(tmp_path / "interrupt.pids", minimum=2)
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=5)
    return


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_pipeline_validation_exact_and_over_boundaries(tmp_path: Path, engine: str) -> None:
    import json

    helper = build_fixture(tmp_path)
    argv = [str(helper), "exit", "0"]
    base = {
        "commands": [argv],
        "environments": [{}],
        "cwd": str(tmp_path),
        "input": "",
        "timeout": 3000,
        "output": 0,
        "error": "",
    }
    cases = []

    def case(error: str = "", **changes: object) -> None:
        cases.append(dict(base, **dict(changes, error=error)))
        return

    case(commands=[argv + [""] * 125])
    size = 65536 - sum(len(value.encode()) + 1 for value in argv) - 1
    case(commands=[argv + ["x" * size]])
    case(environments=[{"E" + str(index): "" for index in range(256)}])
    case(environments=[{"A" * 128: ""}])
    case(environments=[{"A": "x" * 65533}])
    case(input="limit.bin", output=16777216, commands=[[str(helper), "copy"]], timeout=60000)
    for commands in [[], [argv] * 9]:
        case("pipeline requires 1..8 stages", commands=commands)
    case("pipeline environment count mismatch", environments=[])
    for commands in [[[]], [["relative"]], [argv + ["\0"]], [argv + [""] * 126], [argv + ["x" * (size + 1)]]]:
        case(
            "pipeline argv requires an absolute executable and 1..128 NUL-free arguments within 64 KiB",
            commands=commands,
        )
    for environment in [
        {"E" + str(i): "" for i in range(257)},
        {"A" * 129: ""},
        {"A": "x" * 65534},
        {"": ""},
        {"0A": ""},
        {"世界": ""},
        {"A=B": ""},
        {"A": "\0"},
    ]:
        case(
            "pipeline environment requires at most 256 ASCII names and NUL-free values within 64 KiB",
            environments=[environment],
        )
    for cwd in [".", str(tmp_path / "absent"), str(helper), str(tmp_path) + "\0", "/" + "x" * 4096]:
        case("pipeline cwd must be an absolute directory", cwd=cwd)
    for changes in [{"timeout": 0}, {"timeout": 60001}, {"output": -1}, {"output": 16777217}]:
        case("pipeline timeout/output bounds invalid", **changes)
    case("pipeline input exceeds 16 MiB", input="over.bin")
    (tmp_path / "limit.bin").write_bytes(bytes(range(256)) * 65536)
    (tmp_path / "over.bin").write_bytes(b"x" * 16777217)
    (tmp_path / "cases.json").write_text(json.dumps(cases))
    body = """    cases: Json = json_loads(read_text(cwd+"/cases.json"))
    for item in json_array(cases):
        commands: list[list[str]] = []
        environments: list[dict[str,str]] = []
        for stage in json_array(item["commands"]):
            arguments: list[str] = []
            for argument in json_array(stage):
                arguments.append(json_string(argument))
            commands.append(arguments)
        for row in json_array(item["environments"]):
            environment: dict[str,str] = {}
            for name in json_keys(row):
                environment[name] = json_string(row[name])
            environments.append(environment)
        data: bytes = b""
        if json_string(item["input"]) != "":
            data = read_bytes(cwd+"/"+json_string(item["input"]))
        message: str = ""
        try:
            got: tuple[list[int],bytes,list[bytes]] = process_pipeline(commands,environments,json_string(item["cwd"]),data,json_int(item["timeout"]),json_int(item["output"]))
            assert got[0] == [0]
            if len(data) > 0:
                assert got[1] == data
        except Exception as error:
            message = str(error)
        assert message == json_string(item["error"]), message
    print("boundaries passed")"""
    source = source_for(helper, tmp_path, body).replace(
        "def check()",
        "from py2rust.stdlib import json_loads, json_array, json_keys, json_string, json_int, read_text, read_bytes\n\ndef check()",
    )
    command = program(tmp_path, source, engine)
    result = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0 and not result.stderr and result.stdout == "boundaries passed\n", result
    return


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_pipeline_thread_disposition_restoration_and_no_leaks(tmp_path: Path, engine: str) -> None:
    import time

    helper = build_fixture(tmp_path)
    prefix = """from py2rust.stdlib import json_string, write_text, path_exists

def worker(item: Json) -> Json:
    try:
        result: tuple[list[int],bytes,list[bytes]] = process_pipeline([[json_string(item),"copy"]],[{}],"/",b"",1000,0)
    except Exception as error:
        return str(error)
    return "unexpected success"

"""
    body = """    if env_get("CHLD_TEST", "") == "yes":
        try:
            got: tuple[list[int],bytes,list[bytes]] = process_pipeline([[helper,"copy"]],[{}],cwd,b"",1000,0)
        except Exception as error:
            assert str(error) == "pipeline requires the default SIGCHLD disposition"
            print("disposition rejected")
        return
    results: list[Json] = parallel_map(worker,[helper],1)
    assert json_string(results[0]) == "pipeline requires the main thread"
    write_text(cwd+"/ready","yes")
    while not path_exists(cwd+"/continue"):
        sleep(0.01)
    for index in range(50):
        got: tuple[list[int],bytes,list[bytes]] = process_pipeline([[helper,"copy"]],[{}],cwd,b"ok",3000,2)
        assert got[1] == b"ok"
        try:
            got = process_pipeline([[cwd+"/missing"]],[{}],cwd,b"",3000,0)
        except Exception as error:
            assert str(error) == "pipeline spawn failed at stage 0"
    write_text(cwd+"/finished","yes")
    sleep(10.0)"""
    source = source_for(helper, tmp_path, body).replace(
        "def check()", prefix + "from py2rust.stdlib import env_get\n\ndef check()"
    )
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
    assert rejected.returncode == 0 and rejected.stdout == "disposition rejected\n" and not rejected.stderr, rejected
    process = subprocess.Popen(command, cwd=tmp_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:

        def wait_file(name: str) -> None:
            deadline = time.monotonic() + 10
            while not (tmp_path / name).exists():
                assert process.poll() is None and time.monotonic() < deadline
                time.sleep(0.01)
            return

        wait_file("ready")
        fd_path = Path(f"/proc/{process.pid}/fd")
        before = len(list(fd_path.iterdir()))
        (tmp_path / "continue").write_text("yes")
        wait_file("finished")
        assert len(list(fd_path.iterdir())) == before
        assert not Path(f"/proc/{process.pid}/task/{process.pid}/children").read_text().strip()
        process.terminate()
        output, error = process.communicate(timeout=3)
        assert process.returncode == -signal.SIGTERM and not output and not error
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=3)
    return
