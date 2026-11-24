"""Linux reference backend for bounded foreground pipelines; no shell syntax is interpreted here."""

# ruff: noqa: PLR1711 - explicit repository returns

import contextlib
import os
import re
import selectors
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

_signals_active = False


class _Signals:
    """One main-thread owner shared by foreground execution and a live process pool."""

    def __init__(self) -> None:
        global _signals_active
        self.saved: dict = {}
        self.closed = True
        self.number = 0
        if sys.platform != "linux":
            raise ValueError("pipeline currently requires Linux")
        if threading.current_thread() is not threading.main_thread():
            raise ValueError("pipeline requires the main thread")
        if signal.getsignal(signal.SIGCHLD) != signal.SIG_DFL:
            raise ValueError("pipeline requires the default SIGCHLD disposition")
        if _signals_active:
            raise ValueError("process signal ownership is already active")
        _signals_active = True
        self.closed = False
        try:
            for number in [signal.SIGINT, signal.SIGTERM]:
                self.saved[number] = signal.signal(number, self.interrupt)
        except BaseException:
            self.close()
            raise
        return

    def interrupt(self, number: int, _frame: object) -> None:
        if not self.number:
            self.number = number
        return

    def close(self) -> None:
        global _signals_active
        if not self.closed:
            for number, handler in reversed(self.saved.items()):
                signal.signal(number, handler)
            self.closed = True
            _signals_active = False
        return


class _ExecutionFailure(ValueError):
    """An expected execution outcome with bounded bytes observed before cancellation."""

    def __init__(self, kind: str, message: str, interrupt_signal: int = 0) -> None:
        super().__init__(message)
        self.kind = kind
        self.interrupt_signal = interrupt_signal
        self.stdout = b""
        self.stderr: list[bytes] = []
        return


def _validate(
    commands: list[list[str]],
    environments: list[dict[str, str]],
    cwd: str,
    data: bytes,
    timeout_ms: int,
    max_output: int,
) -> None:
    if not 1 <= len(commands) <= 8:
        raise ValueError("pipeline requires 1..8 stages")
    if len(environments) != len(commands):
        raise ValueError("pipeline environment count mismatch")
    if not 1 <= timeout_ms <= 60000 or not 0 <= max_output <= 16777216:
        raise ValueError("pipeline timeout/output bounds invalid")
    if len(data) > 16777216:
        raise ValueError("pipeline input exceeds 16 MiB")
    if len(cwd.encode()) > 4096 or "\0" in cwd or not Path(cwd).is_absolute() or not Path(cwd).is_dir():
        raise ValueError("pipeline cwd must be an absolute directory")
    for arguments, environment in zip(commands, environments, strict=True):
        if (
            not 1 <= len(arguments) <= 128
            or any("\0" in value for value in arguments)
            or sum(len(value.encode()) + 1 for value in arguments) > 65536
            or not Path(arguments[0]).is_absolute()
        ):
            raise ValueError(
                "pipeline argv requires an absolute executable and 1..128 NUL-free arguments within 64 KiB"
            )
        if (
            len(environment) > 256
            or any(
                not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,127}", key) or "\0" in value
                for key, value in environment.items()
            )
            or sum(len(key.encode()) + len(value.encode()) + 2 for key, value in environment.items()) > 65536
        ):
            raise ValueError("pipeline environment requires at most 256 ASCII names and NUL-free values within 64 KiB")
    return


