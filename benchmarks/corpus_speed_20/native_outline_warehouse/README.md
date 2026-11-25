# Handwritten source-outline and warehouse comparisons

Raw report filenames below refer to [local archived reports](../../REPORTS.md#local-archive),
not files shipped in this repository. Source programs and Markdown summaries remain in Git.

These are independent complete-job Rust implementations. No compiler or Python
application changes were required. Each batch rotates current generated,
preceding generated and handwritten release executables over fresh identical
inputs. Every invocation passes an independent oracle and exact complete-file
checks; compilation and checking are untimed.

| Application | Size | Generated median (ms) | Handwritten median (ms) | Ratio |
|---|---|---:|---:|---:|
| Source outline | Small | 14.95 | 14.48 | 1.03× |
| Source outline | Large | 109.17 | 77.34 | 1.41× |
| Warehouse simulation | Small | 30.75 | 29.87 | 1.03× |
| Warehouse simulation | Large | 52.55 | 45.17 | 1.16× |

Both applications pass <2.00× at both sizes. The two `*-results.json` files retain
180 timed invocations in total (15 per executable and size), fingerprints and raw
wall/CPU/RSS observations. Timings include startup, parsing, serialization and
durable publication; these are not isolated compute-kernel speedups.

## Source outline

`../native/source_outline.rs` shares the native Python statement parser and static
stylesheet with the application. Analysis uses typed Rust structures for scopes,
definitions and imports; docstring cleaning, ambiguity handling, relative import
resolution, HTML generation and project orchestration are handwritten. Raw source
bytes, normalized source-line anchors and portable replay bundles are preserved.
The shared parser is a Rust library, not an embedded Python runtime.

The baseline passed 33 additional jobs (`outline-checks.json`) against the
independent CPython AST oracle: decorators, Unicode, cleaned docstrings, nested
scopes, relative imports, ambiguous symbols, actual application sources, line
endings/BOM, byte-identical replay, invalid syntax and existing-output preservation.
Shared snapshots reject hard-linked inputs more strictly than this Python
application; timed inputs are unaliased regular files.

## Warehouse simulation

`../native/warehouse.rs` uses a byte grid, typed commands, compact undo records
and immutable per-step state snapshots. Simulate and verify modes recompute the
complete trace. It exports real continuation, rewind, restart and replay jobs,
with the same normalization, bounds, manifest and durable publication.

The baseline passed 374 additional jobs (`warehouse-checks.json`), including
all four push directions and six blocking reasons; generated and rotated programs;
continuation edits; exact move/push undo; malformed/duplicate JSON; archive
tampering; full 1,024-entry history and 2,048-command rewind; 32×32 grids; byte
limits; and filesystem/permission guards. The independent oracle uses coordinate
sets and snapshot undo rather than this implementation's grid mutation records.

Native benchmarks omit the corpus fault-injection/pause hooks. Their race and
hard-kill suites were not run against these baselines. This limitation does not
exclude ordinary durable-publication work from the timed jobs.

Coverage is now nineteen original applications: eighteen below 2.00× at both
sizes, plus the accepted resolver exception at 2.39×. Code metrics (095) and the
ten additional examples remain outstanding.
