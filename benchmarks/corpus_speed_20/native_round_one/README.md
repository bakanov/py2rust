# First native-comparison milestone — 2026-11-25

Raw report filenames below refer to [local archived reports](../../REPORTS.md#local-archive),
not files shipped in this repository. Source programs and Markdown summaries remain in Git.

This is partial evidence for the [active performance goal](../../../doc/NATIVE_PERFORMANCE_GOAL.md), not a claim that all twenty applications meet it.

- `native-results.json`: five handwritten baselines, two sizes, 15 timed observations per old-generated/current-generated/native executable; complete output equality and independent oracle checks. Nine of ten size cases pass; the large resolver is 2.92×.
- `corpus-results.json`: all twenty applications, two sizes, five observations per Python/generated executable. All correctness checks passed. Python ratios do not establish native performance.
- `varied-checks.json`: eleven additional complete native jobs, including edge cases, checked against independent corpus oracles.
- `equivalence.json`: all twenty newly emitted Rust/Cargo inputs equal the measured inputs after a final internal representation-tag collision fix. Compiler fingerprints are deliberately distinct; executable hashes retain measured provenance.

The original `../results.json` is historical and is preserved. Handwritten implementations are in `../native/`; their supported modes and limitations are documented there. Reproduction commands and remaining coverage are in the linked report. Timings include process startup, I/O, computation and durable publication, and depend on the host and workloads.

Local full artifacts (executables are not checked into the repository):

- `/home/dima/.cache/py2rust-build/corpus-native-round-one-final`: timed executable copies and Cargo projects.
- `/home/dima/.cache/py2rust-build/corpus-speed-json-views`: generated builds and twenty-application observations.
- `/home/dima/.cache/py2rust-build/corpus-native-varied-final`: additional checked native jobs.
