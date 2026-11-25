# Scaling improvements: autocomplete, route planner and scheduler

This follow-up goal is complete under the user's accepted **large-workload ratio
below 6×**. The existing small-workload gate remains below 2×. A final audit of all
three applications using one compiler revision passes with no exemptions:

| Application | Small ratio | Large ratio |
|---|---:|---:|
| Autocomplete | 1.07× | 1.96× |
| Route planner | 1.03× | 4.10× |
| Scheduler | 1.03× | 1.34× |

[Final acceptance evidence](../benchmarks/scaling/final/README.md) includes 270
matched timed jobs, full application checks for all three final binaries, a
five-size route sweep with 135 additional checked timed jobs, and a fingerprint/
source/binary audit. Python applications and handwritten baselines are unchanged.
This is acceptance of these selected bounded workloads, not the whole corpus.

The sections below preserve historical intermediate measurements in implementation
order; statements about work remaining describe their respective stages. The
previous thirty-application comparison is also historical and does not establish
performance for this newer compiler.

## Scope and evidence

Improve the transpiler's general handling of recursive data, ownership and hot
JSON loops without editing the three Python applications or handwritten baselines.
Preserve checked errors, evaluation order, independent owned values, event/history
snapshots and resource lifetimes. Measure the new generated executables against
both the preserved generated executables and handwritten Rust on identical jobs.

The initial large-case ratios were 72.00× for autocomplete, 23.52× for route
planning and 105.29× for scheduling. Preserved release executables, generated source
and compiler/application fingerprints are in the `corpus-additional-generated`
build cache and the saved follow-up benchmark evidence. They must not be
overwritten by this work.

## First general fixes

1. **Borrow ancestor records for field projections.** An expression such as
   `index.root.nodes` previously cloned the complete recursive root just to read
   an integer. Attribute emission now uses the existing stable local-place
   machinery for the receiver. Scalar fields are copied directly; an owned
   string, collection or record result still copies its final field as required.
   Temporary/call receivers retain the existing fallback and checked indexing.
2. **Distinguish old and replacement values in liveness.** For an assignment such
   as `state = transition(state, ...)`, later reads refer to the replacement
   value. They must not keep the previous value alive across its own replacement.
   The typed and legacy analyses now subtract the statement's writes when
   deciding whether its incoming read is live afterward. Repeated reads in the
   same expression and exception/resource regions remain conservative, as do
   resource-containing types and values that back live borrowed views.

The subsequent owned-field and shared-record changes below address scheduler and
autocomplete copying. Subsequent rules reduce repeated lookup, hashing and JSON
copying inside route-planning loops.

## Optional future investigations

- Extend the proven owned-field rule only where additional control-flow and
  lifetime evidence permits it. The scheduler case is now covered; old-field
  length snapshots preserve its sequence numbering.
- Borrow recursive traversal results while retaining the owned missing-result
  fallback and materializing snapshots when values escape or their backing mutates.
- Generalize returned-view provenance beyond the current pure projection helpers
  and scoped borrowed maps, preserving argument evaluation order and checked errors.
- Extend beyond the selected bounded workloads when further performance work is
  requested. Current size sweeps and accepted gates do not guarantee other inputs.

## First matched measurement

[The first patch results](../benchmarks/scaling/owned_boundaries/README.md) retain
270 timed complete jobs and both generated compiler generations. The targeted
regressions passed 39 distinct cases. Substantial gaps remain; this goal is active.

## Owned field moves and scheduler size sweep

[The second patch](../benchmarks/scaling/owned_fields/README.md) removes scheduler
jobs/counts/trace clones using conservative partial moves and old-length snapshots.
The large matched case is now 28.45 ms versus 22.20 ms handwritten Rust (1.28×),
compared with 1,092.18 ms from the immediately preceding compiler. A five-size
sweep remains below 2× at 32, 64, 128, 256 and 512 jobs, with matching outputs.
The full generated scheduler oracle, capacity and publication suite passed.

This addresses the observed scheduler copying/scaling problem within its bounded
application domain. Autocomplete and route planning remain active work. The field
move analysis currently lives in the host emitter and is deliberately conservative;
it does not yet generalize to arbitrary control flow, borrowed owners or IR-native
self-hosting.

## Borrowed projection helpers and route-planner profile

