# Performance of 20 suspected-costly corpus applications

Measured 2026-11-25 using the current typed host compiler, optimized release Rust,
and the complete original applications. No application algorithms were rewritten
for this assessment. There are **20 applications, 40 deterministic workloads and
440 validated timed invocations** in the retained results, plus warm-ups and
separate diagnostic runs. The other 100 corpus applications were not run.

All 20 generated Rust applications were faster than their Python references on
the measured larger jobs. That is **not** evidence that they are within 2× of
idiomatic handwritten Rust. This study has no handwritten implementations of the
20 complete applications; its comparisons are explicitly against CPython. The
strongest next compiler/runtime investigation candidates are dependency-resolution
cost, telemetry memory, and JSON/AST representation costs. The slowest wall-clock
job, sprite-atlas export, is mainly waiting for durable file publication.

## What was selected and why

Selection was based on source patterns likely to expose remaining costs: recursive
JSON/record processing, nested indexing, backtracking, text scanning, byte/pixel
loops, repeated statistics, Unicode segmentation, and serialization of large
results. This is a deliberately biased stress sample, not a claim that these are
the objectively slowest 20 out of all 120; proving that would require a broader run.

| ID | Complete application | Suspected cost |
| --- | --- | --- |
| 068 | [Huffman file compressor](../examples/corpus/068_huffman/) | Frequency maps, tree construction and bit packing |
| 071 | [Access-log analyzer](../examples/corpus/071_access_log/) | Regex captures, timestamps and report aggregation |
| 077 | [Python source-outline browser](../examples/corpus/077_source_outline/) | Parsing and traversing generic AST trees |
| 078 | [Regex batch rewrite tool](../examples/corpus/078_regex_rewrite/) | Regex matching and replacement expansion |
| 079 | [Tiny automation-language interpreter](../examples/corpus/079_automation_language/) | Repeated dynamic expression and statement evaluation |
| 080 | [Stateful syntax-highlighting exporter](../examples/corpus/080_syntax_highlighter/) | Stateful tokenization and HTML serialization |
| 095 | [Project code-metrics browser](../examples/corpus/095_code_metrics/) | Repeated parsing, AST traversal and report trees |
| 096 | [Small package constraint resolver](../examples/corpus/096_package_resolver/) | Backtracking with copied constraint collections |
| 100 | [Text diff and patch utility](../examples/corpus/100_text_patch/) | Quadratic line comparison and patch construction |
| 104 | [Series/parallel circuit calculator](../examples/corpus/104_circuit_calculator/) | Recursive circuit trees and numerical evaluation |
| 105 | [Telemetry trend analyzer](../examples/corpus/105_telemetry_analyzer/) | Window statistics and retained per-sample JSON |
| 109 | [Warehouse movement simulator](../examples/corpus/109_warehouse_simulator/) | Repeated state updates and command processing |
| 110 | [Population simulation runner](../examples/corpus/110_population_simulator/) | Repeated numeric simulation with retained results |
| 111 | [PNG structure inspector](../examples/corpus/111_png_inspector/) | Chunk scanning and binary validation |
| 112 | [PCM WAV analyzer](../examples/corpus/112_wav_analyzer/) | PCM decoding and numeric aggregation |
| 113 | [BMP thumbnail maker](../examples/corpus/113_bmp_thumbnails/) | Nested pixel loops and thumbnail conversion |
| 114 | [PPM image filter pipeline](../examples/corpus/114_ppm_filters/) | Per-pixel filter pipeline and image serialization |
| 115 | [Sprite-atlas packer](../examples/corpus/115_sprite_atlas/) | Pixel packing and many durable output files |
| 117 | [Terminal task dashboard](../examples/corpus/117_terminal_dashboard/) | Unicode text segmentation and repeated layout |
| 118 | [ZIP manifest validator](../examples/corpus/118_zip_validator/) | Archive decompression and manifest validation |

