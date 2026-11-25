# py2rust

Compile complete applications written in a typed Python subset into standalone
Rust executables. Python is used to compile and test; deployed applications do not
require Python. Local `.rs` imports work directly within transpiled projects.

## Quick start with Docker (no local Python or Rust)

From the repository root on Linux x86-64, build the image once:

```sh
docker build -t py2rust-demo .
```

Then run the example and benchmark with this command:

```sh
mkdir -p docker-output && docker run --rm --network none \
  --user "$(id -u):$(id -g)" \
  -v "$PWD/docker-output:/output" py2rust-demo
```

Only Docker is required on the host. Building the image downloads Python, Rust,
the pinned frontend and Cargo dependencies. Running the image works offline:
it transpiles the example, compiles both Rust implementations in release mode,
checks their outputs and prints benchmark timings and the sample program's JSON
output directly in your terminal. Compilation may take a few minutes.

Each run creates a new directory under `docker-output/`, preserving earlier runs:

```text
docker-output/run-<timestamp>-<suffix>/
  rust/                       # complete generated Cargo project + native baseline
    src/main.rs               # generated Rust for the Python application
    src/bin/access-log-native.rs
    Cargo.toml
    Cargo.lock
  bin/access-log-generated    # compiled application, no Python runtime
  bin/access-log-native       # compiled handwritten comparison
  sample.jsonl
  results.json                # all timings, medians, ratios and source hashes
  build.log
```

`--user` makes exported files belong to your Linux user. Cargo's intermediate
files stay inside the container and are removed with it, so the output directory
can also be on an external drive. Each run recompiles and measures the current
image; rebuild the image after changing the source. To request a shorter run,
append `--sizes 10000 --samples 3` to the `docker run` command.

To rerun the exported application, use the directory printed by the container:

```sh
cd docker-output/run-<timestamp>-<suffix>
ACCESS_LOG="$PWD/sample.jsonl" ./bin/access-log-generated
```

The executable targets the image's Linux architecture and uses glibc (Debian 12
baseline); this recipe targets Linux x86-64, not a universal static executable.
Docker resource limits and host load affect timings; use the freshly printed
results when assessing your machine. See the [code and benchmark comparison](benchmarks/access_log/README.md).

## Start

Use Linux x86-64, Python 3.10+, Rust/Cargo 1.83+, and rustfmt. Activate a virtual
environment on a Linux filesystem, then run from this directory:

```sh
python tools/build_frontend_wheel.py --fetch --output "$HOME/.cache/py2rust-build/frontend-wheels"
python -m pip install --find-links "$HOME/.cache/py2rust-build/frontend-wheels" -e '.[test,corpus-checks]'
```

### Transpile, compile and run one complete program

The [access-log analyzer](examples/projects/access_log/main.py) reads HTTP request
logs in JSON Lines format and reports requests, errors, bytes, maximum latency,
and counts by route. Its two Python modules demonstrate imports, a dataclass,
typed dictionaries, loops, string operations, validation, environment variables,
file input and JSON input/output. It processes recorded HTTP traffic; it does not
start an HTTP server.

After installation, run this **single command from the repository root**:

```sh
python -m py2rust run examples/projects/access_log --release --name access-log \
  -o "$HOME/.cache/py2rust-build/access-log-example"
```

This transpiles the whole project, invokes Cargo/rustc in release mode, then runs
the resulting executable on the included five-record sample. The first build
needs network access for Cargo dependencies; add `--offline` once they are cached.
Use `build` instead of `run` to transpile and compile without executing.

Generated files remain alongside the executable, outside the checkout:

```text
~/.cache/py2rust-build/access-log-example/
  Cargo.toml             # generated Cargo project
  Cargo.lock
  src/main.rs            # generated Rust for both Python modules
  target/release/access-log
```

The output is a JSON object (shown formatted here):

```json
{
  "requests": 5,
  "errors": 2,
  "total_bytes": 11456,
  "max_elapsed_ms": 120,
  "routes": {"/api/messages": 3, "/files/世界.png": 1, "/api/search": 1}
}
```

Run the compiled application on your own log without invoking Python:

```sh
ACCESS_LOG=/absolute/path/to/events.jsonl \
  "$HOME/.cache/py2rust-build/access-log-example/target/release/access-log"
```

Each input line has `path` (string), `status`, `bytes`, and `elapsed_ms` (integers);
see [sample.jsonl](examples/projects/access_log/sample.jsonl). Blank lines are
ignored and query strings are removed when grouping routes. Without `ACCESS_LOG`,
the program reads `sample.jsonl` in its working directory. The `run` command sets
that directory to the Python project's root.

