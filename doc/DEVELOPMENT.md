# Development

## Setup from a fresh checkout

Use Linux x86-64, Python 3.10 or newer, Rust/Cargo 1.83 or newer, and rustfmt.
Use a Linux filesystem for virtual environments and build output; exFAT does not
support the links and permission semantics required by some tools and tests.

```sh
python3 -m venv "$HOME/.venvs/py2rust"
. "$HOME/.venvs/py2rust/bin/activate"
export PY2RUST_BUILD_DIR="$HOME/.cache/py2rust-build"
export CARGO_TARGET_DIR="$PY2RUST_BUILD_DIR/service-test-target"
python tools/build_frontend_wheel.py --fetch --output "$PY2RUST_BUILD_DIR/frontend-wheels"
python -m pip install --find-links "$PY2RUST_BUILD_DIR/frontend-wheels" -e '.[test,corpus-checks]'
cargo fetch --locked --manifest-path py2rust/compiler/service_runtime/Cargo.toml
py2rust run examples/projects/json_app -o "$PY2RUST_BUILD_DIR/json-app" --offline
```

The frontend builder downloads the immutable mypy revision recorded in
`py2rust/compiler/frontend/mypy-source.json`, checks the complete reviewed source
inventory and builds a pure-Python wheel in temporary storage. The pinned wheel
is a compiler dependency, not an application runtime. For offline installation,
replace `--fetch` with a matching local mypy source directory and use cached Python
and Cargo dependencies. The source directory is never modified.

## Checks

Start with checks relevant to the change. For project/native-source development:

```sh
ruff check py2rust tools tests
black --check py2rust tools tests
python tools/generate_native_contracts.py --check
python -m pytest tests/test_frontend_wheel.py tests/test_project.py tests/test_native_source_frontend.py -q
```

Run `python -m pytest tests -q` for the complete regression suite when needed.
Do not run pytest processes, corpus checks or Cargo-producing verification scripts
concurrently: they share native build destinations. Set `PY2RUST_BUILD_DIR` before
running checks to keep generated projects and evidence outside the checkout.

The application corpus accepts selected IDs, for example `python tools/corpus.py 120`.
Its default is the typed host frontend. A full `python tools/corpus.py` run is
optional broad acceptance, not a routine requirement for every change. The
[application catalog](../examples/corpus/README.md) lists independent interoperability
checks. Historical corpus results do not establish correctness of a later compiler.

Use `python tools/check_optimization_gates.py` for deterministic generated-code
cost checks; see [optimization diagnostics](OPTIMIZATION_DIAGNOSTICS.md). Native
self-hosting has a smaller supported subset and its own [verification guide](SELF_HOSTING.md).

## Application UI

See [Paper Plane](../examples/telegram/README.md) for desktop/web setup. Run
`node examples/telegram/tools/check-ui.cjs` for composer response-race checks.
Inside `examples/telegram`, `npm ci` installs locked dependencies and
`npm run package` creates a desktop package. `PAPER_PLANE_PYTHON` selects the host
Python when launching Electron outside the activated environment.

## Layout and storage

- `py2rust/` contains the compiler, native Rust runtime and Python reference APIs.
- `tests/` contains regression and executable-parity checks.
- `examples/projects/`, `examples/services/` and `examples/corpus/` are source fixtures.
- `examples/telegram/` is the complete desktop/web application.
- `tools/` contains build, generation and verification entry points;
  `tools/corpus_checks/` contains independent application oracles.
- `benchmarks/` contains benchmark source and acceptance thresholds.
- `doc/` contains architecture, semantics, setup and scoped evidence.

Keep generated Cargo projects, target directories, wheels, caches and reports out
of Git. Preserve source fixtures, lockfiles, licenses and application data. Chat
data under `examples/telegram/data/` is ignored and must not be deleted as build
cleanup. Back it up separately. Generated project markers contain absolute source
paths; regenerate outputs after moving the checkout.