## Method and scope

- Linux x86-64, Intel Core i3-12100, rustc 1.83.0, Python 3.13.5. Builds, inputs and
  outputs were on the local Linux filesystem under `$HOME/.cache/py2rust-build`,
  not on the repository's external exFAT drive. These were host runs, not Docker.
- Each entire reachable Python application was transpiled and Cargo-built with
  `--release --locked --offline`. Measured Rust processes ran with Python absent
  from `PATH` and unusable `PYTHONHOME`/`PYTHONPATH`.
- Each size/engine has one untimed warm-up, then five measured fresh-job runs,
  alternating Python/Rust order. Application 095 was repeated with **15** samples
  per size/engine because the initial five samples showed substantial variation.
- The timed section is the application subprocess: startup/imports, computation,
  input/output, durability operations and shutdown are included. Fixture creation,
  compilation and independent correctness oracles are excluded. GNU `time` records
  process CPU time and maximum RSS; its small launch overhead is included in wall
  time for both engines. Inputs have warm caches from fixture creation; output
  directories are new for every invocation.
- Every measured invocation passes the existing application's independent fixture
  checker. Expected domain-result exit codes are accepted: the resolver reports
  unsatisfiable dependencies and diff reports changed files with exit code 1.
  Inputs are regenerated deterministically and their hashes must match
  across samples and engines. The fixtures exercise real jobs rather than isolated
  extracted functions. Regex rewriting uses **preview**, while the other jobs
  write their normal output bundles; terminal rendering uses one refresh to avoid
  measuring an intentional waiting interval.
- Peak RSS is resident process memory, including libraries/runtime, not a heap
  allocation count. CPU figures from GNU `time` have coarse 10 ms resolution; zero
  does not mean the application did no CPU work. Five samples do not establish
  reliable p95/p99 latency; the evidence contains individual observations and maxima.
- These are bounded single jobs, not long-running HTTP/TCP load tests. Python
  startup/import costs contribute substantially to the observed speedups. Workload
  sizes differ by application, so ranking these jobs is not a universal ranking of
  the applications' efficiency.

## Current timings and memory

Times are medians in milliseconds. “Python/Rust” is the larger-job Python time
divided by Rust time: a larger number means Rust finished sooner. RSS is the
median larger-job **Rust** peak RSS. Small/large input definitions follow below.

| ID | Rust small ms | Rust large ms | Python large ms | Python/Rust | Rust RSS MiB |
| --- | ---: | ---: | ---: | ---: | ---: |
| 068 | 11.43 | 45.16 | 268.06 | 5.94× | 10.5 |
| 071 | 17.96 | 155.33 | 502.00 | 3.23× | 35.6 |
| 077 | 15.67 | 111.73 | 301.50 | 2.70× | 26.0 |
| 078 | 1.97 | 2.81 | 85.62 | 30.50× | 5.0 |
| 079 | 11.77 | 40.94 | 277.47 | 6.78× | 24.5 |
| 080 | 17.82 | 72.49 | 405.46 | 5.59× | 24.0 |
| 095 | 15.27 | 131.13 | 312.39 | 2.38× | 39.5 |
| 096 | 14.79 | 111.55 | 196.93 | 1.77× | 4.9 |
| 100 | 19.28 | 57.96 | 189.01 | 3.26× | 9.6 |
| 104 | 17.17 | 43.81 | 151.63 | 3.46× | 19.1 |
| 105 | 18.83 | 105.91 | 306.14 | 2.89× | 57.5 |
| 109 | 29.16 | 58.79 | 282.81 | 4.81× | 14.8 |
| 110 | 21.26 | 44.26 | 154.03 | 3.48× | 7.8 |
| 111 | 18.47 | 38.16 | 180.91 | 4.74× | 12.2 |
| 112 | 21.95 | 46.48 | 168.24 | 3.62× | 11.2 |
| 113 | 27.12 | 26.97 | 110.85 | 4.11× | 3.8 |
| 114 | 23.28 | 61.42 | 191.04 | 3.11× | 11.0 |
| 115 | 39.40 | 164.20 | 264.52 | 1.61× | 6.7 |
| 117 | 17.09 | 17.40 | 116.65 | 6.70× | 3.5 |
| 118 | 20.23 | 38.41 | 179.26 | 4.67× | 9.0 |

