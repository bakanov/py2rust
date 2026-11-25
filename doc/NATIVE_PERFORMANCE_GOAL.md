# Generated Rust versus handwritten Rust: completed comparison goal

This is the completed comparison milestone for its recorded compiler fingerprint.
Subsequent compiler work is tracked in [scaling improvements](SCALING_IMPROVEMENTS.md);
these measurements are not automatically measurements of later compiler revisions.

The revised goal is **generated/native execution time below 2.00× in the selected
applications except the package resolver (096)**, whose observed **2.39×** result
was explicitly accepted by the user. Stop resolver-specific optimization. Complete
native comparisons for all twenty selected applications, then ten additional
applications. This requested optimization-and-comparison scope is **complete**;
seven additional applications expose unresolved performance gaps. CPython speedups do not satisfy the
native-Rust gate. Historical strict ratios and measurements remain unchanged.

## Current coverage

The table includes nested JSON-array and string views and a fresh matched
[twelve-application comparison](../benchmarks/corpus_speed_20/json_views/README.md),
extended with [BMP and ZIP](../benchmarks/corpus_speed_20/native_bmp_zip/README.md)
using the same compiler fingerprint in two additional matched batches, plus
the [sprite-atlas comparison](../benchmarks/corpus_speed_20/native_atlas/README.md),
[automation interpreter](../benchmarks/corpus_speed_20/native_automation/README.md),
[syntax highlighter](../benchmarks/corpus_speed_20/native_highlighter/README.md),
[source outline and warehouse](../benchmarks/corpus_speed_20/native_outline_warehouse/README.md),
and [code metrics](../benchmarks/corpus_speed_20/native_metrics/README.md).
The before column is the preceding optimized compiler with parser caching.

All twenty original applications now have independently handwritten complete-job
baselines. The [fixed ten additional applications](../benchmarks/corpus_speed_10/README.md)
were selected before measuring them. All ten generated release executables built;
[route planning](../benchmarks/corpus_speed_10/route_planner/README.md) measured
1.05× small and **23.52× large**. [Terrain and cron](../benchmarks/corpus_speed_10/terrain_cron/README.md)
measured **2.89×** and **2.003×** on their large workloads respectively. All three
large cases fail the strict threshold; none has an accepted exception.
[Scheduler and redactor](../benchmarks/corpus_speed_10/scheduler_redactor/README.md)
measured **105.29×** and **1.90×** large respectively. Repeated state/field copies
are visible in the scheduler’s generated code.
[JSON diff/patch](../benchmarks/corpus_speed_10/json_patch/README.md) measured
**2.49×** large and passed 980 additional correctness jobs.
[LRU cache](../benchmarks/corpus_speed_10/lru_cache/README.md) measured **6.30×**
large and passed 288 additional jobs, including saved-state split replay.
[Autocomplete](../benchmarks/corpus_speed_10/autocomplete/README.md) measured
**72.00×** large and passed 312 additional jobs, including Unicode normalization,
ranking, pruning and split replay. [CSV conversion](../benchmarks/corpus_speed_10/csv_conversion/README.md)
measured **1.28× / 1.46×** large for its two directions and passed 162 additional
jobs. [CSV join](../benchmarks/corpus_speed_10/csv_join/README.md) measured **1.12×**
large and passed 333 additional jobs. All ten comparisons are complete; the seven
new performance gaps remain unresolved.

Measured on 2026-11-25, with 15 timed repetitions per executable and size.
The table reports median complete-job wall time; lower ratios are better.

