# Handwritten complete-job baselines

These are independent Rust implementations, not generated Rust with renamed
symbols. They use typed structures and borrowing where appropriate. Shared
library implementations of JSON validation/canonical formatting, date parsing,
hashing and no-replace rename are used equally by generated and native programs.
The build uses the same pinned dependencies and release settings.

Current implementations:

- `access_log.rs`: preview/write common-log analysis, UTC filtering, deterministic
  rankings, lossless malformed-line exports and full report bundles. Inputs in
  these comparisons are unaliased regular files; shared snapshot checks reject
  hard links, more strictly than the Python access-log application.
- `regex_rewrite.rs`: complete preview plans with rule grammar validation, ordered
  literal replacements, hashes, metadata and Unicode previews. Apply/restore
  modes are not implemented. It shares the runtime regex engine to preserve
  Python anchor semantics; planning and aggregation are handwritten. Like the
  access-log baseline, its snapshot helper rejects hard-linked inputs.
- `huffman.rs`: compression jobs, including container validation and codebook
  statistics. Decompression mode is not implemented.
- `circuits.rs`: solve/verify jobs with validated resistor trees, identical scaled
  compensated arithmetic and postorder audit steps.

- `resolver.rs`: resolve-mode dependency jobs; same DFS order, tie breaking,
  budgets and retained conflict explanations. Requirements and version triples
  are parsed once into typed structures. Verify-lock mode is not implemented.
- `telemetry.rs`: analyze/verify telemetry jobs; same compensated sums,
  population variance, count windows, gap boundaries and archive format.
- `text_diff.rs`: diff-mode jobs; same quadratic LCS, deletion-first ties,
  merged context intervals and exact line framing. Apply mode is not implemented.
- `population.rs`: simulate/verify population experiments with the same guarded
  RK4 stages, complete series, CSV, shared-scale SVG and replay archives.
- `wav.rs`: process/verify mono signed16 PCM, validated RIFF chunks, exact rational
  gain/rounding/clipping, full sample CSV, envelope SVG and normalized WAV.
- `terminal_dashboard.rs`: watch/replay task dashboards with Unicode grapheme
  layout, bounded refresh, terminal resize, invalid-snapshot recovery, plain
  output, SIGINT/SIGTERM cleanup and reusable frame archives.
- `png.rs`: inspect/verify PNG structure, chunk CRCs and selected metadata,
  including recoverable forensic errors and exact HTML/JSON/archive exports.
  Image data and compressed metadata remain explicitly uninspected, matching
  the Python application.
- `ppm.rs`: process/verify bounded P6 images with exact 8/16-bit samples, ordered
  crop/invert/channel-or-mean-threshold filters, full histograms/CSV, sampled SVG,
  original and filtered exports, and recomputed archive verification. Header/raster
  boundaries and pixel/filter budgets match the Python application.
- `bmp.rs`: build/verify BMP contact sheets from CORE/INFO/V4/V5 inputs, exact
  nearest-neighbor thumbnails, contain/stretch layouts, HTML and portable
  rebuild/retile/replay bundles. Color-management metadata is inspected without
  applying color transforms, matching the Python application.
- `zip.rs`: inspect/verify ZIP32 physical records, bounded stored/deflate payloads,
  CRCs, Unicode/portable-name diagnostics, overlap detection, budget accounting
  and source-preserving replay reports. Entries are never extracted to disk.
- `atlas.rs`: pack/verify first-fit shelf atlases, bounded P6 inputs, Unicode
  ordering, exact sampled SVG and actual pixel extraction, with reusable repacking
  and replay projects. Sprite dimensions and pixel budgets match the application.
- `automation.rs`: complete bounded language parsing and execution, checked i64
  arithmetic, lexical scopes, budgets, partial-error traces and flat AST/source
  coordinates. Shared snapshots reject hard-linked inputs more strictly than the
  Python application.
- `highlighter.rs`: bounded configuration tokenization, Unicode coordinates,
  diagnostics, escaped HTML in both themes and exact-source replay bundles.
  Static CSS and the number-validation regex library are shared with the
  application. Shared snapshots reject hard-linked inputs more strictly.