## Workload sizes

The larger inputs were increased after a pilot showed mostly startup/publication
cost. Sizes stay within application limits. A parser rejects a single oversized
source module, so the larger source-analysis jobs use eight individually valid
modules. The interpreter job is syntactically valid, and regex replacement output
stays below its byte budget. Rejected pilot inputs are not counted as successful
performance measurements.

| ID | Small job | Larger job |
| --- | --- | --- |
| 068 | 4096 input bytes | 1048576 input bytes |
| 071 | 100 access-log records | 8000 access-log records |
| 077 | 1 modules × 20 Python functions | 8 modules × 160 Python functions |
| 078 | 4000 text bytes; 2 regex rules | 48000 text bytes; 2 regex rules |
| 079 | 200 interpreter loop iterations | 4000 interpreter loop iterations |
| 080 | 40 configuration lines / 240 tokens | 1200 configuration lines / 7200 tokens |
| 095 | 1 modules × 20 Python functions | 8 modules × 160 Python functions |
| 096 | 4 binary-choice packages plus impossible dependency | 10 binary-choice packages plus impossible dependency |
| 100 | 50 lines on each side of diff | 900 lines on each side of diff |
| 104 | 4 circuits / 60 nodes | 16 circuits / 1008 nodes |
| 105 | 64 timestamped samples; window 8 | 2048 timestamped samples; window 8 |
| 109 | 100 warehouse commands | 2000 warehouse commands |
| 110 | 4 populations × 64 steps | 4 populations × 2048 steps |
| 111 | 16 ancillary PNG chunks × 1024 bytes | 512 ancillary PNG chunks × 1024 bytes |
| 112 | 1024 signed PCM samples | 65536 signed PCM samples |
| 113 | 32×32 BMP pixels | 192×192 BMP pixels |
| 114 | 32×32 PPM pixels; invert and threshold | 192×192 PPM pixels; invert and threshold |
| 115 | 4 sprites of 8×8 pixels | 32 sprites of 16×16 pixels |
| 117 | 16 Unicode-labelled tasks; one refresh | 128 Unicode-labelled tasks; one refresh |
| 118 | 16 ZIP entries × 4096 uncompressed bytes | 512 ZIP entries × 4096 uncompressed bytes |

## Findings that matter for the compiler

### 096: dependency resolver deserves a focused computation benchmark

The larger input has ten two-version packages plus an impossible dependency. It
explores **4,095 states**, records 2,048 conflicts and retains 32 conflict details.
Rust takes about **112 ms**, including about **90 ms** of CPU; Python takes about
197 ms. More revealingly, the small-to-large wall-time increase is approximately
97 ms for Rust and 99 ms for Python. That subtraction is only an indicator, not
an isolated kernel benchmark, but it suggests that startup explains much of the
whole-job advantage.

[solving.py](../examples/corpus/096_package_resolver/solving.py) deliberately rebuilds
constraint collections for each branch, traverses generic JSON, parses versions,
and constructs conflict records. The combinatorial search is an application
algorithm property, not a transpiler defect. Avoidable representation changes,
map/JSON copies and repeated conversions are compiler/runtime candidates. A native
baseline for the **same search order and conflict-output contract** would be the
most useful next comparison; pruning the search only in the baseline would be unfair.

### 105: telemetry is the clearest memory warning

The 2,048-sample job uses roughly **57.5 MiB** peak Rust RSS versus **36.2 MiB** for
Python. Input is about **100 KiB**, and the output bundle is about **1.7 MB**.
Rust completes in about **106 ms**, with around **80 ms** CPU.