[The third patch](../benchmarks/scaling/projected_strings/README.md) borrows checked
JSON string projections through simple pure helpers, borrows membership keys and
avoids allocating duplicate borrowed set keys. The large route workload improves
to 256.25 ms, but remains 17.52× handwritten Rust. The full graph oracle passed.
A new checked profile identifies repeated JSON lookup, map probes and string
comparison as the main remaining costs. Stable per-element projection reuse and
predecessor representation remain work to investigate. Autocomplete is unresolved.

## Borrowed record traversal and autocomplete

[The fourth patch](../benchmarks/scaling/record_cursors/README.md) represents proven
read-only recursive cursors as references, preserving checked descents and owned
escapes. Autocomplete's large matched run falls from 1,435.33 ms to 858.78 ms,
versus 24.93 ms handwritten Rust (34.45×). Its complete oracle suite passes,
including Unicode, split replay, state, capacity and publication checks.

This removes ancestor copies during lookup, but owned lookup results, recursive
child-map updates and exception-preserving state copies remain. Both autocomplete
and route planning still require substantial improvement at this stage.

## Shared recursive storage and autocomplete size sweep

[The fifth patch](../benchmarks/scaling/shared_records/README.md) uses copy-on-write
storage for resource-free recursive value records. Clones share immutable nodes;
mutating access detaches the changed node without copying all descendants. This
preserves independent snapshots and checked-error behavior.

The large autocomplete workload now takes 46.92 ms versus 24.82 ms handwritten
(1.89×), down from 881.15 ms in the matched previous generated executable. A sweep
at 8, 16, 32, 64 and 128 terms stays below 2×, with full output equality. The full
autocomplete oracle, state, capacity and publication suite passes.

This addresses the observed autocomplete recursive-copying problem within the
checked bounded workloads. The largest ratio has limited margin; it is not a
universal performance guarantee. Route planning remains unresolved and the goal
is active. Its last measured large case is 17.52× from the earlier projection patch.

## Lazy projections across repeated scans

[The sixth patch](../benchmarks/scaling/projection_cache/README.md) caches successful
constant-key string projections per stable JSON list position across repeated
scans. Validation stays on its original control-flow path; failures are not cached.
The matched large route case improves from 354.79 ms to 291.34 ms, approximately
18%, but remains 13.93× handwritten Rust. The full graph oracle passes.

String-keyed set/map operations and predecessor snapshots remain. Route planning
is unresolved, and the overall goal remains active.

## Stable dictionary entry positions

[The seventh patch](../benchmarks/scaling/map_positions/README.md) caches entry
positions for proven append-only dictionaries and stable projected string keys.
Values are read fresh, replacements retain positions, and misses are searched
again after later insertions. Deletion, clear, rebinding and escaping maps retain
ordinary lowering.

The matched large route case improves from 206.48 ms to 150.34 ms, approximately
27%, but remains 9.79× handwritten Rust. The complete graph oracle passes.
Repeated set operations and predecessor snapshots remain; the goal is active.

## Growing-set membership caches

[The eighth patch](../benchmarks/scaling/growing_sets/README.md) proves that selected
sets only grow, caches positive membership, and reuses negative membership only
until the set's size changes. Validation and loop/body execution stay in place.
Two matched measurements show approximately 26% and 24% large-case improvements.
The final large case is 107.98 ms versus 18.53 ms handwritten Rust (5.83×).

Both versions pass the complete graph oracle. Checked profiles show `can_reach`
falling from 26.75% to 5.98% of inclusive instructions between these versions.
JSON cloning/allocation/disposal is now a clearer target, alongside numeric
projection reuse. The route-planner problem remains unresolved and the goal active.

## Borrowed maps and final acceptance

[The ninth patch](../benchmarks/scaling/borrowed_maps/README.md) borrows JSON records
while constructing proven write-only dictionaries, then materializes independent
owned entries once after the loop. Its matched large route case improves from
105.90 ms to 75.61 ms (4.07× handwritten Rust). Checked partial-write observation,
mutable backing and reads during construction retain conservative lowering.

The user then accepted a large-workload ratio below 6×. Fresh builds, matched
comparisons and complete application checks for all three programs meet that gate
and the small-workload 2× gate. The final route sweep also remains below 6× at 12,
25, 50, 75 and 100 vertices/queries. The final evidence linked above supersedes
intermediate status statements; further optimization is optional future work.
