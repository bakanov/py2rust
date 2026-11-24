# Systematic performance plan

P01–P12 optimization cores and scoped diagnostics are implemented. The recorded
optimization checkpoint passed 825 tests and 120 applications; that historical
result does not certify subsequent revisions. See [OPTIMIZATION_STATUS.md](OPTIMIZATION_STATUS.md)
and [recorded measurements](OPTIMIZATION_RESULTS.md). Architectural proposals below
remain guidance where not explicitly implemented. Original measurements are in
[RUST_QUALITY.md](RUST_QUALITY.md).

## Objective and priority

Prefer predictable cost and readable generated Rust. Roughly 2× handwritten Rust
is acceptable for now. Prioritize much larger regressions, material absolute time,
peak-memory problems and algorithms whose cost worsens with input size. A large
ratio against a nanosecond baseline is not automatically a high-priority issue.

We cannot guarantee arbitrary user programs are fast or automatically replace all
poor algorithms. We can prevent known compiler-induced cost patterns, make required
copies explicit in the compiler, and detect regressions systematically. A claim
such as “zero-copy” must name the operation, input lifetime and enforced boundary;
it cannot describe the entire application without evidence.

## Problem inventory

“Measured” means release timing against a checked handwritten baseline. “Source”
means a concrete lowering/runtime pattern is present; its workload impact still
needs measurement. Priorities for unmeasured cases are provisional.

| ID | Problem and trigger | Evidence and priority | Systematic solution | Required validation |
| --- | --- | --- | --- | --- |
| P01 | Growing strings rebuilt on each concatenation | Measured: 10,000 appends, 22.9 ms vs 7.11 µs; highest | Recognize self-append; use a builder/`push_str`; move final result | Linear copied-byte growth; retained earlier string values; self-reference; throwing RHS |
| P02 | Read-only function calls copy large inputs | Measured: 1 MiB length-call kernel, 46.3 µs vs 0.046 µs; release can eliminate some inner copies | Infer read-only parameters, pass references/slices, move consumed arguments | No size-dependent argument copies on proven read-only edges; nested calls and recursion |
| P03 | Borrowing runtime APIs receive references to freshly cloned values | Source: `library_call` calls `expr` and then wraps owned output in `&(...)` | Declare parameter effects and borrowing in the API registry; lower directly from a borrowed place | Copy/allocation-free argument preparation for applicable hash/write/send calls; evaluation order |
| P04 | A tiny string index or slice scans/materializes the full string repeatedly | Source: `char_at` and `str_slice` collect all characters; character-by-character indexing can be quadratic | Recognize sequential traversal; use a UTF-8 iterator/cursor; use direct boundary scans or a bounded reusable index for random access | ASCII, multibyte Unicode, negative indices, bounds/errors; length scaling and memory |
| P05 | Repeated `len(text)` rescans Unicode text inside a loop | Source: string length lowers to `chars().count()` | Hoist invariant length when safe; do not confuse UTF-8 byte length with character count | Zero-trip loops, mutation, Unicode and exception order; scan count |
| P06 | Collection iteration or item access deep-copies values only to read them | Measured integer list scan ~1.2–2×; source generic `at<T: Clone>` can copy larger elements | Borrow read-only iterators/items; consume dead collections; preserve snapshots where mutation is possible | Nested records/strings, modifying original during iteration, escaping items; copied bytes |
| P07 | JSON field chains and array extraction materialize owned intermediate values | Measured scalar lookup ~2×; nested/large subtrees unmeasured | Borrowed JSON views; fused typed scalar access; materialize only on ownership escape or mutation | Missing vs null, type errors, defaults, detached copy behavior, deeply nested inputs |
| P08 | Serialization constructs an intermediate JSON tree before writing JSON | Source: `json_dumps -> to_json -> serde_json::to_string` | Serialize validated typed values directly where the contract permits; reuse validation facts until mutation | Exact output and validation parity, finite-number/depth constraints, peak memory |
| P09 | Sliced byte/list chunks allocate and may be copied again at a call boundary | Source: `bytes_slice/list_slice` materialize; traffic replay passes a cloned fixture per record | Internal slice views plus borrowed calls; owned slices when escaping or requiring independent values | Backing storage lifetime, mutation, bounds, chunk budgets, file/socket exact bytes |
| P10 | Repeated regex translation/compilation | Source: search/fullmatch call `compile` directly; capture paths already have a small cache | Reusable compiled patterns; lazy literal initialization or bounded runtime cache | Invalid patterns keep runtime error timing; cache eviction and concurrency; warm/cold measurements |
| P11 | Clones on returns, temporary assignments and branches despite last use | Source: name expressions clone all non-scalars, including return operands | Control-flow liveness and ownership transfer; move values once no later path needs them | Early returns, handlers/finally, partially moved records, source value used on another path |
| P12 | Generated code obscures the real work with unnecessary mutability and wrappers | Source: Clippy findings across chat, traffic and gzip | Emit `mut` only when needed; simplify redundant expressions; infer infallibility later | Readability snapshots and Clippy; lower priority unless release measurement shows cost |

