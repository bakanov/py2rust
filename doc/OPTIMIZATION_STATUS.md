# Optimization implementation map

This page maps the host compiler's optimization mechanisms to the original problem
inventory. See [the plan](OPTIMIZATION_PLAN.md) for goals and
[recorded measurements](OPTIMIZATION_RESULTS.md) for scoped historical results.
Those results do not certify later revisions or the separate native emitter.

| Category | Mechanism | Main boundary |
| --- | --- | --- |
| P01 string builders | Prepared append decisions and `push_str` emission | Evaluate suffix effects before mutating the destination |
| P02 application arguments | Read-only parameter proofs and borrowed ABIs | Unknown effects, callbacks and mutation retain conservative passing |
| P03 runtime arguments | Explicit runtime passing contracts | Shared Rust parameters alone do not establish purity |
| P04 Unicode access | Sparse checkpoints and specialized codepoint caches | Preserve Python-style character indices, negative indices and errors |
| P05 lengths | Invariant character-length plans | Zero-trip loops and mutation invalidate unsafe hoisting |
| P06 iteration | Borrow, consume or snapshot selection | Aliases, mutations, cleanup and later uses constrain selection |
| P07 JSON inspection | Borrowed path and array views | Backing storage must stay valid and unchanged |
| P08 serialization | Direct serialization of compatible representations | Validate types and preserve required output bytes |
| P09 slices | Borrowed byte/list/text views | Backing lifetimes and mutation checks still apply |
| P10 regex | Bounded compiled-pattern cache | Errors, eviction and oversized patterns retain defined behavior |
| P11 moves | Control-flow liveness and resource-aware move checks | Exceptional exits, cleanup and aliases can block moves |
| P12 readability | Mutability, tails, forwarding and reference rendering | Preserve expression order and fallible/cleanup semantics |

[Architecture](ARCHITECTURE.md) names the implementing policy modules.
[Memory oracle](MEMORY_ORACLE.md) describes borrowing, lifetime and alias limits.
[Generated Rust](GENERATED_RUST.md) shows before/after examples from the host
readability pass. Native borrowing and self-compilation performance are documented
separately in [self-hosting](SELF_HOSTING.md).

## Verification

Use semantic tests for values, effects, errors and cleanup; structural gates for
allocation/copy decisions; and dedicated release benchmarks for speed or memory
claims. A compiling Rust program alone does not establish semantic parity. A
structural no-copy check is not a measured speedup. Allocation counts, cumulative
allocated bytes and peak RSS measure different things.

`python tools/check_optimization_gates.py` runs selected structural application
gates. `tools/assess_rust.py` and `tools/assess_unicode_access.py` provide benchmark
entry points; inspect `--help` for their current options. Benchmark source and
thresholds live in `benchmarks/`. Keep generated outputs outside the checkout.
The [checkpoint audit](OPTIMIZATION_AUDIT.md) retains the scope of earlier broad
acceptance; do not add overlapping test counts or treat it as a current pass.
