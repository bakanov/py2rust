# Handwritten code-metrics comparison

Raw report filenames below refer to [local archived reports](../../REPORTS.md#local-archive),
not files shipped in this repository. Source programs and Markdown summaries remain in Git.

`../native/code_metrics.rs` implements bounded directory discovery, typed scoped
statement counters, physical definition spans, threshold flags, all eight import
classifications, escaped HTML and the reusable raw-source archive. It shares the
native Python parser, canonical JSON formatting and static stylesheet. Source
analysis and rendering are handwritten Rust, with no Python runtime.

Publication rechecks the complete source inventory and input snapshots after
staging and syncing files, before the no-replace rename and parent-directory sync.
Fault/pause controls are omitted, consistent with the other native baselines.

| Size | Generated median (ms) | Handwritten median (ms) | Ratio |
|---|---:|---:|---:|
| Small | 15.34 | 14.08 | 1.09× |
| Large | 120.88 | 68.21 | 1.77× |

Both sizes pass <2.00×. `results.json` retains 90 timed complete jobs (15 samples
per size and executable), all fingerprints and raw wall/CPU/RSS observations.
Current generated, previous generated and native executables rotated over fresh
identical jobs; all passed the independent oracle and exact complete-file checks.
Timings include startup, parsing, report generation and durable publication.

This is the isolated repeat. An earlier timing run briefly overlapped additional
correctness checks and is not used for the reported performance conclusions.
No compiler or Python application changes were needed.

`checks.json` records 73 additional jobs against independent AST/HTML oracles:
scoped ownership/spans, threshold boundaries, all import categories, exact raw
sources, malformed configurations and Python, filesystem guards, 64 modules,
32,768 statements, 1 MiB project sources, depth/inventory limits and oversized
report rejection. Fault-injection/pause race tests were not run on this baseline.

All twenty original applications now have native comparisons. Nineteen are below
2.00× at both sizes and resolver 096 remains the accepted 2.39× exception.
The fixed ten additional examples are documented in `../../corpus_speed_10/README.md`;
the overall goal remains open until those comparisons are complete.