| Application | Before views, large (ms) | Now, large (ms) | Native, large (ms) | Small ratio | Large ratio |
|---|---:|---:|---:|---:|---:|
| 068 Huffman compressor | 32.05 | 32.94 | 18.81 | 1.02× | 1.75× |
| 071 Common-access-log analyzer | 85.67 | 85.57 | 45.87 | 0.94× | 1.87× |
| 077 Source outline | 110.10 | 109.17 | 77.34 | 1.03× | 1.41× |
| 078 Regex rewrite (preview) | 2.80 | 2.77 | 2.60 | 1.01× | 1.07× |
| 079 Automation interpreter | 55.42 | 54.50 | 50.42 | 1.09× | 1.08× |
| 080 Syntax highlighter | 51.11 | 50.59 | 50.70 | 1.04× | 1.00× |
| 095 Code metrics | 122.36 | 120.88 | 68.21 | 1.09× | 1.77× |
| 096 Package resolver | 55.01 | 54.26 | 22.68 | 1.01× | 2.39× |
| 100 Text diff | 36.72 | 35.95 | 25.58 | 1.01× | 1.41× |
| 104 Circuit calculator | 37.30 | 37.09 | 25.74 | 1.01× | 1.44× |
| 105 Telemetry analyzer | 85.19 | 86.68 | 66.05 | 1.01× | 1.31× |
| 109 Warehouse simulator | 54.00 | 52.55 | 45.17 | 1.03× | 1.16× |
| 110 Population simulator | 41.93 | 41.12 | 35.97 | 0.98× | 1.14× |
| 111 PNG inspector | 41.20 | 41.33 | 34.64 | 1.02× | 1.19× |
| 112 WAV analyzer | 44.08 | 45.16 | 29.78 | 1.09× | 1.52× |
| 113 BMP thumbnails | 27.24 | 27.40 | 28.05 | 0.95× | 0.98× |
| 114 PPM filters | 50.65 | 51.37 | 28.58 | 1.07× | 1.80× |
| 115 Sprite atlas | 156.87 | 159.40 | 150.30 | 0.96× | 1.06× |
| 117 Terminal dashboard | 19.00 | 18.45 | 17.86 | 0.97× | 1.03× |
| 118 ZIP validator | 38.78 | 38.75 | 37.54 | 1.05× | 1.03× |

**Nineteen of twenty applications are below 2.00× at both sizes. The resolver
is an accepted exception at 2.39×, not a strict threshold pass.** The revised
original twenty-case gate is met in these measurements. The requested ten
additional comparisons are also complete, with their failures retained explicitly.

