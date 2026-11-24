# Generated Rust assessment — 2026-11-20

The main problem is avoidable copying and repeated string rebuilding. A roughly
2× slowdown is acceptable for this project's current priorities; concentrate on
large regressions, absolute time, and scaling rather than polishing every lint.

## Measured release performance

Rust 1.83, local Linux x86-64. Each row is one kernel invocation, excluding process
startup and input construction. Generated function argument copies are included.
Native baselines use borrowed inputs, checked i64 arithmetic and Unicode character
counts. Results match the Python reference. Seven alternating-order samples,
warmup, adaptive batching and black-box barriers were used. Timings below are
medians from the uninstrumented release executable.

| Work | Generated | Handwritten | Ratio |
| --- | ---: | ---: | ---: |
| Append an 8-byte string 1,000 times | 149 µs | 0.581 µs | 256× |
| Append an 8-byte string 10,000 times | 22.9 ms | 7.11 µs | 3,222× |
| Read-only calls with a 64 KiB buffer, 128 rounds | 1.24 µs | 0.047 µs | 27× |
| Read-only calls with a 1 MiB buffer, 128 rounds | 46.3 µs | 0.046 µs | 998× |
| Scan 1,024 integers, 32 rounds | 10.6 µs | 8.45 µs | 1.25× |
| Scan 32,768 integers, 32 rounds | 512 µs | 261 µs | 1.97× |
| Read a JSON string field 1,000 times, 32 other fields | 69.7 µs | 30.3 µs | 2.30× |
| Same lookup, 1,024 other fields | 156 µs | 73.4 µs | 2.12× |
| Checked integer accumulation, 100,000 iterations | 24.9 µs | 24.8 µs | 1.00× |

These are diagnostic kernels, not a measurement of chat throughput or end-to-end
network latency. Tiny baselines make ratios especially large. Hardware, compiler
version and workload affect the numbers; do not extrapolate the ratios to all code.

## Highest-priority finding: repeated string growth

The generated assignment is:

```rust
result = format!("{}{}", result.clone(), "message ".to_string());
```

It clones the growing prefix, formats a fresh string, and ultimately clones the
returned string too. Repeating this operation scales quadratically in the amount
of output. The equivalent Rust baseline uses `result.push_str("message ")` and
amortized capacity growth. Ten times the input took approximately 154 times the
generated time in this run. The exact growth factor is affected by allocation and
cache behavior; the copying algorithm itself explains the scaling risk.

A separate counting-allocator build requested about 1.6 GB cumulatively for the
10,000-append case, compared with 262 KB for the baseline. This is allocation and
reallocation traffic, not peak memory or RSS. Allocation instrumentation changes
optimization and these counts must not be interpreted as exact allocation counts
of the uninstrumented timing executable.

Recommended first change: recognize safe string self-concatenation and emit
`push_str`, respecting evaluation order and aliases. Move a return value at its
last use. Keep checked arithmetic and failure behavior intact.

## Second priority: ownership at read-only function boundaries

Generated functions accept `Vec<u8>`, `Vec<T>`, `String` and JSON values by value;
call sites commonly clone their arguments. For example:

```rust
fn payload_size(mut data: Vec<u8>) -> rt::Result<i64> { /* ... */ }
// In a loop:
payload_size(data.clone())?;
```

A read-only `&[u8]` parameter removes the need for that ownership transfer.
The benchmark shows large relative overhead even for a length-only operation,
but the absolute 1 MiB cost here is 46 µs, much less urgent than the string case.
Release LLVM can eliminate some of these copies: the instrumented build recorded
129 allocations/135 MB for that case, which must not be assumed to survive in the
normal release build. Source clone counts alone are insufficient evidence.

This pattern also occurs in a real application: the traffic replayer's generated
`connected` function calls `exchange` with `data.clone()` per record, although
`exchange` only reads the immutable fixture. This is a concrete candidate for an
end-to-end replay benchmark before claiming a measured service-level impact.

Implement read/write/escape analysis for parameters and last-use moves. Borrow
immutable inputs where proven safe; retain owned snapshots where mutation or
aliasing requires them. Resource-handle clones may only increment a shared handle
count and should not be equated with deep copies of buffers or JSON.

## Lower priority: approximately 2× cases

List iteration emits a snapshot clone and JSON field extraction allocates an
owned string. Both are candidates for later improvements, but the measured
slowdowns are near the acceptable range. JSON indexing already borrows the outer
local object; it does not necessarily clone the entire document on every lookup.
Do not replace correct code simply to reduce the textual number of `clone()` calls.

## Idiomaticity inspection

Clippy all/pedantic and unused-mut/parentheses diagnostics were force-enabled to
bypass generated-file allow attributes. Counts below cover primary diagnostics
in generated `src/main.rs`, excluding the runtime and dependencies.

| Complete project | Python lines | Rust lines | Clone call sites | Diagnostics |
| --- | ---: | ---: | ---: | ---: |
| Paper Plane chat | 711 | 1,794 | 414 | 507 |
| Traffic replayer | 322 | 935 | 87 | 243 |
| Gzip archiver | 486 | 1,129 | 235 | 368 |

Line counts include comments and blank lines. These are inspection aids, not
quality scores. Many diagnostics are cosmetic: unnecessary `mut`, parentheses,
returns, owned string comparisons and `Ok(expression?)`. The chat output has 134
unused-mut and 67 owned-comparison findings. These affect readability, but their
runtime impact needs measurement. Checked arithmetic, resource cleanup and explicit
error handling are useful semantic guarantees, not defects to remove wholesale.

## Repeat the assessment

From the repository with its environment activated:

```sh
python tools/assess_rust.py --output $HOME/.cache/py2rust-quality-next
```

Use a fresh output directory on a Linux filesystem. The runner builds release
kernels, validates outputs against Python, measures them, builds an independent
allocation diagnostic executable, and inspects three complete projects with
Clippy. Inputs and handwritten baselines live in `benchmarks/rust_quality/`.
Raw results and generated Rust from this assessment are outside the repository at
`$HOME/.cache/py2rust-quality-20261120/`; `results.json` includes samples and
source hashes. No compiler optimization was applied during this assessment.

For subsequent optimization work, prioritize a large slowdown (for example >5×)
with material absolute cost or worsening size scaling. Repeat the same release
measurement, then validate whole applications and mutation/error semantics.
