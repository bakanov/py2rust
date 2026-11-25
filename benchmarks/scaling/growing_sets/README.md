# Membership caches for sets that only grow

Raw report filenames below refer to [local archived reports](../../REPORTS.md#local-archive),
not files shipped in this repository. Source programs and Markdown summaries remain in Git.

Historical measurement stage; see the [final acceptance audit](../final/README.md) for the current status.

Repeated scans can reuse membership of stable string projections when a set only
grows. The compiler proves that all uses of the selected set inside the outer loop
are membership checks or `add` calls. Rebinding, clearing, escaping to another
callee and other methods reject the optimization. Keys must be proven immutable
JSON projections, either direct helper calls or unchanged local bindings.

A positive result stays valid for the lifetime of the loop. A negative result is
valid only while the set's length remains the same: in a growing set, a content
change necessarily increases its length. Each selected list-position/field/set
combination stores `Option<(usize, bool)>`. A miss is searched again after growth.
Successful insertion records positive membership. Missing or wrongly typed JSON
fields do not initialize the cache, preserving repeated exceptions and skipped
validation paths. The compiler does not skip loop iterations or body side effects.

The implementation uses the host emitter's existing immutable repeated-scan proof.
It is independent of graph names and field names. Cache storage scales with list
length and selected field/set combinations and is released with the loop. This is
not a general optimization for mutable sets or arbitrary key expressions.

## Two matched measurements

Each measurement rotates previous/current/handwritten release binaries, with a
warm-up and 15 timed runs per engine and size. Every run passes an independent
oracle and complete-output equality. Startup and output I/O are included;
compilation and checking are excluded. Keep each speedup within its matched run:
host timing conditions differ between sessions.

The first version cached only positive membership:

| Size | Previous generated (ms) | Positive-only (ms) | Handwritten (ms) | New/native |
|---|---:|---:|---:|---:|
| small | 11.37 | 10.97 | 10.91 | 1.01× |
| large | 200.03 | 148.94 | 18.72 | 7.96× |

The final version also reuses negative results until growth:

| Size | Previous positive-only (ms) | Final generated (ms) | Handwritten (ms) | New/native |
|---|---:|---:|---:|---:|
| small | 11.51 | 11.17 | 11.01 | 1.01× |
| large | 141.99 | 107.98 | 18.53 | 5.83× |

The matched large improvements are approximately 26% and 24%, respectively.
`positive-results.json` and `results.json` preserve all 180 timed observations;
their corresponding build files identify application/compiler/binary fingerprints.
Both binaries passed the complete graph oracle: 11 jobs and 219 answers (77 finite,
9 closed, 63 unreachable, 70 negative-cycle), validated witnesses and preservation
of existing reports on invalid input. Check files identify each tested binary.

The final version passes 12 targeted cases covering growing sets, map-position
caches and projection caches across typed/legacy frontends with optimization
on/off. They check absent-to-present transitions, direct and named projected keys,
body execution counts, clear/rebinding fallback, skipped validation and repeated
missing-key/type errors. Earlier fixtures using unsupported set-removal methods
were corrected before acceptance. Formatting, lint and whitespace checks passed.

## Checked profiles and remaining work

Both Callgrind runs passed the independent large-workload oracle and produced the
same complete-file hash as the earlier route profiles. The positive-only version
executed 1,519,656,858 instructions; the final version executed 1,139,495,502.
Raw profiles remain in the corresponding build-cache directories; summary files
record their hashes and the archived annotations give detailed counts.

Inclusive `can_reach` instructions fell from 406.55 million (26.75%) to 68.18 million
(5.98%). The remaining profile includes JSON value cloning (21.39% inclusive),
JSON disposal (18.77% inclusive), and allocation/free work. Inclusive categories
overlap and must not be summed; these are instruction shares, not wall-time shares.
Borrowed predecessor storage and reuse of numeric JSON projections are next
candidates, not implemented improvements in this patch.

Route planning remains above 2×. This is progress on the active goal, not completion.
