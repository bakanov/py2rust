# Additional terrain and cron comparisons

Raw report filenames below refer to [local archived reports](../../REPORTS.md#local-archive),
not files shipped in this repository. Source programs and Markdown summaries remain in Git.

These comparisons use unchanged compiler/application sources and independently
handwritten complete-job Rust implementations. Each batch rotates generated and
native release executables over fresh identical inputs. Every run passes an
independent oracle and exact complete-file comparison. Compilation, fixture
creation and checking are excluded from timing; startup and durable publication
remain included.

| Application | Size | Generated median (ms) | Handwritten median (ms) | Ratio |
|---|---|---:|---:|---:|
| Terrain routes | Small | 25.49 | 14.71 | 1.73× |
| Terrain routes | Large | 79.53 | 27.49 | **2.89×** |
| Cron explorer | Small | 13.25 | 12.86 | 1.03× |
| Cron explorer | Large | 30.94 | 15.45 | **2.003×** |

Both large cases fail the strict <2.00× threshold and have no accepted exception.
Cron's full ratio is 2.003064571; rounding it to 2.00 does not turn it into a pass.
It is a borderline observation, not evidence of a stable gap above 2.00 across
runs or hosts. The two `*-results.json` files retain all 120 timed invocations
(15 per executable and size), raw wall/CPU/RSS observations and fingerprints.

## Terrain routes (065)

`../../corpus_speed_20/native/terrain_routes.rs` preserves A* priorities
`(estimated total, current cost, position)`, neighbor order, stale tickets,
predecessor ties and every reported search statistic. Typed arrays and a reversed
Rust binary heap implement the same search; the implementation also constructs
all ASCII overlays, canonical inputs, route JSONL and the checksummed bundle.
Preview and write modes are implemented.

The timed grids are 12×12 with four queries and 64×64 with 32 queries. Variable
terrain costs and a wall with two gaps exercise detours. Existing Dijkstra and
small-grid relaxation oracles check costs/reachability; complete output equality
also checks the exact selected paths, counters and exports.

`terrain-checks.json` records 533 varied complete jobs, including 226 exhaustive
tiny grids with 4,896 queries, generated grids, zero costs, normalization/replay,
161 invalid inputs, path guards, maximum dimensions/costs and a 2,078-step maze.

Source inspection suggests further general compiler opportunities: fixed tiny
lists used only for iteration can become stack arrays, returned nonescaping
neighbor lists can be consumed as iterators, and proven bounded integer-indexed
sets can use dense storage. The current generated renderer also constructs
per-cell strings. These are candidates, not profiled cost percentages or changes
implemented in this comparison. Any lowering must preserve errors, order,
negative-index behavior and escape/mutation semantics.

## Cron explorer (082)

`../../corpus_speed_20/native/cron_explorer.rs` implements the numeric grammar,
Unicode source columns, exact recoverable diagnostics, Sunday alias and cron day
rules. Calendar exploration retains chronological day/hour/minute traversal,
inspected-day counts, inclusive start/exclusive end and proof of an additional
match before truncation. JSON/text/CSV reports and replay files are byte-identical.

Workloads use four sparse schedules over 366 days and sixteen over 3,660 days,
including leap days and impossible February dates. An independent year/date
constructor supplies expected occurrences, avoiding a multi-million-minute
reference scan for every timing sample. The native implementation still scans
every day, matching the application algorithm.

`cron-checks.json` records 65 additional jobs: minute-grid oracle comparisons,
80 generated expressions, exact grammar diagnostics, leap-century and UTC-offset
boundaries, truncation limits, replay and a 16,000-occurrence export under a
256 MiB address-space limit. The count includes its separate prlimit-wrapped job.

The handwritten version reads calendar components directly. Generated Rust
formats each day as `%m %d %w`, splits strings and parses integers, following the
Python source. Potential improvements include typed date-component APIs or a
proven format/parse simplification; removing checks or recognizing application
names would not be a general compiler solution.

Both baselines use shared JSON/low-level filesystem primitives. Shared snapshots
reject hard-linked inputs more strictly than these Python applications; measured
inputs are unaliased regular files. Native fault-injection/pause hooks are not
implemented, so those race/interruption suites are excluded.

Three of ten additional comparisons are complete. The earlier route planner
remains at 23.52× large; seven comparisons remain pending. None of these outliers
has been optimized or accepted as an exception.
