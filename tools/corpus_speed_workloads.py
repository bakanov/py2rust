"""Deterministic, oracle-checked performance jobs for twenty real corpus applications."""

from __future__ import annotations

import importlib
from collections.abc import Callable
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

from corpus_checks.common import Application


def job(identifier: str, root: Path, large: bool) -> tuple[Callable[[Application], object], str, int]:
    """Create a fresh complete input and return its existing independent checker."""
    from assess_corpus_speed import ADDITIONAL

    if identifier in ADDITIONAL:
        from corpus_additional_workloads import job as additional_job

        return additional_job(identifier, root, large)
    names = {
        "068": "huffman",
        "071": "access_log",
        "077": "source_outline",
        "078": "regex_rewrite",
        "079": "automation_language",
        "080": "syntax_highlighter",
        "095": "code_metrics",
        "096": "package_resolver",
        "100": "text_patch",
        "104": "circuit_calculator",
        "105": "telemetry_analyzer",
        "109": "warehouse_simulator",
        "110": "population_simulator",
        "111": "png_inspector",
        "112": "wav_analyzer",
        "113": "bmp_thumbnails",
        "114": "ppm_filters",
        "115": "sprite_atlas",
        "117": "terminal_dashboard",
        "118": "zip_validator",
    }
    m = importlib.import_module("corpus_checks." + names[identifier])
    if identifier == "068":
        n = 1048576 if large else 4096
        data = bytes((i * 17 + i // 101) % 256 for i in range(n))
        case = m.fixture(root, "job", data)
        return lambda app: m.success(app, case), f"{n} input bytes", n
    if identifier == "071":
        n = 8000 if large else 100
        data = (
            b"\n".join(
                m.line(target=f"/route/{i % 31}?page={i % 5}", status="503" if i % 13 == 0 else "200") for i in range(n)
            )
            + b"\n"
        )
        case = m.fixture(root, "job", {"traffic": data})
        return lambda app: m.success(app, case), f"{n} access-log records", n
    if identifier in {"077", "095"}:
        n = 160 if large else 20
        modules = 8 if large else 1
        data = "".join(
            f"def function_{i}(value):\n    if value:\n        return value + {i}\n    return 0\n\n" for i in range(n)
        ).encode()
        if identifier == "077":
            case = m.fixture(root, "job", {f"module{i}": data for i in range(modules)})
            return lambda app: m.run(app, case), f"{modules} modules × {n} Python functions", n * modules
        files = {f"module{i}.py": data for i in range(modules)}
        config = m.fixture(root, files)
        return lambda app: m.run(app, root, config, files), f"{modules} modules × {n} Python functions", n * modules
    if identifier == "078":
        n = 48000 if large else 4000
        case = m.fixture(root)
        data = (b"TODO user=42 DONE\n" * (n // 18 + 1))[:n]
        case.original["a.txt"] = data
        path = root / "a.txt"
        path.chmod(0o600)
        path.write_bytes(data)
        mode, stamp = case.metadata["a.txt"]
        path.chmod(mode)
        os.utime(path, ns=(stamp, stamp))
        case.config["rules"] = [
            {"name": "todo", "pattern": "TODO", "replacement": "done"},
            {"name": "user", "pattern": r"user=[0-9]+", "replacement": "user=hidden"},
        ]
        m.save(case)

        def verify(app: Application) -> dict:
            expected, _ = m.oracle(case)
            actual = m.invoke(app, case, "preview")
            assert actual == expected
            return actual

        return verify, f"{n} text bytes; 2 regex rules", n
    if identifier == "079":
        n = 4000 if large else 200
        case = m.fixture(root, f"let x=0; repeat {n} {{ set x=x+1; }}; emit x", budget=10000)
        return lambda app: m.run(app, case, 0), f"{n} interpreter loop iterations", n
    if identifier == "080":
        n = 1200 if large else 40
        tokens = [
            ("identifier", "value"),
            ("space", " "),
            ("punctuation", "="),
            ("space", " "),
            ("number", "42"),
            ("space", "\n"),
        ] * n
        case = m.fixture(root, expected={"config": tokens})
        return lambda app: m.run(app, case), f"{n} configuration lines / {n*6} tokens", n
    if identifier == "096":
        n = 10 if large else 4
        index, roots = m.binary_tree(n)
        config = m.fixture(root, index, roots, max_steps=10000)
        return (
            lambda app: m.run(app, root, config, timeout=120),
            f"{n} binary-choice packages plus impossible dependency",
            n,
        )
    if identifier == "100":
        n = 900 if large else 50
        before = "".join(f"line-{i}\n" for i in range(n)).encode()
        after = "".join(f'{"changed" if i % 5 == 0 else "line"}-{i}\n' for i in range(n)).encode()
        config = m.fixture(root, before, after)
        return lambda app: m.run(app, root, config, after, timeout=120), f"{n} lines on each side of diff", n
    if identifier == "104":
        f = importlib.import_module("corpus_checks.circuit_fixture")
        n = 16 if large else 4
        tree = f.resistor(100)
        for depth in range(5 if large else 3):
            tree = f.group("series" if depth % 2 else "parallel", tree, tree)
        rows = [f.case(f"network-{i}", tree) for i in range(n)]
        config = m.fixture(root, rows)
        return lambda app: m.run(app, root, config), f"{n} circuits / {n*(63 if large else 15)} nodes", n
    if identifier == "105":
        f = importlib.import_module("corpus_checks.trend_fixture")
        n = 2048 if large else 64
        source = f.document([f.series("latency", [float(10 + i % 17) for i in range(n)])], window=8)
        config = m.fixture(root, source)
        return lambda app: m.run(app, root, config), f"{n} timestamped samples; window 8", n
    if identifier == "109":
        f = importlib.import_module("corpus_checks.warehouse_fixture")
        n = 2000 if large else 100
        source = f.document()
        source["commands"] = (source["commands"] * (n // len(source["commands"]) + 1))[:n]
        config = m.fixture(root, source)
        return lambda app: m.run(app, root, config), f"{n} warehouse commands", n
    if identifier == "110":
        f = importlib.import_module("corpus_checks.population_fixture")
        n = 2048 if large else 64
        config = m.fixture(root, f.document(steps=n))
        return lambda app: m.run(app, root, config), f"4 populations × {n} steps", n
    if identifier == "111":
        f = importlib.import_module("corpus_checks.png_fixture")
        n = 512 if large else 16
        parts = f.minimal()
        parts[1:1] = [(b"vpAg", bytes(range(256)) * 4) for _ in range(n)]
        config = m.fixture(root, f.image(parts))
        return lambda app: m.run(app, root, config, codes=[]), f"{n} ancillary PNG chunks × 1024 bytes", n
    if identifier == "112":
        n = 65536 if large else 1024
        config = m.fixture(root, [(i * 97 % 65536) - 32768 for i in range(n)])
        return lambda app: m.run(app, root, config), f"{n} signed PCM samples", n
    if identifier == "113":
        n = 192 if large else 32
        config = m.fixture(root, [m.bitmap(m.pattern(n, n))])
        return lambda app: m.run(app, root, config), f"{n}×{n} BMP pixels", n * n
    if identifier == "114":
        n = 192 if large else 32
        config = m.fixture(root, m.ppm(m.pattern(n, n)), [{"op": "invert"}, m.threshold(100, "mean")])
        return lambda app: m.run(app, root, config), f"{n}×{n} PPM pixels; invert and threshold", n * n
    if identifier == "115":
        n = 32 if large else 4
        side = 16 if large else 8
        config = m.fixture(
            root, [m.ppm(m.pattern(side, side, seed=i)) for i in range(n)], m.settings(width=80, max_height=256)
        )
        return lambda app: m.run(app, root, config), f"{n} sprites of {side}×{side} pixels", n * side * side
    if identifier == "117":
        f = importlib.import_module("corpus_checks.terminal_fixture")
        n = 128 if large else 16
        source = f.snapshot([f.task(f"task-{i}", label=f"Upload 世界 👩🏽‍💻 é {i}") for i in range(n)])
        config = m.fixture(root, source, refreshes=1)
        return lambda app: m.run(app, root, config), f"{n} Unicode-labelled tasks; one refresh", n
    if identifier == "118":
        n = 512 if large else 16
        entries = [(f"data/{i}.bin", bytes(range(256)) * 16, 8) for i in range(n)]
        config = m.fixture(root, m.standard(entries))
        return lambda app: m.run(app, root, config, codes=set()), f"{n} ZIP entries × 4096 uncompressed bytes", n
    raise ValueError(identifier)


class TimedApplication(Application):
    """Time only the actual application process, excluding fixture and oracle work."""

    def __init__(self, command: list[str], engine: str) -> None:
        super().__init__(command, engine)
        self.observations: list[dict] = []

    def run(self, directory: Path, settings: dict[str, str], timeout: int = 120) -> subprocess.CompletedProcess:
        with tempfile.NamedTemporaryFile(prefix="corpus-speed-time-") as timing:
            original = self.command
            self.command = ["/usr/bin/time", "-q", "-o", timing.name, "-f", "%U %S %M", *original]
            started = time.perf_counter_ns()
            try:
                result = super().run(directory, settings, timeout)
            finally:
                elapsed = (time.perf_counter_ns() - started) / 1e6
                self.command = original
            user, system, rss = Path(timing.name).read_text().split()
            self.observations.append(
                {
                    "wall_ms": elapsed,
                    "user_seconds": float(user),
                    "system_seconds": float(system),
                    "peak_rss_kib": int(rss),
                    "returncode": result.returncode,
                }
            )
        return result


def measure(output: Path, identifiers: list[str], repeats: int) -> None:
    """Alternate engines on fresh jobs and persist each independently checked row."""
    import hashlib
    import platform
    import shutil
    import statistics
    import sys
    import traceback

    if repeats < 1:
        raise ValueError("at least one measured repetition is required")
    repository = Path(__file__).resolve().parents[1]
    from assess_corpus_speed import digest

    compiler_files = [
        path
        for path in (repository / "py2rust").rglob("*")
        if path.is_file() and path.suffix in {".py", ".rs", ".toml", ".lock", ".json"}
    ]
    compiler_hash = digest(compiler_files)
    records = []
    for identifier in identifiers:
        work = output / identifier
        build = json.loads((work / "build.json").read_text())
        if build["status"] != "built":
            raise RuntimeError(f"{identifier}: no successful build; run --phase build first")
        source = repository / "examples/corpus" / build["path"]
        if compiler_hash != build["compiler_sha256"] or digest(list(source.rglob("*.py"))) != build["source_sha256"]:
            raise RuntimeError(f"{identifier}: compiler/application changed; run --phase build first")
        if hashlib.sha256((work / "program").read_bytes()).hexdigest() != build["binary_sha256"]:
            raise RuntimeError(f"{identifier}: executable changed; rebuild before measuring")
        for size in ["small", "large"]:
            samples = {"python": [], "rust": []}
            row = {
                "id": identifier,
                "title": build["title"],
                "size": size,
                "status": "failed",
                "repetitions": repeats,
                "build": build,
                "samples": samples,
            }
            try:
                for repeat in range(repeats + 1):
                    engines = ["python", "rust"] if repeat % 2 == 0 else ["rust", "python"]
                    for engine in engines:
                        run_root = work / "runs" / size / f"{engine}-{repeat}"
                        if run_root.exists():
                            shutil.rmtree(run_root)
                        verify, description, units = job(identifier, run_root, size == "large")
                        paths = sorted(path for path in run_root.rglob("*") if path.is_file())
                        input_hash = hashlib.sha256()
                        for path in paths:
                            input_hash.update(str(path.relative_to(run_root)).encode())
                            input_hash.update(path.read_bytes())
                        fingerprint = input_hash.hexdigest()
                        if "input_sha256" in row:
                            assert fingerprint == row["input_sha256"], "input differs across samples/engines"
                        row.update(
                            description=description,
                            units=units,
                            input_sha256=fingerprint,
                            input_bytes=sum(path.stat().st_size for path in paths),
                        )
                        command = (
                            [sys.executable, str(repository / "examples/corpus" / build["path"] / "main.py")]
                            if engine == "python"
                            else [str(work / "program")]
                        )
                        app = TimedApplication(command, engine)
                        verify(app)
                        assert len(app.observations) == 1, "expected one whole-application invocation per job"
                        if repeat:
                            samples[engine].append(app.observations[0])
                            shutil.rmtree(run_root)  # Keep warm-up inputs/outputs for inspection.
                medians = {
                    engine: statistics.median(item["wall_ms"] for item in values) for engine, values in samples.items()
                }
                row.update(
                    status="measured",
                    median_ms=medians,
                    max_ms={
                        engine: sorted(item["wall_ms"] for item in values)[-1] for engine, values in samples.items()
                    },
                    median_peak_rss_kib={
                        engine: statistics.median(item["peak_rss_kib"] for item in values)
                        for engine, values in samples.items()
                    },
                    rust_over_python=medians["rust"] / medians["python"],
                )
                print(
                    f"{identifier} {size}: Rust {medians['rust']:.2f} ms; Python {medians['python']:.2f} ms; Rust/Python {row['rust_over_python']:.2f}x",
                    flush=True,
                )
            except Exception as error:
                row["error"] = traceback.format_exc()
                print(f"{identifier} {size}: FAILED {error}", flush=True)
            record = work / f"{size}-measurements.json"
            if record.exists():
                history = output / "measurement-history"
                history.mkdir(exist_ok=True)
                shutil.copyfile(record, history / f"{identifier}-{size}-{time.time_ns()}.json")
            record.write_text(json.dumps(row, indent=2) + "\n")
            records.append(row)
            (output / "measurements.json").write_text(
                json.dumps(
                    {
                        "platform": platform.platform(),
                        "python": platform.python_version(),
                        "rustc": subprocess.check_output(["rustc", "--version"], text=True).strip(),
                        "method": "Per-row sample counts; one warmup per engine; alternating Python/Rust order; complete application subprocess wall time, CPU time and peak RSS; fixtures and independent oracles excluded; release Rust; native execution without Python on PATH",
                        "rows": [
                            json.loads(path.read_text())
                            for path in sorted(output.glob("[0-9][0-9][0-9]/*-measurements.json"))
                        ],
                    },
                    indent=2,
                )
                + "\n"
            )
    return


def trace(output: Path, identifiers: list[str]) -> None:
    """Separate checked syscall diagnostics; never mix traced runs into timings."""
    import hashlib

    for identifier in identifiers:
        work = output / identifier
        build = json.loads((work / "build.json").read_text())
        binary = work / "program"
        assert build["status"] == "built"
        assert hashlib.sha256(binary.read_bytes()).hexdigest() == build["binary_sha256"]
        destination = Path(tempfile.mkdtemp(prefix="syscall-profile-", dir=work))
        verify, description, _ = job(identifier, destination / "job", True)
        log = destination / "syscalls.txt"
        verify(Application(["/usr/bin/strace", "-f", "-c", "-w", "-o", str(log), str(binary)], "rust"))
        print(f"{identifier}: checked syscall profile of {description}: {log}", flush=True)
    return
