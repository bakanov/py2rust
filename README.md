# py2rust

Compile complete applications written in a typed Python subset into standalone
Rust executables. Python is used to compile and test; deployed applications do not
require Python. Local `.rs` imports work directly within transpiled projects.

## Start

Use Linux x86-64, Python 3.10+, Rust/Cargo 1.83+, and rustfmt. Activate a virtual
environment on a Linux filesystem, then run from this directory:

```sh
python tools/build_frontend_wheel.py --fetch --output "$HOME/.cache/py2rust-build/frontend-wheels"
python -m pip install --find-links "$HOME/.cache/py2rust-build/frontend-wheels" -e '.[test,corpus-checks]'
py2rust run examples/projects/json_app -o "$HOME/.cache/py2rust-build/json-app" --offline
python examples/telegram/tools/run.py
```

The first Cargo build needs the dependencies in the lockfile downloaded; omit
`--offline` if they are not cached. `python -m py2rust` is equivalent to `py2rust`.

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
