# Additional case 061: route planner

Raw report filenames below refer to [local archived reports](../../REPORTS.md#local-archive),
not files shipped in this repository. Source programs and Markdown summaries remain in Git.

This is the first measured application from the fixed follow-up set. The workload
uses 12/100 vertices, 21/197 edges and 12/100 queries. Edges are reversed to exercise
repeated Bellman–Ford passes. Queries include forward and reverse routes, closed
endpoints, closed edges and identical endpoints. Nonnegative costs allow an
independent heap-based Dijkstra oracle; additional small graphs exercise negative
cycles through exhaustive simple-path and cycle enumeration.

| Size | Generated median (ms) | Handwritten median (ms) | Ratio |
|---|---:|---:|---:|
| Small | 8.65 | 8.25 | 1.05× |
| Large | 325.21 | 13.83 | **23.52×** |

The large case fails the 2.00× comparison threshold and has no accepted exception.
It does not invalidate the recorded original twenty-case results, but demonstrates
that their performance does not generalize to all applications. No compiler or
Python application changes were made for this extension.

`results.json` contains 60 timed invocations: 15 repetitions per executable and
size, rotating order after warm-up. Both executables run fresh identical complete
jobs; every invocation checks the independent oracle and equal complete input/
output file contents. These wall times include startup and atomic report writes.
There is no fabricated previous-compiler baseline for this new comparison.

## Reference and correctness

`../../corpus_speed_20/native/route_planner.rs` implements the same bounded graph,
query validation, edge-order-preserving Bellman–Ford, pass/relaxation counters,
relevance propagation, unreachable diagnostics and directed route/cycle witnesses.
The handwritten representation interns vertex names once and uses index arrays,
borrowed edges and optional predecessor references. It does not use a faster
shortest-path algorithm or skip the repeated reachability passes. Shared runtime
JSON formatting and atomic report writes match the generated program.

`checks.json` records 11 additional complete jobs: ten graphs with 219 independently
checked answers (77 finite, 9 closed, 63 unreachable, 70 negative-cycle), validated
witnesses and one invalid graph that preserves the existing report. All thirty
current generated compiler/source/binary fingerprints were checked; the measured
native binary matches its source and broader correctness record.

## Measured cause and systematic follow-up

A separate oracle-checked Callgrind run recorded **5,253,586,289** instructions in
generated Rust and **68,416,451** in handwritten Rust. These are instruction counts,
not timing samples. `profile-summary.json` records binary/profile hashes and equal
checked-output hashes. Annotated profiles are in the local archive; full raw profiles remain
at the recorded build-cache paths.

In generated code, `can_reach` accounts for 36.80% of inclusive instructions;
`json_key_ref` 18.68%; deallocation 15.16%; map hashing 12.30%; and the `text`
wrapper 11.92%. These inclusive categories overlap and must not be added.
The profile supports the source-level finding: repeated JSON field lookup,
owned string extraction, key clones/hashing and cloned predecessor objects occur
inside the relaxation and reachability loops.

For example, the generated helper returns an owned string on every call:

```rust
fn text(value: &rt::Json, key: &str) -> rt::Result<String> {
    rt::json_string(rt::json_key_ref(value, key)?)
}
```

Callers then clone that string for membership checks, and successful relaxations
clone the edge JSON into the predecessor map. The native implementation validates
and resolves names once, then indexes `Vec<Option<i64>>` and `Vec<Option<&Edge>>`.

General compiler improvements suggested by this evidence, not yet implemented:

1. Carry read-only returned-view provenance through small projection helpers,
   allowing borrowed strings at read-only call sites and materializing only where
   ownership is required. Prove source lifetime and mutation safety and retain
   dynamic key/type errors.
2. Borrow keys for membership/lookups and reuse checked lookups where effects
   permit, including calls hidden behind helper functions.
3. Represent confined predecessor collections with references or stable indices
   into immutable backing records; preserve snapshot semantics on mutation or escape.
4. Support validated typed input records and explicit indexed models. Automatically
   interning arbitrary string-keyed maps needs a broader identity/order proof; it
   should not be silently assumed from this particular graph application.

These are remaining optimization opportunities. This comparison records the gap;
it does not claim it has been solved.