Do not treat every clone equally. Integer copies, reference-counted resource handles,
small strings, and deep trees have different costs. In particular, removing a
resource-handle clone is not equivalent to eliminating an 8 MiB buffer copy.

## Preserve the language contract first

The current subset specifies owned/value semantics for containers and records,
and snapshot iteration. File/socket handles instead share resource state; closing
one alias affects the others. See [the subset reference](service-subset.md).

Optimization must preserve these contracts, not accidentally introduce CPython
mutable aliasing or new shared mutable Rust references. Borrowing a parameter is
valid when its behavior is observationally equivalent to the owned snapshot. A
callee that modifies its input may need a local copy even if the caller retains
its value. Passing by move is valid when the caller no longer needs that value.
Copy-on-write can be investigated later; it is not a default replacement for all
containers and introduces its own mutation, refcount and allocation costs.

The Python reference is a useful oracle only for the shared semantics. Native
value/snapshot behavior needs explicit contract tests when ordinary Python aliases
would behave differently. Never adjust the semantics solely to make a benchmark
pass. Any deliberate language change requires a separate documented decision.

## Compiler architecture

The current frontend mixes checking, ownership decisions and Rust text generation
inside `ServiceCompiler`. `Expr(code, type, borrowed)` cannot adequately explain
why a copy is necessary. Add a small typed intermediate representation (IR) between
checking and Rust rendering, incrementally rather than rewriting the compiler.

Proposed pipeline:

1. Resolve modules and types; retain source spans.
2. Normalize expressions into typed operations with explicit evaluation order.
3. Build control-flow and call graphs, including error exits and cleanup edges.
4. Infer effects and ownership requirements to a fixed point.
5. Choose moves, borrows, required copies, iteration and builder operations.
6. Verify the decisions, render Rust, format it, and retain source mappings.
7. Emit optional cost explanations and run performance/correctness gates.

Start the IR with local reads, calls, assignments, concatenation, slicing and
returns. Expressions that have not migrated retain their conservative lowering.
Do not optimize by editing emitted Rust strings or matching formatted source text.

### Function and runtime API summaries

For each parameter and result, record:

- Type and representation: scalar, owned string/buffer, collection/tree, shared handle.
- Reads, writes, consumes, escapes/stores, closes a resource, or returns a view of an argument.
- Fallibility, observable I/O, callbacks, concurrency, and global-state effects.
- Cost properties where known: scans argument, allocates proportional to argument,
  retains storage, materializes a subtree, or compiles a pattern.

Analyze local functions transitively, including recursive call groups. Unknown
native calls are conservative barriers. Rust signatures can establish an interface
borrow but cannot prove purity, absence of global effects, or non-retention by all
possible implementations. Runtime metadata needs tests and review, not unchecked
“pure” annotations that silently authorize incorrect reordering.

### Ownership decisions

Represent an assignable location separately from a computed owned value. Track
last use on every reachable normal/error path, references into containers, mutation,
and values live across `try`, `except`, `finally` and resource scopes.

Each non-scalar use chooses one explicit operation:

- **Borrow:** read without transferring ownership, with a valid lifetime.
- **Move:** transfer a value the caller will not need again.
- **Copy:** preserve independent value/snapshot semantics when required.
- **Materialize:** convert a view or iterator into an owned result at a real boundary.

A copy must carry a reason and source span, such as `snapshot_mutated_in_loop`,
`caller_value_live_after_mutating_call`, or `unknown_native_effects`. This allows
both auditing and stable regression tests without depending on exact Rust text.

### Loop and builder decisions

Use these facts for read-only iteration, invariant hoisting, string/byte builders,
and borrowed slice pipelines. A safe append rewrite evaluates the RHS before
mutating the destination. For `s = s + f(s)`, `f` must see the old value; if it
raises, `s` must remain unchanged. Materialize a temporary when self-borrowing
would overlap a mutable borrow. Previously saved values of `s` stay independent.

