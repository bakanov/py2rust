# Additional CSV join comparison

Raw report filenames below refer to [local archived reports](../../REPORTS.md#local-archive),
not files shipped in this repository. Source programs and Markdown summaries remain in Git.

The unchanged Python application and compiler were compared with independently
handwritten complete Rust, using identical pinned dependencies and release
settings. Execution order rotates after warm-up over fresh identical inputs.
An independent nested-loop relational oracle and complete-output equality check
every invocation. Compilation, fixture creation and checking are untimed.

| Size | Generated median (ms) | Handwritten median (ms) | Ratio |
|---|---:|---:|---:|
| Small | 10.89 | 10.35 | 1.05× |
| Large | 16.70 | 14.94 | 1.12× |

Both cases pass. `results.json` retains 60 timed jobs (15 per executable and size),
raw observations and source/binary fingerprints. Timings include startup, parsing,
report serialization and durable publication. Workloads contain 32/1,024 rows per
table, two-column keys, quoted Unicode/CRLF values, different input delimiters,
left-outer semantics, unmatched rows and stable key ordering. The composite keys
are unique in these timed fixtures; duplicate expansion is exercised separately
by the broader correctness suite.

`csv_join.rs` uses hash indexes with borrowed composite keys and vectors of source
row numbers. It checks expansion bounds before constructing output, retains
source order within ties and duplicate matches, and serializes sorted duplicate
reports. Matched-row flags provide exact unmatched reports. Both supported join
kinds, both ordering modes, projection aliases and duplicate policies are retained.
The shared `csv_codec.rs` implements the application's exact bounded CSV dialect.

`checks.json` records 333 additional complete jobs covering independent relational
results, random joins, composite keys, duplicate multiplicity, ordering, malformed
inputs, path guards and capacities under a 256 MiB address-space limit. These
include 10,000 input rows, 100,000 output rows, 64 key columns, 65,536-byte fields,
4 MiB input, exact 8 MiB output and rejection of a 100-million-pair expansion
before allocating output. The checked binary hash matches both timed sizes.

Preview/join, complete hashes and reports, per-file atomic writes, synchronization,
input revalidation after staging and no-replace publication are retained. The
shared native input helper rejects hard links more strictly than the Python
application; timed inputs are unaliased. Fault-injection/pause hooks and their
associated interruption/race checks are excluded. No compiler or Python
application changes were made for this comparison.
