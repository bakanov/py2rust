# Additional JSON diff/patch comparison

Raw report filenames below refer to [local archived reports](../../REPORTS.md#local-archive),
not files shipped in this repository. Source programs and Markdown summaries remain in Git.

The unchanged Python application and compiler were compared with a handwritten
complete Rust implementation, using the same pinned dependencies and release
settings. Execution order rotates after warm-up, with fresh identical inputs.
Every invocation passes the independent recursive patch oracle and complete-output
comparison. Fixture construction, compilation and checking are untimed.

| Size | Generated median (ms) | Handwritten median (ms) | Ratio |
|---|---:|---:|---:|
| Small | 12.88 | 11.16 | 1.15× |
| Large | 301.43 | 121.10 | **2.49×** |

The large workload fails the strict threshold and has no accepted exception.
`results.json` retains 60 timed invocations (15 per executable and size), raw
observations and source/binary fingerprints. Times include startup, serialization,
file synchronization and durable publication. These are complete-job measurements,
not isolated edit-kernel timings.

Workloads contain 8/128 nested records, with 26/386 guarded changes respectively:
scalar replacements, positional array edits, additions/removals and escaped Unicode
object paths. Both forward edits and undo reconstruction are verified.

`../../corpus_speed_20/native/json_patch.rs` supports diff/apply and preview/write.
It preserves sorted object traversal, positional array semantics, canonical numeric
guards, stale-value/hash diagnostics, exact path grammar and bounded intermediate
results. It clones the base document once into a private editable value; failed
edits leave the caller's original document intact. It retains whole-document
validation after every change and validates inverse reconstruction. Publication
uses per-file atomic writes, synchronization, input snapshot revalidation and a
no-replace bundle rename.

`checks.json` records 980 additional complete jobs: recursive round trips, manual
patches, numeric distinctions, malformed/stale patches, escaped paths, input/output
path guards and capacity checks under a 256 MiB address-space limit. Capacity
checks exercise 20,000 nodes, 2,000 changes, depth 24 and a 4 MiB document.
The checked executable hash matches both timed sizes.

The shared native input helper rejects hard-linked files more strictly than the
Python application; measured inputs are unaliased. Native fault-injection/pause
hooks are excluded, so their associated interruption/race checks were not run.
No compiler optimization was introduced for this comparison. The remaining gap
is recorded for investigation rather than attributed to an unmeasured cause.
