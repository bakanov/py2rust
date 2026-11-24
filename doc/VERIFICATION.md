# Verification and release preparation

Use [development setup](DEVELOPMENT.md) to install the pinned frontend and Cargo
dependencies. Run one Cargo-producing check suite at a time. Select programs
relevant to the change; a full corpus run is not required for routine work.

## Before committing

1. Inspect `git status` and the complete diff, including new files and deletions.
   Preserve licenses, runtime lockfiles, source fixtures and application data.
2. Run `ruff check py2rust tools tests`, `black --check py2rust tools tests`,
   `git diff --check`,
   `cargo fmt --check --manifest-path py2rust/compiler/service_runtime/Cargo.toml`,
   and `python tools/generate_native_contracts.py --check`.
3. Run focused regression tests. The CI workflow selects frontend installation,
   typing, whole-project linking and native-source checks, plus UI race checks.
   Add runtime/domain tests when changing their behavior.
4. Build a wheel with `python -m pip wheel --no-deps --wheel-dir DIRECTORY .`.
   Verify its runtime sources, Cargo lockfile and frontend contract are included.
   Install it in a fresh environment and run a complete example from outside the
   checkout so editable imports cannot hide missing package data.
5. Check documentation links and command paths. Mark old benchmark/test results as
   historical evidence with their scope; do not present them as a new test run.
6. Keep caches, generated projects, reports, wheels and dependency installations
   outside the submitted tree. Do not clean chat data as though it were a cache.

The GitHub workflow in `.github/workflows/checks.yml` is a focused check, not a
full regression/corpus certification. Inspect its actual result after pushing.
Preparing the tree does not itself push, publish a package or deploy an application.

## Evidence scopes

- A frontend/type check does not prove the emitted program builds or runs.
- A Rust build does not prove Python/native semantic agreement.
- Source equality establishes generation stability, not independent runtime behavior.
- A passing selected application does not certify all corpus applications.
- Historical reports apply to their recorded source/test fingerprints.
- The native compiler's subset and self-rebuild are documented in
  [self-hosting](SELF_HOSTING.md); they do not establish host feature parity.

Store local logs and build receipts under `PY2RUST_BUILD_DIR`, not in the repository.
Keep durable commands, contracts and limitations here and in the relevant reference
pages instead of accumulating numbered reports.