The implementation repeatedly constructs per-sample JSON results, computes window
statistics, retains the full result set and constructs a canonical archive plus
additional exports. Generated Rust still has owned JSON trees and copies at some
serialization boundaries. See [analysis.py](../examples/corpus/105_telemetry_analyzer/analysis.py),
[statistics.py](../examples/corpus/105_telemetry_analyzer/statistics.py), and
[reports.py](../examples/corpus/105_telemetry_analyzer/reports.py).

The high RSS is measured; the exact fraction attributable to avoidable copies is
not. Allocation profiling should separate necessary output trees from temporary
copies before extending borrowed views or direct serialization. This is a stronger
memory-optimization lead than simply counting `.clone()` calls in generated text.

### 071: access-log parsing remains a substantial CPU workload

The real corpus application processes 8,000 common-log records in about **155 ms**,
roughly **51,500 records/second including startup and publication**. It uses about
130 ms CPU and 35.6 MiB peak RSS. This application differs from the smaller JSON
Lines demo: it parses regex captures and timestamps, validates records, aggregates,
and publishes a full report.

[parser.py](../examples/corpus/071_access_log/parser.py) constructs a month-name map
on each call and turns captures into generic JSON fields. Immutable-literal
hoisting, capture views, and ownership of derived strings are candidates. The
runtime already caches compiled regex patterns; blindly adding another regex
cache would not address the remaining work. These are source-inspection findings,
not a measured cost decomposition.

### 095 and 077: AST representation and worker overhead

For eight modules containing 1,280 functions, source outline takes about **112 ms**;
code metrics takes about **131 ms** in the extended 15-sample measurement. Code
metrics uses about **39.5 MiB** peak RSS, higher than Python's roughly 32 MiB.

The initial five code-metrics Rust observations ranged from about 129–330 ms,
with median 295 ms. The extended observations were about 130–137 ms, median 131 ms.
We retain the extended raw samples and explicitly report the earlier instability;
295 ms should not be treated as a stable compiler slowdown. Host scheduling and
publication variability remain possible influences.

The code-metrics project validates module names by parsing an import statement,
then parses each full module. The runtime's
[Python AST helper](../py2rust/compiler/service_runtime/src/python_ast.rs) spawns and
joins a separate parser worker with a bounded **64 MiB virtual stack** per parse;
that is not a claim that every worker consumes 64 MiB resident RAM. The diagnostic
run observed 16 thread creations, matching two parses for each of eight modules.
Worker reuse or a cheaper validated module-name API, plus fewer generic-AST copies,
are plausible general runtime improvements. The bounded-stack protection must be
preserved. [project.py](../examples/corpus/095_code_metrics/project.py) and
[metrics.py](../examples/corpus/095_code_metrics/metrics.py) show the call sites.

### 115: the slowest tested job is mainly durable output, not pixel copying

Sprite-atlas export takes about **164 ms**, but only about **10 ms CPU** at the
measurement's coarse resolution. It publishes **75 files**. A separate checked
`strace -c -w` run recorded **77 `fsync` calls taking 141 ms**, including directory
synchronization. That supports a storage-publication explanation for most of the
latency. The traced run is diagnostic and is not included in the timing samples.

[documents.py](../examples/corpus/115_sprite_atlas/documents.py) explicitly synchronizes
each staged file and the publication directories. Removing those calls would
weaken the application's durability contract. This should not be presented as a
transpiler optimization opportunity without first designing an equivalent durable
publication protocol or changing the application's requirements.

### Other selected programs

Huffman, text diff, circuit evaluation, simulation, image/audio operations and
archive validation all completed the larger valid jobs in roughly **27–73 ms**
with the exception of the already discussed workloads. Most use noticeably less
RSS than their Python references. No catastrophic scaling appeared on these bounded
inputs. That is not a proof against worst-case inputs: diff is still quadratic in
line counts, dependency search is exponential, and these jobs are far smaller than
unbounded production streams.

