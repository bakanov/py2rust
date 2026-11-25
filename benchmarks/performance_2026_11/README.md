# Selected performance evidence

Raw report filenames below refer to [local archived reports](../REPORTS.md#local-archive),
not files shipped in this repository. Source programs and Markdown summaries remain in Git.

See [the compiler performance report](../../doc/COMPILER_PERFORMANCE.md) for scope,
correctness checks, safety conditions, limitations and reproduction commands.

- `text.json`: prefix extraction, split counting and split traversal.
- `counter.json`: repeated string-key counters; baseline already has split-loop fusion.
- `access-log.json`: complete JSON Lines analyzer at two input sizes.

Each file contains nine raw timings per implementation, medians, ratios, CPU/OS,
generated-source hashes and executable hashes. Timings rotate old/new/native order
and check outputs on every run. These generated evidence files are retained in the local archive;
Cargo intermediates and executables also stay outside the repository.

The preserved local build directories for this measurement are under
`$HOME/.cache/py2rust-build/`:

| Workload | Before | After |
| --- | --- | --- |
| Text | `performance-before-text` | `performance-final-text-count` |
| Counter | `performance-before-counter` | `performance-final-counter` |
| Access log | `performance-before-access-log` | `performance-final-access-log` |

Each has `generated/src/main.rs`, the bundled runtime sources, `target/release/`,
input data, build logs and original benchmark results. The archived JSON files
are the later interleaved comparison, so their times need not equal those from
the initial standalone benchmark runs. The final character-count helper is used
only by the text fixture; counter/access-log timings use their unchanged generated
main programs from the preceding final build. These results do not measure the
whole corpus or the separately self-hosted native compiler.