Do not hoist a possibly failing operation out of a zero-iteration loop, across a
branch, or before observable I/O. Do not reorder serialization errors or resource
closure. Capacity reservation must be bounded and based on sound size information;
preallocating the maximum possible input is not an optimization by default.

## Prevention instead of recurring fixes

An optional performance-explanation mode is implemented as `py2rust explain`;
see [its supported checks and explicit coverage](OPTIMIZATION_DIAGNOSTICS.md).
The broader complete-operation reporting described below remains a design goal.
Diagnostics should identify the source operation, its cost, and the reason it could
not be optimized. For example:

```text
replay.py:95: copies the complete fixture for each record
reason: callee ownership effects not proven
candidate: infer a borrowed read-only parameter
```

Default compilation remains conservative and correct. An opt-in strict profile
could reject known implicit size-dependent copies in designated hot functions,
unexplained materialization, or uncovered API cost summaries. It must distinguish
unknown cost from proven high cost. Such a profile would guarantee only the named
IR/runtime properties, not whole-program speed or third-party implementation cost.

For every new supported operation, require an ownership/effect summary, a cost
classification, semantic tests, and a scaling case when it can allocate or scan
input. Do not allow “make it compile by cloning” to be an unreviewed permanent fix.

## Validation and gates

1. **Correctness:** compare reference and optimized output where contracts agree;
   also compare optimized and conservative native lowering. Include alias/snapshot
   cases, nested mutations, evaluation order, early exits, exceptions, Unicode,
   overflow, native calls and resource cleanup. Add generated/property-based cases.
2. **Structural guarantees:** test typed IR decisions. Read-only parameter paths
   should contain no size-dependent copies; proven last-use returns should move;
   applicable self-appends should use a builder. Assert the reason for retained copies.
3. **Release timing:** keep startup/setup separate, verify results, alternate order,
   warm up, use repeated samples and realistic input distributions. Track absolute
   time as well as handwritten-Rust ratio. Approximately 2× is a watch item, not
   a reason to block every change. A >5× ratio is a triage trigger, not a universal failure.
4. **Scaling and memory:** test at least four geometrically spaced sizes for each
   growing-input case. Prefer copied-byte/scan counts to timing alone for asymptotic
   claims. Track peak memory separately from cumulative requested allocations.
5. **Instrumentation:** allocation counters are diagnostic builds; they can inhibit
   LLVM optimizations. Do not mix their timings/counts into uninstrumented claims.
6. **Real applications:** benchmark chat rendering/search with fixed histories,
   JSON request handling, traffic replay at varying fixture/record sizes, and file
   transfer with exact-byte verification. Record throughput, latency distribution,
   CPU and memory; avoid confusing network/disk waits with compiler overhead.
7. **Stable CI:** enforce deterministic semantics/IR checks on every change. Use a
   controlled runner and repeated confirmation for performance regressions; retain
   concise baselines, not a succession of bulky report directories. Clippy style
   warnings are a separate readability signal.

Proposed milestone criteria: P01 must demonstrate near-linear growth over four
sizes and eliminate the large absolute slowdown; P02/P03 must eliminate proven
avoidable buffer copies before any universal timing target is adopted. Afterward,
set workload-specific limits from repeated measurements on the controlled runner.

## Implementation order

- [x] Preserve baseline benchmarks; add Unicode indexing and byte-chunk pipeline cases.
- [x] Define typed use decisions, stable-place lowering and tested runtime API effect metadata (incremental coverage).
- [x] Implement local safe string builders (P01) with negative semantic tests.
- [x] Add interprocedural read-only analysis and borrowed calls (P02/P03).
- [x] Add control-flow liveness and last-use moves (P11).
- [x] Optimize Unicode traversal and borrowed slices (P04/P05/P09).
- [x] Reassess nested JSON, serialization and regex workloads (P07/P08/P10).
- [x] Optimize collection snapshots only where safe (P06).
- [x] Add explanation/strict cost checks, real-service gates and readability cleanup.

- [x] Finish the final full regression and 120-application run against the measured compiler (825 tests, 120 apps).

These implementation checks do not claim a complete typed IR or exhaustive runtime
cost inventory. Unknown calls and uncovered expression costs remain conservative;
strict gates establish only their documented properties.

Use small reviewed steps. An optimization is complete only when its safety
conditions, counterexamples, cost effect and real application behavior are tested.
