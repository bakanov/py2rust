# Optimization checkpoint audit

This historical checkpoint covered P01–P12 and performance validation in selected
applications, plus actual before/after examples of more idiomatic generated Rust.
All twelve optimization categories have implemented mechanisms and verified
evidence below. At that checkpoint, broad acceptance passed: **825 tests and 120 applications**.
The bounds of the implemented analyses and guarantees remain explicit.

## Requirement evidence

| Category | Implemented mechanism and evidence | Final acceptance |
| --- | --- | --- |
| P01 builders | Typed self-append decisions; RHS ordering/error tests; four-size scaling; current 10,000-append timing 7.08 µs versus original 22.89 ms | 825 tests / 120 apps passed |
| P02 application arguments | Interprocedural read-only parameter analysis; borrowed ABI; conservative callbacks/mutation boundaries; current length-call kernel matches native | 825 tests / 120 apps passed |
| P03 runtime arguments | Shared-parameter metadata; stable-place borrowing; effectful arguments preserve evaluation snapshots; hashing/write/send tests | 825 tests / 120 apps passed |
| P04 string access | Sparse UTF-8 checkpoints bound random/reverse scans; ASCII direct access; borrowed character views; typed numeric-only codepoint cache; current Unicode kernel 1.14–1.20× native | 825 tests / 120 apps passed |
| P05 lengths | Lazy invariant character lengths and cached-index length reuse; zero-trip, mutation and Unicode tests | 825 tests / 120 apps passed |
| P06 iteration | Read-only borrowing, dead-input consumption and required snapshot preservation; current integer scan 1.01–1.02× native | 825 tests / 120 apps passed |
| P07 JSON views | Borrowed field/index chains and read-only array locals; validator stage 4.3–6.1× improvement; current scalar lookup 1.15–1.39× native | 825 tests / 120 apps passed |
| P08 serialization | Validated direct serialization for supported representations; exact-byte checks; refreshed chat response 2.83× improvement and lower peak RSS | 825 tests / 120 apps passed |
| P09 slices | Borrowed bytes/list slices with backing-lifetime and mutation guards; refreshed traffic parser 1.10× improvement and lower peak RSS | 825 tests / 120 apps passed |
| P10 regex | Bounded cache, uncached oversized patterns, eviction/errors/concurrency tests; actual warm transform stage 54× improvement, cold 1.39× | 825 tests / 120 apps passed |
| P11 moves | Control-flow liveness; cleanup/resource barriers; owned returns and dead iteration inputs move; explicit direct-boundary move/copy/materialization reasons | 825 tests / 120 apps passed |
| P12 readability/prevention | Mutability inference, literal borrowing, Result forwarding, tail expressions and JSON scalar construction; actual chat/traffic/gzip before/after; scoped strict gates | 825 tests / 120 apps passed |

Current timing and memory results: [OPTIMIZATION_RESULTS.md](OPTIMIZATION_RESULTS.md).
Stage-specific application evidence: [OPTIMIZATION_STATUS.md](OPTIMIZATION_STATUS.md).
Actual generated examples: [GENERATED_RUST.md](GENERATED_RUST.md).

## Semantic and reporting boundaries

Owned containers/records retain value and snapshot semantics. Shared resource
handles retain their resource-state and lifetime semantics. Optimizations preserve
negative Unicode indices, bounds/errors, checked arithmetic and cleanup behavior.
Conservative native lowering supplies the oracle where ordinary Python aliases
have different semantics. Python/native parity is used where contracts agree.

Typed decisions, control-flow liveness, recursive call summaries and stable-place
lowering form an incremental analysis layer. The current host compiler has structured typed IR in `compiler/ir.py`, while
its backend still uses a transitional AST adapter. The native compiler has a
separate direct IR emitter; see [architecture](ARCHITECTURE.md). Unreviewed calls
remain unknown; diagnostic effect summaries do not authorize optimization.

`py2rust explain` reports parameter ABI, selected builders/views/iteration and
committed direct-name assignment/return ownership. Its strict checks are
`unknown-effects`, `snapshot-iteration` and `owned-boundary-copy`. See
[their exact scopes](OPTIMIZATION_DIAGNOSTICS.md). None claims whole-function
allocation freedom or universal speed. The registry reviews 51 helpers; uncovered
methods/runtime operations remain conservative unknowns.

A rejected prototype counted speculative name-expression receiver probes as
copies. Current boundary reporting avoids that error; regression tests assert
that `append` receiver probes produce no phantom copies. Reports are also checked
to leave generated Rust unchanged in chat, traffic and gzip.

## Validation evidence

- Pre-follow-up full regression: 817 passed in 878.25 seconds;
  `/tmp/py2rust-full-validation.log`.
- Pre-follow-up complete application run: 120 verified, zero stale/failed/pending;
  `/tmp/py2rust-full-corpus.log`. Preserved status:
  `$HOME/.cache/py2rust-unicode-candidate/preintegration-corpus-status.json`.
- Integrated Unicode/diagnostic follow-up: 61 focused tests and six structural
  application gates passed.
- Numeric-cache follow-up: 58 overlapping Unicode/ord/optimizer checks, two new
  selection/semantic tests, and all seven runtime unit tests passed.
- Fresh measurements verify outputs and run separately from regression/build work;
  allocation counts and whole-process peak RSS are distinct metrics.
- **Final measured version:** full pytest passed **825 tests in 868.21 seconds**.
  All 120 applications passed with zero stale/failed/pending entries. Evidence: `/tmp/py2rust-final-regression.log` and
  `/tmp/py2rust-final-corpus.log`. Every stage and current fingerprint was checked.

Overlapping test counts must not be added together. Earlier full-suite/catalog
passes establish their own compiler version. The final run validates the measured
version: all compiler/runtime hashes match `validation-source-sha256.json` in
`$HOME/.cache/py2rust-quality-final/`, and every application fingerprint is current.