### Generated Rust versus handwritten Rust

The analyzer's [Python implementation](examples/projects/access_log/analysis.py)
and [handwritten Rust baseline](benchmarks/access_log/native.rs) implement the same
summary for valid log records. Generated Rust already borrows the complete input
as `&str`, uses `i64` counters with checked arithmetic, and produces a standalone
executable. The shared compiler now avoids temporary split lists for immediate
consumers and avoids key allocation on repeated counter hits. Generic JSON
construction and owned derived strings remain optimization targets. See the
[current compiler performance report](doc/COMPILER_PERFORMANCE.md) for measured
before/after results, safety conditions and remaining gaps.

The **original baseline**, before these compiler optimizations, used an Intel
i3-12100 with Rust 1.83.0. Seven alternating release runs gave:

| Log records | Generated Rust (median) | Handwritten Rust (median) | Slowdown |
| ---: | ---: | ---: | ---: |
| 10,000 | 11.30 ms | 2.84 ms | 3.98× |
| 100,000 | 107.04 ms | 22.63 ms | 4.73× |

These include startup, file input, processing and JSON output with warm file
caches. Every result was checked against independently calculated counts, and
both fixtures also matched the Python reference. This workload exceeds our 2×
target; the result is specific to this program and machine.

See [the code comparison and reproducible measurements](benchmarks/access_log/README.md)
for actual generated excerpts, timing results and remaining optimization targets.

## Typed frontend

The mypy-based frontend is the default for project and service commands, including
`explain`. It uses the analyzed Python tree shared with mypyc, then lowers into
compiler-owned typed IR. The pinned pure-Python mypy wheel built above is a
required compiler dependency. Use `--frontend legacy` for explicit comparison
with the previous frontend; unsupported typed input never silently falls back.
The backend transition and final application validation remain in progress.

The wheel is built from an immutable upstream revision and checked against a
reviewed source checksum. Builds happen in a temporary directory. For offline
setup, supply an existing matching checkout instead of `--fetch`. It is a compiler dependency, not an application runtime.
See [frontend migration](doc/FRONTEND_MIGRATION.md) for current coverage and limits.

## Documentation

- [Scaling improvements and final acceptance](doc/SCALING_IMPROVEMENTS.md): general compiler fixes for autocomplete, routing and scheduling, with checked results.
- [Handwritten-Rust performance comparison](doc/NATIVE_PERFORMANCE_GOAL.md): the completed original 20-case gate (with the accepted resolver exception), ten additional comparisons and remaining gaps.

- [Performance of 20 selected corpus applications](doc/CORPUS_SPEED_20.md): complete-job timings, memory, bottleneck analysis and reproducible evidence.

- [Current compiler performance report](doc/COMPILER_PERFORMANCE.md): general split/counter improvements, selected-program verification and remaining gaps.

- [Optimization results](doc/OPTIMIZATION_RESULTS.md): current timing, memory and readability evidence.
- [Optimization plan](doc/OPTIMIZATION_PLAN.md): problem inventory, compiler analyses and regression gates.
- [Generated Rust assessment](doc/RUST_QUALITY.md): measured bottlenecks and priorities.
- [Semantic audit](doc/SEMANTIC_AUDIT.md): supported behavior, deliberate differences and remaining gaps.
- [Translation rules](doc/TRANSLATION_RULES.md): explicit mappings, semantic audit and self-hosting preparation.
- [Architecture](doc/ARCHITECTURE.md): source layout and compiler boundaries.
- [Memory management oracle](doc/MEMORY_ORACLE.md): ownership analysis and proposed checked hints.
- [Self-hosting](doc/SELF_HOSTING.md): native source self-reproduction, usage and limitations.
- [Development](doc/DEVELOPMENT.md): setup, verification and build storage.
- [Migration](doc/MIGRATION.md): rename, removed components and evidence policy.
- [Subset reference](doc/service-subset.md): supported syntax, APIs and limits.
- [Whole projects](doc/projects.md): packages and direct Rust imports.
- [Application catalog](examples/corpus/README.md): 120 complete examples.
- [Paper Plane](examples/telegram/README.md): desktop/web chat and saved notebooks.

This is a Python-like subset, not full CPython compatibility. The compiler and
runtime are maintained here; no installed py2many dependency is needed.

Derived from the MIT-licensed py2many project. The original copyright and license
remain in [LICENSE](LICENSE); see [NOTICE](NOTICE) for attribution.
