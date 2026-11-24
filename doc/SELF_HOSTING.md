# Native compiler and self-hosting

The portable compiler is written in the typed Python subset and can compile its
own source into Rust. The resulting native compiler accepts Python source,
checks it and emits Rust without a Python interpreter. It is a second frontend
and emitter alongside the broader host compiler, not a native build of mypy.

The native subset currently covers the compiler's own implementation and selected
applications. The host CLI, full host memory policies, direct Rust-module import
packaging and Cargo project orchestration remain separate. Do not assume host
feature parity from a successful self-rebuild.

## Build and run

First follow [development setup](DEVELOPMENT.md). Then build a bootstrap executable:

```sh
export PY2RUST_BUILD_DIR="${PY2RUST_BUILD_DIR:-$HOME/.cache/py2rust-build}"
export CARGO_TARGET_DIR="$PY2RUST_BUILD_DIR/service-test-target"
python tools/bootstrap_native.py "$PY2RUST_BUILD_DIR/native-bootstrap" --source --build
```

This initial build uses the Python host compiler and Cargo. Subsequent source
translation runs in the resulting native executable:

```sh
PY2RUST_PYTHON_INPUT=/absolute/path/program.py \
PY2RUST_RUST_OUTPUT=/absolute/path/program.rs \
"$CARGO_TARGET_DIR/debug/py2rust-native-source"
```

For a project, set `PY2RUST_SOURCE_INPUT` instead of `PY2RUST_PYTHON_INPUT`. It names
a JSON array of modules with `name`, `package`, `path` and raw `source` fields.
The entry module is `main`; `path` supplies diagnostic/source-map locations.
The native compiler resolves imports among these modules. The bundle contains
source text, not precomputed IR or Rust output.

The output uses the Rust runtime in `py2rust/compiler/service_runtime`. Package
it with `py2rust.compiler.project_output.write_service_project` and build that
Cargo project. Packaging currently runs on the host; generated applications do
not require Python. Without `--source`, the bootstrap tool builds an IR-input
emitter, which is a different interface and is not source self-hosting evidence.

Set `PY2RUST_TRACE=1` to print compiler phases and emitted function names to stdout.
Tracing is disabled by default and does not change the emitted file.

## Implementation

| Stage | Portable implementation |
| --- | --- |
| Syntax | Runtime Ruff parser exposes bounded, versioned syntax through `python_syntax_tree`; Python reference code supplies the same contract |
| Declarations | `native/declarations.py` resolves imports, annotations and record/function signatures |
| Type checking and lowering | `native/source_frontend.py` produces typed node trees with source locations |
| Ownership | `native/source_ownership.py` and `source_aliases.py` check mutation and returned aliases |
| IR exchange | `native/ir_builder.py` flattens trees; `ir_schema.py` validates typed backward references |
| Rust emission | `native/emitter.py` traverses IR and uses shared production rules in `compiler/rules/` |
| Parameter borrowing | `native/borrowing.py` checks parameter writes and rebinding before choosing shared arguments |

`tools/bootstrap_native.py` stages the actual `native/` and `rules/` Python files
without rewriting them, plus a small Python entry driver. Runtime calls use the
reviewed registry in `library_contracts.py`; regenerate their portable metadata
with `tools/generate_native_contracts.py` and verify it with `--check`.

## Semantic and performance limits

The source frontend rejects unsupported constructs instead of falling back to
Python. Supported records are dataclasses, not arbitrary Python classes. Recursive
record layouts, field writes, general generators/async functions and broad
exception lowering are not native-subset features. The host's wider support is
documented separately in the [subset reference](service-subset.md).

Only proved unshared local containers can be mutated. Parameters, extracted
children and uncertain call results stay conservative. Return-retention summaries
distinguish an original outer object from a fresh container that retains it.
Shallow copies do not establish independence of contained objects. Loop and branch
joins preserve these restrictions; this is not general Python alias analysis.

Read-only value parameters can borrow caller storage. Reassigned or mutated
parameters remain owned. Unknown argument effects preserve snapshots; read-only
slices are recognized as effect-free. Named length/index/slice reads and single
membership tests avoid whole-container copies. Membership evaluates the needle
before borrowing the container. Results remain owned; full lifetime inference and
the host's complete memory oracle are not implemented here.

`TcpListener` and `TcpStream` are opaque runtime handles. TCP operations work, but
handle serialization, structural equality, membership, keys and record fields
are rejected. This does not imply general runtime-class or HTTP response support.

## Verification

Run selected checks rather than treating every corpus example as a native-subset
program:

```sh
python -m pytest tests/test_native_emitter.py tests/test_native_source_frontend.py -q
```

`test_native_source_rebuilds_portable_compiler` compiles the actual portable sources
with the bootstrapped native executable, builds the emitted Rust, then uses the
rebuilt compiler on a multi-module record/JSON application and invalid source.
Compiler invocations disable Python executable/search paths.

The November 24, 2026 self-hosting checkpoint additionally verified:

- All 37 portable modules (228,915 source bytes; 57,989 IR rows) matched the source
  bundle and compiled natively. Output matched the Python reference byte-for-byte.
- The rebuilt compiler reproduced that Rust from the same Python source bundle.
  Self-compilation took 31.76 seconds with `cargo rustc -- -C opt-level=2`.
- A further executable built from that output passed TCP/JSON/file I/O, records
  and membership evaluation-order checks. Nine selected applications were checked
  on the preceding generation, plus invalid-source diagnostics/output preservation.
- Process tracing recorded only the compiler's own `execve`; dynamic linkage had
  no Python library. No full corpus was run for this native checkpoint.

These are scoped historical results, not a performance guarantee or fresh
acceptance for later revisions. The local evidence snapshot is
`$PY2RUST_BUILD_DIR/selfhost/native-source-selfhosted` when retained. It is disposable
build evidence, not a repository dependency. The common generated Rust SHA-256
was `15a08a780e5f09b5a078faf51b4a8bdeb24c149d631ad93c7b97e3300dace330`.
