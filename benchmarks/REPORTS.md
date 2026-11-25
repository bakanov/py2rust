# Benchmark reports and local evidence

Git contains benchmark programs, handwritten Rust baselines, reproduction tools,
the hand-maintained `optimization-gates.json` specification and Markdown summaries.
Generated measurements, build manifests, audit output and profiler/syscall reports
belong outside the checkout. The report locations previously used under
`benchmarks/` are ignored to prevent accidental recommits.

## Local archive

The reports removed during the 2026-11-25 cleanup were preserved locally under:

```text
$HOME/.local/share/py2rust/benchmark-reports/2026-11-25-pre-push/
  manifest.json
  benchmarks/
    access_log/
    corpus_speed_10/
    corpus_speed_20/
    performance_2026_11/
    scaling/
```

The archive preserves each report's former repository-relative path. For example,
the final scaling measurements are at
`benchmarks/scaling/final/results.json` inside this archive. A report name such as
`results.json` in a historical benchmark summary refers to its archived counterpart,
not a file shipped with the repository. Profile annotations and syscall summaries
follow the same convention.

All 118 files were copied and SHA-256 verified before removing their checkout
copies. `manifest.json` records every path, byte count and hash. This is a local
archive, not a downloaded dependency or an artifact available from a fresh clone.
The Markdown results remain historical summaries of those checked runs.

## New measurements

Run the reproduction commands in the corresponding benchmark README, choosing a
fresh output directory under `$PY2RUST_BUILD_DIR` (normally
`$HOME/.cache/py2rust-build`). Tools read their measurement inputs from the explicit
build/comparison directories; they do not require the removed repository reports.
Comparisons against old generated binaries require those preserved builds; a fresh
clone can generate and measure the current compiler against the bundled native
baselines without claiming a historical before/after comparison.

Do not add raw result JSON or profiler output to Git. Keep concise checked results,
methodology, limitations and reproduction commands in Markdown instead. See the
[development storage policy](../doc/DEVELOPMENT.md#layout-and-storage).
