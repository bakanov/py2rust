# PNG and terminal-dashboard native comparisons — 2026-11-25

Raw report filenames below refer to [local archived reports](../../REPORTS.md#local-archive),
not files shipped in this repository. Source programs and Markdown summaries remain in Git.

These comparisons extend the [active performance goal](../../../doc/NATIVE_PERFORMANCE_GOAL.md)
to eleven original applications. Ten pass both sizes; the resolver remains open.

- `png-results.json` and `terminal-results.json`: two sizes and 15 observations per
  original-generated/current-generated/handwritten executable, 180 timed runs in
  total. Every run passed the independent oracle and complete-file hash equality.
- `png-checks.json`: 148 additional complete jobs, including metadata, Latin1/UTF8,
  HTML escaping, exact malformed diagnostics, structural replay and every proper
  prefix of a minimal PNG.
- `terminal-checks.json`: 79 additional jobs, including narrow/Unicode layouts,
  watch/replay, six live PTY processes and four replay jobs. Actual terminal bytes,
  seven resizes, sequence conflicts, missing/invalid snapshots, plain-terminal
  fallback, SIGINT and SIGTERM cleanup were checked.

Large-workload ratios: PNG 1.14×; terminal dashboard 1.07×. Both small cases pass.
The compiler and Python application sources are unchanged from round two; no
additional compiler optimization was needed to meet the target for these cases.
All twenty generated build/source/binary fingerprints and all eleven current
native source/binary fingerprints were verified. The existing 40-workload
correctness sweep remains applicable and was not redundantly rerun.

Full executables and Cargo projects remain outside Git:

- `/home/dima/.cache/py2rust-build/corpus-native-png`
- `/home/dima/.cache/py2rust-build/corpus-native-png-varied`
- `/home/dima/.cache/py2rust-build/corpus-native-terminal`
- `/home/dima/.cache/py2rust-build/corpus-native-terminal-varied`

Sources are `../native/png.rs` and `../native/terminal_dashboard.rs`. PNG supports
inspect/verify and reports compressed data as uninspected, matching the original.
The dashboard supports watch/replay, interactive terminals and process signals.
Fault-injection/publication-pause hooks are excluded, as for the other baselines.