Regex preview completed in about 2.8 ms and the one-refresh dashboard in about
17 ms. Their large Python/Rust ratios are especially affected by Python startup;
they are not evidence of a 30× or 7× advantage in a warmed, persistent service.

## Diagnostic evidence and next priorities

[Raw observations (local archive)](../benchmarks/REPORTS.md#local-archive) (`benchmarks/corpus_speed_20/results.json`) include all samples,
CPU/RSS, input hashes, compiler/application fingerprints and executable hashes.
[Five syscall summaries (local archive)](../benchmarks/REPORTS.md#local-archive) (`benchmarks/corpus_speed_20/syscalls`) are kept separately.
Their percentages are percentages of **time in traced syscalls**, not percentages
of entire application runtime; they cannot be used as whole-program profiles.

Recommended follow-ups, without claiming they are already fixes:

1. Measure allocations and JSON/collection copying in **105** and **096**; add a
   matched native search/statistics baseline before asserting a 2× Rust slowdown.
2. Benchmark parser worker creation, duplicate validation parses and AST conversion
   in **095/077**, preserving source limits and stack isolation.
3. Measure constant-table construction, field extraction and derived strings in
   **071**, then implement only transformations supported by ownership/effect proofs.
4. Treat **115** publication as an I/O contract issue rather than deleting `fsync`
   calls to improve a benchmark.

## Correctness issue found during the assessment

The first release build of application 071 exposed a Rust 2021 temporary-lifetime
error in the recent split-index optimization when used inside a returned JSON
object. The shared lowering now completes the owned result in a local block before
that surrounding tail expression. This is a general compiler fix, not an edit to
071. All 20 builds were then refreshed against the corrected compiler fingerprint.
The [six split-consumer regression tests](../tests/test_split_consumers.py) passed,
including the new returned-JSON case. No other performance optimizations were
introduced during this study.

These measurements check the selected valid jobs against their independent
oracles, not every malformed-input or failure-injection test in the corpus. They
also assess the host typed frontend, not the separate self-hosted native compiler.

## Reproduce

After normal development setup and Cargo dependency fetching, run from the repo:

```sh
PYTHONPATH="$PWD" python tools/assess_corpus_speed.py \
  --output "$HOME/.cache/py2rust-build/corpus-speed-20-new"
```

This selects exactly the documented 20 IDs, builds sequentially with a shared
release target, then measures both sizes with five repetitions. Build time is not
part of application timing. Linux `/usr/bin/time` is required. Output is retained
outside the checkout; warm-up input/output bundles remain available for inspection.
Independent oracles run after each timed subprocess. The command exits with an
error if a workload fails rather than quietly treating rejection as performance.

For the extended code-metrics sample or a selected rerun:

```sh
PYTHONPATH="$PWD" python tools/assess_corpus_speed.py --phase measure \
  --ids 095 --repeats 15 \
  --output "$HOME/.cache/py2rust-build/corpus-speed-20-new"
```

Successful matching release builds are reusable; measurements reject changed
compiler/application fingerprints or modified executables. Use `--phase build`
after changing code. New measurements archive previous per-job JSON records.

To reproduce separate syscall diagnostics (requires `strace`):

```sh
PYTHONPATH="$PWD" python tools/assess_corpus_speed.py --phase trace \
  --ids 095 115 071 096 105 \
  --output "$HOME/.cache/py2rust-build/corpus-speed-20-new"
```

The original preserved artifacts are at
`$HOME/.cache/py2rust-build/corpus-speed-20/<id>/`: `program`, `rust/src/main.rs`,
`build.json`, build logs, size-specific measurements, and `runs/<size>/<engine>-0/`.
CPU/RSS and latency will depend on your machine, filesystem and background load.
