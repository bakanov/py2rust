# Selected 20-application performance evidence

Raw report filenames below refer to [local archived reports](../REPORTS.md#local-archive),
not files shipped in this repository. Source programs and Markdown summaries remain in Git.

See [the assessment](../../doc/CORPUS_SPEED_20.md) for selection, workload sizes,
results, limitations and reproduction commands.

`results.json` contains 40 successful workload records from 20 complete corpus
applications, measured on 2026-11-25. Each size has five observations per engine,
except application 095, which has 15: 440 timed invocations in total. Every
invocation passed its existing independent application oracle. Compiler/source
fingerprints, executable hashes, input hashes, wall time, CPU time and peak RSS
are included. These compare release generated Rust with CPython, not handwritten
Rust. Compilation, fixture construction and correctness checking are untimed.

`syscalls/` contains separate checked large-job `strace -f -c -w` diagnostics for
071, 095, 096, 105 and 115. They are not included in the latency samples. Syscall
percentages describe syscall time, not whole-program CPU percentages.

The original binaries, generated projects, build logs, and warm-up input/output
bundles are retained locally under
`$HOME/.cache/py2rust-build/corpus-speed-20/<id>/`. Machine-specific artifacts are
not committed. Use `tools/assess_corpus_speed.py` to build and measure fresh jobs.
