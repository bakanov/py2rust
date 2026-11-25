# Ten additional application comparisons

Raw report filenames below refer to [local archived reports](../REPORTS.md#local-archive),
not files shipped in this repository. Source programs and Markdown summaries remain in Git.

This selection is fixed before collecting its timings. It extends the original
20-case optimization set with different data structures and algorithms. It is a
follow-up comparison set, not a claim that the compiler handles arbitrary Python
or that these applications have already met a performance threshold.

| ID | Application | Additional coverage |
|---|---|---|
| 041 | CSV/JSON converter | Quoted CSV, Unicode, declared types and row rejection |
| 044 | CSV join | Composite keys, duplicate multiplicity and ordered output |
| 045 | JSON diff/patch | Recursive values, escaped paths, guarded edits and undo |
| 051 | LRU cache | Recency mutation, eviction, resizing and persistent state |
| 055 | Autocomplete | Unicode trie traversal, ranking, updates and pruning |
| 061 | Route planner | Weighted graph relaxation and negative-cycle diagnostics |
| 065 | Terrain routes | A* frontier, weighted grids and path reconstruction |
| 082 | Cron explorer | Calendar traversal, field sets and UTC schedule bounds |
| 088 | Scheduler simulator | Heap events, queues, tie ordering and conservation |
| 089 | Log redactor | Nested JSON fields, ordered regex/literal rules and counts |

All ten generated release executables built successfully (`generated-builds.json`).
All ten native comparisons are complete:

| Application | Small ratio | Large ratio |
|---|---:|---:|
| [041 CSV → JSON](csv_conversion/README.md) | 1.02× | 1.28× |
| [041 JSON → CSV](csv_conversion/README.md) | 1.03× | 1.46× |
| [044 CSV join](csv_join/README.md) | 1.05× | 1.12× |
| [045 JSON diff/patch](json_patch/README.md) | 1.15× | **2.49×** |
| [051 LRU cache](lru_cache/README.md) | 1.01× | **6.30×** |
| [055 Autocomplete](autocomplete/README.md) | 1.34× | **72.00×** |
| [061 Route planner](route_planner/README.md) | 1.05× | **23.52×** |
| [065 Terrain routes](terrain_cron/README.md) | 1.73× | **2.89×** |
| [082 Cron explorer](terrain_cron/README.md) | 1.03× | **2.003×** |
| [088 Scheduler simulator](scheduler_redactor/README.md) | 1.34× | **105.29×** |
| [089 Log redactor](scheduler_redactor/README.md) | 1.01× | 1.90× |

Seven large cases exceed the strict threshold, without accepted exceptions.
Cron is borderline; raw results retain its unrounded ratio. The scheduler is the
largest observed outlier; source inspection finds repeated whole-state and field
copies. No comparisons remain pending. Three applications (041, 044 and 089)
pass at all measured sizes; seven have a failing large case.

The [aggregate evidence (local archive)](../REPORTS.md#local-archive) (`benchmarks/corpus_speed_10/summary.json`) covers 22 cases, 660 timed invocations and
2,976 additional correctness jobs. Conversion includes both directions at each
size. All thirty generated compiler/application/source/binary fingerprints and
all thirty native source/binary fingerprints were audited against current files.
The original twenty gate passes with the resolver exception; this follow-up
comparison does not establish a universal 2× bound.

Workloads use two deterministic sizes
within each application's documented bounds, checked by its existing independent
oracle and by equal complete outputs from generated and handwritten Rust. Native
implementations must implement the selected complete jobs, with no fixture-specific
answers or code-generation substitutions. Use the same release flags and pinned
libraries, rotate execution order, and retain raw observations and fingerprints.

The original twenty remain separately identifiable in
`doc/NATIVE_PERFORMANCE_GOAL.md`; the accepted resolver exception applies only to
096. Results from these additional examples must be reported even if they are
above 2.00×. Selection must not change in response to observed timings.

## Reproduce

Build the fixed ten with `tools/assess_corpus_speed.py --phase build --ids
041 044 045 051 055 061 065 082 088 089 --output /absolute/new/generated`.
Then run:

```sh
PYTHONPATH="$PWD" python tools/compare_corpus_native.py \
  --generated /absolute/new/generated --output /absolute/new/comparison \
  --ids 041 044 045 051 055 061 065 082 088 089 --repeats 15
PYTHONPATH="$PWD" python tools/check_corpus_native.py \
  --native /absolute/new/comparison --output /absolute/new/checks \
  --ids 041 044 045 051 055 061 065 082 088 089
```

Run these sequentially using the repository development environment. The comparator
automatically covers both conversion directions for 041. Add `--check-target`
to enforce the strict threshold; it is expected to fail for the current follow-up
results. No resolver exemption applies to these ten applications.
