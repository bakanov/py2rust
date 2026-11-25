# Recorded optimization measurements

See [the 2026-11-25 compiler performance report](COMPILER_PERFORMANCE.md) for the
latest split/counter before-and-after measurements and selected application checks.

These historical measurements describe the host compiler at its Unicode
codepoint-cache checkpoint; they are not fresh acceptance for later revisions. They are release builds with correctness checks and alternating samples;
allocation counters run separately. Final acceptance passed: 825 regression tests and all 120 applications.

## Generated versus handwritten Rust

| Kernel | Size | Generated | Handwritten | Ratio |
| --- | ---: | ---: | ---: | ---: |
| bytes | 65,536 | 0.046 µs | 0.046 µs | 1.00× |
| bytes | 1,048,576 | 0.046 µs | 0.046 µs | 0.99× |
| list | 1,024 | 8.587 µs | 8.439 µs | 1.02× |
| list | 32,768 | 262.621 µs | 259.398 µs | 1.01× |
| json | 32 | 40.925 µs | 29.397 µs | 1.39× |
| json | 1,024 | 81.157 µs | 70.486 µs | 1.15× |
| text | 1,000 | 0.583 µs | 0.602 µs | 0.97× |
| text | 10,000 | 7.077 µs | 7.112 µs | 1.00× |
| arithmetic | 10,000 | 2.477 µs | 2.484 µs | 1.00× |
| arithmetic | 100,000 | 24.666 µs | 24.885 µs | 0.99× |

The payload case measures repeated length calls on an existing buffer. The compiler
can optimize that tiny kernel; 46 ns is not the cost of copying or sending 1 MiB.
Integer scans use 32 rounds and JSON lookups use 1,000 calls. These are selected
kernels, not a claim that every transpiled program is within 2× native Rust.

Compared with the initial assessment, the 10,000-append kernel improves from
22.89 ms to 7.08 µs; the 1 MiB length-call kernel from 46.34 µs to 46.08 ns;
and the large integer scan from 512.4 µs to 262.6 µs. Original and final artifacts
are `$HOME/.cache/py2rust-quality-20261120/` and
`$HOME/.cache/py2rust-quality-final/`.

## Unicode indexing

Large Unicode reverse access previously restarted scans from the beginning, causing
quadratic work. Sparse checkpoints removed that behavior. Numeric-only indexing
now selects a lazy direct-character cache when all indexed uses are stable built-in
`ord` calls. General string access keeps sparse checkpoints.

Across 8,192–65,536 characters and sequential, reverse and permuted access, numeric
indexing measures 1.14–1.20× handwritten Rust. At 65,536 characters the three
orders take 0.191/0.192/0.194 ms. The old reverse-access implementation took about
1.07 seconds at this size in a separate before/after run.

For 4,194,304 characters, median whole-process peak RSS was 60,800 KiB with the
codepoint cache and 60,928 KiB handwritten. The sparse baseline used 48,752 KiB.
These measurements include inputs and index construction: the faster specialized
representation deliberately uses more memory. ASCII cache input remains borrowed.
Artifacts: `$HOME/.cache/py2rust-unicode-codepoint-cache/`; the earlier
quadratic comparison is `$HOME/.cache/py2rust-unicode-final/`.

## Readability

The refreshed assessment reproduces generated-main Clippy totals of 203 for chat,
117 for traffic and 164 for gzip, down from 613/240/294 before the readability pass.
Unnecessary mutable bindings fall from 68/56/59 to 1/0/0. Remaining warnings include
parentheses, formatting temporaries, conservative ownership and checked conversions.
See [actual before/after excerpts](GENERATED_RUST.md). Warning counts are readability
signals, not speed or correctness proofs.

## Refreshed application comparisons

These comparisons toggle one optimization in the current compiler, preserving the
rest of its improvements and checking exact results. Seven alternating timing
samples use 200 calls; three separate fresh-process samples measure peak RSS.

| Operation | Timing case | Speedup | Memory case | Peak RSS before → after |
| --- | --- | ---: | --- | ---: |
| Chat JSON response serialization | 256 messages | 2.83× | 16,384 messages | 58,112 → 49,408 KiB |
| Traffic payload slice views | 4 MiB payload | 1.10× | 4 MiB payload | 10,484 → 6,272 KiB |

Traffic remains dominated by hashing, so eliminating its slice copy has a larger
relative memory benefit than time benefit. The memory metric includes input and
expected-output setup, and is distinct from cumulative allocations. Chat's expected
bytes are produced directly with serde so the memory oracle does not construct
the old intermediate JSON tree before measurement.

Sources and runners are preserved in
`$HOME/.cache/py2rust-serialization-final/` and
`$HOME/.cache/py2rust-slice-views-final/`.

## Validation status

The preceding compiler version passed 817 regression tests and all 120 application
checks. The integrated follow-up passed 61 focused tests and six structural gates;
subsequent codepoint-cache changes passed 58 overlapping regression checks and two
additional selection/semantic tests. All benchmark runs check their outputs.

The fresh full regression run passed **825 tests in 868.21 seconds** against the
measured compiler. All 120 applications also passed, with zero stale, failed or pending entries. Logs are
`/tmp/py2rust-final-regression.log` and `/tmp/py2rust-final-corpus.log`. Every application result and stage was inspected, its fingerprint matches current
sources, and the compiler/runtime source hashes match the measurement manifest.
The final status snapshot is `$HOME/.cache/py2rust-quality-final/final-corpus-status.json`.
