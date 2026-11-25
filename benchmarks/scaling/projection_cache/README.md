# Lazy projections across repeated JSON scans

Raw report filenames below refer to [local archived reports](../../REPORTS.md#local-archive),
not files shipped in this repository. Source programs and Markdown summaries remain in Git.

Historical measurement stage; see the [final acceptance audit](../final/README.md) for the current status.

The compiler now caches successful constant-key string projections when an inner
loop repeatedly scans an unchanged JSON list. This uses the previously proven pure
projection helpers; no application or field-name specialization is involved.

Each inner scan enumerates the same stable list positions. Per-field vectors of
`OnceCell<String>` live for the surrounding loop and allocate slots on first scan.
Successful checked projections initialize the corresponding slot once. A cached
string is borrowed at read-only uses and materialized when it escapes as an owned
value. This removes repeated JSON object lookups and type validation for those
uses without changing the original validation position.

Branches that skip a projection still do not validate it. Failed lookups/types are
not cached, so exception handlers can retry and observe the same checked errors.
Zero-iteration loops perform no projection validation. Lists written or rebound
inside the outer loop, outer-loop targets reused as inner sources, mutable items,
dynamic keys and effectful helpers retain ordinary lowering. The rule currently
covers direct nested `for` loops in the host emitter. Memory is proportional to
list size and the selected constant fields; caches are released with the loop.

## Matched measurements

Previous/current/handwritten release runs rotate order, with one warm-up and 15
timed invocations per engine and size. Every run passes the independent oracle
and complete-output equality. Startup and output I/O are included; compilation
and checking are excluded. The previous binary is the borrowed-projection patch.
The current compiler also includes intervening recursive-record changes, which
do not select any record types in this application.

| Size | Previous generated (ms) | New generated (ms) | Handwritten (ms) | New/native |
|---|---:|---:|---:|---:|
| small | 12.78 | 13.61 | 12.21 | 1.11× |
| large | 354.79 | 291.34 | 20.92 | 13.93× |

The large matched improvement is approximately 18%. The small case is slower in
this run. Historical runs used different timing conditions; comparing absolute
times or dividing ratios across sessions would not establish a patch speedup.
`results.json` retains all 90 timed observations and fingerprints. `builds.json`
identifies the generated application and compiler.

The complete graph oracle passes: 11 jobs and 219 answers (77 finite, 9 closed,
63 unreachable, 70 negative-cycle), including route/cycle witnesses and existing
report preservation after invalid input. `checks.json` identifies the checked binary.

Seventeen targeted regression cases passed across repeated scans, projection
helpers, JSON consumers and string views. They cover both frontends with
optimization on/off, escaped strings, changed list entries, rebound scan sources,
skipped validation and repeated missing-key/type failures. Formatting, lint and
whitespace checks also passed.

Route planning remains far above 2× and the goal is active. Generated loops still
use string-keyed sets and maps, whereas the handwritten model resolves vertex
names once and uses integer-indexed arrays. Reusing stable dictionary entry
positions and reducing predecessor snapshots are next candidates; neither is
implemented by this patch.