The [aggregate evidence (local archive)](../benchmarks/REPORTS.md#local-archive) (`benchmarks/corpus_speed_20/original_twenty_summary.json`)
covers all forty size cases and 1,800 timed invocations. All twenty current
compiler/application/generated-binary fingerprints and all twenty native
source/binary fingerprints were audited. Results come from matched batches with
the same compiler, not one simultaneous run; startup and I/O variation limit
claims about isolated computation speed or other machines.

[Seven-application observations](../benchmarks/corpus_speed_20/native_round_two/README.md),
[two additional numeric applications](../benchmarks/corpus_speed_20/native_numeric/README.md),
and [PNG and terminal dashboard](../benchmarks/corpus_speed_20/native_png_terminal/README.md).
Those earlier four batches use the same pre-cache compiler fingerprint; each comparison rotates its
three executables independently. No compiler or application changes were needed
for population, WAV, PNG and terminal dashboard to meet the target.
[Previous five-application milestone](../benchmarks/corpus_speed_20/native_round_one/README.md)
is preserved as historical evidence. The access-log baseline here is application
071's common-log parser, not the separate JSONL README demonstration.

## General compiler/runtime changes

Application Python sources were not edited. These changes apply through shared
host-backend lowering, with conservative fallback when proofs are unavailable:

1. **Immediate JSON collection consumers:** `name in json_keys(value)`,
   `len(json_keys(value))` and `len(json_array(value))` validate the container
   directly without allocating/sorting a temporary collection. Operands retain
   their evaluation order; invalid container kinds still raise errors.
2. **JSON construction:** serialization borrows stable typed collections instead
   of first cloning them. Existing `list[Json]` elements transfer into an owned
   JSON array instead of being reserialized. Conversion still checks the JSON
   nesting and number constraints; escaping outputs remain owned.
3. **Read-only constant tables:** scalar literal dictionaries that are proved
   unmodified use a local `OnceLock` table. Owned escapes still copy. This removes
   repeated month-table construction in the access-log parser without recognizing
   month names, the application ID, or a particular function.
4. **Borrowed projections:** stable indexed/record string comparisons, dictionary
   lookup keys and read-only JSON locals borrow their backing values. Effectful
   operands and mutable sources keep the existing owned fallback. This removes
   per-cell string copies from text diff's quadratic LCS loop.
5. **Temporary JSON records:** lists of uniform, nonescaping object literals can
   become tuples with owned scalar fields and borrowed JSON fields. Checked IR
   types, a complete use audit, and immutable borrowed parameter roots determine
   eligibility. Dynamic keys, escaping objects, mixed field types/order and
   mutation keep ordinary JSON. The current host adapter performs this narrow
   representation rewrite; it is not a general interprocedural schema inference
   pass. Its positional tuple fields are less descriptive than named structs,
   which is a readability improvement still to make.
6. **Integer lookup views:** read-only, index-only integer dictionaries used in
   byte traversal can use a bounded reference table. Preparing the table scans
   at most 256 dictionary entries. Larger dictionaries and keys outside 0..255
   use the original map lookup. The source map, insertion order, missing-key
   errors and owned value-copy boundaries remain unchanged. Nested views reuse
   the existing backing map; writes prevent this lowering.
7. **Small runtime helpers:** checked shifts and byte-buffer append helpers are
   eligible for cross-crate inlining. Overflow, byte-range, allocation and buffer
   size checks are retained. Inlining allows Rust's optimizer to remove checks
   that are redundant for a particular call, such as appending `value & 255`.

8. **String concatenation:** proven string addition chains produce one `format!`
   instead of formatting and allocating every intermediate prefix. Operand order
   and value snapshots across later mutations are preserved. Numeric and collection
   addition keep their existing lowering.
9. **Null identity:** `value is None` and its reversed/negated forms inspect stable
   JSON paths without cloning the JSON tree. Missing keys and invalid projections
   retain their failures.
10. **Regex capture consumers:** constructing a full capture result moves its
    existing JSON arrays instead of serializing them again. A conservative audit
    may additionally omit the `spans` field when all local uses and direct helper
    parameter uses inspect only `groups` or null identity. Escapes, dynamic root
    keys, reassignment, unknown/recursive consumers and observed spans retain the
    full result. Pattern, group-count and input limits still run. This is a narrow
    consumer specialization, not a public change to `regex_capture`.

Implementation: [JSON consumers](../py2rust/compiler/backend/json_consumers.py),
[record-view proof](../py2rust/compiler/backend/record_views.py),
[local bindings](../py2rust/compiler/backend/binding_emission.py),
[string comparisons](../py2rust/compiler/backend/operator_emission.py),
[integer lookup proof](../py2rust/compiler/backend/lookup_views.py), and
[integer lookup runtime](../py2rust/compiler/service_runtime/src/integer_lookup.rs),
and [capture-use audit](../py2rust/compiler/backend/regex_consumers.py).
These changes do not extend the separate self-hosted compiler.

For example, the resolver's temporary request list now has this representation:

```rust
let mut requests: Vec<(String, &rt::Json)> = vec![("root".to_string(), roots)];
```

Previously it was `Vec<rt::Json>` whose objects each owned a copied dependency
subtree. Read-only projected locals similarly change from an owned `rt::Json`
returned by `rt::json_key` to `&rt::Json` returned by `rt::json_key_ref`.
The JSON returned to callers is still owned; that boundary remains a substantial
cost in the resolver.

## Bounded parser caching

A further host-backend pass memoizes conservatively audited deterministic functions
with one immutable string input and a Copy scalar/tuple result. It rejects unknown
calls, environmental state, observable side effects, parameter mutation and mutable
returned values. A mutex protects at most 64 successful results per function;
keys longer than 256 UTF-8 bytes bypass caching. Calculation holds no cache lock,
and failures are never retained. Optimization-disabled builds keep direct execution.

The [initial matched resolver comparison](../benchmarks/corpus_speed_20/parser_memoization/README.md)
reduces its large median from 62.98 to 55.73 ms (11.5%), versus 22.34 ms handwritten:
**2.49×**, still above target. The subsequent eleven-application batch in the table
from that milestone measures **2.42×**; both batches retain their raw observations.
The refreshed native comparison checks all 990 timed invocations with the new
compiler. Ten of eleven applications still pass both sizes.
All twenty applications rebuilt successfully and passed all forty workload checks
(400 timed Python/generated invocations). Three cache-runtime tests, four executable
parser-parity cases and nine effect/cost regressions passed. Only two selected
applications currently receive this lowering: source outline and package resolver.

Implementation: [parser proof](../py2rust/compiler/backend/memoization.py) and
[bounded cache](../py2rust/compiler/service_runtime/src/memoization.rs).

## Nested JSON array and string views

The typed memory oracle now carries stable JSON backing through read-only nested
`json_array` loops, confined to each loop body. Read-only extracted array locals
can use `&[rt::Json]`; JSON string locals can use `&str`. Source or local mutation
retains owned snapshots, and escaping outputs materialize. Move safety retains an
owned backing argument while its string view remains live, including callbacks.
Legacy and optimization-disabled builds use the existing owned fallback.

The [before/after examples and raw observations](../benchmarks/corpus_speed_20/json_views/README.md)
show the change. The resolver measured 55.01 → 54.26 ms in this matched batch:
a small difference, not evidence of a large or statistically established speedup.
The PPM application's generated source is unchanged; its new handwritten baseline
expands measured coverage and passes at 1.80× on the large workload.

The current compiler passed forty focused view/effect/move-safety cases and the
full selected twenty-application sweep: forty checked workloads and 400 timed
Python/generated invocations. The twelve-baseline JSON-view comparison passed all
1,080 timed complete-output checks. The later BMP and ZIP batches add 180
timed checks, with no compiler change, bringing current coverage to fourteen
baselines and 1,260 timed invocations. BMP and ZIP also passed 822 varied complete
jobs (398 and 424 respectively); their raw evidence is linked above. Compiler/application/binary fingerprints are
recorded with the results. The PPM baseline additionally passed 322 varied complete jobs, including all u16
sample values, generated filter properties, malformed inputs and archive tampering.
The sprite-atlas extension adds 90 timed comparisons and 341 varied complete
jobs without changing the compiler. The automation interpreter adds another 90
timed comparisons and 232 varied complete jobs. The syntax highlighter adds 90
timed comparisons and 46 varied complete jobs; the generated program also passed
its strengthened invalid-content checks. Source outline and warehouse add another
180 timed comparisons and 407 varied complete jobs (33 and 374 respectively).
Code metrics adds 90 isolated timed comparisons and 73 varied complete jobs.
Current coverage totals 1,800 timed native comparison invocations across all twenty
original applications. Its preliminary overlapping run is excluded from this total. Raw observations are in the
linked evidence directories. Historical validation below
belongs to earlier batches.

## Resolver: accepted exception

A separate oracle-checked Callgrind run, before the record-view optimization,
recorded approximately **1.27 billion instructions** in generated code versus
**152 million** in handwritten Rust. Inclusive constraint construction accounted
for about **68%** of generated instructions; version parsing accounted for about
11%. Allocation/freeing and JSON/string copies dominate the constraint path.
These are instruction counts, not wall-time percentages; inclusive costs overlap.
A fresh profile after the record-view work but before parser caching records
703 million generated instructions: constraint construction accounts for 48.74%
and version parsing for 19.82% inclusively. The caching pass addresses part of the
latter, while the larger constraint representation cost remains.

The native resolver parses requirements into typed structures once and borrows
those structures while constructing branch constraints. It uses the same DFS
order, budgets, tie-breaking and retained conflict descriptions. A lower native
state count or omitted reports would be an unfair baseline, and the comparison
requires identical complete file contents.

The implemented local record views reduce intermediate copying, but returned
constraint collections still use owned JSON objects. This diagnosis is retained
for reference, but further resolver-specific optimization is out of scope under
the user’s revised instruction accepting the 2.39× result.

## Measurement and validation

Use the same host and bounded workload definitions as the
[20-application assessment](CORPUS_SPEED_20.md). Complete optimized executables
include startup, computation, output serialization and durable publication.
Compilation, fixture creation and independent oracle checks are untimed.
Each timed run has freshly generated identical inputs and a new output directory.
Rust processes run without Python on their executable search path.

The native comparison rotates old-generated, current-generated and handwritten
executables, checking every run against the existing independent application
oracle and requiring identical input and final file hashes. Source hashes must
match between the old and new generated applications. Small workloads often have
an I/O/startup floor, so ratios should not be read as isolated kernel speedups.

The [handwritten sources](../benchmarks/corpus_speed_20/native/README.md) document
supported modes. These are complete implementations of the measured jobs, not
production replacements for every application mode. They share the pinned
low-level JSON formatting, date parsing, hashing and filesystem primitives with
the generated applications. Durable publication retains per-file and directory
synchronization. Fault-injection/pause controls are not implemented in the native
benchmarks and are not part of the measured workload.

The memory changes passed 27 targeted regression cases. The final byte-loop and
inlining changes additionally passed 28 bitwise, bytearray and integer-view
cases. The first five handwritten implementations also passed 11 varied jobs beyond the
timing fixtures: empty/single/multiple-symbol compression; resolved and bounded
search; Unicode/CRLF/LCS ties; 16 reference circuits; and eight reference telemetry
series including cancellation, gaps and timestamp offsets.

The pre-parser-cache 20-application sweep passed all 40 size cases, with five repetitions
for each of Python and generated Rust (400 timed invocations). The pre-parser-cache native
comparisons passed their output checks for all 990 timed invocations across eleven
applications, two sizes and three executables, collected in four batches. These correctness checks do not
imply that the global performance gate passed.

The first seven handwritten baselines passed 27 varied jobs: the original
11 jobs plus eight access-log preview/write cases and eight regex-rewrite preview
cases. These cover empty inputs, UTC filtering, Unicode, malformed-line reasons,
ranking ties, literal and empty replacements, Python regex anchors, invalid
patterns, and preservation of input contents and metadata.

Population and WAV add 36 complete jobs (63 across nine baselines). These include
closed-form Decimal references, RK4 refinement, zero/constant/equilibrium cases,
Unicode/escaped SVG, alternate RIFF layouts, archive replay and all 65,536 signed16
values under five gain settings. The compiler was unchanged for this extension;
all twenty build/source/binary fingerprints and all nine native source/binary
fingerprints were checked, so the previous twenty-application sweep still applies.

PNG and terminal dashboard add 227 complete jobs (290 across eleven baselines).
PNG checks include exact metadata errors, CRC and ordering diagnostics, replay
and every proper prefix of a minimal image. Terminal checks include 69 static/
Unicode/replay jobs plus six real PTY processes and four replay jobs: resizing,
sequence conflicts, invalid/missing snapshots, plain fallbacks and SIGINT/SIGTERM
cleanup. All twenty generated and eleven native fingerprints were rechecked at that milestone.
Those additions changed benchmark coverage, not the compiler.

The new capture-consumer and string-concatenation tests exercise typed/legacy
frontends with optimization enabled and disabled. Capture tests retain full
results when callers inspect spans, escape the object or reassign it, and check
Unicode offsets, optional groups, no match, empty matches and validation limits.
The complete existing capture-vector tests also passed. A final 11-test run
covering runtime costs, committed ownership diagnostics, typed string effects,
regex anchors and Unicode regex behavior passed. All twenty measured compiler
and application fingerprints were checked against the sources at that milestone.

The earlier round-one equivalence audit applies only to its saved measurements.
Round two rebuilt all twenty applications with its recorded compiler fingerprint;
its measurements do not rely on that earlier audit.

## Reproduce and enforce the target

After the normal development setup, release-build the selected programs:

```sh
PYTHONPATH="$PWD" python tools/assess_corpus_speed.py --phase build \
  --output "$HOME/.cache/py2rust-build/native-target-generated"
```

Then compare the currently implemented native references:

```sh
PYTHONPATH="$PWD" python tools/compare_corpus_native.py \
  --generated "$HOME/.cache/py2rust-build/native-target-generated" \
  --output "$HOME/.cache/py2rust-build/native-target-comparison-new" \
  --ids 068 071 077 078 079 080 095 096 100 104 105 109 110 111 112 113 114 115 117 118 \
  --repeats 15 --check-target --exempt-from-target 096
```

`--check-target` exits unsuccessfully if any non-exempt measured ratio is 2.00
or higher. `--exempt-from-target 096` explicitly records the accepted resolver
exception. Its actual ratio and strict `target_met` flag remain visible; output
correctness checks are never exempted.
Omitting `--ids` requests all twenty original applications. Missing handwritten
baselines fail explicitly; the tool
never silently skips missing cases.
Output directories must be new. The comparison saves source, executable hashes,
raw wall/CPU/RSS observations, and separate copies of the timed executables.

For a true before/after comparison add `--before /absolute/path/to/preserved/builds`.
Those builds must use unchanged application sources; compiler fingerprints may
differ. Do not use two builds of the same compiler as a before/after comparison.

Additional native correctness jobs:

```sh
PYTHONPATH="$PWD" python tools/check_corpus_native.py \
  --native "$HOME/.cache/py2rust-build/native-target-comparison-new" \
  --output "$HOME/.cache/py2rust-build/native-target-checks-new"
```

The original twenty comparisons meet the revised gate. All fixed ten additional
comparisons are complete: 22 workload cases, 660 timed invocations and 2,976
additional correctness jobs, summarized in [the follow-up evidence (local archive)](../benchmarks/REPORTS.md#local-archive) (`benchmarks/corpus_speed_10/summary.json`).
The completion audit checked current source/generated/binary fingerprints and
the original forty cases against their saved matched batches. This completes the
requested goal, not a claim that the seven new performance gaps have been fixed.
The resolver remains informational under the accepted exception.
