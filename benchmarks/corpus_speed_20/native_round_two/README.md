# Second native-comparison milestone — 2026-11-25

Raw report filenames below refer to [local archived reports](../../REPORTS.md#local-archive),
not files shipped in this repository. Source programs and Markdown summaries remain in Git.

Partial evidence for the [active performance goal](../../../doc/NATIVE_PERFORMANCE_GOAL.md).
Six of seven handwritten comparisons pass both sizes. The large package resolver
remains at 2.70×. Thirteen original native baselines and the later ten applications
remain open.

- `native-results.json`: seven applications, two sizes, 15 timed observations for
  each original-generated/current-generated/handwritten executable (630 runs).
  Every run passed the independent oracle and complete-file hash comparison.
- `corpus-results.json`: all twenty selected applications, two sizes, five
  observations per Python/generated executable (400 runs); all correctness checks
  passed. Python speedups are not the native-Rust performance gate.
- `varied-checks.json`: 27 additional complete handwritten jobs, including invalid
  inputs, Unicode, empty inputs and unchanged-file/metadata checks.

Inputs and application source are unchanged. Compiler/runtime improvements are
shared: fused string addition, borrowed null checks, moved capture arrays and
proved capture-field demand join the optimizations documented in round one.
Both old measurements and their compiler fingerprints remain historical; this
round rebuilt all twenty applications under the new compiler fingerprint.

Full executable and Cargo artifacts remain outside Git:

- `/home/dima/.cache/py2rust-build/corpus-native-access-generated`
- `/home/dima/.cache/py2rust-build/corpus-native-round-two`
- `/home/dima/.cache/py2rust-build/corpus-native-round-two-varied`

See the report for reproduction commands, hardware/methodology, supported native
modes and remaining work. Handwritten sources are in `../native/`. The regex
rewrite comparison measures preview mode; it does not claim apply/restore support.
