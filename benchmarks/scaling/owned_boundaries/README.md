# First scaling fixes: field projections and self-replacing moves

Raw report filenames below refer to [local archived reports](../../REPORTS.md#local-archive),
not files shipped in this repository. Source programs and Markdown summaries remain in Git.

Historical measurement stage; see the [final acceptance audit](../final/README.md) for the current status.

This is an intermediate result, not completion of the three-application scaling
goal. The compiler changes are general; Python sources and handwritten baselines
are unchanged. The previous generated executables are genuine preserved builds.

Each size uses 15 timed invocations per executable after warm-up, rotating old,
new and handwritten Rust on fresh identical inputs. Every invocation checks the
independent application oracle and equal complete output files. The raw evidence
contains 270 timed complete jobs with hashes and individual observations.

| Large workload | Old generated (ms) | New generated (ms) | Handwritten (ms) | New/native | Old/new speedup |
|---|---:|---:|---:|---:|---:|
| Autocomplete | 1534.16 | 1456.45 | 24.99 | 58.28× | 1.05× |
| Route planner | 333.11 | 336.23 | 14.40 | 23.35× | 0.99× |
| Scheduler | 1852.88 | 1137.99 | 22.30 | 51.02× | 1.63× |

Use the matched old/new medians to assess the compiler change. Historical ratios
came from a different run and startup/I/O/machine variation can change both native
and generated times. In particular, autocomplete's historical 72× ratio should
not be compared directly with the new ratio to infer the speedup of this patch.

The patch borrows ancestor records while reading fields and fixes incoming-value
liveness across self-replacing assignments. Final owned field snapshots remain
copies; try/resource regions, repeated reads and live view backing remain guarded.
The scheduler now passes state by value without a call-site clone, but still copies
its large fields inside transitions. Trie traversal/update copies and route-planner
JSON/string allocation remain unresolved.

Validation: 39 distinct targeted execution/analysis cases passed across record
projection, recursive records, self-replacement, typed liveness, move safety and
owned-boundary policy. New cases cover typed/legacy frontends with optimizations
on/off, missing keys, temporary receivers, independent final field values, loops,
repeated reads and exception-visible old values. This is selected-program evidence;
the historical thirty-application results are not claimed for this changed compiler.

Compiler/application hashes were checked against current sources, both generated
binary generations were checked against recorded hashes, and all six cases contain
15 samples for each engine. The next steps are recorded in
[the active scaling plan](../../../doc/SCALING_IMPROVEMENTS.md).
