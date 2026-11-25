# Handwritten automation-language comparison

Raw report filenames below refer to [local archived reports](../../REPORTS.md#local-archive),
not files shipped in this repository. Source programs and Markdown summaries remain in Git.

The independent Rust interpreter in `../native/automation.rs` parses the complete
bounded language into a typed AST before execution. It preserves checked signed64
arithmetic, Python floor division and remainder, lexical scopes, execution budgets,
partial results after errors, source coordinates, the flat AST and trace exports.
Invalid programs in unexecuted branches are still parsed and rejected.

No compiler or application changes were required. The comparison rotates current
generated, preceding generated and handwritten release executables. Every run
passes the independent interpreter oracle and exact complete-file comparisons.

| Size | Generated median (ms) | Handwritten median (ms) | Ratio |
|---|---:|---:|---:|
| Small | 20.00 | 18.39 | 1.09× |
| Large | 54.50 | 50.42 | 1.08× |

`results.json` retains all 90 timed runs, source and binary fingerprints, and raw
wall/CPU/RSS observations. Timings include startup and durable publication; they
do not establish isolated interpreter-kernel performance. Both sizes pass <2.00×.

`checks.json` records 232 additional complete jobs, including 160 independent-oracle
programs, 42 boundary runs under a 256 MiB memory limit, 24 no-write validation
cases, exact diagnostics, scopes and error unwinding. Shared input snapshots reject
hard-linked inputs more strictly than the Python application; measured inputs are
unaliased regular files. Fault-injection and pause controls are not implemented.

This extends coverage to sixteen original applications, fifteen below 2.00× at
both sizes plus the accepted resolver exception at 2.39×. Missing references are
077, 080, 095 and 109. The additional ten examples remain outstanding.