def process_pipeline(
    commands: list[list[str]],
    environments: list[dict[str, str]],
    cwd: str,
    data: bytes,
    timeout_ms: int,
    max_output: int,
) -> tuple[list[int], bytes, list[bytes]]:
    """Run concurrent direct-argv stages; capture bounded bytes and always reap owned leaders.

    This foreground API requires Linux's main thread and a default SIGCHLD
    disposition. Each stage gets its own process group. SIGINT/SIGTERM cancel the
    call; previous dispositions are restored after cleanup. Environments are
    complete replacements, and executable paths are absolute. Nonzero exits are
    results, while validation, spawning, I/O, deadlines and cancellation raise.
    """
    if sys.platform != "linux":
        raise ValueError("pipeline currently requires Linux")
    _validate(commands, environments, cwd, data, timeout_ms, max_output)
    signals = _Signals()
    deadline = time.monotonic() + timeout_ms / 1000
    children: list[subprocess.Popen] = []
    streams = []
    captured = [bytearray() for _ in range(len(commands) + 1)]

    def cancel_check() -> None:
        if signals.number:
            raise _ExecutionFailure("interrupted", f"pipeline interrupted by signal {signals.number}", signals.number)
        if time.monotonic() >= deadline:
            raise _ExecutionFailure("timeout", "pipeline deadline exceeded")
        return

    def kill_groups() -> None:
        for child in children:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(child.pid, signal.SIGKILL)
        return

    try:
        incoming = None
        writer = None
        readers = [None] * (len(commands) + 1)
        for index, (arguments, environment) in enumerate(zip(commands, environments, strict=True)):
            cancel_check()
            try:
                child = subprocess.Popen(
                    arguments,
                    stdin=subprocess.PIPE if incoming is None else incoming,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=cwd,
                    env=environment,
                    process_group=0,
                    bufsize=0,
                )
            except OSError as error:
                raise _ExecutionFailure("spawn_error", f"pipeline spawn failed at stage {index}") from error
            children.append(child)
            if incoming is not None:
                incoming.close()
            if index == 0:
                writer = child.stdin
                streams.append(writer)
            incoming = child.stdout
            readers[index + 1] = child.stderr
            streams.extend([child.stdout, child.stderr])
        readers[0] = incoming
        statuses = [None] * len(commands)
        position = 0
        total = 0
        groups_killed = False
        with selectors.DefaultSelector() as selector:
            for index, stream in enumerate(readers):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ, index)
            os.set_blocking(writer.fileno(), False)
            if data:
                selector.register(writer, selectors.EVENT_WRITE, -1)
            else:
                writer.close()
                writer = None
            while True:
                cancel_check()
                for index, child in enumerate(children):
                    if statuses[index] is None:
                        state = os.waitid(os.P_PID, child.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
                        if state is not None:
                            statuses[index] = state.si_status if state.si_code == os.CLD_EXITED else -state.si_status
                if all(status is not None for status in statuses):
                    if not groups_killed:
                        kill_groups()
                        groups_killed = True
                        if writer is not None:
                            selector.unregister(writer)
                            writer.close()
                            writer = None
                    if not selector.get_map():
                        break
                for key, _events in selector.select(min(0.01, max(0.0, deadline - time.monotonic()))):
                    index = key.data
                    stream = key.fileobj
                    if index == -1:
                        try:
                            count = os.write(stream.fileno(), data[position : position + 65536])
                            position += count
                        except (BlockingIOError, InterruptedError):
                            continue
                        except BrokenPipeError:
                            count = 0
                        if position == len(data) or count == 0:
                            selector.unregister(stream)
                            stream.close()
                            writer = None
                    else:
                        try:
                            chunk = os.read(stream.fileno(), min(65536, max_output - total + 1))
                        except (BlockingIOError, InterruptedError):
                            continue
                        if not chunk:
                            selector.unregister(stream)
                            stream.close()
                        else:
                            captured[index].extend(chunk[: max_output - total])
                            total += len(chunk)
                            if total > max_output:
                                raise _ExecutionFailure("output_limit", "pipeline output limit exceeded")
        return statuses, bytes(captured[0]), [bytes(value) for value in captured[1:]]
    except _ExecutionFailure as error:
        error.stdout = bytes(captured[0])
        error.stderr = [bytes(value) for value in captured[1:]]
        raise
    finally:
        try:
            for stream in streams:
                with contextlib.suppress(OSError):
                    stream.close()
            kill_groups()
            for child in children:
                child.wait()
        finally:
            signals.close()


def process_run(
    arguments: list[str],
    environment: dict[str, str],
    cwd: str,
    data: bytes,
    timeout_ms: int,
    max_output: int,
) -> tuple[Any, bytes, bytes]:
    """Run one foreground command, retaining captured prefixes for expected failures.

    Metadata has kind, returncode and interrupt_signal. Kinds are exited,
    timeout, output_limit, spawn_error and interrupted. Only exited carries a
    returncode; a signal exit has a negative code. Validation/I/O failures raise.
    The same process-group ownership and argument bounds as process_pipeline apply.
    """
    try:
        codes, output, errors = process_pipeline([arguments], [environment], cwd, data, timeout_ms, max_output)
        return {"kind": "exited", "returncode": codes[0], "interrupt_signal": 0}, output, errors[0]
    except _ExecutionFailure as error:
        return (
            {"kind": error.kind, "returncode": None, "interrupt_signal": error.interrupt_signal},
            error.stdout,
            error.stderr[0],
        )


class ProcessPool:
    """Scoped main-thread ownership of at most 32 concurrently live process groups.

    Polling reads at most limit bytes from each stream, once, without waiting.
    Exit observation kills remaining group members; the direct child is reaped
    only after both pipes reach EOF. Completed IDs are removed and never reused.
    Stdin is /dev/null. Closing kills/reaps all groups and restores signal handlers.
    """

    def __init__(self) -> None:
        self.children: dict[int, subprocess.Popen] = {}
        self.codes: dict[int, int] = {}
        self.next_id = 1
        self.signals = _Signals()
        self.closed = False
        return

    def _check(self) -> None:
        if threading.current_thread() is not threading.main_thread():
            raise ValueError("process pool requires the main thread")
        if self.closed:
            raise ValueError("process pool is closed")
        return

    def __enter__(self) -> "ProcessPool":  # noqa: PYI034 - support the Python 3.10 reference environment
        self._check()
        return self

    def __exit__(self, _kind: object, _value: object, _trace: object) -> None:
        self.close()
        return

    def __del__(self) -> None:
        if hasattr(self, "closed") and not self.closed:
            with contextlib.suppress(Exception):
                self.close()
        return

    def close(self) -> None:
        if threading.current_thread() is not threading.main_thread():
            raise ValueError("process pool requires the main thread")
        if not self.closed:
            try:
                # Signal every group before waiting for any leader.
                for child in self.children.values():
                    with contextlib.suppress(ProcessLookupError):
                        os.killpg(child.pid, signal.SIGKILL)
                for child in self.children.values():
                    child.stdout.close()
                    child.stderr.close()
                    child.wait()
                self.children.clear()
                self.codes.clear()
            finally:
                self.closed = True
                self.signals.close()
        return


def process_pool() -> ProcessPool:
    return ProcessPool()


def process_pool_close(pool: ProcessPool) -> None:
    pool.close()
    return


def process_pool_signal(pool: ProcessPool) -> int:
    pool._check()
    return pool.signals.number


def process_spawn(pool: ProcessPool, arguments: list[str], environment: dict[str, str], cwd: str) -> int:
    pool._check()
    _validate([arguments], [environment], cwd, b"", 1, 0)
    if pool.signals.number:
        raise ValueError("process pool is interrupted")
    if len(pool.children) >= 32 or pool.next_id >= 9223372036854775807:
        raise ValueError("process pool capacity exceeded")
    try:
        child = subprocess.Popen(
            arguments,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            env=environment,
            process_group=0,
            bufsize=0,
        )
    except OSError as error:
        raise ValueError("process pool spawn failed") from error
    identifier = pool.next_id
    pool.next_id += 1
    pool.children[identifier] = child
    try:
        os.set_blocking(child.stdout.fileno(), False)
        os.set_blocking(child.stderr.fileno(), False)
    except BaseException:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(child.pid, signal.SIGKILL)
        child.stdout.close()
        child.stderr.close()
        child.wait()
        del pool.children[identifier]
        raise
    return identifier


def process_signal(pool: ProcessPool, identifier: int, number: int) -> None:
    pool._check()
    if number not in [signal.SIGTERM, signal.SIGKILL]:
        raise ValueError("process pool signal must be TERM or KILL")
    if identifier not in pool.children:
        raise ValueError("unknown process pool child")
    with contextlib.suppress(ProcessLookupError):
        os.killpg(pool.children[identifier].pid, number)
    return


def process_poll(pool: ProcessPool, identifier: int, limit: int) -> tuple[Any, bytes, bytes]:
    pool._check()
    if not 1 <= limit <= 65536:
        raise ValueError("process pool read limit must be 1..65536")
    if identifier not in pool.children:
        raise ValueError("unknown process pool child")
    child = pool.children[identifier]
    if identifier not in pool.codes:
        try:
            state = os.waitid(os.P_PID, child.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
        except InterruptedError:
            state = None
        if state is not None:
            pool.codes[identifier] = state.si_status if state.si_code == os.CLD_EXITED else -state.si_status
            with contextlib.suppress(ProcessLookupError):
                os.killpg(child.pid, signal.SIGKILL)
    output = []
    for stream in [child.stdout, child.stderr]:
        data = b""
        if not stream.closed:
            try:
                data = os.read(stream.fileno(), limit)
                if not data:
                    stream.close()
            except (BlockingIOError, InterruptedError):
                pass
        output.append(data)
    code = pool.codes.get(identifier)
    complete = code is not None and child.stdout.closed and child.stderr.closed
    result = {"pid": child.pid, "exited": code is not None, "returncode": code, "complete": complete}
    if complete:
        child.wait()
        del pool.children[identifier]
        del pool.codes[identifier]
    return result, output[0], output[1]