- `source_outline.rs`: typed scopes, definitions, cleaned docstrings, resolved
  import links and complete source-browser/replay exports over the shared native
  Python parser. Static CSS is shared; snapshot checks reject hard links more
  strictly than this Python application.
- `warehouse.rs`: simulate/verify byte grids with typed commands and compact undo
  records, full per-step snapshots, archive verification, continuation, rewind
  and restart requests, with identical bounds and publication semantics.
- `code_metrics.rs`: bounded source discovery, typed scoped metrics, physical
  spans and threshold flags, import classifications, escaped HTML and raw-source
  archives. Shares the native Python parser and static CSS; publication rechecks
  the inventory and input snapshots after staging.
- `route_planner.rs` (additional case 061): complete Bellman–Ford route batches,
  exact pass/relaxation counters, directed negative-cycle witnesses and closure
  diagnostics, using indexed vertices and borrowed edges. Results are recorded
  separately in `../../corpus_speed_10/route_planner/README.md`.
- `terrain_routes.rs` (additional case 065): stable A* with exact search counters,
  ASCII overlays, preview/write modes and complete checksummed input/route bundles.
- `cron_explorer.rs` (additional case 082): numeric grammar and exact diagnostics,
  bounded UTC day traversal, truncation proof and complete JSON/text/CSV/replay
  exports. Both 065 and 082 use stricter hard-link rejection than their Python
  applications; measured inputs are unaliased files.
- `scheduler.rs` (additional case 088): typed event simulation with exact phase,
  worker and FIFO ordering, deterministic rejection sampling, trace integrals and
  complete replay/report exports.
- `log_redactor.rs` (additional case 089): disjoint nested-field mutation, ordered
  literal/regex rules, exact audit/expansion accounting and sanitized exports with
  fixed phase-only diagnostics. The regex engine is shared.
- `json_patch.rs` (additional case 045): recursive deterministic diff, guarded
  edits on a private owned document, exact intermediate bounds, verified inverse
  patches and canonical exports. Input hard-link rejection is stricter than the
  Python application; timed inputs are unaliased.
- `lru_cache.rs` (additional case 051): owned cache values, indexed recency order,
  exact events/counters, checked integer increments and resumable checksummed
  snapshots. Input hard-link rejection is stricter than the Python application;
  timed inputs are unaliased.
- `autocomplete.rs` (additional case 055): an owned Unicode trie with cached counts,
  borrowed traversal, deterministic ranked suggestions, pruning and checksummed
  snapshot reconstruction. Input hard-link rejection is stricter than the Python
  application; timed inputs are unaliased.
- `csv_json.rs` (additional case 041): both schema-driven conversion directions,
  typed validation, exact rejected rows and ordered projections.
- `csv_join.rs` (additional case 044): borrowed composite-key indexes, stable
  ordering, duplicate multiplicities, expansion bounds and unmatched reports.
- `csv_codec.rs`: shared exact bounded CSV dialect for 041 and 044. Both applications
  use stricter hard-link rejection than their Python versions; timed inputs are
  unaliased.
- `common.rs`: bounded input snapshots, metadata revalidation, per-file sync,
  staging-directory sync, no-replace rename and parent-directory sync. It does
  not implement the corpus applications' fault-injection/pause controls.

The performance comparison covers the documented workloads and supported modes;
these baselines are not replacement production applications. No input sizes,
expected answers or fixture contents are embedded in the implementations.

`tools/compare_corpus_native.py` applies the existing independent correctness
oracle to both executables, additionally requiring identical input and final
file contents. It rotates fresh jobs after warm-up and excludes fixture
creation, compilation and output checking from timings. Missing baselines cause
an error. `--check-target` exits unsuccessfully if any requested case has a median
generated/native ratio of 2.00 or higher, except IDs explicitly listed with
`--exempt-from-target`. The user has accepted resolver 096 at its observed 2.39×;
its ratio and strict threshold result stay visible and all output checks still run. A selected subset does not establish
that the entire 20-application goal is met.

With `--before /path/to/preserved/generated-builds`, the same run additionally
checks and times the previous generated binaries. Rotation then includes all
three engines, avoiding comparisons made under separate machine load. The
application-source hashes must match; compiler hashes are intentionally allowed
to differ for the preserved before build.
