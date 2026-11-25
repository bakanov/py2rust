# Stable dictionary entry positions

Raw report filenames below refer to [local archived reports](../../REPORTS.md#local-archive),
not files shipped in this repository. Source programs and Markdown summaries remain in Git.

Historical measurement stage; see the [final acceptance audit](../final/README.md) for the current status.

The compiler reuses entry positions for string-keyed dictionaries during repeated
scans of immutable JSON lists. Keys must come from proven constant-field string
projections, bound to unchanged local names before their use. The surrounding
loop must retain all dictionary keys in order: indexed reads, membership and
plain indexed assignments are admitted; deletion, clear, rebinding, escaping
whole dictionaries and other methods reject this optimization.

Each scan position/field/dictionary combination has a `Cell<Option<usize>>`.
Successful lookups cache the `IndexMap` position; missing keys are searched again
because a later iteration may insert them. Reads fetch the current value through
that position, not a cached value. Replacements preserve positions, and new keys
append. Assignment still evaluates the value before the key and map update.
Iteration order, checked missing-key errors and owned result boundaries remain.

The lowering is general, with no route-planner or field-name recognition. It
currently applies to the host emitter's proven repeated-scan subset, not arbitrary
dictionary mutations or portable IR-native code generation. Cache storage is
proportional to scan size and selected field/dictionary combinations and lasts for
the surrounding loop. This can add overhead where lookups rarely repeat.

## Matched benchmark

The previous executable includes lazy JSON projection caching. The harness rotates
previous/current/handwritten release binaries after warm-up, with 15 timed runs per
engine and size. All runs pass an independent oracle and complete-output equality.
Startup and output I/O are included; compilation and checking are excluded.

| Size | Previous generated (ms) | New generated (ms) | Handwritten (ms) | New/native |
|---|---:|---:|---:|---:|
| small | 9.31 | 9.03 | 8.60 | 1.05× |
| large | 206.48 | 150.34 | 15.36 | 9.79× |

The matched large improvement is approximately 27%. Earlier absolute timings used
different conditions and are not the denominator for this speedup. `results.json`
preserves all 90 timed observations and fingerprints; `builds.json` records the
application/compiler identity.

The complete graph oracle passes: 11 jobs, 219 answers (77 finite, 9 closed,
63 unreachable, 70 negative-cycle), validated route/cycle witnesses and existing
report preservation on invalid input. `checks.json` identifies the checked binary.

Completed targeted batches cover map positions, repeated projection scans and JSON
consumers: 13 distinct cases across typed/legacy frontends and optimization on/off.
New cases check changing values at cached positions, initially missing keys that
later appear, checked missing reads, deletion/reinsertion, clear and rebinding.
An additional broader batch was terminated before its summary and is not counted
as completed. Formatting, lint and whitespace checks passed, and the current
compiler fingerprint matches the measured build.

The route-planner goal is still active. Repeated reachability-set operations and
owned predecessor JSON copies remain in the generated code. Monotonic set
membership caching and borrowed predecessor storage are next candidates, not
features implemented or measured by this patch.
