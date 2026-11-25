# Final acceptance: three scaling regressions

Raw report filenames below refer to [local archived reports](../../REPORTS.md#local-archive),
not files shipped in this repository. Source programs and Markdown summaries remain in Git.

The user accepted **generated/handwritten Rust <6× for large workloads**. Small
workloads retain the existing <2× gate. All three applications pass with one
current compiler fingerprint and no exemptions. This is scoped acceptance for
these selected programs and bounded workloads, not a claim about the whole corpus.

## Final matched benchmark

| Application | Small ratio | Large original generated (ms) | Large final generated (ms) | Large handwritten (ms) | Large ratio |
|---|---:|---:|---:|---:|---:|
| Autocomplete | 1.07× | 2144.67 | 58.46 | 29.88 | **1.96×** |
| Route planner | 1.03× | 422.29 | 74.52 | 18.19 | **4.10×** |
| Scheduler | 1.03× | 1848.99 | 29.36 | 21.96 | **1.34×** |

All entries come from the final matched run, not ratios divided across sessions.
The original generated binaries are preserved from before this scaling work.
The harness rotates original/current/handwritten release executables after one
warm-up, with 15 timed runs per engine and size: **270 timed complete jobs**.
Every job passes an independent oracle and complete file-content equality.
Startup and output I/O are included; compilation and checking are excluded.

`results.json` retains samples, input/output hashes, source/binary/compiler
fingerprints and explicit size-specific thresholds. `builds.json` identifies all
three final builds. No Python application or handwritten baseline was changed to
obtain these improvements. Generated applications run without a Python runtime.

The acceptance command, after building the three selected applications, was:

```sh
python tools/compare_corpus_native.py \
  --generated "$PY2RUST_BUILD_DIR/scaling-final-generated" \
  --before "$PY2RUST_BUILD_DIR/corpus-additional-generated" \
  --output "$PY2RUST_BUILD_DIR/scaling-final-comparison" \
  --ids 055 061 088 --repeats 15 --large-target 6 --check-target
```

Use a fresh output directory when rerunning. The tool's default large threshold
remains 2×; the explicit option records this user's accepted 6× target.

## Correctness and scaling checks

All three final binaries passed their complete application suites (`checks.json`):

- Autocomplete: 41 traces including 32 seeded traces, 23 split replays, 92 invalid
  inputs, 32 state checks, 16 capacity checks and 22 publication checks.
- Route planner: 11 jobs, 219 independently checked answers, route/cycle witnesses
  and existing-report preservation on invalid input.
- Scheduler: 41 explicit and nine seeded workloads, deterministic repeats and
  generator checks, 90 invalid documents, the 512-job capacity/memory test and
  failure/alias/concurrent-publication checks.

The application wrapper recorded 337, 11 and 177 calls respectively. Some
publication checks additionally launch subprocesses directly; these counts are
not total process counts. Targeted executable regressions also cover the compiler
rules; the final borrowed-map/map-position batch passed nine cases, including
typed/legacy frontends, optimization on/off and independent owned snapshots.

The final route sweep uses the same compiler and nine timed runs per engine and
size after warm-up: **135 additional checked timed jobs** (`route-scaling.json`).

| Vertices / queries | Original generated (ms) | Final generated (ms) | Handwritten (ms) | Ratio |
|---|---:|---:|---:|---:|
| 12 | 8.97 | 9.04 | 8.44 | 1.07× |
| 25 | 13.81 | 10.41 | 8.80 | 1.18× |
| 50 | 49.38 | 18.28 | 10.22 | 1.79× |
| 75 | 151.45 | 35.07 | 12.24 | 2.87× |
| 100 | 342.43 | 57.82 | 15.17 | 3.81× |

Reproduce with `tools/compare_route_scaling.py --comparison <final-comparison>
--output <fresh-directory> --repeats 9`. It verifies compiler, application and binary
hashes. Earlier autocomplete and scheduler sweeps are retained in their patch
directories with their own compiler fingerprints; they are historical evidence,
not represented as fresh final-compiler sweeps.

## Root fixes and boundaries

The transpiler now avoids cloning record ancestors for scalar reads, moves owned
state/fields when safe, borrows read-only recursive traversal and uses copy-on-write
storage for resource-free recursive records. Repeated JSON scans can reuse checked
string projections, stable dictionary entry positions and membership in sets that
only grow. Write-only JSON maps can borrow input records during construction and
materialize independent owned entries once afterward.

These are general type/use-based rules, with conservative fallbacks for mutation,
escaping values, exception observation and resources. They currently live in the
host emitter and are not claims of portable IR-native/self-hosted optimization.
Remaining route costs and broader optimizations are optional future work under the
accepted threshold. Timing ratios remain dependent on workloads and hardware.
