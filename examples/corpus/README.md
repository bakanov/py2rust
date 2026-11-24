# Complete-application verification corpus

The target is all **120 applications** in the [catalog](../../doc/example-program-catalog.md).
All 120 implementations are available. They passed acceptance before the package
rename; those historical results do not verify this migration. Regenerate
evidence with the commands below; compilation alone does not prove parity.

Every application module written in Python is transpiled into Rust. The native
executables use the shared Rust runtime and contain no Python interpreter,
CPython bindings, or embedded source evaluator. Applications use readable Python
source in several modules. Application 094 deliberately adds three small, declared
Rust adapters to exercise direct native imports; its validation, comparison and
reporting remain in six Python modules. Other applications retain the Python-only
source requirement. Python is needed for development/transpilation and reference
runs, not for running the resulting binaries. Builds and checks target Linux x86-64.

| ID | Application | Acceptance coverage |
| --- | --- | --- |
| [001](001_file_drop/main.py) | Binary file-drop HTTP service | Exact bytes, Unicode filenames, invalid input, persistence/restart, expiration, deletion, orphan recovery |
| [002](002_webhook_inbox/main.py) | Webhook inbox | Envelope validation, immutable receipts, deduplication, pagination/filtering, NDJSON export, bounds and restart |
| [003](003_bookmark_redirector/main.py) | Bookmark redirector | Exact Location headers, visit counters, Unicode search, editing/deletion, transactional import/export and restart |
| [004](004_expiring_pastes/main.py) | Expiring paste service | Unicode/CRLF preservation, separate private read/delete capabilities, public-only search, strict deadlines, storage bounds and sweep |
| [005](005_versioned_settings/main.py) | Versioned settings API | Schema validation, competing writers, stale/no-op updates, immutable history, exact rollback, corruption detection and restart |
| [006](006_mock_api/main.py) | Scenario-based mock HTTP API | Validated route definitions, field rules, state transitions, JSON/text/binary responses, transcript, reset and restart |
| [007](007_leased_queue/main.py) | Leased work queue | Priority/delay, queue isolation, exclusive claims, token fencing, expiry/requeue, idempotent acknowledgments, clock rollback and restart |
| [008](008_reservations/main.py) | Resource reservation service | Half-open intervals, UTC normalization, conflict/cancellation, competing bookings, sorted agenda, persistence and an independent interval oracle |
| [009](009_rate_limiter/main.py) | Weighted rate limiter | Exact rolling windows, per-key isolation, idempotent requests, fractional Retry-After, capacity, clock rollback and an independent admission oracle |
| [010](010_notification_board/main.py) | Server-sent-event notification board | Live delivery, Last-Event-ID replay, durable IDs, explicit retention gaps, heartbeats, stalled readers, connection capacity and disconnect cleanup |
| [011](011_health_monitor/main.py) | Service health monitor | Failure/recovery thresholds, outage durations, network-error isolation, measured latency, retained history, clock rollback and partial checkpoints |
| [012](012_json_harvester/main.py) | Paginated JSON harvester | Whole-page checkpoints, restart/resume, duplicate/conflicting records, cursor loops, origin restrictions, budgets, malformed responses and interruption boundaries |
| [013](013_resumable_download/main.py) | Resumable file downloader | Verified byte ranges, strong ETags, SHA-256, five interruption boundaries, corrupt prefixes, safe publication and a 192 MiB download under a 128 MiB address-space limit |
| [014](014_contract_runner/main.py) | HTTP contract runner | Named status/JSON/field/snapshot failures, disconnected requests, body limits, continued execution, CI exit status, JSON/text reports |
| [015](015_delivery_outbox/main.py) | Webhook delivery outbox | Idempotency headers, atomic imports/checkpoints, disconnects, retry schedules, dead letters, report path protection and crash recovery |
| [016](016_link_auditor/main.py) | Local website link auditor | HTML5 parsing, relative links and base URLs, assets, URL deduplication, redirect loops and shortest depth, broken-link sources, crawl budgets and excluded origins |
| [017](017_change_watcher/main.py) | JSON endpoint change watcher | Recursive add/remove/replace reports, ignored subtrees, null versus missing, strict scalar comparisons, retained event IDs, continued polling after failures, restart and checkpoint interruption |
| [018](018_quota_batcher/main.py) | Quota-aware API batcher | Numeric and HTTP-date Retry-After, shared quota gates, completed-ID deduplication, JSON results, retry exhaustion, malformed headers, truncated bodies and three interruption boundaries |
| [019](019_circuit_gateway/main.py) | Circuit-breaker gateway | Closed/open/half-open transitions, consecutive failure thresholds, successful recovery probes, exact binary forwarding, repeated query fields, competing probes, bounded history, fault boundaries and real process termination |
| [020](020_load_probe/main.py) | Bounded HTTP load probe | Measured worker limits, active-request drain on cancellation, unsent-request accounting, schedules, lateness, deadlines, response digests, independent histograms/percentiles and CSV |
| [021](021_tcp_broker/main.py) | Framed TCP task broker and batch client | Fragmented/coalesced frames, UTF-8, EOF/half-close, durable submissions/acknowledgments, deduplication, bounded pagination, deadlines, six interruption boundaries, corruption, graceful stop and client reconnection |
| [022](022_room_chat/main.py) | Line-based room chat | Multiple peers and rooms, ordered Unicode broadcasts, nicknames, fragmented/coalesced commands, partial writes, real slow-reader eviction, byte/line queue bounds, room/peer limits, deadlines and disconnect cleanup |
| [023](023_smtp_capture/main.py) | Local SMTP capture server | Independent SMTP delivery, MIME attachments, 8-bit bodies, dot stuffing, strict CRLF, envelope/state validation, limits, absolute deadlines, exact durable bytes, four publication interruption points, corruption and restart |
| [024](024_resp_store/main.py) | RESP key-value server | redis-py interoperability, binary keys/values, nulls, ordered pipelines, concurrent increments, integer overflow, exact expiration boundaries, restart/clock rollback, nested-frame limits, slow-reader eviction and snapshot interruption recovery |
| [025](025_udp_directory/main.py) | UDP service directory and retrying client | Source addresses, sequence ordering, duplicate leases, expiration/tombstones, clock rollback, bounded discovery pages, malformed/truncated packets, reply correlation, lost acknowledgements and retry exhaustion |
| [026](026_dns_diagnostic/main.py) | DNS lookup diagnostic | A/AAAA, all record sections, compressed CNAME chains, arbitrary escaped wire labels, exact name bounds, 32 malformed-packet cases, source/ID/question matching, truncation, finite retries and checkpoints after process termination |
| [027](027_websocket_rooms/main.py) | WebSocket room server | Independent client, Unicode/empty text, 64-bit frame lengths, fragmentation, room isolation, ping/pong/close, malformed HTTP/frames, absolute deadlines, one-byte writes, real slow-reader eviction and graceful shutdown |
| [028](028_mqtt_sink/main.py) | MQTT telemetry sink | Paho publishing, Unicode topics, binary/empty payloads, retained values, bounded durable history, strict framing, client takeover, keep-alives, concurrent peers, buffered EOF, queue limits, corruption and interrupted checkpoints |
| [029](029_tcp_transfer/main.py) | Chunked TCP file transfer | Complete sender/receiver, durable chunk acknowledgements, lost replies and bounded retries, verified resume prefixes, corrupt chunks, changed sources, safe publication, five interruption boundaries and a 160 MiB transfer under 128 MiB per process |
| [030](030_unix_bus/main.py) | Unix-domain command bus and batch client | Correlated replies, concurrent clients, duplicate IDs, receipt eviction, pipelined frames, EOF draining, malformed inputs, backpressure, deadlines, graceful shutdown and stale-socket recovery |
| [031](031_inventory/main.py) | Directory inventory reporter | Independent metadata/tree oracle, exclusions, hard links, sparse files, symlink cycles, unreadable directories, empty directories, exact timestamps, traversal/report limits and 2,000-file scaling |
| [032](032_rename_planner/main.py) | Batch rename planner | Approved plans, regex rules, collisions, swaps, file/directory/symlink moves, guarded reversal, 50 interruption boundaries, real I/O failures, process termination and root-wide locks |
| [033](033_duplicate_finder/main.py) | Duplicate-file finder | Size pruning, streamed SHA-256, byte confirmation, deliberate digest-prefix collisions, hard-link accounting, guarded review plans, changing files, partial scans and bounded-memory scaling |
| [034](034_snapshot_backup/main.py) | Incremental snapshot backup | Shared content objects, complete version manifests, historical restore, hard links/symlinks, metadata, retention, corruption, killed processes and streamed copies under a memory limit |
| [035](035_sync_planner/main.py) | Two-tree synchronization planner | Three-way baselines, 125 state combinations, preserved conflicts/exclusions, ordered copy/remove operations, independent execution, dry-run idempotence and bounded-memory scanning |
| [036](036_artifact_store/main.py) | Content-addressed artifact store | Shared blobs, canonical manifest graphs, guarded named roots, exact retrieval, reachability collection, corruption/interruption recovery, capacity bounds and mixed-engine storage |
| [037](037_text_normalizer/main.py) | Batch text normalizer | Preview, LF/CRLF, trailing whitespace, final-newline policy, exact backups, idempotence, restore conflicts, per-file failures and path validation |
| [038](038_config_merger/main.py) | Layered configuration merger | Recursive precedence, per-node provenance, exact type-conflict paths, explicit type changes, 60 generated overlays, protected inputs, interrupted publication and bounded-memory scaling |
| [039](039_download_organizer/main.py) | Download-folder organizer | UTC date/extension classification, independent collision oracle, reviewed plans, durable move journals, interrupted directory/move recovery, hard links, real I/O failures and 1,000-file scaling |
| [040](040_fixture_tree/main.py) | Fixture-tree scaffolder | Exact text/binary payloads, implicit and reused directories, collision rejection, ownership receipts, interrupted creation/cleanup, real permission failures and bounded-memory limits |
| [041](041_csv_json/main.py) | CSV/JSON converter | Independent CSV oracle, quoted/newline/Unicode round trips, declared types, projection, lossless rejection reports, atomic result bundles, interruption/permission failures and bounded-memory limits |
| [042](042_record_cleaner/main.py) | Schema-driven record cleaner | Strings, regexes, strict types, UTC timestamps, defaults, bounds, choices, unknown-field policies and lossless accepted/rejected partitioning |
| [043](043_jsonl_transform/main.py) | Streaming JSONL transformer | Bounded line chunks, object filtering/projection, verbatim quarantine, durable prefix checkpoints, interrupted/cancelled batch recovery, corruption rejection and streams larger than process memory |
| [044](044_csv_join/main.py) | CSV join utility | Inner/left composite-key hash joins, duplicate multiplicities, ordered projection, complete unmatched-row reports, interrupted atomic publication, capacity limits and mixed conversion pipelines |
| [045](045_json_patch/main.py) | Nested JSON diff and patch | Exact-value recursive differences, escaped paths, old-value and whole-document guards, functional application, undo patches, atomic bundles, capacity/fault checks and mixed-engine round trips |
| [046](046_event_log/main.py) | Event-log consistency checker | Exact record locations, duplicate IDs/sequences, temporal high-water marks, observed state chains, final missing ranges, malformed rows, atomic diagnostic bundles and mixed filtering pipelines |
| [047](047_config_migrator/main.py) | Versioned configuration migrator | Validated migrations, structural preview, exact backups, four interruption boundaries, guarded rollback and conflict detection |
| [048](048_contact_import/main.py) | Contact import deduplicator | Unicode normalization, composite matching, transitive groups, complete provenance, explicit field/identity conflicts, exact repeat imports, atomic bundles, capacity/fault checks and mixed-engine books |
| [049](049_json_query/main.py) | JSON query console | Boolean filters, escaped paths, projections, stable multi-field ordering, exact scalar comparisons, grouped counts/sums, source diagnostics, atomic saved results and mixed CSV pipelines |
| [050](050_jsonl_partition/main.py) | JSONL partition writer | UTC date/topic grouping, duplicate preservation, row order, exact manifests and checksums, deterministic shards, interruption recovery, capacity limits and mixed-engine repartitioning |
| [051](051_lru_cache/main.py) | LRU cache workbench | Logical-clock eviction oracle, overwrites, zero capacity, peeks, resizing, hit rates, exact save/restore, split traces, accounting validation and mixed-engine snapshots |
| [052](052_ttl_notebook/main.py) | TTL key-value notebook | HTTP JSON values, replacement deadlines, exact expiry, prefix search, durable clock rollback protection, bounded snapshots, concurrent clients and mixed-engine recovery |
| [053](053_priority_queue/main.py) | Persistent priority work queue | Stable priority ties, queued/running transitions, cancellation, retries, ID reuse, heap reconstruction, exact split replay and mixed-engine snapshots |
| [054](054_document_search/main.py) | Small document search engine | Unicode tokenization, weighted inverted index, updates/deletion, nested AND/OR search, ranking/pagination, brute-force equivalence and mixed-engine snapshots |
| [055](055_autocomplete/main.py) | Prefix autocomplete index | Recursive Unicode trie, normalized replacements, usage counters, ranked suggestions, branch pruning, dictionary export and mixed-engine snapshots |
| [056](056_bloom_gate/main.py) | Bloom-filter ingestion gate | Sized bytearray filter, exact audit set, measured false positives, capacity decisions, raw bit export, corruption rejection and mixed-engine snapshots |
| [057](057_external_sort/main.py) | External record sorter | Stable keyed runs, checksummed heap merges, interrupted-work recovery, atomic publication and larger-than-memory sorting |
| [058](058_ring_recorder/main.py) | Time-series ring-buffer recorder | Circular wraparound, inclusive retention and interval queries, compensated summaries, snapshot validation and mixed-engine restarts |
| [059](059_interval_browser/main.py) | Interval-indexed log browser | Balanced interval tree, overlap/point queries, Unicode text filters, updates/deletion, subtree pruning and mixed-engine snapshots |
| [060](060_mini_database/main.py) | Append-only miniature database | Checksummed committed frames, exact byte replay, incomplete-tail recovery, snapshot compaction, process-kill durability and shared Python/Rust databases |
| [061](061_route_planner/main.py) | Weighted route planner | Bellman–Ford, node/edge closures, finite routes, reachability explanations and directed negative-cycle witnesses, checked by an exhaustive oracle |
| [062](062_build_planner/main.py) | Dependency build planner | Prerequisite closure, minimal deterministic layers, directed cycle witnesses, exhaustive tiny graphs, canonical exports and mixed-engine replanning |
| [063](063_shift_scheduler/main.py) | Small shift scheduler | Availability, skills, rest and workload constraints; scored backtracking; explicit search-limit status; exhaustive optima and mixed-engine replanning |
| [064](064_parcel_planner/main.py) | Parcel packing planner | Weight/volume/count limits, finite inventory, destination and dedicated packages, deterministic first-fit decisions, explicit rejections and mixed-engine manifests |
| [065](065_terrain_routes/main.py) | Terrain route visualizer | Weighted A*, zero-cost terrain, independent optimal-cost checks, deterministic ASCII paths, search statistics and mixed-engine exported grids |
| [066](066_dependency_impact/main.py) | Dependency impact auditor | Reverse dependencies, strongly connected groups, exact affected sets, deterministic shortest explanations and mixed-engine graph exports |
| [067](067_phrase_auditor/main.py) | Repeated-phrase document auditor | Unicode token normalization, original offsets, n-gram indexing, merged passages, unique token coverage and mixed-engine document exports |
| [068](068_huffman/main.py) | Huffman file compressor | Canonical codebooks, bit packing, checked binary containers, exact round trips, malformed prefix codes and mixed-engine compression |
| [069](069_timetable/main.py) | Timetable journey planner | Earliest arrivals, station transfer times, overnight services, exact boarding boundaries, independent temporal search and mixed-engine replanning |
| [070](070_sudoku/main.py) | Sudoku batch-solving tool | Duplicate diagnostics, unique/multiple/unsatisfiable results, counted search budgets, independent completion oracles and mixed-engine exports |
| [071](071_access_log/main.py) | Access-log analyzer | Numbered regex fields, UTC windows, literal path rankings, malformed-byte diagnostics, exact aggregates and mixed-engine source exports |
| [072](072_static_site/main.py) | Small static-site builder | Recursive inline formatting, escaped HTML, unique Unicode heading IDs, validated page links, complete atomic sites and mixed-engine Markdown rebuilds |
| [073](073_template_renderer/main.py) | Template rendering engine | Escaped values, lexical loop scopes, validated includes, bounded rendering, located errors and atomic project rebuilds |
| [074](074_expression_calculator/main.py) | Expression calculator with variables | Checked arithmetic, precedence, recoverable line errors, persistent variables and reproducible mixed-engine session replay |
| [075](075_ini_editor/main.py) | INI-style configuration editor | Quoted strings, retained comments, transactional edits, scoped expansion, cycle diagnostics and atomic mixed-engine replay |
| [076](076_command_shell/main.py) | Minimal command shell | Quoted argv, concurrent native pipelines, complete environments, binary captures, status policies, deadlines and interrupt cleanup |
| [077](077_source_outline/main.py) | Python source-outline browser | Native parser, nested scopes, docstrings, decorators, relative imports, linked source pages and portable project snapshots |
| [078](078_regex_rewrite/main.py) | Regex batch rewrite tool | Whole-batch preview, literal replacements, per-rule audits, exact backups, guarded restoration and mixed-engine recovery |
| [079](079_automation_language/main.py) | Tiny automation-language interpreter | Recursive AST, lexical scopes, checked integers, exact step limits, source diagnostics and portable execution replays |
| [080](080_syntax_highlighter/main.py) | Stateful syntax-highlighting exporter | Exact token fixtures and coordinates, nested comments, escaped HTML, both themes, diagnostics, preserved source and portable replay |
| [081](081_reminder_daemon/main.py) | Recurring reminder daemon | Three missed-run policies, durable clock rollback protection, bounded catch-up, restart, crash boundaries, writer locks and real polling |
| [082](082_cron_explorer/main.py) | Cron schedule explorer | Numeric field sets, UTC calendar search, cron day matching, leap centuries, exact diagnostics, truncation proof and portable schedule exports |
| [083](083_activity_timer/main.py) | HTTP activity timer journal | Start/pause/resume/stop, exact interval totals, monotonic/wall clocks, persisted restarts, concurrency, crash recovery and grouped JSON exports |
| [084](084_log_router/main.py) | Rotating log router | Multiple inputs, severity/substring filters, JSONL segments, saved positions, input rotation and crash-safe append recovery |
| [085](085_deadline_inspector/main.py) | Job deadline inspector | Exact grace cutoffs, UTC offsets, duplicate/future events, microsecond lateness, reports and cross-runtime replay |
| [086](086_timezone_converter/main.py) | Named-timezone appointment converter | Explicit fold/gap policies, historical offsets, portable TZif replay, exact boundaries, resource limits and atomic publication |
| [087](087_directory_watcher/main.py) | Debounced directory watcher | Stable hashed snapshots, quiet windows, rename cycles, durable pending events, cancellation and cross-runtime checkpoint resume |
| [088](088_scheduler_simulator/main.py) | Discrete-event scheduler simulator | Seeded workloads, heap events, FIFO queues, deadline ties, exact statistics, conservation and portable replay |
| [089](089_log_redactor/main.py) | Structured-log redactor | Ordered literal/regex masking, nested field paths, exact counts, unique JSON keys, secret-free diagnostics and atomic sanitized bundles |
| [090](090_batch_worker/main.py) | Checkpointed batch worker | Atomic progress/results, killed-process resume, portable checkpoints, deterministic reports, cancellation and competing workers |
| [091](091_process_runner/main.py) | Process-based test runner | Native command outcomes, exact/regex output assertions, retained failure captures, deadlines, process-group cleanup and atomic reports |
| [092](092_build_executor/main.py) | Incremental build executor | Content-based freshness, exact command invocation oracle, dependency invalidation, staged artifacts, durable cache recovery and mixed-engine reuse |
| [093](093_process_supervisor/main.py) | Local process supervisor | Concurrent native services, measured retry backoff, bounded binary logs, live status, signal/deadline shutdown and complete owned-group cleanup |
| [094](094_rust_imports/main.py) | Rust-import validation workbench | Direct native imports, checked integer conversions, Unicode/binary tuples, nested finite values, Result recovery and replayable inspection reports |
| [095](095_code_metrics/main.py) | Project code-metrics browser | Automatic module discovery, exact scope metrics and spans, import links, oversized-function flags, escaped HTML and source snapshots |
| [096](096_package_resolver/main.py) | Local package constraint resolver | Bounded version ranges, deterministic backtracking, reproducible conflicts, dependency lock verification and portable replay bundles |
| [097](097_source_headers/main.py) | Source-header checker | Exact file/line findings, configurable header/year policy, preserved BOMs and preambles, hash-bound edits, corrected copies and idempotent rechecks |
| [098](098_transfer_bench/main.py) | Transfer benchmark | Native child workers, exact TCP payloads, fragmented frames, bounded deadlines, independent timing summaries, report comparison and replay |
| [099](099_environment_validator/main.py) | Environment configuration validator | Typed JSON scalars, defaults, enums, exact numeric bounds, prerequisite cascades, redacted reports and external-schema rechecks |
| [100](100_text_patch/main.py) | Text diff and patch | Canonical LCS context hunks, exact Unicode/newline preservation, stale and altered patch rejection, corrected copies and zero-diff rechecks |
| [101](101_expense_allocator/main.py) | Shared-expense allocator | Exact weighted cent splits and refunds, deterministic remainder ties, persistent imports, replay, settlements and conservation invariants |
| [102](102_inventory_ledger/main.py) | Inventory reservation ledger | Atomic multi-item stock changes, reservation invariants, idempotent accepted IDs, hash-chain replay, locked persistence and crash recovery |
| [103](103_unit_converter/main.py) | Dimensional unit converter | Compound unit parsing, exact-factor oracle, dimension compatibility, affine temperature conversion, round trips and portable notebooks |
| [104](104_circuit_calculator/main.py) | Series/parallel circuit calculator | Recursive resistor trees, exact-rational reductions, open/short rules, extreme ratios, diagnostic recovery and portable replay |
| [105](105_telemetry_analyzer/main.py) | Telemetry trend analyzer | Exact timestamp gaps, preceding-window outliers, centered population variance, constant/empty data, high-precision oracle and portable replay |
| [106](106_tariff_simulator/main.py) | Electricity-tariff simulator | Exact rational interval allocation, UTC bands, cumulative tiers, half-even totals, partition invariance and portable replay |
| [107](107_recipe_scaler/main.py) | Recipe and shopping-list scaler | Exact fractional portions, compatible unit conversion, Unicode grouping, reusable scaled recipes, weekly plans and portable replay |
| [108](108_tournament_standings/main.py) | Tournament standings manager | Registered teams, validated fixtures, explicit sporting ties, edited results, independent standings oracle and portable replay |
| [109](109_warehouse_simulator/main.py) | Warehouse movement simulator | Mutable grids, single-box pushes, blocked moves, compact undo records, independent step oracle, reusable continuation and full rewind |
| [110](110_population_simulator/main.py) | Population simulation runner | Fixed-step RK4, exponential/logistic growth, Decimal analytic oracles, timestep refinement, CSV/SVG exports and portable edited experiments |
| [111](111_png_inspector/main.py) | PNG structure inspector | Exact chunk provenance, CRC-32, bounded metadata, forensic diagnostics, every-prefix truncation, escaped HTML and portable binary replay |
| [112](112_wav_analyzer/main.py) | Mono PCM WAV analyzer and normalizer | RIFF framing, exact gain/rounding/clipping, exhaustive signed16 samples, statistics, CSV/SVG and portable audio replay |
| [113](113_bmp_thumbnails/main.py) | BMP thumbnail/contact-sheet maker | Four DIB layouts, row orientation/padding, exact pixel oracle, edited layouts, reusable thumbnails and portable binary replay |
| [114](114_ppm_filters/main.py) | P6 image-filter pipeline | 8/16-bit samples, exact crop/invert/threshold, full histograms, binary boundaries, SVG and portable pipeline replay |
| [115](115_sprite_atlas/main.py) | PPM sprite-atlas packer | Deterministic shelves, padding/non-overlap, exact extraction, Unicode key sorting, edited layouts and portable atlas replay |
| [116](116_svg_dashboard/main.py) | SVG metrics dashboard | Bounded linear scales, exact decimal ticks, bar/line geometry, escaped standalone HTML/SVG, edited layouts and portable replay |
| [117](117_terminal_dashboard/main.py) | Terminal task dashboard | Live PTY resizing, Unicode grapheme clipping, snapshot recovery, signal cleanup, plain fallback and portable replay |
| [118](118_zip_validator/main.py) | ZIP manifest validator | Stored/DEFLATE entries, CRCs, safe-name diagnostics, bounded expansion, descriptor ambiguity, exact binary replay and atomic reports |
| [119](119_gzip_archiver/main.py) | Gzip log archiver | Streaming compression, durable pending transactions, exact-byte verification, source rotation, crash recovery and portable indices |
| [120](120_traffic_replayer/main.py) | Binary traffic-fixture replayer | Strict binary framing, immutable snapshots, scheduled local TCP replay, fragmented replies, record/byte diagnostics, absolute deadlines and portable inspection reports |

## Reproduce the evidence

From the repository root, with the development environment installed:

```bash
python -m pip install -e '.[service-reference,corpus-checks]'
python tools/corpus.py {001..120}
python tools/check_webhook_pair.py
python tools/check_http_clients.py
python tools/check_gateway_stack.py
python tools/check_tcp_broker.py
python tools/check_udp_directory.py
python tools/check_tcp_transfer.py
python tools/check_unix_bus.py
python tools/check_artifact_store.py
python tools/check_download_organizer.py
python tools/check_fixture_tree.py
python tools/check_csv_json.py
python tools/check_jsonl_transform.py
python tools/check_csv_join.py
python tools/check_json_patch.py
python tools/check_event_log.py
python tools/check_contact_import.py
python tools/check_json_query.py
python tools/check_jsonl_partition.py
python tools/check_lru_cache.py
python tools/check_ttl_notebook.py
python tools/check_priority_queue.py
python tools/check_document_search.py
python tools/check_autocomplete.py
python tools/check_bloom_gate.py
python tools/check_external_sort.py
python tools/check_ring_recorder.py
python tools/check_interval_browser.py
python tools/check_mini_database.py
python tools/check_build_planner.py
python tools/check_shift_scheduler.py
python tools/check_parcel_planner.py
python tools/check_terrain_routes.py
python tools/check_dependency_impact.py
python tools/check_phrase_auditor.py
python tools/check_huffman.py
python tools/check_timetable.py
python tools/check_sudoku.py
python tools/check_access_log.py
python tools/check_static_site.py
python tools/check_template_renderer.py
python tools/check_calculator.py
python tools/check_ini_editor.py
python tools/check_command_shell.py
python tools/check_source_outline.py
python tools/check_regex_rewrite.py
python tools/check_automation_language.py
python tools/check_syntax_highlighter.py
python tools/check_reminder_daemon.py
python tools/check_cron_explorer.py
python tools/check_activity_timer.py
python tools/check_log_router.py
python tools/check_deadline_inspector.py
python tools/check_timezone_converter.py
python tools/check_directory_watcher.py
python tools/check_scheduler_simulator.py
python tools/check_log_redactor.py
python tools/check_batch_worker.py
python tools/check_process_runner.py
python tools/check_build_executor.py
python tools/check_process_supervisor.py
python tools/check_rust_imports.py
python tools/check_code_metrics.py
python tools/check_package_resolver.py
python tools/check_source_headers.py
python tools/check_transfer_bench.py
python tools/check_environment_validator.py
python tools/check_text_patch.py
python tools/check_inventory_ledger.py
python tools/check_unit_converter.py
python tools/check_circuit_calculator.py
python tools/check_telemetry_analyzer.py
python tools/check_bmp_thumbnails.py
python tools/check_png_inspector.py
python tools/check_population_simulator.py
python tools/check_ppm_filters.py
python tools/check_recipe_scaler.py
python tools/check_sprite_atlas.py
python tools/check_svg_dashboard.py
python tools/check_tariff_simulator.py
python tools/check_terminal_dashboard.py
python tools/check_tournament_standings.py
python tools/check_warehouse_simulator.py
python tools/check_wav_analyzer.py
python tools/check_zip_validator.py
python tools/check_gzip_archiver.py
python tools/check_traffic_replayer.py
python tools/corpus.py --status
```

Tests use disposable directories and ephemeral loopback ports; socket permission
is required. Cargo builds with the locked dependencies and `--offline` using a
shared dependency cache. If dependencies are not present, first fetch them with
`cargo fetch --locked --manifest-path py2rust/compiler/service_runtime/Cargo.toml`.
The command-shell checks build native child fixtures with a C compiler (`cc`);
Python reference execution of that application requires Python 3.11+.
The downloader and TCP transfer memory checks use Linux `prlimit`; their fixtures
need about 400 MiB and 640 MiB of disk space respectively across both engines.

For every selected program the verifier:

1. Measures 200–500 substantive Python source lines across the application,
   excluding blank lines, comments, docstrings, tests, assets and generated code.
   A multiline string literal counts once rather than inflating the measurement.
2. Transpiles every Python application module. Handwritten Rust is rejected except
   for 094's exact three declared native fixtures, which are independently hashed
   and checked against the linked module inventory.
3. Compiles a uniquely named native executable, preserving source maps and
   formatted generated Rust.
4. Runs independent acceptance assertions against both CPython and native Rust,
   including malformed inputs and persistence where applicable. For 094, CPython
   uses explicit test-only adapter shims outside the application source tree; the
   Rust executable links the actual `.rs` files.
5. Runs the native process with `PATH`, `PYTHONHOME`, and `PYTHONPATH` set to
   `/nonexistent`, then compares the observable results.

Evidence lives in `build/corpus/<id>/result.json`; generated sources are in
`build/corpus/<id>/rust/src/main.rs`; binaries are `build/corpus/<id>/corpus_<id>`.
Build and process logs are retained alongside them. `build/corpus/status.json`
tracks every catalog ID. Evidence becomes **stale** after changes to source,
compiler/runtime, fixture assets, the selected manifest record, or its acceptance
checker and statically imported local helpers. Package initializers and transitive
helper imports are included, along with shared compiler/reference/runtime sources,
Cargo locks, the runner and project dependency metadata. Unrelated catalog records
or checker files do not invalidate this application's evidence. Checkers use
static imports so their local dependency graph is explicit; importlib/dynamic
imports are rejected. New shared changes still invalidate every affected result.

Running `tools/corpus.py` without IDs requires **all 120** to pass and returns
nonzero while any implementation is missing. A selected passing batch never
marks the full catalog complete. The tests and runner are development tools;
their Python is not part of any generated application.

## Run the native applications

After verification, these commands run binaries directly:

```bash
DROP_DATA=/tmp/file-drop-data DROP_PORT=8766 build/corpus/001/corpus_001

MOCK_CONFIG="$PWD/examples/corpus/006_mock_api/routes.json" \
MOCK_STATE=/tmp/mock-state.json MOCK_PORT=8767 build/corpus/006/corpus_006

CONTRACT_CONFIG="$PWD/examples/corpus/014_contract_runner/contracts.json" \
CONTRACT_REPORT=/tmp/contract-report.json \
CONTRACT_TEXT_REPORT=/tmp/contract-report.txt \
CONTRACT_SNAPSHOTS=/tmp/contract-snapshots build/corpus/014/corpus_014
```

The sample contract suite exercises the running mock API. A failing suite exits
with status 1 and writes both reports. Snapshot replacement requires the explicit
`update_snapshots: true` configuration and passing status/field checks for that
case. All fixture configuration is validated before requests are sent.

The file-drop service accepts `POST /files?name=<basename>&ttl=<seconds>` with a
binary body, lists `GET /files`, serves `GET /files/<id>` and
`GET /metadata/<id>`, deletes `DELETE /files/<id>`, and expires files with
`POST /sweep`. A known expired ID returns 410; unknown or swept IDs return 404.
`DROP_MAX_BYTES` defaults to 1 MiB, `DROP_TTL` to one hour. `DROP_NOW` overrides
the clock for deterministic tests. The mock API exposes `GET /_mock/state`,
`GET /_mock/transcript`, and `POST /_mock/reset`; its transcript is bounded at
1,000 requests. Request field kinds are `string`, `number`, `bool`, `array`,
`object`, `null`, or `any`. Both servers bind only to loopback.

The normalizer reads a manifest selected by `NORMALIZE_CONFIG`, for example:

```json
{
  "root": "/tmp/my-text-files",
  "files": ["notes.txt", "subfolder/readme.txt"],
  "mode": "preview",
  "newline": "lf",
  "trim_trailing": true,
  "final_newline": "ensure",
  "max_bytes": 1048576,
  "backups": ".normalizer-backups"
}
```

Run `NORMALIZE_CONFIG=/path/to/manifest.json build/corpus/037/corpus_037`.
`NORMALIZE_REPORT` selects the report path. Modes are `preview`, `apply`, and
`restore`; newline policies are `lf`/`crlf` and `preserve`/`ensure`/`remove`.
Files must already exist, have valid UTF-8 without NUL, and use safe relative names.
Symlinked input paths are rejected. Empty files remain empty.

Applying saves byte-for-byte originals and normalized copies, then atomically
replaces each text file. Restoration refuses files changed since normalization.
Receipts and backups are retained; archive them or choose a fresh backup directory
before another apply. A batch is not a transaction across files: failures are
reported per file, and there is a crash window between replacement and recording
that file in the receipt. This program does not claim crash-atomic batch recovery.

The record cleaner takes `CLEAN_SCHEMA`, `CLEAN_INPUT`, and `CLEAN_OUTPUT` paths.
For example, after building it:

```bash
CLEAN_SCHEMA="$PWD/examples/corpus/042_record_cleaner/schema.json" \
CLEAN_INPUT="$PWD/examples/corpus/042_record_cleaner/records.json" \
CLEAN_OUTPUT=/tmp/cleaned.json build/corpus/042/corpus_042
```

Its JSON report retains input indices, accepted normalized records, and original
rejected records with field-level reasons. It exits 1 when records are rejected.
Schema kinds are `string`, `int`, `float`, `bool`, and `timestamp`; timestamps
require an explicit UTC offset and are emitted in UTC. Unknown fields can be
rejected, dropped, or preserved. Defaults and choices are validated before reading
records; choice values must already be normalized. Input is limited to 16 MiB and
10,000 records. The input file is never replaced by its output.

The configuration migrator defaults to a preview. It upgrades the sample service
configuration through versions 1 → 2 → 3, validating every intermediate result:

```bash
cp examples/corpus/047_config_migrator/settings-v1.json /tmp/migration-demo.json
MIGRATE_FILE=/tmp/migration-demo.json build/corpus/047/corpus_047
MIGRATE_FILE=/tmp/migration-demo.json MIGRATE_MODE=apply build/corpus/047/corpus_047
```

The original bytes remain in `<file>.backup`. A before/after journal is written
and synced before replacing the configuration; a subsequent apply recovers an
interrupted operation. External edits or inconsistent sidecars cause an error
without overwriting the configuration. `MIGRATE_MODE=rollback` restores the exact
backup only when the current document still matches its migration result. It is
idempotent. `MIGRATE_STOP` can inject exit status 75 at `after_backup`,
`after_journal`, `after_replace`, or `after_cleanup` for recovery tests. Use one
writer at a time; this example does not implement interprocess locking.

The route planner accepts a directed graph with named nodes, edge IDs and signed
integer costs, followed by a list of queries:

```bash
ROUTE_INPUT="$PWD/examples/corpus/061_route_planner/graph.json" \
ROUTE_REPORT=/tmp/routes.json ROUTE_TEXT=/tmp/routes.txt build/corpus/061/corpus_061
```

Queries may specify `closed_nodes` and `closed_edges`. A reachable negative cycle
invalidates a route only if that cycle can also reach its destination; unrelated
cycles do not invalidate finite routes. The JSON report includes edge/node
witnesses and unreachable-component diagnostics, alongside a plain-text report.
Limits are 100 nodes, 2,000 edges, 100 queries and edge costs of magnitude at most
one billion. Exit status is 1 if any query has no finite route.

The expense allocator uses integer cents and positive integer share weights:

```bash
EXPENSE_INPUT="$PWD/examples/corpus/101_expense_allocator/expenses.json" \
EXPENSE_STATE=/tmp/expense-demo-state.json \
EXPENSE_REPORT=/tmp/expense-demo-report.json build/corpus/101/corpus_101
```

Each allocation floors its exact weighted share, then distributes the remaining
cents by descending fractional remainder, breaking ties by Unicode person name.
This also defines refund splits for negative amounts. Identical transaction IDs
are idempotent; conflicting IDs and invalid expenses/settlements are rejected.
Settlements move from a debtor to a creditor without exceeding either balance.
The persistent ledger is replayed and checked on startup. Reports contain the
allocation audit, balances, purchase/refund totals and a suggested settlement
plan. Limits are 100 people, 1,000 stored transactions, expense magnitudes up to
10¹² cents and weights of 1–10⁶. A storage failure stops the import. Use one writer
per ledger; no interprocess locking is claimed.

## Webhook inbox and outbox

Run the inbox in one terminal, then submit the sample delivery from another:

```bash
INBOX_STATE=/tmp/webhook-inbox.json INBOX_PORT=8768 build/corpus/002/corpus_002

OUTBOX_IMPORT="$PWD/examples/corpus/015_delivery_outbox/jobs.json" \
OUTBOX_STATE=/tmp/webhook-outbox.json OUTBOX_REPORT=/tmp/webhook-report.json \
build/corpus/015/corpus_015
```

The inbox accepts `POST /events` with an object containing `id`, `source`, `type`,
`occurred_at` (RFC3339 with an explicit offset), and `data` (an object). It returns
201 for a new event, 200 for an identical duplicate, and 409 for conflicting
content under an existing ID. An optional `Idempotency-Key` must equal the ID.
`GET /events?after=0&limit=100&source=desktop&type=note.created` filters and pages
receipt order; `GET /receipts/<id>` reads a receipt; `GET /stats` counts sources
and types. `POST /export` with `{"ids":["note-1"]}` returns NDJSON in selection
order. Limits default to 1,000 events, 64 KiB per event and an 8 MiB snapshot;
configure them with `INBOX_LIMIT`, `INBOX_MAX_BODY`, and `INBOX_MAX_STATE`.

The outbox imports an array of `{id, url, payload, headers?}` jobs atomically.
IDs are immutable; repeating identical jobs never resets their attempts.
It performs one pass over due deliveries and exits; invoke it again for another
pass. It saves each attempt, sends the job ID as `Idempotency-Key`, and classifies
2xx as delivered, disconnects/408/431/5xx as retryable, and other statuses as dead
letters. Redirects are not followed. `OUTBOX_ATTEMPTS` defaults to four;
`OUTBOX_DELAY` defaults to two seconds with exponential backoff capped at one
hour. A nonnegative integer `Retry-After` of up to nine digits extends that delay
up to the same cap; HTTP-date values use the normal backoff. `OUTBOX_TIMEOUT`
defaults to 2,000 ms. `OUTBOX_CA` selects a PEM CA bundle for HTTPS destinations.
URLs use ASCII DNS/IPv4 hosts, an optional port and percent-encoded paths; IPv6
literal URLs and credentials are outside this application's input grammar.

The report retains pending, delivered and dead-letter receipts. Exit status 1
means dead letters are present or an operation failed; pending retries alone
exit 0. `OUTBOX_MODE=inspect` reads existing state without importing or sending.
The queue is bounded at 1,000 jobs, 64 KiB payloads and an 8 MiB snapshot. Use
one process per state file; these examples do not implement writer locking.

Delivery is at least once. A crash after the peer accepts a request but before
the local checkpoint can resend it; the inbox's stable IDs prevent duplicate
storage. `OUTBOX_STOP=after_send` injects that interruption with exit status 75.
`INBOX_NOW` and `OUTBOX_NOW` select deterministic clocks for testing. The pair
check runs all four Python/Rust client/server combinations through interruption,
replay and restart; evidence is in `build/corpus/webhook-pair/result.json`.

## Bookmarks, pastes and versioned settings

After building the corpus, run each service in its own terminal:

```bash
BOOKMARK_STATE=/tmp/bookmarks.json BOOKMARK_PORT=8769 build/corpus/003/corpus_003

PASTE_STATE=/tmp/pastes.json PASTE_PORT=8770 build/corpus/004/corpus_004

SETTINGS_SCHEMA="$PWD/examples/corpus/005_versioned_settings/schema.json" \
SETTINGS_STATE=/tmp/settings-state.json SETTINGS_PORT=8771 build/corpus/005/corpus_005
```

The bookmark service accepts `POST /bookmarks` with
`{"name":"docs","title":"Documentation","url":"https://example.org/docs","tags":["work"]}`.
Names use lowercase ASCII letters, digits, underscores and hyphens, starting with
a letter. Destinations use HTTP(S), DNS names or canonical dotted-decimal IPv4,
optional ports 1–65535, and escaped ASCII paths/query/fragments. Credentials, IPv6
literals, empty DNS labels and malformed percent escapes are rejected. Accepted
URLs are returned unchanged in `GET /r/<name>`'s 302 `Location` header; each
successful redirect persists one visit before responding.

Use `GET /bookmarks?q=<text>&tag=<tag>` for Unicode title/name/URL search and tag
filtering, or `GET`, `PUT`, `DELETE /bookmarks/<name>` to inspect, replace or remove
a bookmark. Updates retain its creation time and visits. `GET /export` includes
complete records; `POST /import` merges that format atomically. Identical records
are skipped, conflicts return 409 without changing any record, and invalid
snapshots return 400. `BOOKMARK_LIMIT` defaults to 1,000; snapshots are capped at
8 MiB. The application does not fetch destinations or verify their availability.

The paste service accepts `POST /pastes` with
`{"title":"Notes","text":"Hello, 世界","visibility":"private","ttl":3600}`.
It returns an opaque ID and delete key; private pastes also receive a separate
read key. Keep this creation response: subsequent listings and metadata never
return keys. `GET /pastes/<id>` serves exact UTF-8 text, including original line
endings; `GET /metadata/<id>` serves public metadata. Private reads require
`Authorization: Bearer <read_key>` or the delete key. `DELETE /pastes/<id>` requires
the delete key; a read key cannot delete. Unknown and unauthorized private IDs
both return 404.

`GET /pastes?q=<text>&offset=0&limit=100` lists only unexpired public pastes, with
Unicode title/content search. At the exact expiration deadline, authorized reads
return 410; `POST /sweep` removes expired records, after which reads return 404.
TTL is 1–86,400 seconds. Defaults are 64 KiB of UTF-8 per paste, 1,000 retained
records and an 8 MiB snapshot, configured with `PASTE_MAX_BYTES`, `PASTE_LIMIT`
and `PASTE_MAX_STATE`. Full storage returns 507 without replacing the snapshot.

The settings service loads the sample schema's bool, bounded integer, string,
choice and unique string-list fields. `GET /settings` returns the current revision
and values. `PUT /settings` takes `{"revision":0,"changes":{"workers":8}}`;
unknown fields and invalid types/ranges return 400, and stale revisions return
409. Successful changes append a revision. A valid no-op retains the revision
and does not write the snapshot. Two clients updating the same revision cannot
both succeed.

`POST /rollback` takes `{"revision":1,"target":0}` and appends a new revision
containing the complete target values. Earlier history remains intact.
`GET /history?after=-1&limit=100` pages the audit trail, including changed fields,
operation kind and source revision. `GET /schema` describes the fields.
`SETTINGS_HISTORY` defaults to 100 retained revisions, including the initial one;
a full history or an 8 MiB snapshot returns 507 instead of discarding old entries.
On restart, the application checks the entire revision sequence and rollback
values against the stored schema. Changing the schema requires a separate
migration; an incompatible configured schema is rejected without rewriting state.

These three services bind to loopback. Use one server per state file; HTTP
operations are serialized within that server, without interprocess writer locks.
`BOOKMARK_NOW`, `PASTE_NOW` and `SETTINGS_NOW` override clocks for reproducible
tests. Application source, including authorization and revision logic, is Python;
the shared Rust runtime provides generic I/O, regex and byte-comparison operations.

## Queues, reservations and rate limits

Run these services in separate terminals after verification:

```bash
QUEUE_STATE=/tmp/work-queue.json QUEUE_PORT=8772 build/corpus/007/corpus_007

RESERVE_STATE=/tmp/reservations.json RESERVE_PORT=8773 build/corpus/008/corpus_008

RATE_STATE=/tmp/rate-limits.json RATE_PORT=8774 build/corpus/009/corpus_009
```

The work queue accepts `POST /jobs` with
`{"id":"resize-1","queue":"images","priority":5,"delay":0,"payload":{"file":"photo.png"}}`.
Only `id` and `payload` are required; queue defaults to `main`, priority and delay
to zero. Identical IDs are idempotent, including completed jobs; different job
definitions under the same ID return 409. A worker uses `POST /claim` with
`{"worker":"worker-1","queue":"images","seconds":30}`. The highest-priority ready
job wins, with enqueue order breaking ties. An empty queue returns `{"job":null}`.

A successful claim returns a public job record and a separate lease token.
`POST /ack` and `POST /release` take `{id, worker, token}`; release may include
`delay`. Only the current unexpired lease can acknowledge or release a job.
An expired or released token cannot acknowledge a subsequent claim, even when
the worker name is reused. Repeating an already successful acknowledgment is
idempotent. At the exact lease deadline, the job becomes pending. `POST /sweep`
reports requeued jobs; other valid operations also expire leases.

Use `GET /jobs?queue=images&state=pending` or `GET /jobs/<id>` to inspect jobs
without revealing lease tokens. `DELETE /jobs/<id>` purges completed receipts
only, allowing their IDs to be reused with new tokens. `QUEUE_LIMIT` defaults to
1,000 retained jobs, including completed receipts. `QUEUE_LEASE` defaults to 30
seconds; claims can request 1–3,600 seconds. Priorities are 0–9, delays 0–86,400
seconds, canonical payloads at most 16 KiB and snapshots at most 8 MiB. A persisted
clock watermark prevents backward wall-clock changes from extending leases.

The reservation service accepts `POST /resources` with
`{"id":"room-a","name":"Meeting room A"}`, then `POST /bookings` with:

```json
{
  "id": "planning-1",
  "resource": "room-a",
  "owner": "alice",
  "title": "Planning",
  "start": "2026-10-06T09:00:00+05:00",
  "end": "2026-10-06T10:00:00+05:00"
}
```

Timestamps require explicit offsets and normalize to UTC. Each resource is
exclusive during `[start, end)`: adjacent bookings fit; any positive overlap
returns 409. Repeating a booking ID with the same normalized definition is
idempotent. `DELETE /bookings/<id>` cancels while retaining its history and frees
the interval; replaying that booking never resurrects it. `GET /bookings/<id>`
reads its current state. `GET /agenda` accepts `resource`, `owner`, `from`, `to`
and `include_cancelled=true` filters; it returns intersecting bookings ordered by
start time and ID. `GET /resources` lists resources; `DELETE /resources/<id>`
requires no booking history referencing the resource. Defaults are 100 resources
and 1,000 bookings, controlled by `RESERVE_RESOURCES` and `RESERVE_BOOKINGS`.
Cancelled bookings count toward this bounded audit history. Snapshots are capped
at 8 MiB and validated for conflicting active intervals on restart.

The rate limiter accepts `POST /admit` with
`{"key":"client-a","id":"request-1","cost":2}`. Cost defaults to one. `RATE_QUOTA`
defaults to five units per key during `RATE_WINDOW` seconds (default 60). Accepted
charges stay in the exact rolling window `(now - window, now]`; denied requests
are not charged. A repeated accepted request ID with the same cost is idempotent
while retained; a conflicting cost returns 409. After expiry its ID may be reused.
Keys have independent quotas. Accepted requests return 200; exhausted quotas
return 431 with `Retry-After` rounded upward to whole seconds.

Responses include `used`, `remaining`, `retry_at` (enough capacity for this cost)
and `reset_at` (full capacity). `GET /quota?key=client-a` inspects without charging;
`GET /quotas` lists active keys. `POST /sweep` reports expired charges and removed
keys. `RATE_KEYS` defaults to 1,000 active keys and `RATE_MAX_STATE` to 8 MiB;
capacity failures return 507 without admitting the request. Quota/window policy
is stored with the ledger; an incompatible restart fails instead of reinterpreting
existing charges. The persisted clock watermark also protects these windows from
backward wall-clock changes. Valid inspection/denial requests can advance the
watermark and remove expired charges.

These servers bind to loopback and serialize callbacks. Use one server per state
file; there is no interprocess writer lock. `QUEUE_NOW`, `RESERVE_NOW` and
`RATE_NOW` override time for deterministic tests. Each service atomically replaces
its snapshot and checks persisted records before starting to serve requests.

## Live notification board

```bash
BOARD_STATE=/tmp/notifications.json BOARD_PORT=8775 build/corpus/010/corpus_010
```

Open `curl -N http://127.0.0.1:8775/subscribe` in another terminal, then publish:

```bash
curl -H 'Content-Type: application/json' -d \
  '{"key":"note-1","topic":"notes","data":{"text":"Hello, world"}}' \
  http://127.0.0.1:8775/events
```

`POST /events` returns 201 and a durable numeric ID. Repeating a retained key
with identical topic/data returns the original event and 200; conflicting content
returns 409. Retention bounds deduplication too: once a key is pruned, it can be
published again with a new, never-reused sequence ID. Keys and topics use 1–64
ASCII letters, digits, underscores or hyphens. Event data is arbitrary JSON up to
8 KiB. Requests are capped at 16 KiB; persisted snapshots at 16 MiB.

`GET /subscribe` replays retained events and remains open for new ones. Frames
use `event: notification`, a canonical decimal `id`, and a compact JSON `data` record.
Embedded line breaks in data are escaped. Reconnect using `Last-Event-ID` or
`?after=<id>`; a nonempty header takes precedence over the query. The cursor is
the last event the client received and processed; no application acknowledgment
protocol or exactly-once delivery is claimed. Idle connections receive comments
as heartbeats. These framing/reconnect rules follow the
[WHATWG SSE format](https://html.spec.whatwg.org/multipage/server-sent-events.html).

`BOARD_RETAIN` defaults to 128 events (1–1,000). A requested cursor older than the
retained replay window, or ahead of the log, gets HTTP 409 with current bounds.
If an already open subscriber falls behind retention, it receives an `event: gap`
frame and the response ends. The client must inspect/reload current history and
choose a new cursor; the board never silently skips a missing interval.

`GET /events` returns JSON history with `after`, `limit` (1–100), and optional
`topic` filters. Its `next` cursor includes scanned nonmatching events, allowing
filtered pagination to advance. `GET /status` reports oldest/latest IDs and
retained count. Reads never rewrite the log; publication checkpoints before
responding. `BOARD_NOW` overrides publication time for testing, with a persisted
watermark protecting event timestamps against backward clock changes.

Subscriptions poll in serialized, bounded callbacks; `BOARD_POLL` defaults to
50 ms (1–1,000). The generic runtime emits at most one 64 KiB chunk at a time and
requests more only when the network writer is ready. Stalled peers have no
unbounded producer queue. There are at most 32 subscriptions among 64 active
connections; excess subscriptions get 503. Each connection has a 60-second total
lifetime, so consumers reconnect with their cursor. Disconnect/error/timeout
releases its stream state. Both Python and native Rust checks deliver 600 events
to a healthy subscriber beside a non-reading peer. Use one loopback server per
state file; there is no cross-process writer lock.

## Health monitoring and paginated imports

The health monitor's sample policy checks the notification board on port 8775:

```bash
HEALTH_CONFIG="$PWD/examples/corpus/011_health_monitor/endpoints.json" \
HEALTH_STATE=/tmp/health-state.json build/corpus/011/corpus_011
```

It polls each configured endpoint independently and checkpoints after every check.
A refused connection, timeout, invalid response or body-limit failure produces a
failed observation without stopping the remaining endpoints. GET requests use
configured success status codes (default `[200]`); redirects are not followed.
Elapsed latency uses a monotonic clock and is measured for failed checks too.
JSON and text reports are written beside the state file with `.report.json` and
`.report.txt` suffixes. Exit status is 0 only when every endpoint is `up`; otherwise
it is 1. Configuration/storage errors also exit nonzero.

The first successful check establishes `up`. Failures first produce `degraded`
(or retain initial `unknown`), then become `down` at `failure_threshold`, default
two consecutive failures. A confirmed outage starts at the first failure of that
streak. While down, successful checks produce `recovering`; `recovery_threshold`
consecutive successes (default two) close the outage. Another failure resets the
recovery streak. Closed outage durations and the current open outage contribute
to reported downtime. This is duration under the sampling policy, not continuous
observation of upstream availability.

Policy fields are `endpoints`, `failure_threshold`, `recovery_threshold`, `retain`,
`timeout_ms` and `max_body`. Each endpoint has `id`, `url` and optional `statuses`.
Limits are 100 endpoints, thresholds 1–20, retained samples/closed outages 1–100,
timeouts 1–30,000 ms, response bodies 1–1,048,576 bytes, and an 8 MiB snapshot.
`retain` defaults to 20; lifetime check/failure/downtime counters survive history
truncation. The normalized policy is immutable for a state file. An incompatible
policy or corrupt stored counters, measurements or outage intervals fails before
polling or replacing reports.

`HEALTH_ROUNDS` runs 1–50 rounds (default one); `HEALTH_INTERVAL` waits 0–60 seconds
between them. Scheduling another process invocation preserves thresholds and
history. `HEALTH_MODE=inspect` renders saved state without polling or rewriting it.
`HEALTH_NOW` supplies a deterministic wall clock; a persisted watermark prevents
backward changes from decreasing observation times. `HEALTH_STOP=<endpoint-id>`
injects exit 75 after that endpoint's checkpoint, leaving a partial round available
for inspection. A later normal run starts a new round from the first endpoint.

For a complete harvester demo, start the existing mock API with the supplied page
fixture, then run the native harvester from another terminal:

```bash
MOCK_CONFIG="$PWD/examples/corpus/012_json_harvester/pages-api.json" \
MOCK_STATE=/tmp/harvest-pages.json MOCK_PORT=8780 build/corpus/006/corpus_006

HARVEST_CONFIG="$PWD/examples/corpus/012_json_harvester/harvest.json" \
HARVEST_STATE=/tmp/harvest-state.json HARVEST_STEPS=1 build/corpus/012/corpus_012
```

The page API returns exactly `{items: [...], next: URL-or-null}`. Each item is a
JSON object with a nonempty string `id`; other fields are retained. `next` must be
an absolute URL with the same normalized scheme, host and port as the start URL.
A null cursor marks completion. Relative URLs, fragments, credentials, changed
origins and repeated page URLs are rejected. URLs use ASCII DNS/canonical IPv4,
optional ports 1–65535, an explicit slash path, and valid percent escapes; IPv6
literal hosts are outside these examples' grammar. Host case and default ports
normalize before cursor comparison. Both clients require percent-encoded URLs.

Run the harvester command again to fetch its second page. It produces three
unique records and counts the overlapping record as a duplicate. A retained ID
with structurally identical content is skipped; conflicting content rejects the
entire page. Integer/float equivalents compare equal, while booleans stay distinct
from numbers. Record order follows first occurrence. Validation, duplicate checks,
new records, the page receipt and the next cursor form one atomic checkpoint.
Earlier records cannot be partially modified by a failed page.

`HARVEST_STEPS` limits requests per invocation to 1–100 (default ten). Exhausting
this invocation budget is a successful partial run; invoke it again to continue.
The policy's `max_pages` and `max_records` bound the entire import, defaulting to
100 and 10,000 respectively. `page_size` defaults to 1,000 records and `max_body`
to 1 MiB; `timeout_ms` defaults to 2,000. Each record is capped at 16 KiB and the
snapshot at 16 MiB. A whole-import limit, HTTP error, transport failure or invalid
page stops with exit 1 and leaves the next cursor available for retry. Reports
include an error category and URL. Policy changes require a separate state file.

The state file plus `.report.json` retain all accepted records, page/duplicate
counts, completion and next cursor. A completed import performs no further
requests. `HARVEST_MODE=inspect` generates a report without fetching or rewriting
state. `HARVEST_STOP=before_checkpoint` and `after_checkpoint` inject exit 75 to
test both sides of the atomic replacement: restart refetches an uncommitted page
and skips a committed page. The sample API is read-only, so refetching is safe.

Both applications require one writer per state file. Path checks reject aliases
between configuration, state and reports. `tools/check_http_clients.py` runs
the mock API with these clients, the downloader, the link auditor, the change
watcher, the quota-aware batcher and the load probe in all four Python/Rust
server/client combinations, including a persisted health threshold, a harvester
interruption after its first page, downloader publication recovery and a cyclic
website with a broken link, ignored-versus-visible JSON snapshot changes, and a
quota pause followed by completed-ID deduplication, and 14 scheduled probe requests
with successful and unsuccessful HTTP responses. Evidence
is in `build/corpus/http-clients/result.json`.

## Resumable binary downloads

The downloader is 376 substantive Python lines across `main.py` (streaming and
orchestration), `model.py` (policy and range validation), and `storage.py`
(verified prefixes and publication). Every module transpiles to native Rust.
For a small runnable example, start the mock API with its download fixture,
then run the downloader from another terminal:

```bash
MOCK_CONFIG="$PWD/examples/corpus/013_resumable_download/download-api.json" \
MOCK_STATE=/tmp/download-api-state.json MOCK_PORT=8767 build/corpus/006/corpus_006

DOWNLOAD_CONFIG="$PWD/examples/corpus/013_resumable_download/download.json" \
build/corpus/013/corpus_013
```

The sample publishes `downloaded-artifact.txt` containing exactly `abc`. The
sample mock route always returns this single range; the independent acceptance
peer additionally checks multiple ranges, errors and restarts. A repeated
completed run verifies the existing file without making another HTTP request.

`DOWNLOAD_CONFIG` defaults to `download.json`. Required fields are `url`,
`target`, and the expected `sha256` digest. Optional fields are `max_bytes`
(0–1 GiB, default 1 GiB), `chunk_size` (1 byte–16 MiB, default 1 MiB), and
`timeout_ms` (1–60000, default 5000). The parent directory must already exist.
`DOWNLOAD_STEPS` permits 1–1000 ranges per invocation, default 8; reaching this
budget exits successfully with a resumable checkpoint. Run again to continue.
Errors exit 1 and preserve the last accepted range. Automatic retries and
concurrent download workers are not implemented.

Requests use `Range`, identity content encoding, and the saved strong ETag in
`If-Range`. A validator mismatch can cause an HTTP server to send the whole
representation instead; this application rejects that response to avoid mixing
versions. This follows the conditional range semantics in
[RFC 9110 §13.1.5](https://www.rfc-editor.org/rfc/rfc9110.html#section-13.1.5).
The application requires a numeric total, a matching single `Content-Range`,
and a strong printable-ASCII ETag. Missing/weak validators, altered totals,
encoded bodies, redirects and full status-200 responses are rejected. An empty
file can be recognized from status 416 with `Content-Range: bytes */0` and a
strong ETag, then verified against the expected empty-file digest. These are
deliberately narrower requirements than general HTTP download behavior.

The adjacent `.part` file contains downloaded bytes, `.download.json` stores
the policy, validator, verified offset and prefix digest, and `.report.json`
reports progress and any error. Each complete accepted range is synced before
its checkpoint is atomically replaced. Restart rehashes the committed prefix;
corruption or missing bytes stop recovery without modifying that prefix. Any
uncommitted tail is truncated and fetched again. The transfer and rehash loops
use 64 KiB buffers. Acceptance downloads a 192 MiB file with both execution
engines under a 128 MiB process address-space limit.

After full SHA-256 verification, a `ready` checkpoint precedes no-clobber
hard-link publication. Directory syncs and a final `published` checkpoint make
the tested interruption boundaries recoverable. An interrupted publication can
leave both final and partial names; restart validates the final bytes and
removes the partial name. Existing unrelated output, orphan partial files,
symlinks and configuration/report aliases are rejected. Use one writer per
target in a directory it owns, on a Linux filesystem supporting hard links and
directory sync; the path checks are not protection against a concurrent hostile
filesystem writer. Tests cover process interruption, not simulated power loss.

`DOWNLOAD_STOP=mid_body`, `after_write`, `after_checkpoint`, `before_publish`,
or `after_publish` exits 75 at that boundary. Clear it when resuming. Changing
URL, target, digest or limits requires a separate target/checkpoint. URLs use the
same bounded ASCII HTTP(S) policy as the other clients; IPv6 literals,
credentials, fragments and automatic redirects are excluded. HTTPS uses the
runtime's normal certificate validation.

## Local website link auditing

The auditor is 284 substantive Python lines in three modules. `model.py`
validates limits and fetches/parses responses, `crawl.py` traverses and reports
the link graph, and `main.py` writes the report and sets the exit status.
The whole application compiles to Rust. Its shared HTML runtime uses a native
HTML5 parser; the reference implementation uses the optional `html5lib` Python
package installed above. The compiled executable does not use that package.

Run the supplied sample website through the existing mock API, then run the
auditor from another terminal:

```bash
MOCK_CONFIG="$PWD/examples/corpus/016_link_auditor/site-api.json" \
MOCK_STATE=/tmp/audit-site-state.json MOCK_PORT=8781 build/corpus/006/corpus_006

AUDIT_CONFIG="$PWD/examples/corpus/016_link_auditor/audit.json" \
AUDIT_REPORT=/tmp/audit-report.json build/corpus/016/corpus_016
```

The sample has a home page, a guide linking back home, an external link, and a
deliberately missing page. The auditor fetches each of the three local URLs once,
records the broken link's source, and exits 1. It sends no request to the external
origin. The JSON report contains pages, link edges, terminal redirect outcomes,
broken pages, broken links, and summary counts. It is pretty-printed and replaced
atomically; stdout contains the summary. Report paths may not alias the config.

`AUDIT_CONFIG` defaults to `audit.json`; only `start` is required.
`AUDIT_REPORT` defaults to `audit-report.json`. Limits are:

| Setting | Default | Allowed range |
| --- | --- | --- |
| `max_depth` | 3 | 0–20 |
| `max_pages` | 100 | 1–500 distinct requested URLs |
| `max_links` | 1000 | 1–2000 extracted links per HTML document |
| `max_edges` | 5000 | 1–50000 recorded edges per run |
| `max_body` | 262144 | 1–1048576 response bytes |
| `timeout_ms` | 2000 | 1–30000 per request |

Normal links add one depth; redirects add zero. Pending URLs are processed in
order of their smallest known depth, preserving discovery order on ties. Thus a
later redirect can shorten an already queued route before that page is processed.
Each URL is requested once, cycles terminate, and redirect loops are reported.
Exit 0 means no broken links/pages or unresolved crawl limits, exit 1 means broken
links/pages, and exit 2 means limits prevented a complete crawl without a detected
broken link. A failed fetch or HTML parse appears in the report and does not stop
other queued URLs. `complete` describes traversal budgets, not a guarantee that
all requests or parses succeeded. Invalid configuration fails before fetching
or replacing a previous report.

The crawler extracts static HTML links and resource attributes, including images,
scripts, stylesheets, media and embedded objects. It honors the first `<base href>`
and resolves relative paths, query strings, dot segments and percent-encoded dot
segments. Fragments are removed for request deduplication; fragment IDs are not
checked. Scripts are not executed. Comments, raw text, template contents and
foreign-namespace tags do not become links. CSS URLs, `srcset`, forms and links
created by JavaScript are outside this static-link profile.

Only the start URL's exact origin (scheme, normalized hostname and port) is
requested. External links, external base URLs and external redirects are reported
without fetching them. Common non-HTTP schemes such as `mailto:` and `javascript:`
are ignored; malformed HTTP links are broken links. URLs accept ASCII DNS names
or canonical IPv4, Unicode paths/queries, and ports 1–65535; IPv6, credentials,
backslashes, controls and invalid percent escapes are rejected. Redirects are
followed explicitly under these same rules. HTTPS uses the runtime's normal
certificate validation. HTML must be uncompressed UTF-8 with `text/html` content
type; non-HTML responses are checked as bounded assets and are not parsed.

## Watching JSON endpoint changes

The change watcher consists of 425 substantive Python lines in four modules:
`changes.py` handles recursive comparison and filtering, `model.py` validates
policy and timestamps, `storage.py` validates/checkpoints state, and `main.py`
polls and renders reports. It uses the existing subset without compiler/runtime
changes; every application module transpiles to Rust.

Start the mock API with its changing snapshots, then run the watcher from another
terminal:

```bash
MOCK_CONFIG="$PWD/examples/corpus/017_change_watcher/snapshots-api.json" \
MOCK_STATE=/tmp/watch-api-state.json MOCK_PORT=8782 build/corpus/006/corpus_006

WATCH_CONFIG="$PWD/examples/corpus/017_change_watcher/watch.json" \
WATCH_STATE=/tmp/watch-state.json WATCH_ROUNDS=4 build/corpus/017/corpus_017
```

The first response establishes a baseline. The second only changes the ignored
`observed_at` field. The third adds `writer` at `/profile/roles/1`, and the fourth
repeats that snapshot. The result is one retained event. The adjacent
`/tmp/watch-state.json.report.json` and `.report.txt` show the current filtered
snapshot and readable before/after changes. Restart with the same state to
continue; an unchanged response does not create another event.

`WATCH_CONFIG` defaults to `watch.json` and `WATCH_STATE` to `watch-state.json`.
Configuration requires `url`; other fields are:

| Setting | Default | Allowed range |
| --- | --- | --- |
| `ignore` | `[]` | Up to 100 distinct JSON Pointers, each at most 1024 characters |
| `retain` | 20 | 1–100 most recent events |
| `max_changes` | 100 | 1–1000 changes in one accepted transition |
| `max_body` | 65536 | 1–262144 response bytes |
| `timeout_ms` | 2000 | 1–30000 per request |
| `interval_ms` | 1000 | 1–60000 between polls in the same invocation |

`WATCH_ROUNDS` is 1–100, default 1. Each response must have status 200 and contain
uncompressed UTF-8 JSON. Objects, arrays and scalar roots are accepted, with at
most 2000 JSON nodes and 24 levels below the root. A failure records its category
and status while preserving the last accepted snapshot and event history. Later
polls continue. Exit 1 means at least one poll failed in this invocation, even if
the last poll recovered; exit 0 means all polls succeeded. Invalid configuration
or state fails before requests or report replacement.

Pointers use `/` between tokens, `~1` for a slash in a key and `~0` for a tilde;
the empty pointer denotes the whole document, while `/` denotes its empty-name
member. This is the spelling defined by
[RFC 6901](https://www.rfc-editor.org/rfc/rfc6901.html#section-3).
Ignore entries suppress the named subtree, without wildcards. Ignored object
members are removed before persistence; ignored array slots use null placeholders
so other indices stay stable. Presence changes at an ignored array index are also
suppressed. Adding/removing an ancestor container can still be a structural
change, with ignored contents removed from its recorded value. Changing the
policy, including ignore rules, requires a separate state file.

The differ uses explicit `add`, `remove`, and `replace` records containing a path,
previous value and following value. Operation names distinguish absent members
from actual JSON null. Equivalent integer/float values compare equal; booleans
remain distinct from numbers, and large integers are not rounded through floats.
Array positions are compared by index; moves and set-like matching are not
inferred. These are comparison records, not an RFC 6902 patch stream: removals
refer to indices in the old snapshot. Independent acceptance checks reconstruct
20 transitions from the reported records, including shrinking arrays and changes
between object, array, boolean, number and null roots.

Every successful or failed observation increments the check count. Visible
transitions receive increasing event IDs; retention discards old events without
resetting that sequence. Timestamps are normalized UTC RFC3339 values. Set
`WATCH_NOW` to an RFC3339 timestamp for deterministic runs; a time earlier than
the last committed observation is rejected before requesting data.
`WATCH_MODE=inspect` regenerates the reports without fetching or rewriting state,
and exits 0 even when the saved last observation is a failure.

The accepted snapshot and its events are committed together in one atomic state
replacement, bounded at 8 MiB. Report writes follow the checkpoint and can be
regenerated after interruption. `WATCH_STOP=before_checkpoint` or
`after_checkpoint` injects exit 75. Clearing that variable and rerunning either
records the uncommitted transition or recognizes the already committed snapshot;
the tests verify no duplicate event at either boundary. Use one writer per state
file. State/report symlinks and configuration aliases are rejected. Polling can
only observe snapshots that the endpoint returns; transient intermediate values
between polls are not retained.

## Quota-aware API batches

The batcher is 446 substantive Python lines in four modules: `model.py` defines
the policy and request identities, `quota.py` reads responses and quota headers,
`storage.py` validates/imports/checkpoints the queue, and `main.py` runs due work
and renders results. Every module transpiles to Rust. Shared subset additions
are `http_retry_after(value, now)` and `separator.join(list_of_bytes)`.

Start the sample mock API, then run the native batcher from another terminal:

```bash
MOCK_CONFIG="$PWD/examples/corpus/018_quota_batcher/quota-api.json" \
MOCK_STATE=/tmp/batch-api-state.json MOCK_PORT=8783 build/corpus/006/corpus_006

BATCH_CONFIG="$PWD/examples/corpus/018_quota_batcher/batch.json" \
BATCH_IMPORT="$PWD/examples/corpus/018_quota_batcher/requests.json" \
BATCH_STATE=/tmp/batch-state.json build/corpus/018/corpus_018
```

The first pass completes `profile` and receives a three-second quota pause for
`projects`. Run the same batch command after that pause to finish `projects` and
`notifications`. Further runs send nothing for completed IDs. State and its
`.report.json` retain parsed JSON results, attempt counts, per-request retry
deadlines, the shared `not_before` time, and any blocking reason. The report
can always be regenerated with `BATCH_MODE=inspect`.

Each imported request contains exactly `id` and `url`; URLs resolve against the
configured `base_url` and must stay on its origin. Imports are transactional:
an existing ID with the same normalized URL is ignored; changing its URL rejects
the entire import. GET is the supported method, redirects are not followed,
and results must be JSON or an empty 204 response. This provides safe read-only
batching; it does not model arbitrary mutation requests. The queue holds at most
100 unique IDs, with 1–65,536 bytes per response, 4,096 JSON nodes, 24 nesting
levels, and a 16 MiB state file. Imports are bounded at 1 MiB. State policy is
fixed after creation; use a new state file for a different policy.

`Retry-After` accepts decimal delay seconds, including leading zeroes, or all
three HTTP date forms. Relative delays start after receipt, and past dates never
move the deadline backwards. The paired `X-RateLimit-Remaining` and
`X-RateLimit-Reset` fields use nonnegative decimal counts and **Unix epoch
seconds** respectively; when remaining is zero, subsequent requests share that
reset deadline. These are the explicitly supported quota fields, not a guess at
every vendor's header conventions. If multiple supported fields impose waits,
the longest wait wins. Response headers remain available when reading a body
fails, so an oversized or truncated result does not discard its quota deadline.
As elsewhere in this profile, repeated response header names expose their first
value; servers must send one value per quota field.

Transport failures, 408, 431 and 5xx responses retry with bounded exponential
backoff. A 431 also pauses the whole queue. Other HTTP failures and invalid JSON
are terminal. `attempts` is 1–8 (default 4), `backoff` is 1–3,600 seconds (default
2), and exponential delays cap at 3,600 seconds without shortening a server's
longer deadline. Malformed or incomplete quota headers block further requests
while preserving completed results and any independently valid deadline.
`BATCH_LIMIT` caps requests per invocation at 1–100; the default is 100. Each
invocation makes one pass and reports deferred work rather than sleeping until
the next deadline. Exit 1 indicates a blocked queue or terminal failure; deferred
work alone exits 0. `BATCH_CA` supplies a private HTTPS trust bundle.

A synced atomic checkpoint claims each request **before** sending it. Another
checkpoint commits the result and quota together. `BATCH_STOP=after_claim`,
`after_response` or `after_checkpoint` injects exit 75 for the tested boundaries.
After an uncertain interruption, ordinary runs stop with `unacknowledged request`;
they do not silently replay the GET or guess a lost server deadline. Once an
operator has checked the endpoint's quota, `BATCH_MODE=recover` explicitly
requeues the uncertain request with another backoff, or fails it if its attempt
budget is exhausted. Recovery sends nothing, preserves known quota deadlines,
and also clears a malformed-header block. A request completed before the crash
and committed to disk remains skipped. This is not an exactly-once guarantee
for a remote response lost before its checkpoint.

Use one process per state file. Input/output aliases and output symlinks are
rejected. `BATCH_NOW` supplies deterministic Unix seconds for tests; normal runs
read the system clock and reject time rollback before requesting data. The
acceptance fixture checks exact deadline boundaries and real elapsed time,
continued unrelated work during request-specific backoff, import conflicts,
corrupt checkpoints, explicit recovery, and all three interruption points.

## Circuit-breaker gateway

The gateway is 470 substantive Python lines in four modules: `model.py` validates
routes and filters forwarding headers, `circuit.py` implements the state machine
with a `Phase` enum, `storage.py` validates and checkpoints state, and `main.py`
handles HTTP forwarding and diagnostics. All application logic transpiles to
Rust. The shared server now exposes the original `WebRequest.target`, and its
default Cache-Control header no longer duplicates an application-supplied value.

Run the sample upstream and gateway in separate terminals:

```bash
MOCK_CONFIG="$PWD/examples/corpus/019_circuit_gateway/upstream-api.json" \
MOCK_STATE=/tmp/gateway-upstream-state.json MOCK_PORT=8785 build/corpus/006/corpus_006

GATEWAY_CONFIG="$PWD/examples/corpus/019_circuit_gateway/gateway.json" \
GATEWAY_STATE=/tmp/gateway-state.json GATEWAY_PORT=8784 build/corpus/019/corpus_019

curl -i http://127.0.0.1:8784/catalog
curl -i http://127.0.0.1:8784/catalog
curl -i http://127.0.0.1:8784/catalog
curl http://127.0.0.1:8784/_gateway/state
```

The first two calls forward the sample upstream's 503 responses and open the
`catalog` circuit. A call during its three-second cooldown receives a gateway
503 with `Retry-After`, without contacting the upstream. After the deadline,
the next request is admitted as a half-open probe; two successful probes close
the circuit. `/notes` uses an independent circuit and remains available.

Routes are exact paths, each with a stable ID, a configured absolute upstream
URL, and allowed methods from GET, POST, PUT and DELETE. A route's circuit is
shared by its allowed methods. Clients cannot select another upstream. Binary
request and response bodies are forwarded unchanged, and repeated query fields,
blank values, ordering, plus signs and percent escapes are retained through the
original request target instead of reconstructing a query dictionary. Outbound
HTTP clients still apply their normal URL handling: for example, an empty
trailing `?` is normalized away. This is a bounded API gateway, not a general
transparent HTTP proxy. Redirect responses are returned without following them;
the gateway does not rewrite their Location values.

Forwarded request headers are `Accept`, `Content-Type`, `Authorization`,
`If-Match`, `If-None-Match`, `Idempotency-Key` and `X-Request-Id`. Forwarded response
headers are `Content-Type`, `Content-Encoding`, `Cache-Control`, `ETag`,
`Last-Modified`, `Location`, `Retry-After` and `WWW-Authenticate`. Fields named
by the peer's `Connection` header are excluded, following
[RFC 9110 section 7.6.1](https://www.rfc-editor.org/rfc/rfc9110.html#section-7.6.1).
The transports own framing and connection headers. Requests advertise identity
encoding; bodies are not transformed. A Via marker prevents forwarding back
through this gateway, and `X-Circuit-State` exposes the resulting circuit phase.
Credentials and request bodies are never written into circuit snapshots.

Transport failures, response truncation/overflow, timeouts, 408, 431 and 5xx
responses count as failures. Other completed responses demonstrate upstream
availability; a 404 can therefore be a successful recovery probe. Any successful
closed-circuit request clears consecutive failures. Any failed half-open probe
reopens the circuit for a full cooldown. The gateway forwards a request only
once and performs no automatic mutation retries; a caller can supply an
idempotency key if its upstream supports one.

Configuration bounds are 1–16 routes, failure `threshold` 1–20 (default 3),
`probes` 1–10 (default 2), `cooldown` 0.01–3,600 seconds (default 5), `timeout_ms`
1–10,000 (default 2,000), and `max_body` 1–1,048,576 bytes (default 65,536) in
each direction. Headers use the shared ASCII profile; repeated response headers
expose their first value. Unknown routes return 404, disallowed methods return
405 with Allow, oversized bodies return 413, and unrepresentable targets are
rejected before forwarding. `GATEWAY_CA` supplies a private trust bundle for
HTTPS upstreams. The gateway itself binds HTTP on loopback.

`GET /_gateway/state` returns each circuit's phase, failure/probe counts,
forwarded and rejected counts, last outcome, deadline and last twenty
transitions with monotonic sequence IDs. Reading diagnostics does not contact
an upstream or change a phase. The next admitted request initiates a probe;
there is no background health-check loop. Application callbacks are serialized
by the current server runtime, so one slow upstream can delay other callbacks
until its bounded timeout. Competing recovery requests cannot simultaneously
probe a circuit or continue probing after the first failure reopens it.

A synced atomic claim precedes each upstream call. The outcome and phase change
are then committed together before replying. Startup counts an unfinished claim
as an interrupted failure and never replays its body. Open deadlines and partial
probe progress survive ordinary restarts. `GATEWAY_STOP=after_claim`,
`after_response` or `after_checkpoint` injects a callback failure returning 500;
clear it and restart to exercise recovery. An unresolved claim blocks further
forwarding until restart while leaving diagnostics readable. The acceptance
checks also terminate a real gateway process during an upstream request.
These checkpoints cannot guarantee exactly-once effects in a remote service.

Use one gateway process per state file. Policy changes, malformed snapshots,
clock rollback and input/state aliases are rejected. `GATEWAY_CLOCK` optionally
names a JSON file containing Unix seconds for deterministic fixtures; normal
runs use system time. The state file is bounded at 1 MiB.

`tools/check_gateway_stack.py` combines the mock API, gateway and quota-aware
batcher in all **eight** Python/Rust combinations. Two upstream failures open
the circuit; the batcher honors the gateway's retry deadline, completes recovery
probes, retains three results and skips completed IDs on another run. Evidence
is saved in `build/corpus/gateway-stack/result.json`. Native participants run
with Python unavailable in their environment.

## Bounded HTTP load probe

Application 020 is a finite HTTP load generator implemented in four Python modules:
configuration and schedule expansion, one worker, report aggregation, and execution.
All four transpile into the native program. The shared `parallel_map` API supplies
worker threads; request scheduling, cancellation checks and report calculations
remain in readable Python.

Start the sample mock API in one terminal, then run the probe in another:

```bash
MOCK_CONFIG="$PWD/examples/corpus/020_load_probe/probe-api.json" \
MOCK_STATE=/tmp/load-mock.json MOCK_PORT=8786 build/corpus/006/corpus_006

LOAD_CONFIG="$PWD/examples/corpus/020_load_probe/load.json" \
LOAD_REPORT=/tmp/load-report.json build/corpus/020/corpus_020
```

The sample schedules 14 requests across three targets: eight healthy GETs, three
deliberately unsuccessful GETs, and three JSON POSTs. Expect 11 successes, three
HTTP errors, and exit status **1**. The report and `/tmp/load-report.json.csv`
contain one row for every planned request in stable schedule order.

Each target has a unique `id`, an HTTP(S) `url`, optional `method` (GET by default),
`headers`, and a hexadecimal `body_hex`. GET, POST, PUT and DELETE are supported.
Redirect responses are recorded without following them. Bodies can contain binary
data. The target limit is 16, request bodies are capped at 4 KiB, and header names
and values are validated. Host and framing headers are managed by the HTTP client.
System TLS verification is used unless `LOAD_CA` supplies a private PEM CA bundle.

`schedule` is a list of `{target, at_ms, count, interval_ms}` entries. It expands
into at most 1,000 requests, sorted by planned start time; ties retain configuration
order. Every request gets a stable `target-slot-repeat` ID. Planned start times
are relative to a monotonic clock started immediately before dispatch. Requests
wait for their scheduled time; a busy worker pool can make them late.

| Setting | Default | Range or behavior |
| --- | --- | --- |
| `concurrency` | 4 | 1–32 active workers |
| `timeout_ms` | 2000 | 1–30,000; shortened to the remaining run duration when sending |
| `duration_ms` | 10,000 | 1–120,000; all scheduled times must fall before this deadline |
| `max_lag_ms` | 2000 | 0–60,000; skip a request if its start is later than this tolerance |
| `max_body` | 65,536 | 1–1,048,576 bytes per response |
| `buckets_ms` | `[10, 50, 100, 500, 1000]` | 1–30 strictly increasing positive integer bounds, at most 120,000 |

Set `LOAD_CANCEL` to a marker-file path and create that file to request cancellation.
Workers check while waiting and before sending. Pending requests receive explicit
`cancelled` results with reason `requested` or `deadline`. Requests already in
progress are allowed to finish or reach their HTTP deadlines. Cancellation is
cooperative: it does not forcibly interrupt a network call, and a signal arriving
just after a worker checks can race with that request's start. The map joins every
worker before publishing final results. Excessively late requests are recorded
as `late`, without sending or retrying them.

Reports classify each request as `ok` (2xx), `http_error`, `transport_error`,
`cancelled`, or `late`. Attempted requests record status, elapsed/latency/lateness
in integer microseconds, response length and SHA-256. Transport failures have no
completed response body. Per-target and overall summaries include counts, status
frequencies, total bytes, noncumulative latency buckets with an overflow bucket,
minimum/maximum, integer mean, sum, and nearest-rank p50/p95/p99. Timing values vary
between runs; the schedule, aggregation rules, output schema and row order are
reproducible. Request bodies and headers are omitted from reports.

The report first records `phase: running`. After all workers finish, an atomic CSV
replacement precedes an atomic final JSON replacement. A killed process can leave
a running report; there is no automatic resume or replay. Exit status is 0 for a
fully successful run, 1 for completed HTTP/transport failures, and 2 when any work
was cancelled or too late. Use one process per output path. Configuration,
cancellation, CA and report paths must be distinct; output symlinks and existing
hard-link aliases are rejected.

Independent fixtures hold requests open to prove simultaneous worker limits of
1, 3 and 4. They verify cancellation before dispatch, while waiting, and with three
active requests; deadline exhaustion; lateness; repeated schedule times; binary
and error responses; disconnects; body limits; truncated bodies; and 39 invalid
configuration/path cases. The checker independently recomputes every aggregate
and CSV row for both engines. The separate seven-client integration runs the probe
against the transpiled mock service in all four server/client combinations.

## Framed TCP task broker and batch client

Application 021 combines TCP sockets, binary framing, JSON, persistence and six
Python modules in one generated native executable. Its `serve` mode listens on
loopback; `client` sends a JSON batch of commands, reconnecting when the configured
per-connection frame allowance is exhausted.

Start the server, then use the same executable as a client in another terminal:

```bash
BROKER_CONFIG="$PWD/examples/corpus/021_tcp_broker/broker.json" \
BROKER_STATE=/tmp/broker-state.json BROKER_PORT=8787 build/corpus/021/corpus_021

BROKER_MODE=client BROKER_CONFIG="$PWD/examples/corpus/021_tcp_broker/broker.json" \
BROKER_REQUESTS="$PWD/examples/corpus/021_tcp_broker/requests.json" \
BROKER_REPORT=/tmp/broker-responses.json BROKER_PORT=8787 build/corpus/021/corpus_021
```

The sample submits `note-1`, lists pending work, acknowledges completion, fetches
the stored receipt and requests statistics. Running the client again preserves
the same receipt sequence and produces no duplicate work. Python reference runs
use the same settings with `python examples/corpus/021_tcp_broker/main.py`.

Every request and reply is one four-byte **unsigned big-endian length** followed
by that many UTF-8 JSON bytes. Lengths count encoded bytes. Multiple frames may
share a TCP write, and individual lengths/bodies may span many reads. Empty frames,
oversized declarations, truncation and read deadlines return `frame_error` and
close that connection. Clean EOF between frames closes normally. Invalid UTF-8
or JSON returns `invalid_json`; the next correctly framed command can still run.

| Command | Result |
| --- | --- |
| `{"op":"submit","id":"job-1","payload":...}` | Persist a new pending job and return its stable sequence before sending a successful receipt |
| `{"op":"get","id":"job-1"}` | Fetch the stored payload, sequence and pending/done state |
| `{"op":"pending","after":0,"limit":20}` | List pending jobs in receipt order, with `next` and `more` pagination fields |
| `{"op":"ack","id":"job-1"}` | Atomically mark a job done; repeated acknowledgments return the same receipt with `duplicate:true` |
| `{"op":"stats"}` | Return accepted, pending and done counts, next sequence and retained capacity |

IDs contain 1–40 ASCII letters, digits, underscores or hyphens. A repeated submit
with the same ID and JSON-equal payload returns its existing receipt. A changed
payload produces `id_conflict`. Numeric integer/float equivalents compare equal;
booleans remain distinct from numbers. Unknown IDs and operations return explicit
errors. Invalid request fields or a failed storage operation return `request_failed`.
Successful submissions and acknowledgments are checkpointed before the reply.
If the connection fails after commit, replay can recover the existing receipt.
This does not provide exactly-once execution of external work or exclusive leases
to workers; `ack` records the caller's declaration of completion.

| Configuration setting | Default | Range |
| --- | --- | --- |
| `max_jobs` | 1000 | 1–1000 retained identities, including done jobs |
| `max_payload` | 4096 | 1–4096 compact JSON bytes, also at most `max_frame - 512` |
| `max_frame` | 65,536 | 1024–65,536 bytes |
| `frame_timeout_ms` | 1000 | 50–30,000 milliseconds |
| `connection_frames` | 32 | 1–100 commands before closing a connection |

Pending pages stop at either the requested row count or reply byte limit. Done
identities remain retained for deduplication and still occupy capacity; new IDs
receive `capacity` when full. The snapshot has an 8 MiB cap and validates receipt
order, unique IDs, payloads, states and retained policy. A changed retained policy
or corrupt snapshot is rejected rather than resetting the queue. State writes
use atomic replacement with file and parent-directory sync. Use one server per
state file. Configuration, state, shutdown marker, batch and report aliases are
rejected in their respective modes.

The server processes one connection at a time. One frame read has an absolute
deadline across all its fragments; sending the reply gets a separate deadline.
Slow peers can delay others only within these per-frame and connection limits.
Set `BROKER_SHUTDOWN` to a marker-file path and create it to request a graceful
stop; the listener checks at most 100 ms apart, and active connections check
between bounded frame exchanges. `BROKER_STOP=before_checkpoint`,
`after_checkpoint` or `after_reply` injects exit 75 for interruption testing.

Client batches contain 1–100 commands in a file of at most 1 MiB. `BROKER_HOST`
defaults to numeric `127.0.0.1`; server and client must agree on frame/connection
limits. The client retains received replies in an atomic `phase: running` report,
then publishes `phase: finished` and the error count. A truncated
reply leaves the received prefix available without claiming completion. It does
not automatically retry requests whose result is uncertain. Exit 0 means all
replies succeeded; completed batches with error replies exit 1. Transport and
validation failures also exit nonzero.

The independent checker covers byte fragmentation, split Unicode, coalesced
commands, half-close, malformed input, pagination, capacity, corruption, restart,
absolute deadlines under a slow byte stream, actual process termination, graceful
stop, and all six submit/ack interruption boundaries. A separate socket fixture
checks native client reconnection and incomplete replies. `tools/check_tcp_broker.py`
exchanges real commands in all four Python/Rust server/client combinations;
evidence is saved in `build/corpus/tcp-broker/result.json`.

## Line-based room chat

Run the loopback server, then connect clients using a TCP terminal such as `nc`:

```bash
ROOM_CONFIG="$PWD/examples/corpus/022_room_chat/rooms.json" \
ROOM_PORT=8788 ROOM_STOP=/tmp/room-chat.stop build/corpus/022/corpus_022
```

The stop marker must initially be absent. Creating it stops the server and closes
all sockets; queued messages are not guaranteed to drain during server shutdown.
This example keeps rooms and messages in memory. The separate
[Paper Plane application](../telegram/README.md) provides the desktop/web interface
and persistent chat history.

Each command is a UTF-8 line ending in LF or CRLF. For example, two clients can
send `NICK Alice` / `NICK Bob`, then `JOIN workshop` and `SAY Hello, world!`.
Both receive `MSG <sequence> workshop <nickname> <text>`, including the sender.
Sequence numbers increase across all rooms. `WHO` lists the current room's
members, `ROOMS` lists occupied rooms, `PING text` returns `PONG text`, `STATS`
returns counters, and `QUIT` sends `BYE` before a bounded close. Nicknames are
ASCII, case-insensitively unique, and may be changed after joining; room names
are normalized to lowercase. JOIN, LEAVE and RENAME events notify room members.
Recoverable command errors begin with `ERR`; invalid UTF-8, control characters,
overlong lines and expired line/idle deadlines close the affected peer.

The five Python modules separate configuration, peer state, commands, transport
and startup. They use a readiness loop with per-peer command and write budgets.
`rooms.json` sets the peer/room limits, maximum line size, queue byte/line limits,
socket send-buffer hint and timeouts. A client whose outgoing queue exceeds
either bound is removed without waiting for it to read. Incomplete-line deadlines
do not reset when a slow client sends another byte. Empty rooms release capacity.

Acceptance checks run independent socket clients against both executables. They
verify exact Unicode text and whitespace, room isolation, nickname reuse,
200 coalesced commands, one-byte write budgets, malformed and incomplete lines,
idle expiry, queue limits, peer/room capacity and cleanup after a TCP reset. A
real nonreading peer fills its kernel buffer and application queue while two
healthy peers receive every tested message in order.

## Local SMTP capture

Run the native capture server:

```bash
SMTP_CONFIG="$PWD/examples/corpus/023_smtp_capture/smtp.json" \
SMTP_DATA=/tmp/smtp-capture SMTP_PORT=2525 \
SMTP_SHUTDOWN=/tmp/smtp-capture.stop build/corpus/023/corpus_023
```

Point a development mail client at `127.0.0.1:2525`, without TLS or authentication.
The server captures mail locally and does not relay it. It handles one active
connection at a time with bounded command and DATA deadlines. The default limit
is 100 messages, 100 recipients per message, and 1 MiB per message. `smtp.json`
also configures command count and timeout limits. Creating the shutdown marker
stops acceptance; an active session observes it between commands or reaches its
current I/O deadline. Keep the marker outside the dedicated capture directory.

Supported commands are HELO/EHLO, MAIL, RCPT, DATA, RSET, NOOP and QUIT. EHLO
advertises SIZE and 8BITMIME. Greetings accept ASCII DNS-style names and bracketed
IPv4 addresses. Mailboxes use ASCII dot-atom local parts and DNS-style domains;
the null reverse path is supported. Quoted local parts, address literals in
mailboxes, SMTPUTF8, AUTH, STARTTLS, relaying and delivery retries are outside this
capture subset. A second MAIL within a transaction requires RSET first.

DATA uses strict CRLF framing, removes one transparency dot from each stuffed
line, and preserves all remaining bytes. The message size includes CRLF and
excludes transparency dots and the terminator. BODY=8BITMIME permits high bytes;
NUL is rejected, and BODY=7BIT rejects high bytes. Size/body errors drain through
the terminator within a bounded discard budget, then reset the transaction.
Malformed/overlong framing, excessive discarded data or timeouts close that
session. Message lines allow 1,000 octets including CRLF, excluding the extra
transparency dot. This is an explicit test-service subset of the
[SMTP protocol](https://www.rfc-editor.org/rfc/rfc5321),
[SIZE extension](https://www.rfc-editor.org/rfc/rfc1870), and
[8BITMIME extension](https://www.rfc-editor.org/rfc/rfc6152), not a general mail server.

Each capture has an immutable `<id>.eml` and an envelope receipt in `index.json`.
The receipt includes sender, ordered unique recipients, greeting, body mode,
UTC time, size and SHA-256. The server syncs the message and directory before
atomically replacing the index, then sends its 250 reply. Restart verifies all
indexed bytes and removes unindexed message files left by interrupted writes.
The index is bounded at 8 MiB; retained messages must still fit the configured
limits after configuration changes.
Missing, altered or symlinked indexed files cause startup to fail; unrelated
files in the dedicated directory are preserved and rejected. Use one writer
per directory. An interrupted client can miss a successful commit and resend:
captures are not deduplicated. Back up the complete directory while stopped.

`SMTP_FAULT=before_message`, `after_message`, `after_index`, or `after_reply`
injects exit 75 at a publication boundary. Acceptance tests verify each boundary,
real process termination during DATA, exact MIME attachment bytes, independent
`smtplib` delivery, command-order errors, duplicate recipients, storage capacity,
CRLF fragmentation, slow-byte deadlines and corruption handling. All six Python
modules compile into the native server; the independent clients are test tools.

## RESP key-value server

The five-module application uses the existing TCP, dictionary, JSON, clock and
filesystem subset. It builds without handwritten application Rust:

```bash
KV_CONFIG="$PWD/examples/corpus/024_resp_store/kv.json" \
KV_STATE=/tmp/resp-state.json KV_PORT=6380 KV_STOP=/tmp/resp-store.stop \
build/corpus/024/corpus_024
```

The server binds to loopback and implements these commands through RESP2 arrays
of non-null bulk strings:

| Command | Result |
| --- | --- |
| `PING [value]` | Simple `PONG`, or an exact binary bulk-string echo |
| `GET key` | Binary value, or a null bulk string for an absent/expired key |
| `SET key value [EX seconds / PX milliseconds]` | `OK`; replaces the value and its previous expiration |
| `DEL key [key ...]` | Number of distinct existing keys removed |
| `INCR key` | Signed 64-bit integer reply; starts an absent key at one and retains an existing expiration |

Command names and EX/PX are case-insensitive. Keys and values can contain NUL,
invalid UTF-8, CRLF and RESP-looking bytes, and can be empty. Stored integers must
use canonical decimal spelling; whitespace, plus signs, leading zeros, `-0`,
non-integers and overflow are rejected without changing the value. Expiration
durations are positive decimal integers, bounded at 30 days. NX/XX, additional
Redis commands, RESP3, inline commands, TLS, authentication, transactions and
replication are outside this application. Its protocol and command rules follow
the named subset of the [RESP specification](https://redis.io/docs/latest/develop/reference/protocol-spec/),
[SET](https://redis.io/docs/latest/commands/set/) and
[INCR](https://redis.io/docs/latest/commands/incr/) contracts.

`kv.json` bounds peers, keys, key/value lengths, aggregate stored bytes and
incomplete-frame/idle deadlines. The readiness loop processes at most four
commands per peer per iteration and attempts partial nonblocking writes. Input
and output queues are each bounded at 128 KiB. A nonreading peer that exceeds
the output budget is disconnected. Each RESP frame permits at most 64 elements
per array, 128 total nodes, eight levels below the root, a 64-byte header and
64 KiB per bulk string. The parser handles nested frames and rejects valid RESP
values that are not command arrays. Malformed or over-budget frames close the
connection; ordinary command errors preserve it. Pipelined replies retain their
order, including valid replies queued before a malformed frame. A write half-close
drains complete queued commands; truncated input receives an error when possible.

The event loop serializes command execution, so increments from competing peers
are atomic. Every decoded request checkpoints the resulting state before its
reply is queued, including the effective clock and removal of expired keys.
The JSON snapshot keeps exact key/value bytes as lowercase hex. It is bounded
at 8 MiB and replaced atomically with filesystem sync. Expirations use persisted
Unix milliseconds and a clock high-water mark, preventing observed expiry from
being undone by a wall-clock rollback. Expiration is evaluated when a command
arrives; no background timer rewrites idle snapshots. `KV_CLOCK` can name an
integer-millisecond fixture file for deterministic tests; omit it for real time.
Use one server process per snapshot and keep configuration, clock and stop files
distinct from it. Startup rejects malformed snapshots and incompatible limits.

Create the stop marker to close the listener and peers. Server shutdown does not
promise to drain replies. `KV_FAULT=before_checkpoint`, `after_checkpoint` or
`after_reply` injects exit 75 for interruption tests. A lost reply can leave a
committed mutation; clients must not blindly retry non-idempotent increments.

Acceptance uses pinned `redis-py` 6.4.0, an independent byte codec, a 180-step state
oracle and four competing increment clients. It also verifies real and controlled
clocks, expiry at the exact deadline, persistence, corruption, three interruption
boundaries, process termination, half-closed pipelines, malformed nested frames,
queue limits and slot reuse after slow-reader eviction. The `corpus-checks` extra
installs the independent client for verification; the native server needs no Python.

## UDP service directory and retrying client

Application 025 keeps announcement validation, lease ordering, discovery paging,
retry/correlation rules and reports in six Python modules. The complete project
transpiles to one native binary with server and client modes:

```bash
DIR_MODE=serve DIR_PORT=8790 \
DIR_CONFIG="$PWD/examples/corpus/025_udp_directory/directory.json" \
DIR_REGISTRY=/tmp/udp-registry.json DIR_STOP=/tmp/udp-directory.stop \
build/corpus/025/corpus_025

# In another terminal:
DIR_MODE=client DIR_PORT=8790 \
DIR_CONFIG="$PWD/examples/corpus/025_udp_directory/directory.json" \
DIR_REQUESTS="$PWD/examples/corpus/025_udp_directory/requests.json" \
DIR_REPORT=/tmp/udp-client-report.json build/corpus/025/corpus_025
```

Both modes use numeric IPv4 loopback. Server port 0 selects an available port and
prints `LISTENING udp://127.0.0.1:<port>`; the client requires a nonzero port.
The server publishes a pretty JSON registry and a `REGISTRY` line whenever active
services or retained counts change, including expiry while no queries arrive.
Create `DIR_STOP` to stop it between bounded receive calls. Remove an old stop
marker before starting a new server.

Each UTF-8 JSON datagram contains a `request` ID. An announcement has these exact
fields:

```json
{"op":"announce","request":"room-1","id":"room","seq":1,"service":"chat","name":"Team room","port":8765,"ttl_ms":10000,"tags":["desktop","web"]}
```

Service/request IDs contain 1–40 ASCII letters, digits, underscores or hyphens.
Service kinds start with a lowercase letter and contain up to 24 lowercase
letters, digits, underscores or hyphens. Names contain 1–80 UTF-8 bytes without
ASCII controls. Announcements require a positive signed-64-bit sequence, port
1–65535, TTL 50–30000 milliseconds and at most eight unique lowercase ASCII tags
of 1–16 characters. Tag order is normalized. The advertised host comes from the
datagram source; the source port is not the service's identity.

A higher sequence replaces the service and starts a new lease. Lower sequences
fail with `stale_sequence`; an equal sequence with different contents or host
fails with `sequence_conflict`. An identical announcement returns `duplicate:true`
and **does not extend the lease**, even if the previous acknowledgement was lost.
An expired record remains a tombstone for `remember_ms`, so delayed duplicates
cannot revive it during that interval. At the retention deadline the ID is
forgotten and can be announced afresh. Both live and expired retained records
count against `max_services`.

Discover with `{"op":"discover","request":"find","limit":20,"after":"","service":"chat"}`.
`limit` (1–20), `after` (exclusive service ID) and `service` (empty means all) are
optional. Replies contain `services`, `next` and `more`; records are ordered by ID
and pages fit the datagram byte limit. Follow `next` while `more` is true.
Malformed, empty, non-UTF8 and truncated datagrams produce errors without changing
announcements. Discovery and duplicates never refresh expiry.

| Configuration field | Default | Allowed values |
| --- | --- | --- |
| `max_services` | 100 | 1–100 retained IDs |
| `remember_ms` | 60000 | 100–3600000 ms after lease expiry |
| `max_datagram` | 4096 | 1024–4096 bytes per request/reply |
| `reply_ms` | 200 | 20–5000 ms per client attempt/server send |
| `attempts` | 3 | 1–5 client attempts |

Configuration rejects unknown fields and noninteger values. `DIR_CLOCK` optionally
names a JSON integer Unix-millisecond fixture file. The server keeps an in-memory
clock high-water mark so rollback cannot resurrect an observed expired lease.
The registry is a current report, **not persistent state**: restart starts empty.
Keep configuration, clock, stop, request and report paths distinct within each
mode; overlapping paths and output symlinks are rejected.

The client loads 1–100 requests with unique IDs from a JSON array (at most 1 MiB).
It retries identical encoded bytes with absolute attempt deadlines and a maximum
of 32 received datagrams per attempt. It ignores wrong source ports/hosts, stale
request IDs, malformed JSON, invalid `ok` types and truncated replies. A correlated
error counts as a failed request; the remaining batch still runs. The client
atomically checkpoints after each response and writes a final report with
`complete`, `results` and `errors`. Exit 1 means at least one request failed or
exhausted its retries; an exhausted request has a null reply. This is a bounded
unicast protocol for trusted local peers; UDP delivery/order is not guaranteed,
and no authentication, multicast or broadcast discovery is implemented.

Acceptance uses independent UDP peers and a relay that drops a real accepted
announcement's first acknowledgement. All four Python/Rust server/client
combinations verify the batch and lost-ack retry behavior through
`tools/check_udp_directory.py`, saving `build/corpus/udp-directory/result.json`.

## DNS lookup diagnostic

Application 026 encodes queries, decodes DNS packets and compressed names,
selects address answers through CNAME chains, retries and publishes reports in
five Python modules. All five compile into a standalone executable. The packet
layout follows [RFC 1035](https://www.rfc-editor.org/rfc/rfc1035.html), with AAAA
records from [RFC 3596](https://www.rfc-editor.org/rfc/rfc3596.html).

```bash
DNS_CONFIG="$PWD/examples/corpus/026_dns_diagnostic/dns.json" \
DNS_REPORT=/tmp/dns-report.json DNS_TEXT=/tmp/dns-report.txt \
build/corpus/026/corpus_026
```

The sample expects a DNS server at `127.0.0.1:53`; edit a copy of `dns.json` to
select a reachable resolver. This diagnostic sends real DNS datagrams, not HTTP
requests or calls to the operating system's name resolver. A configuration looks
like this:

```json
{
  "host": "127.0.0.1", "port": 53, "timeout_ms": 500, "attempts": 3,
  "queries": [{"name": "example.com", "type": "A"}, {"name": "example.com", "type": "AAAA"}]
}
```

The server address must be canonical numeric IPv4, and its port must be 1–65535.
`timeout_ms` accepts 20–5000; `attempts` accepts 1–5. The configuration is at most
64 KiB and contains 1–100 distinct name/type pairs. Query names contain ASCII
letters, digits, underscores and hyphens in labels of 1–63 bytes; the expanded
wire name is at most 255 bytes. Root `.` is accepted. Case is normalized and a
missing trailing root dot is added. The entire batch is validated before report
files are replaced or queries sent. Output symlinks and overlapping/aliased
configuration/report paths are rejected.

Each query uses a fresh UDP socket and a random 16-bit ID. Retries preserve its
exact packet and source port. A reply must match the configured source IP/port,
ID, question name (case-insensitively), type and Internet class. Each attempt has
an absolute deadline and a limit of 64 received packets, including ignored ones.
Malformed or unrelated packets are counted and ignored while the attempt budget
remains. A correlated DNS error is a completed response, not retried automatically.

The decoder checks header/record lengths, reserved encodings, backward
compression pointers, pointer cycles, expanded name lengths and trailing bytes.
It permits at most 32 compression pointers and 160 traversal steps per name,
64 records across the three sections and 16 CNAME links. Answer selection uses
only Internet-class records of the requested type at the terminal CNAME name;
unrelated answers and additional-section addresses do not become results.
Conflicting or cyclic CNAME chains are rejected. Binary label bytes are displayed
with decimal escapes when needed, preserving label boundaries.

JSON results retain `records` from all sections, raw TTL values, aliases, canonical
names, addresses, response codes, flags, attempts and ignored-packet counts.
A/AAAA values are formatted as IP addresses; IPv6 uses eight hexadecimal groups
without zero-run compression. NS/CNAME/PTR values are decoded names. Other types
or classes retain hexadecimal RDATA after length validation. This is diagnostic
output, not a DNS cache or validation of every record type.

The program uses classic UDP messages capped at 512 bytes. A correlated reply
with the DNS truncation flag produces `truncated`; an oversized received datagram
is rejected. There is no EDNS, DNSSEC validation, TCP fallback, IPv6 transport,
resolver discovery or follow-up resolution of referrals/CNAME-only answers.
AAAA records still work over IPv4 transport. Statuses distinguish `ok`, `nodata`,
`nxdomain`, `dns_error`, `truncated` and `no_response`. The last status retains the
last parser diagnostic, if any. Exit 1 means at least one query produced no usable
address answer; later queries still run.

JSON and text reports are each replaced atomically before the batch, after each
query and at completion; they are not a two-file transaction. A process stopped
mid-batch leaves completed query results with `complete:false`. Restart starts a
new batch rather than resuming old results. The independent acceptance fixture
validates generated query bytes and response handling with 13 valid scenarios,
32 malformed-packet variants, wrong-source/ID noise, finite flood handling,
silent-peer exhaustion and actual process termination.

## WebSocket room server

Application 027 is a five-module, 444-SLOC Python project. Typed `Peer` and `Frame`
records become named Rust structs; the HTTP upgrade, frame parsing, fragmentation,
broadcasting and readiness loop all compile from Python. It includes a small
browser client, served from a separate HTML/JavaScript asset.

```bash
WS_CONFIG="$PWD/examples/corpus/027_websocket_rooms/rooms.json" \
WS_HOME="$PWD/examples/corpus/027_websocket_rooms/client.html" \
WS_PORT=8791 WS_STOP=/tmp/websocket-rooms.stop \
build/corpus/027/corpus_027
```

Open `http://127.0.0.1:8791/` in two windows, choose the same room and different
names, then connect. Room/name characters are ASCII letters, digits, `_` and `-`,
with limits of 32/24 characters. Each connected room/name pair is unique. A
WebSocket client connects to `/room/<room>/<name>` and receives a JSON `welcome`
with `room`, `name` and `max_bytes`. Send a text frame containing the message;
every connected member of that room, including its sender, receives JSON:

```json
{"type":"message","room":"lobby","name":"Alice","sequence":1,"text":"Hello 世界"}
```

The sequence is global to the running server. Rooms and messages are in memory;
there is no history, identity authentication, TLS or persistence. The server binds
only `127.0.0.1`; HTTP Host must be loopback with its listening port. Browser
origins must match that Host and use `http`; clients without Origin are accepted.
This is a bounded protocol example, not a public chat deployment or a replacement
for Paper Plane's persistent chat interface.

The [RFC 6455](https://www.rfc-editor.org/rfc/rfc6455.html) subset supports version
13, masked client text frames, text continuations (including split UTF-8),
interleaved ping/pong and close handshakes. Server frames are unmasked. Compression,
extensions, subprotocol selection and binary application messages are unsupported.
An offered extension is not negotiated; RSV bits then remain invalid. Reserved
opcodes, invalid masking, nonminimal lengths, fragmented/oversized control frames,
invalid close codes and incorrect continuation state close with 1002; binary
messages use 1003, invalid UTF-8 uses 1007 and excess text size uses 1009.
Close payloads accept the implemented standard codes 1000–1014 excluding
1004/1005/1006, plus 3000–4999, according to the
[IANA registry](https://www.iana.org/assignments/websocket/). Empty close payloads
are echoed. HTTP headers are capped at 8 KiB and 64 fields; duplicates, non-ASCII
values, bodies and invalid upgrade keys are rejected.

Configuration is exact integer JSON. Defaults are 32 peers, 8192 message bytes,
262144 queued output bytes per peer, 4 frames per readiness tick, 3-second
handshake/partial-message deadlines, 60-second receive-idle timeout, 500-ms close
handshake, 8192-byte send-buffer hint and 16384 bytes per write attempt.
`message_bytes` is 1–65536, `queue_bytes` is 8192–1048576 and must hold at least
`6 * message_bytes + 512` bytes for escaped JSON output. Control frames retain
their independent 125-byte limit. `write_bytes` can be as small as one byte.

Partial TCP writes retain the unsent bytes. A peer whose output queue overflows
is disconnected; it cannot block room members that keep reading. Handshake,
partial-frame and fragmented-message deadlines are absolute, so a steady drip
cannot hold a slot forever. Receive-idle peers close with 1001; partial-message
timeouts use 1008. Creating the optional `WS_STOP` marker initiates 1001 closes
and drains each connection until acknowledgment or its bounded close deadline.
Use a fresh marker path, or remove a marker from a previous run before restarting.

Acceptance uses `websockets==17.1` as an independent client and a separate raw
socket encoder/parser. It verifies payload lengths through 65536 bytes, 20 HTTP
rejections, 21 malformed-frame cases, split/coalesced TCP, continuous-drip
deadlines, capacity/rejoining, real nonreader eviction and 23 invalid configurations.
The native run disables Python's path and interpreter environment. The HTML asset
is checked byte-for-byte over HTTP. A separate two-tab browser check against the
native executable confirmed Unicode delivery, replies and literal markup display;
its screenshot is saved at `build/corpus/027/browser-check.jpg`. This manual browser
check is separate from the repeatable protocol acceptance suite.

## MQTT telemetry sink

Application 028 is a six-module, 435-SLOC Python project using the existing
transpiler subset. The variable-length decoder, CONNECT negotiation, enum/record
peer state, QoS-0 ingestion, validation and atomic persistence all compile to
Rust. The executable has no Python runtime or handwritten application Rust.

```bash
MQTT_CONFIG="$PWD/examples/corpus/028_mqtt_sink/sink.json" \
MQTT_STATE=/tmp/mqtt-telemetry.json MQTT_PORT=8792 \
MQTT_STOP=/tmp/mqtt-telemetry.stop \
build/corpus/028/corpus_028
```

It binds `127.0.0.1` only. A clean-session MQTT 3.1.1 client can connect with a
nonempty UTF-8 client ID of at most 64 bytes and publish arbitrary binary data
with QoS 0. An accepted connection receives CONNACK with Session Present zero.
A new connection using an active client ID disconnects the old connection.
The implementation follows the named packet formats in the
[OASIS MQTT 3.1.1 specification](https://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html).
It is a telemetry sink; SUBSCRIBE, QoS 1/2, persistent sessions, authentication,
Last Will, TLS and MQTT 5 are outside its implemented scope.

Each publication atomically updates a versioned JSON snapshot containing a global
sequence, per-topic history and the last retained payload. Payloads use lowercase
hexadecimal, preserving empty messages, NULs and arbitrary bytes. History records
include sequence, client ID, payload and the RETAIN flag. A retained publication
replaces the topic's retained value; an empty retained publication clears it.
Ordinary publications leave that value unchanged. Trimming old history does not
remove an independently retained value. These records are inspectable storage;
the application does not implement subscription delivery.

Use the same configuration/state environment with `MQTT_MODE=report` to validate
and print the snapshot without opening a socket:

```bash
MQTT_CONFIG="$PWD/examples/corpus/028_mqtt_sink/sink.json" \
MQTT_STATE=/tmp/mqtt-telemetry.json MQTT_MODE=report \
build/corpus/028/corpus_028
```

The report starts empty if no checkpoint exists. Startup and report mode validate
schema/version, canonical hex, topic/client strings, strictly increasing per-topic
sequences, global sequence uniqueness, retained/history agreement and configured
budgets. A corrupt or over-budget snapshot stops startup without modifying it.
Sequence exhaustion also preserves the checkpoint. One server process owns a
snapshot; simultaneous writers to the same path are not supported.

| Setting | Default | Accepted range |
| --- | --- | --- |
| `max_peers` | 16 | 1–64 |
| `max_topics` | 64 | 1–256 |
| `history` | 16 messages per topic | 1–128 |
| `topic_bytes` | 256 | 1–1024 UTF-8 bytes |
| `payload_bytes` | 16384 | 0–65536 bytes |
| `total_bytes` | 1048576 | 64–1048576 stored data bytes |
| `packet_bytes` | 66562 | 13–131072 bytes after the fixed header |
| `queue_bytes` | 4096 | 64–65536 pending reply bytes per peer |
| `packets_per_tick` | 4 | 1–32 |
| `write_bytes` | 4096 | 1–65536 bytes per write attempt |
| `handshake_ms`, `partial_ms` | 3000 each | 50–30000 ms |
| `close_ms` | 300 | 50–5000 ms to drain a refusal/EOF reply |

The packet budget must accommodate `topic_bytes + payload_bytes + 2`.
`total_bytes` counts topic-name bytes once, retained payload bytes, and payload/
client-ID bytes for each history record. The encoded snapshot has a separate
8-MiB cap. Bounds, unknown settings and booleans in numeric settings are rejected
before listening. Configuration, snapshot and stop paths must not overlap or
alias existing files; snapshot symlinks are rejected.

Remaining lengths use one to four bytes and must be minimally encoded in this
profile; oversized lengths are rejected before buffering their payload. UTF-8
fields reject malformed encodings and NUL; a BOM remains part of the string.
Topic names must be nonempty and cannot contain `+` or `#`. Unsupported packet
types, QoS, DUP on QoS 0, invalid flags, truncated fields and trailing CONNECT data
close the connection. Unsupported protocol versions and client identifiers use
CONNACK codes 1 and 2; valid but unsupported session/Will/credential options use
code 5. No malformed or over-budget publication modifies the previous snapshot.

PINGREQ receives PINGRESP; DISCONNECT closes without a reply. A nonzero Keep Alive
is enforced at 1.5 times the negotiated seconds after the last complete packet;
zero disables that timer. Independent absolute handshake and partial-packet
deadlines prevent a drip of bytes from keeping incomplete work alive. Fully
buffered packets continue across the per-tick budget after TCP EOF; an incomplete
tail never commits. Partial output writes retain unsent bytes. A peer exceeding
its output queue is disconnected while other peers continue.

QoS 0 has no publication acknowledgement and no exactly-once delivery promise.
The sink persists each accepted message before processing the next packet on that
connection. Tests use a subsequent PING response as an ordering observation, not
as a new MQTT acknowledgement. Creating `MQTT_STOP` closes active peers and exits;
completed checkpoints survive, while unprocessed input can be discarded. Use a
fresh stop-marker path or remove an old marker before starting another run.

Acceptance runs against CPython and standalone Rust with Python unavailable.
It uses `paho-mqtt==2.1.0`, an independent raw packet encoder and a separate history
model: payloads through 65536 bytes, all relevant remaining-length boundaries,
7 CONNECT refusals, 48 malformed packets, 56 invalid startups, one-byte writes,
client takeover, real keep-alive timing, four concurrent publishers beside an
incomplete peer, 64 buffered publications followed by EOF, output-queue pressure,
sequence overflow, restart and real process termination during a partial packet.
Fault injection immediately before/after atomic checkpoint publication verifies
old/new state recovery; later storage corruption isolates the failing publisher
and does not destroy the existing file.

## Resumable TCP file transfer

Application 029 is a six-module, 461-SLOC Python project. One executable provides
both the sender and receiver; every module is transpiled. The Python keeps
configuration and manifests in `model.py`, framing in `wire.py`, durable state in
`storage.py`, and the two protocol loops in `sender.py` and `receiver.py`.
Generated Rust uses module-prefixed function names, Python source-location comments
and a symbol map in `.py2rust-project.json`.

Start the receiver from the repository root:

```bash
XFER_CONFIG="$PWD/examples/corpus/029_tcp_transfer/transfer.json" \
XFER_ROOT=/tmp/transferred-files XFER_PORT=8793 \
XFER_STOP=/tmp/tcp-transfer.stop build/corpus/029/corpus_029
```

Then send a file in another terminal:

```bash
XFER_MODE=send XFER_HOST=127.0.0.1 XFER_PORT=8793 \
XFER_CONFIG="$PWD/examples/corpus/029_tcp_transfer/transfer.json" \
XFER_SOURCE=/path/to/document.pdf XFER_NAME=document.pdf \
build/corpus/029/corpus_029
```

Successful output is readable JSON containing the manifest, attempt count,
starting resume offset and completion status. The destination is
`/tmp/transferred-files/document.pdf`. `XFER_NAME` defaults to the source basename;
spaces and Unicode are supported. Names must contain 1–240 UTF-8 bytes, cannot
start with a dot, and cannot contain either slash, ASCII control characters or DEL.
The receiver binds IPv4 loopback and handles one connection at a time. The sender
accepts numeric addresses. This is a local transfer protocol without authentication
or encryption. Creating `XFER_STOP` requests shutdown after the active session;
remove an old marker before starting again. Configuration and stop paths must
be outside the receiving directory.

| Configuration | Default | Accepted bounds |
| --- | --- | --- |
| `max_bytes` | 134217728 | 0–1073741824 bytes per file |
| `max_files` | 128 | 1–1024 tracked manifests, including completed transfers |
| `chunk_bytes` | 65536 | 1–65536 bytes |
| `io_ms` | 3000 | 50–30000 ms per frame operation |
| `session_ms` | 30000 | 100–300000 ms per connected session |
| `attempts` | 3 | 1–10 sender connection attempts |
| `pause_ms` | 100 | 0–5000 ms between failed attempts |

Unknown keys, wrong types and out-of-range settings fail before listening.
`XFER_PORT` defaults to 8793; receiver port 0 selects an ephemeral port. Increase
`session_ms` when transferring larger files on slow storage. A session deadline
covers that connection's network operations and is renewed on reconnect; hashing
and filesystem operations are synchronous. File capacity includes abandoned
partial transfers and completed metadata, with no automatic eviction.

Frames begin with a four-byte big-endian length. JSON control frames contain at
most 1024 UTF-8 bytes. The first frame is exactly
`{"version":1,"name":"document.pdf","size":123,"sha256":"<64 lowercase hex digits>"}`.
The receiver replies with `ok`, `offset`, `prefix`, `chunk_bytes` and `complete`.
A chunk uses `{"op":"chunk","offset":0,"sha256":"<chunk digest>"}` followed by
a binary frame. Finish uses `{"op":"finish"}`. Chunk acknowledgements contain
the committed offset and SHA-256 of that prefix; they are sent only after the
file is synced and its checkpoint atomically published. Errors use
`{"ok":false,"error":"..."}` where the connection is still writable.

Partial bytes and metadata live in `.incoming`. A reconnect verifies the committed
prefix and truncates an uncommitted tail. The sender independently checks the
receiver's offset and prefix against its source before resuming, validates every
acknowledgement, and verifies size/digest again before finish. Lost replies cause
bounded reconnects. A repeated completed transfer succeeds after checking the
published bytes. Empty files follow the same protocol.

Publication verifies the whole file, checkpoints a `ready` phase, creates a hard
link without overwriting a destination, removes the partial name, and checkpoints
`published`. Restart can recover either intermediate phase. An unrelated existing
file is rejected even when its bytes match. Symlink paths, checkpoint/data inode
aliases and damaged checkpoints are rejected. The receiver expects exclusive
ownership of its staging directory; path checks do not provide isolation from
another process concurrently replacing directory entries.

Acceptance uses independent framing/digest oracles, malformed requests and replies,
startup validation, source changes, byte drips, absolute deadlines, retry exhaustion,
process termination and `XFER_FAULT` interruption points `after_write`,
`after_checkpoint`, `before_publish`, `after_publish` and `after_cleanup`.
Both processes stream 160 MiB with each limited to 128 MiB of address space.
`tools/check_tcp_transfer.py` runs all four Python/Rust sender/receiver combinations,
deliberately loses a committed chunk's acknowledgement, and checks exact resumed
bytes and repeated completion. Native runs disable all Python paths.

## Unix-domain command bus

Application 030 is a six-module, 389-SLOC Python project. Its server and batch
client compile together into `build/corpus/030/corpus_030`. Framing, command
dispatch, IDs, queue scheduling and reports remain in Python. The shared runtime
supplies general Unix socket operations and scoped path cleanup.

Start a server from the repository root:

```bash
install -d -m 700 /tmp/py2rust-bus
BUS_CONFIG="$PWD/examples/corpus/030_unix_bus/bus.json" \
BUS_SOCKET=/tmp/py2rust-bus/command.sock BUS_STOP=/tmp/py2rust-bus/stop \
build/corpus/030/corpus_030
```

Run the provided batch in another terminal:

```bash
BUS_MODE=client BUS_CONFIG="$PWD/examples/corpus/030_unix_bus/bus.json" \
BUS_REQUESTS="$PWD/examples/corpus/030_unix_bus/requests.json" \
BUS_SOCKET=/tmp/py2rust-bus/command.sock BUS_REPORT=/tmp/py2rust-bus/report.json \
build/corpus/030/corpus_030
```

The client prints and atomically saves its report. It exits 0 when all commands
succeed, 2 for valid command-error replies, and nonzero for invalid replies or
transport failures. Failed framing/correlation leaves the previous report intact.
Repeating a batch can reuse the server's bounded receipt cache; the client does
not retry automatically. Configuration, request, report, stop and socket paths
must be distinct and must not alias existing files.

Frames have a four-byte big-endian byte length followed by UTF-8 JSON. Request
objects contain exactly `id`, `op` and `args`. IDs use 1–64 ASCII letters, digits,
underscores, dots, colons or hyphens. Successful replies are
`{"id":"...","ok":true,"result":...}`; errors are
`{"id":"...","ok":false,"error":{"code":"...","message":"..."}}`.
Invalid or unavailable request IDs use the empty string.

| Command | `args` | Result |
| --- | --- | --- |
| `echo` | Any JSON value within `value_bytes` when serialized | That value |
| `sum` | At most 128 integers, each between −10¹² and 10¹² | Exact integer total |
| `set` | `{"key":"name","value":"text"}` | Stored-key acknowledgement |
| `get` | Existing key string | Stored text |
| `delete` | Existing key string | Removed text |
| `keys` | `null` | Sorted keys, subject to the reply frame limit |
| `stats` | `null` | Key and receipt counts before caching this reply |
| `stop` | `null`, with `allow_stop: 1` | `"stopping"`, then graceful shutdown |

Keys use the ID syntax. Stored strings are bounded by their serialized JSON byte
length, including quotes/escapes. Reusing a cached ID with an identical request
returns its original reply; different content produces a conflict. Success and
command-error replies are retained in FIFO order. Evicted IDs execute again.
Values and receipts are process-local and start empty after restart.

| Configuration | Default | Bounds |
| --- | --- | --- |
| `max_peers` | 32 | 1–128 simultaneous connections |
| `frame_bytes` | 16384 | 1024–65536 bytes |
| `queue_bytes` | 65536 | 1028–262144 bytes per peer |
| `keys` | 128 | 1–1024 stored keys |
| `receipts` | 256 | 1–1024 cached request/reply pairs |
| `value_bytes` | 4096 | 1–8192 serialized bytes |
| `session_ms` | 60000 | 100–300000 ms per connection |
| `partial_ms` | 3000 | 50–30000 ms per partial server frame/client request |
| `drain_ms` | 1000 | 50–10000 ms for shutdown/EOF reply draining |
| `write_bytes` | 65536 | 1–65536 bytes per nonblocking write |
| `allow_stop` | 0 | 0 or 1 |

The queue must hold a frame plus its prefix; `frame_bytes` must be at least
`2 * value_bytes + 512`. Unknown keys, wrong types, booleans in integer fields
and invalid bounds fail before listening. Partial-frame and session deadlines
are absolute. Each loop handles at most eight requests per peer, pauses dispatch
when the reply queue lacks room, and retains unsent bytes after a partial write.
Buffered complete frames continue after EOF; an incomplete tail gets a frame error.

Creating `BUS_STOP` or issuing an enabled `stop` command stops new dispatch,
drains queued replies within `drain_ms`, closes peers and removes the owned socket.
Remove an old stop marker before restarting. A killed process can leave a stale
socket; startup reclaims it only when a bounded probe reports connection refused.
An active listener, ordinary file, directory or symlink is preserved. Cleanup
also preserves a socket path replaced with another file.

Use a parent directory writable only by the intended account. Filesystem
permissions control access; there is no application login or peer-credential
policy. Device/inode checks do not isolate the parent directory from hostile
concurrent replacement. The parent must exist and the resolved path must fit
within 107 UTF-8 bytes. Abstract sockets and descriptor passing are unsupported.

Acceptance uses independent frames, eight concurrent clients, split headers,
25 pipelined requests and an incomplete EOF tail, malformed JSON, wrong types,
cache conflicts/eviction, real backpressure and absolute deadlines. It checks
normal stop, process termination, stale-path restart, active listeners and
replacement-file preservation. Independent fake servers verify malformed/slow
replies and preservation of the batch client's previous report.
`tools/check_unix_bus.py` runs all four Python/Rust server/client combinations,
including repeated batches and socket cleanup. Native runs disable Python paths.

## Directory inventory reporter

Application 031 is a four-module, 276-SLOC Python project. Configuration,
iterative traversal, exclusions, aggregation and manifest publication all compile
into `build/corpus/031/corpus_031`; the application has no handwritten Rust.

From the repository root:

```bash
INVENTORY_CONFIG="$PWD/examples/corpus/031_inventory/inventory.json" \
INVENTORY_ROOT="$PWD/examples/corpus/031_inventory" \
INVENTORY_REPORT=/tmp/py2rust-inventory-report.json \
build/corpus/031/corpus_031
```

`INVENTORY_CONFIG` defaults to `inventory.json`. `INVENTORY_ROOT` overrides the
configuration's `root`, which defaults to `tree`. `INVENTORY_REPORT` defaults to
`inventory-report.json`. The report parent must exist. The report must be outside
the canonical input tree, must not be a symlink or alias the configuration, and
must be a regular file if already present. These rules keep output publication
from altering the scanned tree; `/` cannot be the input root under this policy.
An explicitly selected symlink root resolves once to its target directory.

The program writes a readable JSON manifest atomically and prints a compact JSON
summary. Exit 0 means the selected tree was completely observed under the exclusion
policy; exit 2 means a valid partial manifest contains errors or traversal omissions.
Invalid configuration, output-path conflicts or an oversized encoded manifest fail
before replacing the previous report.

| Configuration | Default | Bounds / meaning |
| --- | --- | --- |
| `root` | `tree` | Existing directory, unless overridden by `INVENTORY_ROOT` |
| `exclude` | `[]` | At most 128 regex searches over root-relative paths; 1024 UTF-8 bytes per pattern |
| `max_depth` | 64 | 0–256; root is depth 0; a directory at this depth is recorded without listing it |
| `max_entries` | 20000 | 1–200000; counts root, scheduled entries and excluded path records together |
| `max_children` | 10000 | 1–100000 immediate names per directory; exceeding it records a listing error |
| `max_report_bytes` | 33554432 | 1024–134217728 encoded UTF-8 bytes |

The sample config excludes `.git` components. Excluding a directory skips its
subtree and records the directory's relative path once. The root itself is always
recorded. Directory listing returns all sorted names or an error; it does not
pick an arbitrary subset when a directory exceeds its bound. Global entry and
depth limits produce explicit omissions. Exclusions are deliberate and do not
make an otherwise successful manifest incomplete.

Entries are sorted by relative path. Successful rows contain `kind`, apparent
`size`, permission `mode`, `device`, `inode`, hard-link count, and integer
`mtime_ns`/`ctime_ns` timestamps. Timestamps are nanoseconds since the Unix epoch;
`ctime_ns` records inode changes rather than file creation. The root uses `.`.
Directory rows have a `scan` result; symlink rows preserve their raw target text.
Broken and cyclic symlinks are recorded without following them. FIFOs, sockets
and device nodes are classified through metadata; tree file contents are not loaded.

An unreadable directory retains its metadata and receives a listing error, while
other subtrees continue. A metadata failure retains a row with its path, depth
and failed operation. Unrepresentable UTF-8 names invalidate that directory's
listing; unrepresentable symlink targets retain link metadata with a target error.
Out-of-range metadata integers/timestamps are also reported as entry errors.
Traversal is a best-effort observation of the filesystem. Its no-follow policy
assumes stable directory entries; concurrent replacements can race with path
resolution, and files may change between observations. Conflicting sizes observed
for the same inode are reported explicitly.

`logical_bytes` counts each regular-file pathname. `unique_files` and `unique_bytes`
count each `(device, inode)` once, so hard links are distinguishable from separate
files. These are apparent sizes, including sparse-file holes, rather than allocated
disk blocks. Extension groups contain pathname counts and apparent byte totals:
use the lowercase final suffix, or `(none)` for extensionless names, single-dot
hidden files and trailing dots. Empty directories are counted only after a complete
listing; directories containing excluded children are still nonempty. With no
regular files, both endpoints of `file_mtime_ns` are zero.

Acceptance compares complete rows and totals against independent `os.walk`,
`lstat` and extension grouping. Fixtures include Unicode/control content, a sparse
file larger than 4 GiB, differently named hard links, negative and nanosecond
modification times, unreadable entries, empty directories, FIFOs, sockets,
external/broken/cyclic symlinks, invalid UTF-8 and timestamp overflow. It verifies
byte-identical repeated manifests, every traversal limit, preserved prior output,
configuration/path rejection, and a 2,000-file tree in each engine with Python
unavailable during native runs.

That scale fixture exposed full-container cloning during indexed reads. The
compiler now borrows named containers for reads and length checks while returning
owned values. On this machine's unoptimized build, the measured 2,000-file native
run improved from about 7.4 seconds to 0.35 seconds. These are local measurements,
not a throughput guarantee. Separate regressions verify large list/dictionary
lookups under a 128 MiB address-space limit and preserve value-copy semantics.

## Batch rename planner

Application [032](032_rename_planner/main.py) compiles four Python modules into a
standalone native executable. A JSON configuration selects 1–128 relative paths,
ordered regex rules applied to basenames, optional explicit destination overrides,
and a per-file hashing limit (8 MiB by default, at most 64 MiB). For example:

```json
{
  "root": "/tmp/rename-demo/tree",
  "paths": ["old-notes.txt", "old-photo.png", "a", "b"],
  "rules": [{"pattern": "^old-", "replace": "saved-"}],
  "overrides": {"a": "b", "b": "a"},
  "max_bytes": 8388608
}
```

Put configuration and sidecars outside the input tree, in existing directories:

```bash
export RENAME_CONFIG=/tmp/rename-demo/rename.json
export RENAME_PLAN=/tmp/rename-demo/plan.json
export RENAME_JOURNAL=/tmp/rename-demo/journal.json
RENAME_MODE=preview build/corpus/032/corpus_032
```

Review the source/destination rows and `id` in the resulting plan. Then set
`RENAME_APPROVE` to that exact reviewed ID and run:

```bash
export RENAME_APPROVE='<reviewed plan id>'
RENAME_MODE=apply build/corpus/032/corpus_032
RENAME_MODE=reverse build/corpus/032/corpus_032
```

Keep both the plan and its journal for recovery and reversal. An interrupted
apply resumes by repeating `apply`; finish that forward pass before starting
`reverse`. Reversal is itself resumable. Repeating an already completed mode
validates the resulting tree and succeeds without moving it again. A reversed
plan cannot be reapplied: preview a new plan using fresh sidecar paths.

Preview rejects duplicate destinations, existing destinations that will not be
vacated, unsafe paths, symlinked ancestors, overlapping directory selections,
unsupported file kinds and cross-device moves. These failures leave selected
entries untouched. Rules use the shared regex subset with **literal** replacement
strings; capture-group substitution is unsupported. Source directories may move
with their contents, and final symlinks move as links, including dangling links.
Source/destination parents must already exist. Relative names are at most 1,024
UTF-8 bytes, each component at most 255; `.py2rust-rename*` is reserved.

Apply checks approved inode identities, permissions, modification times and
streamed SHA-256 file contents, plus raw symlink targets and parent identities.
Directory guards cover the directory entry, not a recursive content snapshot:
editing a contained file is preserved when its parent directory is reversed.
New/removed children can change the directory timestamp and prevent reversal.

All moving entries first receive unique staging names; only then are their final
names published. This supports swaps and cycles. Each move atomically refuses
any existing destination, synchronizes both parent directories, and checkpoints
an atomic journal. Recovery accepts only the exact recorded state or the state
one pending move ahead, covering interruption after rename but before checkpoint.
An I/O failure during execution can leave staging names and a pending journal;
correct the cause and resume. The **whole batch is not one atomic filesystem
transaction**, and external readers can observe staging.

The persistent root-wide `.py2rust-rename.lock` serializes cooperating processes,
even when they choose different journal paths. Do not delete it while processes
may be using it. Use a protected, stable local tree and sidecar directory: this
advisory lock does not stop unrelated writers, and path checks do not protect
against hostile concurrent ancestor replacement. Post-preview changes cause a
conflict without overwriting the changed entry. Durability depends on the local
filesystem honoring synchronization; tests exercise process crashes and real
permission failures, not simulated power loss.

The independent checker compares inode/content/name snapshots, exercises 50
forward/reverse interruption boundaries and a killed process, and resumes after
denied destination writes and denied journal updates. `RENAME_STOP=label:step`
exits with status 75 at a test boundary; `RENAME_PAUSE=label:step` pauses there for
60 seconds. Labels are `journal`, `before`, `renamed`, `synced`, and `saved`;
move indices start at zero, while `saved` uses the completed-move count. Leave
both variables unset for ordinary runs.

## Duplicate-file finder

Application [033](033_duplicate_finder/main.py) compiles six Python modules into
one native executable. It traverses a directory, excludes matching paths, groups
regular files by size and digest, and confirms matching candidates byte for byte.
Symlinks and special files are reported as ignored; symlinks are never descended
into. Multiple names for one inode are reported as existing hard links, not
independent duplicate copies. Files with a unique size need no content read.

A configuration can start with:

```json
{
  "root": "/tmp/my-files",
  "exclude": ["(^|/)\\.git(/|$)"],
  "min_size": 0,
  "max_size": 1073741824,
  "max_hash_bytes": 1073741824,
  "max_compare_bytes": 1073741824,
  "max_comparisons": 100000,
  "chunk_bytes": 65536,
  "digest_chars": 64
}
```

Run the native program directly, with output parents already present:

```bash
DUPLICATE_CONFIG=/tmp/duplicates.json \
DUPLICATE_REPORT=/tmp/duplicate-report.json \
DUPLICATE_PLAN=/tmp/deduplication-plan.json \
build/corpus/033/corpus_033
```

Omit `DUPLICATE_PLAN` to write only the report. Both output paths must be outside
the input root, distinct from the configuration and each other, and cannot be
symlinks or special files. Existing regular outputs are atomically replaced.

The report chooses the lexicographically first observed pathname as the keeper
for each confirmed group and retains every inode's aliases, metadata and full
SHA-256 digest. The optional plan names the redundant aliases, keeper, expected
metadata and content digest. It is **for review only**: this application never
executes deletions. A consumer must revalidate the entries and their contents
before acting; the plan explicitly carries `requires_revalidation: true`.

`reclaimable_logical_bytes` counts the apparent sizes of redundant inodes only
when all their hard links were observed. An inode with another alias outside the
selected scan contributes zero: removing the listed names would leave its data
linked elsewhere. Existing hard-link aliases do not multiply the estimate, and
sparse-file apparent sizes are not a prediction of physical disk space reclaimed.

Hashing and comparisons use bounded chunks. Hash work reserves each file's size
before reading; each comparison reserves both complete sizes, even if a mismatch
is found early. These conservative counters enforce the configured budgets,
plus an EOF probe of at most one byte per stream to detect growth. All candidates
in a digest bucket are discarded if comparison fails or its budget is exhausted.
Empty files still require an EOF check and a comparison slot; their byte charge
is zero.

`digest_chars` controls candidate bucketing (1–64 hexadecimal characters, default
64). Every hashed file still receives a full SHA-256 digest, and candidates always
undergo byte comparison. Short prefixes are useful for measuring collision-heavy
bucketing; the checker deliberately puts three different byte sequences into one
prefix bucket and verifies that only actual equal files are grouped.

The default traversal limits are depth 64, 20,000 entries including directories
and excluded names, and 10,000 children per directory. Configured depth may reach
256, entries 200,000 and children 100,000. The per-file size and hash budgets may
reach 1 TiB, comparison bytes 2 TiB, comparisons one million, and chunk size 1 MiB.
`min_size`/`max_size` and exclusions define deliberate selection; hitting traversal
or I/O budgets makes the scan incomplete. Reports default to a 32 MiB byte limit
(`max_report_bytes`, configurable from 1 KiB to 128 MiB).

Metadata is checked before/after reads and again for all observed files and
directories before publication. Access-time changes are excluded from those
guards. Disappearing, replaced, unreadable or changed entries, invalid UTF-8 names,
and exhausted traversal/I/O budgets produce errors or omissions. Exit status 2
means a partial report, with `complete: false`, `ready: false`, and no plan actions.
A prior actionable plan is replaced with this non-actionable result. Other failures
return nonzero; validation/size failures preserve previous outputs.

The report and optional plan are separate atomic files, not one atomic pair.
Their IDs must match (`report.id == plan.report_id`); a failed second publication
can leave an older plan. This is a guarded observation of a stable local tree,
not an atomic filesystem snapshot or protection against hostile ancestor races.
Concurrent changes after validation always require another check before deletion.

Acceptance evidence includes independent inode/content oracles, Unicode and binary
files, empty files/trees, hard links outside the root, deliberate digest-prefix
collisions, permission failures, exact budgets, changed inputs at three phases,
output failures and stale-plan invalidation. Both engines process two files of
160 MiB plus seven bytes, and a 1,000-file duplicate group, under a 128 MiB
address-space limit.

This application exposed repeated copying of growing collections. Indexed
`append`/`extend`, borrowed nested reads and borrowed membership reduced one local
unoptimized 1,000-file native run from about 7.4 seconds to 0.44 seconds; Python
was about 0.3 seconds. These measurements are evidence for the change, not a
throughput guarantee. Test-only `DUPLICATE_PAUSE` phases are `scanned`, `hashed`
and `compared`; `DUPLICATE_CONTINUE` must name an external file the test creates
to release the pause, with a bounded wait of roughly 30 seconds. Leave both unset
for normal use.

## 034: Incremental snapshot backup

[Six Python modules](034_snapshot_backup/main.py), 485 substantive source lines,
compile together into `build/corpus/034/corpus_034`. Application traversal,
manifest validation, incremental decisions, retention and restore are all Python;
the native executable uses shared filesystem/hash operations and no Python runtime.

Create separate source and repository directories, then put this configuration
in `backup.json` in your working directory (all five fields are required):

```json
{
  "repository": "/tmp/backup-demo/store",
  "source": "/tmp/backup-demo/source",
  "keep": 3,
  "max_entries": 10000,
  "max_bytes": 1073741824
}
```

Use an absolute executable path if running from another directory:

```bash
BACKUP_MODE=init build/corpus/034/corpus_034
BACKUP_MODE=snapshot BACKUP_VERSION=before-edit build/corpus/034/corpus_034
BACKUP_MODE=snapshot BACKUP_VERSION=after-edit build/corpus/034/corpus_034
BACKUP_MODE=list build/corpus/034/corpus_034
BACKUP_MODE=restore BACKUP_VERSION=before-edit BACKUP_DEST=/tmp/backup-demo/restored build/corpus/034/corpus_034
```

`BACKUP_CONFIG` overrides `backup.json`. Default mode is `list`. Snapshot and
restore require a version name containing 1–64 ASCII letters, digits, underscores
or hyphens. Names are immutable while retained; retention orders versions by a
monotonically increasing sequence, independent of wall-clock changes. The newest
`keep` versions (1–1000) survive each successful snapshot. Source and repository
must be disjoint trees; restore requires a nonexistent destination outside the
repository with an existing parent. Existing targets are never overwritten.

A bounded breadth-first scan records files, directories and raw UTF-8 symlink
targets, without following symlinks. Unsupported special files, unreadable entries,
invalid UTF-8, excessive depth or exhausted bounds abort the snapshot. Entry limits
include the root; byte limits sum apparent sizes across file paths, including hard
link aliases. `max_entries` is 1–10000, `max_bytes` is 1–1 TiB, depth is at most 64,
and relative paths are at most 2048 UTF-8 bytes. Restore checks the same entry/byte
budgets before creating its staging directory. Documents are limited to 8 MiB.

Every file is hashed from its bytes, so size/mtime alone never marks it unchanged.
SHA-256 names identify stored objects. Existing objects are verified and reused;
new objects are copied in 64 KiB chunks, hashed again and synchronized before
publication. Files with identical contents share storage, while restore preserves
which paths were actual hard links within the source tree. Independent duplicate
files remain separate inodes after restore. Files, empty directories, hard links,
symlink targets, ordinary permission bits and exact modification nanoseconds are
restored. Ownership, ACLs, extended attributes, set-id/sticky bits, access/change
times, sparse allocation and hard links outside the source tree are not preserved.

The persistent `.backup.lock` serializes cooperating commands. A snapshot stages
objects and a checksummed manifest privately; a no-overwrite rename publishes the
manifest only after its data is durable. Source metadata is checked before/after
reads and again before publication. This detects observed changes, but is not an
atomic filesystem snapshot: use a quiescent source and stable ancestor directories.
The repository also requires protection from unrelated writers. SHA-256 checksums
detect corruption; they do not authenticate a maliciously rewritten repository.

Retention removes expired manifests and synchronizes that directory before deleting
unreferenced objects. An interruption can leave extra versions/objects, which the
next successful snapshot can prune; it cannot make a partial snapshot visible.
An error after publication may still leave a complete version: inspect `list`
before retrying its name. `list` validates manifests and object entry types, not
every object's contents; restore checks the bytes it consumes. Corruption causes
an explicit failure, never a silently shortened restore.

Restore builds a private sibling directory named
`.<destination-name>.backup-incomplete`, sets child metadata before parents, then
publishes the completed directory without replacing existing entries. A failed or
killed restore leaves that unpublished directory for inspection. Remove it only
after reviewing it, then retry. Unpublished snapshot temporary files inside the
repository are cleaned automatically by the next locked command. Initializing an
existing populated repository is rejected; partial initialization with empty
managed directories can be retried, while a corrupt format document requires
inspection. Retention and garbage collection run on `snapshot`, not `list`.

The independent acceptance checker compares complete restored tree contents,
link groups, permissions and nanosecond timestamps to OS observations. It verifies
unchanged object identity, same-size/mtime content changes, metadata-only versions,
old-version restore and retention, seven injected snapshot boundaries, three killed
snapshots, three changing-source cases with lock contention, three interrupted
restores, corrupt objects/manifests, invalid inputs, real filesystem write failures,
and recovery after interrupted retention. Both engines also back up and restore a
160 MiB + 17 byte file under a 128 MiB address-space limit, then verify that a second
snapshot writes no new objects. `BACKUP_FAIL` and `BACKUP_PAUSE` are test hooks;
`BACKUP_CONTINUE` names the external signal file used by coordinated fixtures.
Leave these unset for ordinary use.

## 035: Two-tree synchronization planner

[Six readable Python modules](035_sync_planner/main.py), 432 substantive lines,
compile into `build/corpus/035/corpus_035`. This is a complete planning application:
it scans two trees, compares them with an optional common baseline, preserves
conflicts, emits ordered operations, and validates a dry run. It never applies
operations to either input tree. All application logic transpiles from Python;
the generated executable needs no Python interpreter.

Put these five required fields in `sync.json`, using disjoint existing roots:

```json
{
  "source": "/tmp/sync-demo/source",
  "destination": "/tmp/sync-demo/destination",
  "exclude": ["(^|/)cache($|/)"],
  "max_entries": 10000,
  "max_bytes": 1073741824
}
```

Run the compiled binary from the directory containing that configuration, or
supply `SYNC_CONFIG`. Use an absolute executable path from another directory:

```bash
SYNC_MODE=plan build/corpus/035/corpus_035
SYNC_MODE=baseline build/corpus/035/corpus_035
```

`plan` is the default. It writes `sync-plan.json`; `SYNC_PLAN` overrides that path.
`baseline` writes `sync-baseline.json`; `SYNC_BASELINE` overrides that path for both
modes. Baseline capture requires both included trees to match. It records the two
canonical root paths, exclusion policy and signatures under a canonical SHA-256
checksum. A missing baseline permits an initial plan; an invalid or mismatched
baseline causes a failure. Capture a new common baseline after synchronization
and explicit resolution of conflicts. Planning alone never advances it.

| Observed state | Decision |
| --- | --- |
| Source and destination signatures match | No operation |
| Destination still matches the baseline, source changed | Plan the source change |
| Source entry is new and destination has no corresponding entry | Plan creation |
| Destination changed or was deleted independently | Preserve it as a conflict |
| Both sides differ from the baseline and from each other | Preserve a conflict |
| No baseline and both entries differ, or only the destination exists | Preserve a conflict |
| Replacing/removing a directory would destroy a changed descendant | Preserve the whole subtree as a conflict |
| Removing a directory would destroy excluded descendants | Preserve the whole subtree as a conflict |

File signatures use actual streamed SHA-256, apparent size and ordinary permission
bits. Directories compare permission bits; symlinks compare raw targets without
following them. Timestamps do not decide whether content changed. Read-only scans
also record device/inode, size, mode, link count and modification/change nanoseconds
as guards, then recheck them before publishing a report. Changes observed during
scanning/planning fail without replacing the last valid report. Access times can
change as a normal consequence of reading. The scanner requires a quiescent tree
and stable ancestor directories; this is not an atomic filesystem snapshot.

Operations are `remove`, `mkdir`, `copy`, `symlink` and directory `chmod`. Removals
run in reverse pathname order so children precede parents. Creations run in pathname
order so parents exist first; new directories initially use mode 0700. Final
directory permissions run deepest first, after children. A replacement file is
represented explicitly as remove followed by copy. Every operation includes its
expected `before` and `after` signature. Root removal is forbidden.

The dry run evaluates those operations in memory, checking existence, signatures,
parent directories and removal order. It rejects operations inside conflicted
subtrees, then plans again against the simulated result: there must be no further
operations and the conflicts must be unchanged. The report includes the operation
list, detailed conflicts, exclusion/protected paths, both guard inventories, a
baseline ID and a checksum. `validated` means this dry run passed;
`requires_revalidation` remains true. A future executor must freshly validate
inputs and guards, handle permissions and partial failures, and provide its own
publication/recovery semantics. The plan itself is not an atomic filesystem update.

Exclusions use the shared regular-expression subset against relative paths. A
matched entry and its descendants are left out of content comparison. Matched
entries count toward the scan limit and remain guarded/protected, so pruning a
parent cannot silently remove ignored data. Unsupported special files, unreadable
included entries, non-UTF-8 names/targets or exceeded budgets abort planning.
`max_entries` is 1–10000 per tree, including its root and encountered exclusions;
`max_bytes` is 1–1 TiB of included file sizes per tree, counting each hard-link path.
Depth is at most 64, relative paths at most 2048 UTF-8 bytes, and documents/reports
at most 16 MiB. Outputs must be regular files or absent, outside both roots, and
distinct from each other and the configuration. Before publication, an existing
output is also checked against both guard inventories to reject hard links to
input entries. Reports are replaced atomically.

This planner compares ordinary permissions, paths, bytes and symlink targets.
It does not synchronize ownership, ACLs, extended attributes, timestamps, sparse
allocation or hard-link identity. Checksums detect corruption but do not authenticate
an intentionally rewritten baseline. Metadata guards and the external-output rules
assume protected parent directories. Defaults are conservative: a conflict is
reported rather than assigned an implicit winner.

Independent acceptance checks cover all 125 three-way combinations of absence,
two file contents, a directory subtree and a symlink. The checker actually executes
the reported operations in disposable trees through independent OS APIs and checks
the resulting contents and idempotence. A mixed fixture covers simultaneous edits,
source/destination deletions, directory/file/link replacements, permissions,
Unicode/binary content, same-size/mtime changes, excluded descendants, deterministic
reports and preserved conflicts. Additional checks cover corrupt baselines, invalid
configuration/output paths, permission errors and a coordinated tree mutation.
Both engines also plan a 160 MiB + 31 byte file plus 1,000 small files under a
128 MiB address-space limit. `SYNC_PAUSE=scanned` and `SYNC_CONTINUE` are coordinated
test hooks; leave them unset during ordinary use.

## 036: Content-addressed artifact store

[Six Python modules](036_artifact_store/main.py), 500 substantive lines, implement
imports, immutable manifests, named references, retrieval, verification and garbage
collection. The project compiles into `build/corpus/036/corpus_036`; the resulting
executable contains no Python runtime or application-specific Rust modules.

Create an empty repository directory, then put this configuration in `store.json`:

```json
{
  "repository": "/tmp/artifact-demo/store",
  "max_nodes": 10000,
  "max_bytes": 17179869184,
  "max_blob_bytes": 1073741824
}
```

Run `STORE_MODE=init build/corpus/036/corpus_036` once. Subsequent commands read
`request.json` when a request is needed. `STORE_CONFIG` and `STORE_REQUEST` override
those paths; `STORE_MODE` defaults to `list`. Use an absolute executable path when
running from a different working directory.

| Mode | Request fields | Result/effect |
| --- | --- | --- |
| `import` | `path` | Stream a regular file outside the repository; return SHA-256, size and whether a blob was created |
| `manifest` | `name`, `expected`, `files`, `includes`, `metadata` | Create an immutable manifest and optionally attach a named reference |
| `pin` | `name`, `manifest`, `expected` | Attach an existing manifest after verifying its complete dependency graph |
| `unpin` | `name`, `expected` | Remove that reference only if its current manifest matches |
| `get` | `digest`, `destination` | Verify/copy one blob into a new file outside the repository |
| `show` | `manifest` | Return its document and verified reachable manifest/blob IDs |
| `list` | None | List named references and node count; this is not a content scrub |
| `verify` | None | Verify every blob and every manifest, including unreferenced objects |
| `gc` | None | Verify live graphs, then delete only unreferenced manifests and blobs |

For example, an import request is `{"path":"/tmp/artifact-demo/input.bin"}`.
Run `STORE_MODE=import build/corpus/036/corpus_036`, then use the returned digest
and size in a manifest request:

```json
{
  "name": "release",
  "expected": "-",
  "files": {
    "assets/input.bin": {"digest": "<64 lowercase hexadecimal characters>", "size": 123}
  },
  "includes": [],
  "metadata": {"title": "First release", "ratio": 0.1}
}
```

Run `STORE_MODE=manifest build/corpus/036/corpus_036`. A nonempty `name` attaches
that root; an empty name creates an unrooted manifest. `expected` is `"-"` for a
new reference, or the exact old manifest ID for a replacement. Stale expectations
fail. Reference names contain 1–64 ASCII letters, digits, underscores or hyphens.
`includes` contains other manifest IDs, enabling shared/transitive dependencies;
its order is normalized and duplicates are rejected. `files` maps logical relative
artifact names to digest/size pairs. Metadata is a JSON object, including finite
floating-point values. A `get` request uses a blob's digest, independently of the
logical names in manifests.

Blob IDs hash the original bytes. Manifest IDs hash canonical JSON bytes with
sorted object keys, compact separators and literal Unicode. Finite binary64 values
use 17 significant digits, trimmed fractional zeros, and a normalized scientific
exponent. This preserves exact floating-point round trips and gives Python/Rust
the same IDs; integer `1` and floating `1e0` remain distinct representations, as do
positive and negative floating zero. The stored manifest is that canonical JSON.
The profile has its own documented encoding, not an RFC 8785/JCS compatibility
claim. Checksums detect corruption but do not authenticate a maliciously rewritten
repository. Imported blobs are copied, never hard-linked to source files.

A persistent `.store.lock` serializes cooperating commands. Import and publication
use reserved staging files, synchronize their contents, and publish complete files
with atomic renames. Named-reference replacement validates regular-file types and
rejects aliases. Dependency directories are synchronized before publishing a root;
collection synchronizes the reference directory before deleting objects. These
orders cover a previous process dying between a rename/unlink and its directory
sync. A command can fail after publishing a complete blob/manifest/reference;
inspect `list`/`show` before retrying. An unreferenced object left by a failed command
is eligible for collection. There is no lease spanning separate commands: coordinate
manual `gc` with imports that have not yet been attached to a root.

Collection reads every live reference, traverses complete manifest graphs with
visited sets, checks declared blob sizes and actual content hashes, then rechecks
the inventory before deletion. Shared objects survive until no live reference can
reach them. Corrupt/missing reachable data aborts collection before any deletion.
Corrupt unreferenced payloads can be collected; `verify` reports them instead.
An interrupted deletion pass may leave extra unreachable objects; rerunning `gc`
continues safely. A changed inventory aborts before sweeping. These guarantees
require a protected repository and stable ancestor entries; the advisory lock
cannot constrain unrelated writers or provide an atomic filesystem snapshot.

Retrieval rejects existing destinations, symlinks and an existing
`.<destination-name>.artifact-incomplete` sibling. It verifies the streamed copy
before publishing it without overwrite. A stopped or corrupt retrieval leaves
that incomplete file for inspection; remove it after review before retrying.
Known repository staging files are cleaned by the next locked command. Unknown
entries, symlinked namespaces, special files and invalid format documents fail
explicitly. Retrying initialization can reuse empty managed directories; a damaged
format document requires inspection.

`max_nodes` is 1–10000 across blobs, manifests and references. `max_bytes` is
1 byte–1 TiB across those files; `max_blob_bytes` has the same range and cannot
exceed the total limit. Format/lock/directory entries and unpublished staging files
are not included in these accounting limits. Each manifest has at most 1000 artifact
names and 128 dependencies. Artifact names are nonempty UTF-8 relative paths of at
most 1024 bytes, without empty, `.` or `..` components. Configuration, request and
manifest documents are limited to 1 MiB. The store keeps content and JSON metadata;
it does not preserve source ownership, permissions, timestamps, ACLs or sparse-file
allocation. File data moves in 64 KiB chunks.

Acceptance uses independent SHA-256 and decimal-based canonical-JSON oracles,
shared/diamond graphs and a generated 40-manifest DAG. Checks cover deduplication,
reference replacement/removal, exact byte/node limits, missing/corrupt live data,
corrupt orphan collection, six publication boundaries, three killed publishers,
changed sources, changed graphs, actual permission failures and incomplete retrievals.
Both engines import, reuse, pin, verify, collect and retrieve a 160 MiB + 43 byte
blob under a 128 MiB address-space limit. `tools/check_artifact_store.py` additionally
switches Python/Rust writers and readers over the same store in all four combinations,
including extreme floating-point metadata and identical manifest IDs.
`STORE_FAIL`, `STORE_PAUSE` and `STORE_CONTINUE` are test hooks; leave them unset
for ordinary use.

## 038: Layered configuration merger

[Five Python modules](038_config_merger/main.py), 344 substantive lines, implement
ordered configuration loading, recursive overlay, value provenance, conflict
diagnostics, preview and atomic export. Every module compiles to the native
`build/corpus/038/corpus_038` executable; running it requires no Python runtime.
The merge algorithm and validation remain in Python source.

Try the supplied base/site/user example without writing an export:

```bash
MERGE_CONFIG="$PWD/examples/corpus/038_config_merger/merge.json" \
  build/corpus/038/corpus_038
```

The default mode is `preview`. `MERGE_MODE=apply` publishes the resolved settings
to the configured output and prints the same detailed JSON report with `mode`
set to `apply`. A configuration file has these fields:

```json
{
  "layers": [
    {"name": "base", "path": "base.json", "required": true},
    {"name": "site", "path": "site.json", "required": true},
    {"name": "user", "path": "user.json", "required": false}
  ],
  "type_changes": [],
  "output": "resolved.json",
  "max_nodes": 20000
}
```

Relative layer/output paths are resolved beside the configuration file, independently
of the process's working directory. Layer names are unique 1–64-character ASCII
letter/digit/underscore/hyphen identifiers. One to sixteen layers are allowed,
and at least one must be present. An optional layer can be absent; malformed,
unreadable, symlinked or non-regular inputs still fail. Every layer is a JSON
object. Unknown control-document fields and duplicate layer names, paths or
type-change permissions are rejected. Input file aliases are rejected too.

Layers apply in listed order, so later values take precedence. Objects merge
recursively; omission retains an earlier value and an empty object does not erase
earlier children. Arrays replace completely, including any nested objects.
Scalars replace earlier values of the same JSON kind. Integer and floating-point
values share the `number` kind; booleans, null, strings, arrays and objects are
distinct. Null is a literal value, not a deletion marker. Strings such as
`${HOME}` remain literal; the merger performs no interpolation or evaluation.
As with the shared JSON parser, repeated keys inside a JSON object use the last
occurrence. No Unicode normalization is applied.

Changing a value's kind records a conflict at its exact escaped path. A conflict
keeps the previous value while diagnostics for the remaining layers are gathered;
a later correction does not silently erase the earlier conflict. A conflicted
report has `status: "conflicted"`, `resolved: null`, empty `provenance` and exit
status **2**. Apply leaves an existing output byte-for-byte unchanged. Other
validation/I/O failures also exit nonzero and report their error on stderr.

To permit a deliberate type change, list its exact JSON Pointer in `type_changes`,
for example `"/server/tls"`. A permission for a parent does not cover its children.
Permitted changes are still recorded as `type_change` events; unused permissions
appear in `unused_type_changes`. The root pointer is the empty string. Object
keys escape `~` as `~0` and `/` as `~1`; an empty key adds an empty path segment,
so `/` and the root remain distinct. Array indices are decimal path segments.

The successful report contains the resolved document and `provenance`, mapping
**every node's path**, including containers and array members, to the last layer
that supplied it. Merging an object credits that container to the current layer
while retaining each untouched child's source. Replacing an array or changing
a container's type removes obsolete descendant provenance. Repeating the same
value credits the later layer and produces an `unchanged` event. Events also
include the previous layer and before/after kinds. Layer observations include
SHA-256 of original input bytes, byte count, node count and presence.

The exported file contains only the resolved settings, formatted as readable JSON.
The report goes to stdout. No output is written during preview. Apply checks that
the output is absent or regular and cannot alias the configuration or any layer,
including a currently absent optional path. It stages a complete file beside the
output, synchronizes it, atomically replaces the output and synchronizes its
directory. An already-open reader can continue reading the previous file.
Input metadata is checked before/after reads and again before publishing; the
output is also checked against its initial metadata observation. Changed or
deleted inputs, newly appearing optional layers and changed outputs abort the
export. These guards require stable ancestors and cooperating writers; they do
not provide an atomic multi-file snapshot or lock out a concurrent edit after
the final check. Replacement creates a new file with private default permissions
and does not preserve the old output's inode or mode. A failure after publication
can leave the complete new output; inspect it before retrying.

Each input, including the control document, is limited to 1 MiB and 24 nesting
levels. Paths into JSON are limited to 4096 UTF-8 bytes. `max_nodes` is 1–20000
over the sum of present layer nodes, counting container nodes and array elements;
the control document is excluded from that aggregate. There are at most 128
type-change permissions. The pretty report and exported settings each have a
16 MiB encoding limit. The application processes bounded documents in memory.

Acceptance compares the entire report against an independent iterative oracle,
including all 36 JSON-kind transitions, 30 precise rejected type changes, 60
seeded generated four-layer overlays, escaped/empty/Unicode keys, nulls, numeric
types and floating-point bits. Checks cover exact size/depth/node limits,
optional layers, hard-link/symlink/special-file rejection, real read/write
permission failures, five changed-snapshot cases, four injected boundaries and
two killed publishers. A 4,000-key overlay, with 2,000 overrides, runs in both
engines under a 128 MiB address-space limit. `MERGE_FAIL`, `MERGE_PAUSE` and
`MERGE_CONTINUE` are test hooks and should remain unset during ordinary use.

## 039: Download-folder organizer

[Five Python modules](039_download_organizer/main.py), 484 substantive lines,
classify files, choose collision-free names, write a reviewable plan, create target
directories, move files and maintain a resumable journal. All five modules compile
into `build/corpus/039/corpus_039`; the native executable requires no Python runtime
or application-specific Rust. Classification, naming, validation and recovery
are implemented in the Python application.

Copy [organize.json](039_download_organizer/organize.json) beside the plan/journal
you want to retain, set its `root` to a download directory, and run:

```bash
ORGANIZE_CONFIG=/tmp/my-organizer/organize.json \
ORGANIZE_PLAN=/tmp/my-organizer/plan.json \
ORGANIZE_JOURNAL=/tmp/my-organizer/journal.json \
  build/corpus/039/corpus_039
```

Preview prints and saves an envelope containing a plan and its SHA-256 `id`.
Review its `rows`, `skipped` entries and expected parent identities. Apply that
exact plan by supplying its ID:

```bash
ORGANIZE_MODE=apply \
ORGANIZE_PLAN=/tmp/my-organizer/plan.json \
ORGANIZE_JOURNAL=/tmp/my-organizer/journal.json \
ORGANIZE_APPROVE='<reviewed id>' \
  build/corpus/039/corpus_039
```

Apply reads the saved plan and does not require the original configuration.
The same command resumes an interrupted apply. Keep its plan and journal together;
preview refuses to replace a plan when the selected journal already exists.
Choose fresh sidecar paths for a subsequent batch. Reapplying a completed plan
checks the result and succeeds without repeating moves. A fresh preview after
organizing finds no remaining eligible top-level files.

Configuration fields are:

| Field | Meaning |
| --- | --- |
| `root` | Existing download directory, canonicalized once; filesystem root is rejected |
| `categories` | Up to 32 safe category names, each with 1–32 unique lowercase suffixes, such as `.pdf` or `.tar.gz` |
| `date_format` | Portable UTC format, for example `%Y/%m`, `%Y-%m` or `%Y/%m/%d` |
| `include_hidden` | Whether leading-dot files are eligible |
| `skip_suffixes` | Up to 32 lowercase temporary-download suffixes, matched case-insensitively |
| `max_entries` | 1–10000 immediate directory entries, including skipped entries and the lock file |
| `max_files` | 1–1000 files selected for moves |
| `max_bytes` | 1 byte–1 TiB total selected file sizes; content hashes stream in 64 KiB chunks |

The supplied suffix rules cover archives, documents and images. The longest
matching suffix wins, preserving its original spelling in the destination name.
Unrecognized extensions use `other`. Dotfiles without another extension and
trailing-dot names retain their complete names. UTC modification time, rounded
down to integral Unix seconds, supplies the date folders; even the nanosecond
immediately before the epoch belongs to December 1969. Source ownership, mode,
mtime, inode and hard-link relationships survive the same-filesystem rename.
Reads may update access times, and renames update change times.

Only immediate regular files are selected. Directories, symlinks, FIFOs and other
special entries are reported and left alone; the organizer does not recurse into
existing folders. Hidden and temporary files follow the configured rules. The
`.py2rust-organize` prefix is reserved, including the persistent root lock file.
Preview reads and synchronizes selected file contents, writes the external plan,
and may create that lock; it does not move source files or create target folders.

Targets have the form `<category>/<formatted date>/<filename>`. Existing files,
directories and dangling symlinks reserve their names. Planned targets also reserve
names, so two source files cannot collide with each other. In sorted source order,
the organizer chooses the first free name: `report.txt`, `report (1).txt`, and so
on, inserting the counter before the selected suffix. A stem is shortened only
when needed to keep a component within 255 UTF-8 bytes; Unicode characters are
never split. There are at most 10000 counter attempts. Relative paths have at most
eight components and 2048 UTF-8 bytes, with no empty, `.` or `..` components.
Existing ancestors must be real directories; symlinked parents and cross-device
moves are rejected.

Plan signatures include content SHA-256, device/inode, mode, link count, size and
mtime. Reads compare metadata before/after hashing, including change time.
Apply checks all source/target states before moving anything, verifies parent
identities, and uses atomic no-overwrite renames. A changed source, unexpected
destination or replaced parent aborts; it never silently selects a new name after
approval. The root-wide advisory lock excludes other cooperating organizers.
Inputs and ancestor directories must remain protected from unrelated writers;
these checks do not provide a filesystem snapshot or defend against a malicious
writer racing a pathname check.

The journal is created before target directories or files move. New directories
are created exclusively, their parent entries are synchronized, and their identities
are recorded. Recovery can adopt the one empty directory created immediately
before an interrupted journal update; an unrecorded nonempty directory requires
inspection. Each file is synchronized, renamed without overwrite, and both
destination and source directories are synchronized before advancing the journal.
Recovery accepts either the recorded file state or exactly one pending move
beyond it. Changed completed files or ambiguous states stop recovery before the
remaining moves. This is a resumable sequence, not an all-or-nothing batch and
not an undo command. Empty directories may remain after an interrupted attempt.
Checksums detect accidental corruption; they do not authenticate rewritten plans
or journals. File-system power-loss behavior is not physically simulated.

Configuration, plan and journal files must be outside the root, have distinct
paths and be regular files with no other hard links when present. Document and
encoded plan/journal sizes are limited to 2 MiB. Sidecar parent directories must
already exist. Errors leave recoverable progress where possible; do not discard
the journal after a partial apply. `ORGANIZE_STOP`, `ORGANIZE_PAUSE` and
`ORGANIZE_CONTINUE` are test hooks and should remain unset in normal use.

Acceptance checks compare preview rows with an independent destination oracle
and then compare moved contents and OS metadata to that preview. They cover
compound/case-insensitive suffixes, planned/existing collisions, long Unicode
filenames, hard links, pre-epoch/2038 dates, special entries, exact budgets,
45 rejected inputs, 16 interruption points, three killed processes, eight
conflict/locking cases and five real filesystem permission failures. Both engines
organize 1000 files including a 160 MiB + 43 byte file under a 128 MiB address-space
limit. `tools/check_download_organizer.py` verifies all four Python/Rust planner
and recovery combinations over the same plan, files and journal.

## 040: Fixture-tree scaffolder

[Five Python modules](040_fixture_tree/main.py), 451 substantive lines, create
directories and exact text/binary fixtures from a JSON manifest. Preview, validation,
ownership tracking, verification and cleanup all transpile to the standalone
`build/corpus/040/corpus_040` executable. This application needs no new compiler
or runtime adapter and contains no handwritten Rust.

Build and check it from the repository root:

```bash
python tools/corpus.py 040
python tools/check_fixture_tree.py
```

Copy [fixtures.json](040_fixture_tree/fixtures.json) into a working directory and
set its `root` to the tree you want to create. Keep the manifest and receipt outside
that tree. Run the binary with absolute control paths:

```bash
FIXTURE_MANIFEST=/absolute/work/fixtures.json \
FIXTURE_RECEIPT=/absolute/work/receipt.json \
FIXTURE_MODE=preview build/corpus/040/corpus_040

FIXTURE_MANIFEST=/absolute/work/fixtures.json \
FIXTURE_RECEIPT=/absolute/work/receipt.json \
FIXTURE_MODE=create build/corpus/040/corpus_040

FIXTURE_RECEIPT=/absolute/work/receipt.json \
FIXTURE_MODE=verify build/corpus/040/corpus_040

FIXTURE_RECEIPT=/absolute/work/receipt.json \
FIXTURE_MODE=cleanup build/corpus/040/corpus_040
```

The defaults are `FIXTURE_MODE=preview`, `FIXTURE_MANIFEST=fixtures.json` and
`FIXTURE_RECEIPT=fixture-receipt.json`. Preview emits the full planned receipt.
Other successful modes emit a summary with `root`, `phase`, `created`, `bytes`
and `cleanup_step`. `created` counts entries whose creation was recorded, including
directories, even after cleanup. `bytes` is the manifest's planned payload total;
it does not indicate how much of an interrupted creation was completed.

The strict manifest has four fields:

```json
{
  "root": "/tmp/my-fixtures",
  "entries": [
    {"path": "notes/readme.txt", "kind": "text", "data": "Hello, 世界!\r\n"},
    {"path": "data/sample.bin", "kind": "base64", "data": "AAECA/7/"},
    {"path": "empty", "kind": "directory"}
  ],
  "max_entries": 1000,
  "max_bytes": 4194304
}
```

Text is literal UTF-8, preserving CRLF, newlines and embedded NUL bytes. Binary
payloads use canonical standard base64. Missing parent directories are included
in the plan. Existing real directories may be reused; existing files, symlinks
and special entries at requested targets are rejected. An implicit directory
may also be declared explicitly once. Duplicate declarations and file/directory
prefix collisions are errors. Existing unrelated contents in reused directories
are preserved. Creation exclusively opens new files and creates private directories.

Names must be relative: no empty, `.` or `..` components, absolute paths or NULs.
Limits are 255 UTF-8 bytes per component, 16 components and 1024 UTF-8 bytes per
relative path. `max_entries` is 1–1000, counting the root and implicit directories;
`max_bytes` is 0–4 MiB of decoded payload. Individual files are limited to 1 MiB.
Manifest and receipt documents are bounded at 8 MiB. The root's parent and control
file parents must already exist; the filesystem root cannot be a fixture root.
All manifest data, bounds and current collisions are validated before creation.

The checksummed receipt is saved before creating the tree and after recording
each new entry. File stamps include device/inode, size, permission bits, link
count, modification time and SHA-256; directories retain their device/inode.
Verification detects replaced or changed created files, replaced directories,
missing entries and unrecorded children inside created directories. It also checks
reused directory identities, while leaving their unrelated children unclaimed.

Cleanup first verifies the entire recorded state, then removes owned entries in
child-before-parent order. It never removes a reused directory. Progress is saved
after each removal, and a restart accepts the one removal immediately ahead of
its journal update. Repeated completed cleanup succeeds while the recorded paths
remain absent. A replacement tree or changed fixture is preserved and rejected.

Creation is not atomic and does not automatically resume. A stopped creation with
only recorded entries can be cleaned from its partial receipt. If creation stops
after making an entry but before saving its ownership stamp, cleanup refuses
that unrecorded entry. Inspect it and remove it manually if appropriate before
cleaning the recorded prefix. Do not discard a partial receipt. Concurrent changes
or an I/O failure during cleanup can leave a partially cleaned tree; keep the
receipt for the next attempt after resolving the failure.

A root-specific advisory lock excludes cooperating instances and remains as a
small sibling file after exit. Inputs, receipts and ancestor directories must be
protected from unrelated writers; pathname checks do not provide a filesystem
snapshot or protection against malicious races. Checksums detect accidental
corruption, not forged receipts. Tests cover process interruption and permission
failures; they do not physically simulate power loss. `FIXTURE_FAIL`,
`FIXTURE_PAUSE` and `FIXTURE_CONTINUE` are test hooks to leave unset in ordinary use.

Independent acceptance checks compare OS metadata and exact bytes with the
manifest, exercise invalid manifests and collisions, changed ownership/content,
control-path aliases, root-wide locking, all creation/cleanup checkpoints, killed
processes and real permission failures. Both engines create, verify and clean a
4 MiB payload and a 1,000-entry tree under a 128 MiB address-space limit.
`tools/check_fixture_tree.py` checks all four Python/Rust creator-cleaner pairs,
including partial creation, cleanup interrupted after unlink, and refusal to
adopt an unrecorded object.

## 041: CSV/JSON converter

[Five Python modules](041_csv_json/main.py), 408 substantive lines, implement
CSV parsing and formatting, declared column types, ordered column selection,
rejection diagnostics and complete result publication. All five modules transpile
into `build/corpus/041/corpus_041`. There is no handwritten application Rust or
Python runtime in the executable. This application establishes bare `raise` in
exception handlers so failed publication cleanup can propagate its original error.

Build and verify it from the repository root:

```bash
python tools/corpus.py 041
python tools/check_csv_json.py
```

Copy [convert.json](041_csv_json/convert.json) and [people.csv](041_csv_json/people.csv)
to a working directory. Input and output paths resolve relative to the configuration
file's parent directory. Preview validates and converts in memory, prints the
report, and creates no output:

```bash
CONVERT_CONFIG=/absolute/work/convert.json \
  build/corpus/041/corpus_041

CONVERT_CONFIG=/absolute/work/convert.json CONVERT_MODE=convert \
  build/corpus/041/corpus_041
```

The defaults are `CONVERT_CONFIG=convert.json` and `CONVERT_MODE=preview`.
The configuration's `output` names a **new directory**, whose parent must exist.
Successful publication creates `data.json` or `data.csv`, alongside `report.json`.
Existing output files, directories and symlinks are preserved and rejected.
The supplied example deliberately contains one invalid integer: its valid records
are still converted and the invalid source row is retained in the report.

The strict configuration contains:

| Field | Meaning |
| --- | --- |
| `input`, `output` | Input document and new result-directory paths |
| `direction` | `csv-to-json` or `json-to-csv` |
| `delimiter` | Comma, semicolon, tab or vertical bar |
| `columns` | 1–64 objects with `name`, `type`, `nullable` |
| `select` | Nonempty, unique ordered list of declared column names |
| `max_rows` | 1–10,000 data rows, excluding the CSV header |
| `max_field_bytes` | 1–65,536 bytes per decoded/formatted UTF-8 CSV field |
| `max_input_bytes` | 1–4,194,304 bytes per input |

Column names are nonempty, unique, at most 256 UTF-8 bytes, and contain no NUL.
CSV input requires a header with exactly the declared names; their order may differ
from the schema. JSON input is an array of objects with exactly those fields.
Every declared field is validated before projection, including unselected fields.
CSV output preserves the `select` order; JSON object keys use canonical sorting.

| Type | CSV decoding / JSON input requirement |
| --- | --- |
| `string` | Literal text / JSON string; no trimming or case changes |
| `integer` | Signed ASCII decimal with optional sign and ASCII whitespace / JSON integer; signed 64-bit range |
| `number` | JSON numeric syntax / JSON number; finite binary64 or signed 64-bit integer |
| `boolean` | Lowercase `true` or `false` / JSON boolean |
| `json` | A JSON-encoded cell / any supported JSON value |

The exact CSV cell `\N` represents null, allowed only for nullable columns.
To represent literal text beginning with a backslash, the writer adds one leading
backslash; the reader removes one when the cell begins with two. Thus null,
the empty string, literal `\N`, and literal backslashes remain distinct. A JSON
column may also contain the JSON literal `null`, subject to its nullability rule.
Empty numeric/boolean cells are invalid. JSON booleans do not count as integers.
Number spelling is normalized on output using the shared canonical JSON format;
the round-trip guarantee concerns typed values, not original numeric spelling.

The CSV codec preserves Unicode, embedded NULs, commas, doubled quotes and embedded
CR/LF/CRLF exactly. It recognizes LF, CR and CRLF record endings, including a final
record without a terminator, and emits CRLF. Fields containing a delimiter, quote
or newline are quoted; a single empty field is quoted to distinguish it from an
empty record. Like Python's strict CSV reader, a quote in an unquoted field is
literal; text after a closing quoted field is an error. Blank data records have
zero fields and are reported as invalid-width rows. CSV syntax errors, invalid
UTF-8, a missing/mismatched header or invalid configuration abort the whole run.
UTF-8 BOMs are not stripped. JSON uses the shared depth, finite-number and integer
range contract; values outside that document contract abort input parsing.

The report contains total/accepted/rejected counts, selected columns, accepted
source-row numbers, and rejected original rows with named field reasons. Row numbers
are one-based logical data records, not physical lines within multiline cells.
For CSV, rejected input is the decoded cell list; for JSON, it is the original
record value. Accepted and rejected row numbers partition the input in order.
Input/data SHA-256 values identify the source snapshot and matching output file.
Exit status is zero when all rows pass and one when some rows are rejected;
the latter still publishes all accepted rows. Fatal errors also return nonzero
and include an error on stderr.

Configuration documents are limited to 64 KiB, converted data to 8 MiB and reports
to 16 MiB. Output expansion is checked per row before accumulation; rejection
details have a 15 MiB budget leaving room for report metadata. Inputs must be real
regular files. Their metadata is checked around reading and again before publication.
Files and ancestor directories should remain protected from unrelated writers;
these pathname checks do not provide a filesystem snapshot or protection from
malicious races.

Publication writes both files into a private sibling staging directory, synchronizes
them, then atomically renames that directory without overwriting an existing target.
A visible result therefore contains both data and report. Ordinary pre-publication
errors attempt to remove staging files and re-raise the failure. A killed process
can leave a private `.csv-json-*` staging directory for inspection/removal. An error
or kill after the rename may leave a complete published bundle despite unsuccessful
process termination; inspect the report and its data hash before retrying. This is
not a resumable import, and physical power-loss behavior is not simulated.
`CONVERT_FAIL`, `CONVERT_PAUSE` and `CONVERT_CONTINUE` are test hooks to leave unset
in ordinary use.

Independent checks compare parsing and writing with Python's `csv` module across
four delimiters, generated Unicode/quote/newline records, alternate record endings,
malformed CSV, exact integer/float boundaries, null escaping, projection and rejected
rows. They also cover publication interruption, killed processes, changed inputs,
destination collisions and real filesystem permission failures. Both engines run
at the 10,000-row, 64-column, 64 KiB field and 4 MiB input limits under a 128 MiB
address-space limit, and reject excessive output/report expansion within that limit.
`tools/check_csv_json.py` verifies all four Python/Rust CSV-writer/JSON-writer pairs.

## 043: Streaming JSONL transformer

[Four Python modules](043_jsonl_transform/main.py), 437 substantive lines, transform
a finite JSONL file with bounded memory and durable restart checkpoints. Filtering,
projection, quarantine indexing, cancellation, batch commits and recovery all
transpile into `build/corpus/043/corpus_043`. The executable requires no Python
runtime or application-specific Rust. A reusable scoped `LineReader` provides
buffered binary line chunks; the application owns the record and recovery logic.

Build and verify from the repository root:

```bash
python tools/corpus.py 043
python tools/check_jsonl_transform.py
```

Copy [transform.json](043_jsonl_transform/transform.json) and
[events.jsonl](043_jsonl_transform/events.jsonl) to a working directory. Input/output
paths resolve relative to the configuration file. Run or resume with the same
configuration:

```bash
JSONL_CONFIG=/absolute/work/transform.json build/corpus/043/corpus_043
```

The default configuration path is `transform.json`. The output directory's parent
must already exist. A new job is initialized in a private sibling directory and
published with a no-overwrite rename. An existing output must be a valid job
matching the effective configuration, source metadata and recorded identities.
The configuration and input must be outside the output directory. An unrelated
existing directory is preserved and rejected.

The strict configuration has these fields:

| Field | Meaning |
| --- | --- |
| `input`, `output` | Immutable source file and persistent job directory |
| `select` | 1–64 unique, nonempty top-level field names, each at most 256 UTF-8 bytes |
| `where` | Object with up to 64 top-level field/value equality conditions; all must match |
| `chunk_bytes` | 1–65,536 bytes per buffered read; 65,536 is the normal setting |
| `max_line_bytes` | 1–1,048,576 bytes per parseable physical record, including its LF/CRLF terminator |
| `batch_rows` | 1–1,000 completed records per checkpoint threshold |
| `batch_bytes` | 1–16,777,216 consumed source bytes per checkpoint threshold |

The reader splits only on LF, preserving every original byte. CR before LF remains
part of the JSON whitespace; embedded bare CR does not split a record. A final
record without LF is supported. Empty/whitespace records, invalid UTF-8/JSON,
non-object values, unsupported JSON values and missing selected fields are
quarantined. JSON uses the shared signed-64-bit integer, finite-number and nesting
contract. UTF-8 BOMs are not stripped.

Filtering happens after object validation and before projection. Missing filter
fields do not match, including when the requested value is null. Equality is
structural: numeric integer/float spellings may agree, but booleans remain distinct
from numbers, including within nested structures. Filtered records need not contain
projected fields. Extra fields are omitted from accepted output. Output JSON uses
canonical key/number formatting and one LF per accepted object.

The job directory contains:

| File | Contents |
| --- | --- |
| `accepted.jsonl` | Projected records in original input order |
| `quarantine.bin` | Exact concatenation of rejected physical records, including original terminators and invalid UTF-8 |
| `rejected.jsonl` | One index entry per rejected record: one-based line number, source byte offset, byte length, quarantine byte offset, SHA-256 and reason |
| `checkpoint.json` | Checksummed source/output prefix hashes, sizes, file identities, configuration hash, counters and phase |

Oversized records are streamed directly to quarantine in bounded chunks. Their
entire original byte sequence is retained, even if the record is much larger than
process memory. The checkpoint thresholds are evaluated **after a complete
physical record**; one oversized record can exceed the byte threshold without
increasing the memory bound. `lines` always equals `accepted + filtered + rejected`.
`batches` counts checkpoints that commit additional complete records, excluding
empty phase-only transitions.

The checkpoint is the commit marker. While a job runs or after it fails, output
files can contain uncommitted tails; consumers must use the committed sizes in
the checkpoint. A commit synchronizes all three outputs before atomically replacing
the checkpoint. Restart validates every committed prefix and its recorded identity
before truncating any uncommitted tail, then resumes at the saved source offset.
Short, changed, replaced, symlinked or hard-linked committed output files are
rejected. Completed jobs additionally reject unexpected tails. Re-running a valid
completed job verifies the prefixes and returns the same checkpoint without
rewriting outputs.

The source must remain immutable throughout the job's lifetime. Content, identity,
size and metadata changes are rejected; this is a finite-file transformer, not a
live-growing-file follower. Resume verification rehashes the committed source and
output prefixes using bounded buffers, so restart time grows with committed data.
Inputs, checkpoints, outputs and ancestor directories must be protected from
unrelated writers. An advisory sibling lock excludes cooperating instances, but
pathname checks do not provide a filesystem snapshot or defend against malicious
races. Checkpoint checksums detect accidental corruption, not forged job metadata.

For cooperative cancellation, set `JSONL_CANCEL` to an external marker path and
create that file to request a pause:

```bash
JSONL_CONFIG=/absolute/work/transform.json \
JSONL_CANCEL=/absolute/work/cancel build/corpus/043/corpus_043
```

Cancellation is checked between chunks. An incomplete oversized record's temporary
quarantine bytes are removed; complete records already processed in the current
batch are committed. The process prints a `paused` checkpoint and exits with status
75. Remove the marker and run again to resume. Completion prints a `complete`
checkpoint and exits zero, even when some records were quarantined. Fatal errors
return nonzero and retain the last committed checkpoint for inspection/recovery.
Do not discard the job directory after an interrupted run.

A killed process during initialization can leave a private `.jsonl-init-*` sibling
directory for inspection/removal. Once published, interrupted jobs recover through
their checkpoint and verified prefixes. The small sibling lock file remains after
exit and should not be removed while an instance may be running. `JSONL_FAIL`,
`JSONL_PAUSE` and `JSONL_CONTINUE` are test hooks to leave unset in ordinary use.
Tests simulate process termination and I/O failures, not physical power loss.

Independent acceptance checks cover exact accepted/quarantined bytes, structural
filters, byte/line boundaries, 28 interruption cases, cancellation before work and
during an oversized record, corrupt/changed prefixes, uncommitted tails, competing
writers and real permission failures. Both engines process a 180,310,890-byte valid
stream and quarantine a single 160 MiB + 2 byte record under a 128 MiB address-space
limit. The separate reader regression streams a 64 MiB logical line under the same
limit. `tools/check_jsonl_transform.py` verifies all four Python/Rust writer-recovery
pairs across synced-but-uncommitted batches and partial oversized records.

## 044: CSV join utility

[Five Python modules](044_csv_join/main.py), 415 substantive lines, implement
inner and left joins on declared composite keys. The CSV parser, validation,
hash indexes, projection, duplicate accounting and publication all transpile into
`build/corpus/044/corpus_044`. No application-specific Rust or Python runtime is
required. The readable CSV codec is reused from application 041.

```bash
python tools/corpus.py 044
python tools/check_csv_join.py
```

Copy [join.json](044_csv_join/join.json), [people.csv](044_csv_join/people.csv) and
[teams.csv](044_csv_join/teams.csv) into a working directory. Paths resolve relative
to the configuration file, and output parents must already exist. Preview prints
exactly the report that publication would save, without creating an output bundle:

```bash
JOIN_CONFIG=/absolute/work/join.json build/corpus/044/corpus_044
JOIN_CONFIG=/absolute/work/join.json JOIN_MODE=join build/corpus/044/corpus_044
```

The second command creates the new `joined/` directory containing `joined.csv`
and `report.json`. An existing destination is always refused. Both successful
modes exit zero, including when there are unmatched rows. Invalid configuration,
invalid input, capacity overflow or publication failure exits nonzero.

Configuration is strict and requires every field shown in the example:

- `left` and `right` each declare `path`, `delimiter` and an ordered `keys` list.
  Corresponding key positions match; column names and column positions may differ
  between inputs. Both sides need the same number of keys, from 1 through 64.
- `kind` is `inner` or `left`. Every matching left/right pair is emitted: a key
  occurring three times on the left and twice on the right produces six rows.
  A left join emits one row for each unmatched left record, with empty strings
  for selected right fields. An inner join omits those rows.
- `duplicates` is `all` to preserve every pair, or `error` to reject any repeated
  key on either side, including keys with no counterpart.
- `select` contains 1–64 `{side, column, as}` objects in output order. Source
  columns may be repeated under distinct aliases. Aliases must be unique,
  nonempty UTF-8 strings of at most 256 bytes without NUL.
- `order` is `left` for original left-record order, or `key` for lexical ordering
  of the complete string tuple. Within a key, original left-record order is
  preserved; each left record emits matches in original right-record order.
- Input and output delimiters independently support comma, semicolon, tab or pipe.
  Output uses doubled quotes and CRLF record endings. CSV accepts embedded CR/LF,
  quotes, Unicode and NUL cell contents. Headers must be unique, nonempty and at
  most 256 UTF-8 bytes per name. Blank records, inconsistent widths, missing keys,
  invalid UTF-8, malformed quoting and unexpected configuration fields are fatal.
- `max_rows` bounds data records per input at 1–10,000; `max_field_bytes` bounds
  decoded input fields at 1–65,536 bytes; `max_input_bytes` bounds each source at
  1–4,194,304 bytes; `max_output_rows` bounds expansion at 1–100,000 records.
  CSV header records do not count toward row limits. Inputs have at most 64
  columns. Generated CSV is limited to 8 MiB and the JSON report to 16 MiB.

All cells are exact strings. Empty keys match empty keys; whitespace, case,
Unicode normalization and numeric-looking strings are preserved. `\N` has no
special meaning in this application. A typed conversion can be performed before
or after joining with application 041. Composite keys use typed immutable tuples,
so separator characters, empty values and different field boundaries cannot
accidentally merge distinct keys.

The report records input/output hashes, input headers, output aliases, row and
matched-pair counts, matched-row counts, and every unmatched input record with
its original cells and one-based data-record number. Record numbers refer to CSV
records, including embedded newlines, rather than physical lines. Duplicate
reports list each repeated key and its original record numbers, sorted by key.
Unmatched reports retain input order. An empty projected right value can therefore
be distinguished from an unmatched row through the report.

Both inputs and configuration must be regular, non-symlink files. Metadata
observations excluding access time are checked after reading, after validation,
and immediately before publication. A private sibling staging directory holds
both output files; the files and directory are synced before a no-overwrite
rename publishes the bundle. The parent directory is then synced. Ordinary
failures clean known staged files. Killing a writer before publication can leave
an unpublished `.csv-join-*` directory for operator inspection/removal; the program
does not adopt it on rerun. Killing or failing after publication can leave a
complete bundle despite a nonzero exit or missing stdout. Inspect that bundle
before rerunning with a fresh destination. Hostile concurrent pathname changes
and physical power-loss behavior are outside this example's guarantees.

Acceptance uses Python's independent `csv` library and a nested-loop join oracle,
including deterministic generated tables, distinct composite-key boundaries,
all duplicate multiplicities, unmatched rows from both sides, empty tables,
malformed files, real permission failures and killed writers at publication
boundaries. Capacity checks run under a 256 MiB process address-space limit and
exercise 10,000-row inputs, 64-component keys, 64 KiB fields, 4 MiB input files,
100,000 output rows, and output/report overflow. The mixed-engine check runs all
eight Python/Rust combinations of JSON-to-CSV conversion, joining, and conversion
back to JSON, comparing exact CSV and JSON hashes.

Optional test hooks `JOIN_FAIL` and `JOIN_PAUSE` accept `validated`, `stage`,
`data`, `report`, `ready` or `published`; `JOIN_CONTINUE` names the file that
releases a paused process. Leave these unset for normal use.



## 045: Nested JSON diff and patch

[Five Python modules](045_json_patch/main.py), 363 substantive lines, implement recursive differences,
guarded application and reversible patches. All application logic transpiles to
`build/corpus/045/corpus_045`; the executable needs no Python runtime or
application-specific Rust. The shared compiler adds ordinary typed-list
`insert(index, value)` with Python index clamping and argument evaluation order.

```bash
python tools/corpus.py 045
python tools/check_json_patch.py
```

Copy [patch-job.json](045_json_patch/patch-job.json), [before.json](045_json_patch/before.json)
and [after.json](045_json_patch/after.json) into a working directory. Paths resolve
relative to the job file, and output parents must exist. The default preview
prints a report without creating files. Write mode publishes a new output directory:

```bash
PATCH_CONFIG=/absolute/work/patch-job.json build/corpus/045/corpus_045
PATCH_CONFIG=/absolute/work/patch-job.json PATCH_MODE=write build/corpus/045/corpus_045
```

The example creates `difference/patch.json` and `difference/report.json`.
To apply that patch, save this as `apply-job.json` in the same working directory:

```json
{
  "action": "apply",
  "base": "before.json",
  "patch": "difference/patch.json",
  "output": "patched",
  "max_nodes": 20000,
  "max_changes": 2000
}
```

```bash
PATCH_CONFIG=/absolute/work/apply-job.json PATCH_MODE=write build/corpus/045/corpus_045
```

This creates `patched/result.json`, `patched/undo.json`, and `patched/report.json`.
Apply the undo patch with another `apply` job whose `base` is `patched/result.json`,
`patch` is `patched/undo.json`, and `output` is a fresh directory such as `restored`.
It reconstructs the original JSON values, including integer versus float values
and signed floating zero. Output uses canonical JSON; original whitespace and
object member order are not retained. `result.json` has no trailing newline so
a document at the exact input-byte limit can be read back without exceeding it.

Configuration is strict: `action` is `diff` or `apply`; both require `base`,
`output`, `max_nodes` and `max_changes`. Diff additionally requires `target`;
apply requires `patch`. `PATCH_MODE` is `preview` (default) or `write`.
Existing output files/directories/symlinks are refused. Successful commands exit
zero, including unchanged documents and empty patches; errors exit nonzero
without publishing a partial bundle. The JSON report records document hashes,
node counts, change count, and counts of additions, removals and replacements.

The versioned patch format is:

```json
{
  "version": 1,
  "base_sha256": "<64 lowercase hex characters>",
  "target_sha256": "<64 lowercase hex characters>",
  "changes": [
    {"op": "replace", "path": "/profile/name", "before": "Ada", "after": "Ada Lovelace"}
  ]
}
```

Hashes cover canonical JSON values: object keys are sorted, integer values stay
integers, and floats use the shared 17-digit binary64 representation. Formatting
and member-order changes do not make a document stale. Numeric representation
changes such as `1` to `1.0`, `0.0` to `-0.0`, and booleans versus integers remain
observable. All numbers follow the shared signed-64-bit/finite-binary64 subset.
Duplicate JSON object names follow the underlying parsers' last-value behavior.

Paths use `/`-separated components with `~0` for a literal tilde and `~1` for a
literal slash. The empty path selects the root; `/` selects an empty object key.
Object components are literal keys, including numeric-looking keys. Array
components must be canonical nonnegative ASCII decimal indices; signs, whitespace,
leading zeroes, overflow, and `-` append notation are rejected. To append, add at
the current array length. Insertions into the middle of an array are supported.

`add` requires `before: null` as an absent-value placeholder. An object key must
be absent, while an array insertion index must be between zero and its length.
`remove` requires an existing value matching `before` and `after: null` as its
placeholder. `replace` requires an exact old-value match. A real null value is
therefore distinguishable from a missing key through the operation and container
state. Root operations permit replacement only. Patches execute in listed order;
each guard checks the document produced by preceding operations. Unknown fields,
operations, invalid paths, missing parents and scalar traversal are rejected.
This is a guarded format with explicit old/new values, not an implementation of
the general JSON Patch operation set.

Diff traverses object keys in lexical order and compares arrays positionally.
It recursively changes shared positions, removes a shrinking tail from highest
index to lowest, and appends a growing tail in increasing order. Whole-value
replacement handles scalar and container-type changes. The output is deterministic;
it does not attempt move detection or a minimum-edit sequence. Application rebuilds
changed containers without mutating the supplied base, checks every old value,
and checks the complete base and target hashes. The undo patch reverses the
operation sequence and swaps old/new values; both directions are checked before
publication. A stale base, a late failed guard or a wrong target hash leaves all
source files unchanged.

Documents are limited to 4 MiB of input and canonical data, 24 nesting levels,
4,096 UTF-8 bytes per escaped path, and `max_nodes` from 1 through 20,000 (counting
containers and scalars). Patches have `max_changes` from 1 through 2,000; zero
actual changes are allowed. Patch input and serialized patch/bundle files are
limited to 16 MiB. Configuration is limited to 64 KiB. Bounds also apply to each
intermediate result and each before/after value in a supplied patch. Expanded
patch size is checked before application. No truncation or partial application
is used to satisfy a limit.

Inputs must be regular files with non-symlink final path components. Metadata
excluding access time is checked before/after reading and before publication.
Files are written and synced inside a private sibling `.json-patch-*` directory;
a no-overwrite rename publishes the complete directory, then its parent is synced.
Ordinary exceptions attempt to remove known staged files. A killed writer or
filesystem cleanup failure can leave an unpublished stage for operator inspection
and removal. Failure after publication can leave a complete bundle despite an
unsuccessful exit; existing bundles are never adopted or overwritten on rerun.
The example assumes trusted parent directories and does not claim protection from
hostile concurrent pathname changes or simulated physical power loss.

Acceptance compares deterministic patches with an independent iterative diff
oracle and applies them with a separate mutable-tree oracle. It covers all JSON
kind transitions, exact numeric representations, Unicode/empty/escaped keys,
ordered array edits, overlapping manual operations, undo, stale bases and late
failures. Both engines also exercise limits under a 256 MiB address-space cap,
real permission failures, injected errors and killed processes at publication
boundaries. `tools/check_json_patch.py` runs all eight Python/Rust combinations
of diff generation, application and undo, comparing exact patch/result bytes.

Optional test hooks `PATCH_FAIL` and `PATCH_PAUSE` accept `validated`, `stage`,
`report.json`, `patch.json`, `result.json`, `undo.json`, `ready` or `published`
when that output is part of the current action. `PATCH_CONTINUE` names the file
that releases a paused process. Leave these unset for normal use.

## 046: Event-log consistency checker

[Four Python modules](046_event_log/main.py), 500 substantive lines, implement
bounded JSONL scanning, event normalization, sequence/time/state observations and
atomic JSON/text diagnostics. Every module transpiles into
`build/corpus/046/corpus_046`; the executable needs no Python runtime or
application-specific Rust. This project uses the existing subset unchanged.

```bash
python tools/corpus.py 046
python tools/check_event_log.py
```

Copy [event-job.json](046_event_log/event-job.json) and [events.jsonl](046_event_log/events.jsonl)
into a working directory. Paths resolve relative to the configuration file; parent
directories must already exist. Preview prints the complete report without writing
files; write mode also publishes a new directory containing `report.json` and
`report.txt`. Both modes require the destination to be absent.

```bash
EVENT_CONFIG=/absolute/work/event-job.json build/corpus/046/corpus_046
EVENT_CONFIG=/absolute/work/event-job.json EVENT_MODE=write build/corpus/046/corpus_046
```

Exit status **0** means consistent, **1** means a completed report with findings,
and **2** means a fatal configuration, capacity, input-change or publication error.
Findings do not stop scanning later records. Fatal errors never publish a partial
bundle. An error after the publication rename can leave the complete bundle present.
Choose another output directory for a later run; existing destinations are preserved.

Each event has these fields; unknown fields are rejected:

```json
{"id":"order-1","stream":"orders","sequence":1,"time":"2026-01-01T10:00:00Z","from":"new","to":"active","data":{"order":42}}
```

`id` and `stream` are literal, case-sensitive Unicode identifiers, each 1–128 UTF-8
bytes, without surrounding whitespace or C0/DEL controls. `sequence` is a positive
signed 64-bit integer; booleans and floats are rejected. `time` is an explicit-offset
RFC3339-shaped timestamp with up to six fractional digits, normalized to UTC with
microseconds. Leap seconds and dates outside UTC years 0001–9999 are rejected.
`from` and `to` must be declared states. Optional `data` defaults to null and accepts
JSON within 16 nesting edges and 1,000 nodes, counting containers and scalar values.

The sample config declares states, an initial state and allowed directed transition
pairs. State names match `[A-Za-z][A-Za-z0-9_-]{0,31}`; there must be 1–32 unique
states. Edges must be unique and refer to declared states; an empty edge list allows
no transitions. `first_sequence` sets the positive starting sequence for every
stream. `global_time_order` controls cross-stream time checks; each stream always
checks its own ordering. The other required limits are:

| Setting | Allowed range |
| --- | --- |
| `max_streams` | 1–1,000 distinct checked streams |
| `max_records` | 1–10,000 physical records |
| `max_line_bytes` | 1–65,536 bytes, including LF/CRLF when present |
| `max_input_bytes` | 1–8,388,608 bytes |

Configuration is at most 64 KiB, and each exported report is at most 16 MiB.
The scanner drains oversized records in bounded chunks without retaining their
contents. LF separates records; an unterminated final record is checked, CRLF is
preserved in location accounting, and blank physical lines are invalid records.
Input, configuration and output limits fail explicitly instead of truncating results.

IDs are global across streams. A repeated normalized event is `duplicate_id`;
reuse with different contents is `conflicting_id`. UTC-equivalent timestamp spellings
and omitted/null data compare equal; canonical numeric representations such as
`1` and `1.0` remain distinct. These records do not advance observations. A new ID
reserves its identity even when its stream/sequence pair is a `duplicate_sequence`;
that record also does not advance observations. Schema-invalid records reserve nothing.

Every other record advances the observed chain, including records with consistency
findings. Sequence and time comparisons use high-water marks with original line
references, so a regression cannot hide a later regression. State checks compare
`from` with the preceding checked record's `to`, and independently validate the
declared transition edge. **`last_observed_state` describes the recorded chain**;
it does not certify that all transitions leading to that state were valid.

A forward sequence jump records the range missing at that point. A late unique
sequence remains an out-of-order finding but fills the final missing-range summary.
Only gaps between the configured start and the highest observed sequence are
reported; no unobserved tail is inferred. The sequence high-water mark starts at
`first_sequence - 1`, with line reference zero until advanced. Ranges are compact
inclusive `first`/`last` pairs, including near the signed integer limit. Values before the configured start
are diagnosed separately. Equal timestamps are allowed.

Each diagnostic includes its physical line number, byte offset, byte length,
SHA-256 of the exact original bytes, normalized event when valid, and all applicable
issue codes/details. The report also contains total/schema-valid/checked counts,
invalid and duplicate counts, per-code totals, the full input digest, per-stream
state/time/sequence anchors and final missing ranges. `report.txt` includes a readable
summary and one canonical JSON line per stream or individual issue.

Regular, nonsymlink input files are required. Metadata snapshots excluding access
time detect changed configuration/logs before publication. Write mode syncs both
files and the staging directory, performs a no-overwrite rename, then syncs the
parent. Ordinary failures attempt staging cleanup; process termination or denied
cleanup permissions may leave an unpublished `.event-log-*` directory for manual
removal. This assumes trusted parent directories and immutable inputs during a run;
it does not claim protection against hostile path races or simulate power loss.

The independent checker groups records offline rather than replaying the application's
scan loop. Both engines pass 34 sequence/identity cases, 22 time/state cases,
60 malformed-record cases, 24 generated traces, 45 configuration cases,
25 publication/interruption cases and seven path cases. Capacity checks run under
256 MiB per process and cover 10,000 records, 1,000 streams, exact byte/payload bounds
and diagnostic expansion beyond the report limit. All four Python/Rust combinations
of application 043 filtering followed by application 046 analysis consume the actual
filtered file and produce identical canonical JSON and text diagnostics.

Optional test hooks `EVENT_FAIL` and `EVENT_PAUSE` accept `row:N`, `validated`,
`stage`, `report.json`, `report.txt`, `ready` or `published`. `EVENT_CONTINUE` names
the file that releases a paused process. Leave these unset for normal use.

## 048: Contact import deduplicator

[Four Python modules](048_contact_import/main.py), 432 substantive lines, implement
contact normalization, declared matching rules, transitive groups, provenance,
conflict review and immutable import bundles. Every module compiles into
`build/corpus/048/corpus_048`; no Python runtime or application-specific Rust is
needed by the executable. This application establishes shared Unicode normalization
and sorting of nested typed sequences.

```bash
python tools/corpus.py 048
python tools/check_contact_import.py
```

Copy [contact-job.json](048_contact_import/contact-job.json) and
[contacts.json](048_contact_import/contacts.json) into a working directory. Paths
resolve relative to the config file; parent directories must already exist.

```bash
CONTACT_CONFIG=/absolute/work/contact-job.json build/corpus/048/corpus_048
CONTACT_CONFIG=/absolute/work/contact-job.json CONTACT_MODE=write build/corpus/048/corpus_048
```

Preview validates the complete job and prints its summary without creating files.
Write mode creates a new directory with all five outputs, refusing an existing
file, directory or symlink at that destination. Exit **0** means no rejected rows
or groups needing review, **1** means a completed import with those findings, and
**2** means a fatal configuration, capacity, input-change or publication error.
Review findings in the previous book still produce exit 1 on a repeat import.

The config has exactly four fields:

```json
{
  "inputs": ["contacts.json", "another-export.json"],
  "state": "",
  "output": "imported",
  "keys": [["email"], ["phone"], ["name", "address"]]
}
```

Each input is a JSON array. A contact requires literal `source` and `id` strings,
each 1–128 UTF-8 bytes without surrounding whitespace or C0/DEL controls. The
optional fields are `name`, `email`, `phone`, `address` and `organization`; missing
fields default to an empty string for matching. Unknown fields, nulls and other
non-string field values are rejected. At least one field other than organization
must have a nonempty normalized value. For example:

```json
{"source":"crm","id":"17","name":"José García","email":"jose@EXAMPLE.COM","phone":"+34 (912) 345-678","address":"Calle Mayor 1"}
```

Normalization collapses Python whitespace to single spaces, removes surrounding
whitespace and applies **NFC**, preserving case and compatibility distinctions in
names, addresses and organizations. Remaining C0/DEL controls are rejected. Addresses
are free-form text; no abbreviation, country, postal-code or street-name inference
is performed. Original field spellings always remain in the book.

Email addresses use a bounded ASCII dot-atom/local plus DNS-label/domain grammar.
Local parts retain case; domains become lowercase. Empty labels, edge hyphens,
adjacent/edge local dots, quoted local parts and Unicode mailboxes are rejected.
Local parts are at most 64 bytes and domains at most 253, with labels at most 63.
This validates the declared import grammar, not mailbox existence. Phone numbers
remove spaces, parentheses, periods and hyphens, then require `+` followed by
7–15 ASCII digits with a nonzero first digit. Country codes and extensions are
never guessed. Empty email/phone values remain missing values.

Each matching rule contains distinct field names. Fields within one rule are
**AND** conditions; different rules are **OR** conditions. Every field in a rule
must be nonempty to match. Equality uses the normalized values described above.
Rule and field order do not affect the result, and duplicate equivalent rules are
rejected. A record matching one contact by email and another by phone connects
both into the same group. Reuse of the same `(source, id)` also connects variants,
even when their declared matching fields differ.

For each group, every distinct nonempty value retains the variant IDs that supplied
it. A group needs review if any field has multiple normalized values, or if one
source identity supplied multiple distinct raw records. Even presentation-only
changes under one source identity remain visible for review. No conflicting field
gets an automatically chosen winner. Missing values can be filled by the group's
single observed nonempty value.

The five outputs are:

| File | Contents |
| --- | --- |
| `book.json` | Versioned state, normalized matching policy and every distinct valid original record, with a canonical SHA-256 checksum |
| `contacts.json` | Groups without conflicts, including normalized values and per-value/member provenance |
| `review.json` | Ambiguous groups with all value alternatives, conflicting field names and reused source identities |
| `rejected.json` | Complete invalid input rows, stable error-field names, one-based input and record numbers |
| `report.json` | Input paths and exact file hashes, record/add/replay/rejection counts, group counts and state checksum |

Every member reference contains its original source, ID and canonical raw-record
hash. The corresponding original record is retained in `book.json`; rejected rows
are retained separately. Repeated occurrences of an identical source record count
as replays rather than adding provenance duplicates. Variant identity uses canonical
JSON values, so changing JSON formatting or object-key order alone is a replay.
File occurrences belong to the per-run report. Book records and group/member/value order are deterministic.
Group IDs hash their member variants and can change when membership changes.

To continue an import, set `state` to a previous output's `book.json` and choose a
new output directory. The state checksum, schema, all stored records and matching
policy are validated before any publication. All prior variants are preserved;
changed source records become additional variants for review. Importing the same
rows again produces **byte-identical book data** and identical contact/review groups.
Reordering files, rows or equivalent rules also preserves those results; per-run
input paths and counters naturally differ. A different matching policy requires
an explicit fresh import. Checksums detect accidental alteration, not authenticate
an untrusted book.

The application accepts 1–16 input files and 1–8 matching rules, at most 2,000
incoming rows in total and 2,000 distinct valid book variants. A field is at most
2,048 UTF-8 bytes before normalization. Configuration is at most 64 KiB, each input
at most 4 MiB, all new inputs together at most 8 MiB, and a prior/exported book at
most 8 MiB. Each output is at most 16 MiB. Exceeding a bound fails the job instead
of silently dropping records. Rejected raw JSON uses compact serialization to avoid
indentation expansion for deeply nested invalid values.

Inputs and prior state must be regular nonsymlink files. Metadata snapshots excluding
access time detect changed files before publication. A private staging directory
receives and syncs the complete bundle before a no-overwrite rename and parent sync.
Ordinary errors attempt cleanup; killed processes or denied cleanup permissions may
leave an unpublished `.contact-import-*` directory for manual removal. An error
following publication may leave the complete bundle present. Parent directories
and writers are trusted; the checks do not simulate power loss or hostile path races.

The independent oracle uses pairwise adjacency and graph traversal, whereas the
application uses a hash index and disjoint sets. Both engines pass 17 merge cases
and their 17 re-imports, 12 reorderings, three incremental cases, 40 generated
datasets, 88 invalid rows, 38 configuration/state cases, 34 publication cases
and seven path cases. These cover Unicode spellings, composite/overlapping keys,
transitive bridges, source-ID reuse, stale/corrupt state, interrupted publication
and real permission failures. Capacity checks run under
256 MiB per application process. Eight Python/Rust import/update/reimport combinations
consume each other's actual book files and preserve all original variants.

Optional test hooks `CONTACT_FAIL` and `CONTACT_PAUSE` accept `input:N`, `validated`,
`stage`, any output filename, `ready` or `published`. `CONTACT_CONTINUE` names the
file that releases a paused process. Leave these unset for normal use.

## 049: JSON query console

[Five Python modules](049_json_query/main.py), 500 substantive lines, implement
lexing, parsing, nested field access, boolean evaluation, projection, stable merge
ordering, grouping and saved-result publication. Every module is transpiled;
the native executable contains no Python runtime or application-specific Rust.
The shared runtime adds general JSON scalar comparison and numeric addition.

Build and check the application, then verify its composition with the CSV converter:

```bash
python tools/corpus.py 049
python tools/check_json_query.py
```

The second command requires current evidence for application 041 as well. Copy
[query-job.json](049_json_query/query-job.json) and
[dataset.json](049_json_query/dataset.json) into a working directory. The config
contains exactly `input`, `query` and `output`; paths are relative to the config's
parent directory. Input is a JSON array of rows, which may themselves be any JSON
values. Preview prints the pretty JSON array without writing a result file:

```bash
QUERY_CONFIG=/absolute/work/query-job.json build/corpus/049/corpus_049
QUERY_CONFIG=/absolute/work/query-job.json QUERY_MODE=write build/corpus/049/corpus_049
QUERY_CONFIG=/absolute/work/query-job.json QUERY_TEXT='filter "/score" >= 10' build/corpus/049/corpus_049
```

`QUERY_CONFIG` defaults to `query-job.json`; `QUERY_MODE` defaults to `preview`.
`QUERY_TEXT` overrides the configured query, including an empty string. An empty
query returns the original rows. Success exits 0; configuration, syntax, evaluation
and I/O errors log a diagnostic and exit 2 without printing partial results.

Stages are separated by `|` and run left to right:

```text
filter "/active" == true and ("/score" >= 10 or "/team" == "Tools")
| select "/name" as "name", "/team" as "team", "/score" as "score"
| order "/team" asc, "/score" desc
| group "/team" as "team" sum "/score" as "points"
```

| Stage | Behavior |
| --- | --- |
| `filter expression` | Retain matching rows, preserving order |
| `select path as name, ...` | Project required fields into a new object with explicitly named keys |
| `order path asc/desc, ...` | Stable lexicographic ordering by required scalar fields; each column must have a compatible scalar kind across all rows |
| `group path as name, ... [sum path as name, ...]` | Group required scalar keys in first-seen order; emit `{ "key": {...}, "count": N, "sums": {...} }` |

Paths and output names are JSON-quoted strings. The empty path `""` selects the
whole row; `"/"` selects an empty object key. Components use `~1` for `/` and `~0`
for `~`, so `"/meta/a~1b/~0/0"` selects an array item under keys `meta`, `a/b`, `~`.
Array indices must be nonnegative ASCII decimals without leading zeros. An absent
key, invalid/out-of-range array index or traversal through a scalar is missing.
Projection, ordering and grouping fail on missing required fields.

Predicates support `==`, `!=`, `<`, `<=`, `>`, `>=`, `in` and `contains`, followed
by a JSON literal, plus prefix `exists path` and `missing path`. Boolean precedence
is `not`, then `and`, then `or`; parentheses override it. Keywords are lowercase.
Equality is structural: numeric `1` and `1.0` match, while `true` stays distinct.
`in` requires an array literal and checks structural membership. `contains` checks
an array element or a string substring. Missing paths make ordinary comparisons
false, including `!=`; use `missing` or `not exists` to test absence explicitly.
Ordered predicates return false for incompatible kinds or container values.

Ordering supports null, booleans, numbers and Unicode strings. Mixed integers and
floats compare by their actual numeric values without rounding large integers to
float first. Ties retain the current row order. Grouping likewise unifies equivalent
integer/float keys and signed zero, with booleans separate. Integral float group
keys within the signed-64-bit range are written as integers. Each sum starts at
integer zero; integer-only sums detect overflow, while a float operand promotes
the running sum to binary64 and rejects nonfinite results. Floating-point rounding
and dependence on row order remain ordinary binary64 behavior.

The bounds are 64 KiB of config, 4 MiB of input, 2,000 rows, 8,192 UTF-8 query
bytes, 512 tokens, eight stages and eight fields in each field/sum list. A field
path has at most 1,024 UTF-8 bytes and 16 components; an output name has 1–128
UTF-8 bytes and must be unique within its list. Query literal container nesting
is at most 16. Data uses the shared JSON contract (signed-64-bit integers, finite
binary64 and nesting at most 64); the pretty result must fit 16 MiB. Bounds fail
explicitly instead of silently truncating data.

Syntax errors identify a zero-based UTF-8 byte offset and one-based line and
Unicode column. Evaluation errors identify the pipeline stage; missing-field
errors include the path. The parser builds a bounded postfix plan and never
evaluates Python source. This is a batch console configured by files/environment,
with no interactive prompt or arbitrary query functions.

Inputs must be regular nonsymlink files. Metadata snapshots excluding access time
check for changes during reading and before publication. Write mode exclusively
creates a temporary sibling, syncs the whole result and atomically renames it to a
new output file without overwriting an existing path. Ordinary prepublication
errors clean up the temporary file; process termination or denied cleanup may
leave an unpublished `.json-query-*` file. A sync failure after renaming may leave
the complete output present. Parent directories and concurrent writers are trusted;
this is not a filesystem snapshot or a hostile-path-race guarantee.
`QUERY_FAIL=ready` is an optional prepublication failure hook for acceptance checks.

An independent recursive query algebra and Python stable sort check 195 query
cases, including 40 generated boolean expressions, all comparison operators,
2,000-row ordering/grouping and mixed numeric boundaries. Both engines also pass
10 equivalent-query checks, two escaped-literal cases, 34 exact source diagnostics,
11 evaluation failures, seven configuration errors, eight malformed datasets,
20 capacity checks and 13 saved-result checks. Eight Python/Rust CSV import/query/export
combinations consume the actual files written by applications 041 and 049.

The generated Rust retains named functions, typed values, source-file/line comments,
explicit loops and recoverable `Result` propagation. JSON ownership copies and
checked-index/error scaffolding remain more verbose than the Python; the application
sort is written explicitly because callback/key-based sorting is outside the subset.

## 050: JSONL partition writer

[Three Python modules](050_jsonl_partition/main.py), 242 substantive lines, group
one bounded JSONL input by UTC calendar date and exact topic value. Every input
record occurrence is retained, including duplicate records, and each shard retains
its source order. The entire application compiles to a standalone Rust executable
using existing shared JSON, datetime, hashing and filesystem operations.

```bash
python tools/corpus.py 050
python tools/check_jsonl_partition.py
```

Copy [partition-job.json](050_jsonl_partition/partition-job.json) and
[events.jsonl](050_jsonl_partition/events.jsonl) to a working directory. Preview
prints the complete manifest without writing any shards; write mode publishes a
new directory containing every shard and `manifest.json`:

```bash
PARTITION_CONFIG=/absolute/work/partition-job.json build/corpus/050/corpus_050
PARTITION_CONFIG=/absolute/work/partition-job.json PARTITION_MODE=write build/corpus/050/corpus_050
```

`PARTITION_CONFIG` defaults to `partition-job.json`, and `PARTITION_MODE` defaults
to `preview`. Success exits 0; malformed input, capacity, configuration and I/O
failures log a diagnostic and exit 2. The output directory must be absent even
in preview, so the manifest describes a job that can subsequently be written.

The config has exactly these fields:

| Field | Meaning |
| --- | --- |
| `input`, `output` | Input JSONL file and new output directory, relative to the configuration's parent |
| `timestamp_field`, `topic_field` | Distinct top-level record keys, each 1–128 UTF-8 bytes |
| `max_rows` | 1–10,000 input records |
| `max_line_bytes` | 1–65,536 bytes per physical line, excluding LF and including an optional CR |
| `max_input_bytes` | 1–4,194,304 input bytes |
| `max_shards` | 1–256 distinct date/topic pairs |

Every row must be a JSON object containing a strict RFC3339 timestamp string and
a topic string of 1–256 UTF-8 bytes. UTC normalization determines the shard's date:
`2026-10-07T00:30:00+02:00` belongs to `2026-10-06`. Original timestamp spellings,
other fields and nested values remain in the parsed record. Topic values are exact:
case, whitespace and different Unicode normalization forms remain distinct.
Topic text never becomes a path component.

The input must be UTF-8 JSONL. LF, CRLF and a final record without a newline are
supported. Empty input produces an empty manifest; blank physical lines, malformed
JSON and invalid records fail the whole job without publishing a partial dataset.
Record errors identify the one-based physical line. The shared JSON contract
restricts integers to signed 64 bits, floats to finite binary64, and nesting to 64.

Shard filenames are `YYYY-MM-DD--<SHA-256 of topic UTF-8>.jsonl`. The manifest maps
each filename to its readable topic and UTC date, records, exact encoded byte count,
SHA-256 and first/last source-line numbers. It also records the original input's
byte count and SHA-256, total record/shard-byte counts, field names and format version.
A filename collision is detected before publication. Manifest entries sort by date
then topic, independent of their first appearance in the input.

Shard data uses compact canonical JSON with sorted object keys and one LF per
record. This preserves parsed values and duplicate occurrences, while normalizing
source whitespace and numeric spelling. The manifest and shard bytes repeat exactly
for identical input/configuration, even when a different output directory is chosen.
Total encoded shard data must fit 16 MiB and the manifest 1 MiB; configuration is
limited to 64 KiB. Bounds fail explicitly without dropping records.

Input and configuration must be regular nonsymlink files. Their metadata snapshots,
excluding access time, are checked during reading and again before publication.
Write mode builds and syncs a complete private staging directory, then atomically
renames it without overwriting an existing destination and syncs the parent.
Ordinary prepublication failures clean up the staging directory. A killed process
may leave an unpublished `.jsonl-partition-*` directory; a later run uses a fresh
name and preserves those files. A failure after renaming can leave the complete
output present. Parent directories and writers are trusted; no power-loss or
hostile-path-race guarantees are claimed.

Independent grouping and checksum calculations verify 29 datasets (including
24 generated cases), their previews and exact repeat runs, UTC boundary dates,
arbitrary topic characters and custom field names. Both engines pass 20 invalid-record cases,
10 malformed inputs, 34 configuration errors, two input/config symlink checks,
15 capacity checks and 19 publication checks. These include changed input/config,
a competing destination and actual process termination before publication.
All four Python/Rust writer-reader pairs consume the writer's actual shard paths
and reproduce every shard byte-for-byte, preserving all duplicate occurrences.

Optional test hooks `PARTITION_FAIL` and `PARTITION_PAUSE` accept `validated`,
`stage`, a shard filename, `manifest.json`, `ready` or `published`.
`PARTITION_CONTINUE` names the file that releases a paused process. Leave these
unset for normal runs.

## 051: LRU cache workbench

[Four Python modules](051_lru_cache/main.py), 365 substantive lines, replay cache
commands, preserve LRU-to-MRU order, enforce capacity, calculate hit rates and
save/restore the full cache and cumulative counters. Every application module
is transpiled into the standalone Rust executable. The general compiler extension
is true division; there is no application-specific Rust implementation.

```bash
python tools/corpus.py 051
python tools/check_lru_cache.py
```

Copy [cache-job.json](051_lru_cache/cache-job.json) and
[trace.json](051_lru_cache/trace.json) into a working directory. Preview prints the
final report without writing a bundle; write mode creates a new output directory:

```bash
LRU_CONFIG=/absolute/work/cache-job.json build/corpus/051/corpus_051
LRU_CONFIG=/absolute/work/cache-job.json LRU_MODE=write build/corpus/051/corpus_051
```

`LRU_CONFIG` defaults to `cache-job.json`; `LRU_MODE` defaults to `preview`. The
config has exactly `trace`, `state`, `capacity` and `output`. Paths are relative
to the config's parent. An empty `state` starts a fresh cache. To resume, set it
to a previous bundle's `state.json`, set `capacity` to that snapshot's saved
capacity, and choose a new output directory. Use a `RESIZE` command to change
capacity during replay. An existing output path is rejected in both modes.
Success exits 0; malformed commands, state, configuration, capacity and I/O
failures log a diagnostic and exit 2 without publishing a partial bundle.

A trace is a JSON array of commands. Each command accepts exactly its listed
fields; names are uppercase:

| Command | Required fields and behavior |
| --- | --- |
| `GET` | `op`, `key`: report hit/value; a hit promotes the key to MRU and updates GET hit/miss counts |
| `PUT` | `op`, `key`, `value`: insert or replace, promoting the key to MRU; evict the oldest key if needed |
| `DELETE` | `op`, `key`: remove a present key; report whether it existed and its prior value |
| `PEEK` | `op`, `key`: report hit/value without changing recency or GET statistics |
| `RESIZE` | `op`, `capacity`: change capacity and evict oldest entries until it fits |
| `INSPECT` | `op`: return capacity, LRU-to-MRU entries and cumulative statistics |

For example, inserting `a`, inserting `b`, getting `a`, then inserting `c` into a
capacity-two cache evicts `b`. Replacing an existing key changes its value and
recency without evicting another key. Missing GET/DELETE operations leave recency
unchanged. Zero capacity accepts valid PUT commands but stores nothing and counts
them as dropped admissions; this differs from evicting a previously stored entry.
A cached JSON null is distinguished from a miss by the explicit `hit` flag.

Values are opaque JSON: numbers, booleans, strings, arrays, objects and null are
retained without application-level coercion. Keys are exact nonempty strings of
at most 128 UTF-8 bytes, including Unicode and escaped control characters. Capacity
is 0–256 entries. Each value has at most 16 nesting levels and 16 KiB of canonical
JSON. The cache uses an insertion-ordered dictionary; key snapshots during eviction
and the subset's owned-value copies mean this bounded workbench does not promise
constant-time operations.

Every command increments `steps`. `gets = hits + misses`; only GET commands
contribute to `hit_rate = hits / gets`, which is 0.0 before any GET. Other counters
record PUTs, overwrites, dropped admissions, DELETEs, actual deletions, evictions,
resizes, peeks and inspections. An INSPECT result includes that command's own
step/inspection count. Integer true division computes the hit rate directly from
the exact counters, without rounding large counters to floats first.

| File | Contents |
| --- | --- |
| `state.json` | Versioned capacity, ordered key/value entries and all cumulative counters, with a canonical SHA-256 checksum |
| `events.jsonl` | One complete result per command, with the cumulative step number; PUT/RESIZE results include ordered evicted key/value pairs |
| `report.json` | Run command count, before/after step counts, final capacity, ordered entries and cumulative statistics |

State and event data use canonical JSON. Restore verifies the checksum, exact
schemas, key uniqueness, value/capacity bounds, nonnegative counters, operation
counts and entry accounting. The checksum detects accidental alteration; it does
not authenticate a snapshot. Restoring and saving without commands produces
byte-identical state. Replaying a trace in multiple jobs, feeding each actual
saved snapshot into the next, produces the same final state and concatenated
event bytes as one uninterrupted run. Source snapshots are never overwritten.

Configuration is at most 64 KiB; traces contain at most 2,000 commands and 4 MiB
of input. State input/output is limited to 8 MiB, and the complete event history
for one job to 16 MiB. Exceeding a bound fails the job. Counters are signed-64-bit
integers; overflow is fatal rather than wrapping. Errors in a trace identify the
one-based command number. Empty traces and empty caches are valid.

Inputs must be regular nonsymlink files. Metadata snapshots excluding access time
are checked while reading and immediately before publication. The writer stages
and syncs all three files, then atomically renames the complete directory without
overwriting an existing destination. Ordinary errors clean up unpublished staging;
a killed process may leave a `.lru-cache-*` directory, which later runs preserve.
An error after renaming may leave the complete bundle present. Parent directories
and concurrent writers are trusted, and power-loss behavior is not simulated.

An independent logical-access-clock oracle checks 40 traces (32 generated), their
40 previews and 40 unchanged restores. All 19 split points of a representative
trace reproduce uninterrupted state and history. Both engines pass 59 invalid
command/configuration/malformed-input cases, 53 saved-state checks, 16 capacity
checks and 21 publication checks, including changed inputs, a competing writer
and process termination. Eight Python/Rust save/resume/read combinations preserve
actual snapshots, cached null values, zero-capacity states and exact event histories.

Optional test hooks `LRU_FAIL` and `LRU_PAUSE` accept `validated`, `stage`,
`state.json`, `events.jsonl`, `report.json`, `ready` or `published`.
`LRU_CONTINUE` names the file releasing a paused process. Leave these unset for
normal use. Generated Rust retains named functions, source-line comments and
explicit recoverable errors; ownership and bounds checks remain more verbose
than the Python source.

## 052: TTL key-value notebook

[Four Python modules](052_ttl_notebook/main.py), 310 substantive lines, implement
a local HTTP notebook for JSON values with expiration deadlines. The entire
application transpiles into a standalone Rust executable using the existing
shared runtime; this example needs no new compiler or runtime features.

```bash
python tools/corpus.py 052
python tools/check_ttl_notebook.py
TTL_STATE=/tmp/ttl-notebook.json TTL_PORT=8790 build/corpus/052/corpus_052
```

The server listens on loopback. The state directory must already exist; a new
notebook creates its initial snapshot automatically. This is a local service
without authentication. For example, store a note for one hour, then read it:

```bash
curl -X PUT http://127.0.0.1:8790/entry \
  -H 'Content-Type: application/json' \
  --data '{"key":"notes/today","value":{"text":"Remember this","tags":["work"]},"ttl":3600}'
curl 'http://127.0.0.1:8790/entry?key=notes%2Ftoday'
curl 'http://127.0.0.1:8790/entries?prefix=notes%2F&offset=0&limit=20'
curl -X POST http://127.0.0.1:8790/sweep
```

| Request | Behavior |
| --- | --- |
| `PUT /entry` | Exact JSON fields `key`, `value`, `ttl`; create with 201 or replace a live value with 200, resetting its deadline |
| `GET /entry?key=…` | Return a live entry with 200; absent and expired keys return 404 |
| `DELETE /entry?key=…` | Remove the physical record; `deleted` reports whether it was live |
| `GET /entries` | Return live entries in Unicode key order, with `count` and `more`; optional exact `prefix`, `offset` and `limit` filters |
| `POST /sweep` | Remove expired records and report the physical removal count; repeated sweeps are harmless |

Entry responses contain `key`, `value`, `written`, `ttl` and `expires`. Successful
responses, including a missing/expired GET, include the effective `clock`.
JSON null is a stored value, distinguishable from an absent key by the status and
`entry` field. Values retain strings, booleans, numbers, arrays and objects without
application-level coercion. Keys contain 1–128 UTF-8 bytes; Unicode, slash, NUL and
other escaped characters are allowed. URL-encode keys and prefixes in queries.
GET/DELETE/sweep accept no body. Unknown fields or malformed values return 400;
unsupported route methods return 405. Replies use `Cache-Control: no-store`.

`ttl` is an integer from 1 to 86400 seconds. An entry is live only while
`clock < expires`; equality is expired. Replacement starts a new deadline from
the current effective clock. The effective clock is the larger of the wall clock
and the persisted high-water mark. Therefore observing expiration, then restarting
with a backward clock adjustment, cannot revive the entry. A read commits any
advanced watermark before returning; if that cannot be saved, it returns an
error instead of claiming an expiration that a restart could reverse.

Reads filter expired entries without deleting them. Sweep removes them explicitly;
a successful PUT reclaims all expired records before checking the live-key limit.
Replacing a live key is permitted at full capacity. Invalid requests and rejected
capacity/size updates preserve the snapshot, including its clock. Expiration does
not run in a background thread: read filtering is immediate, and physical cleanup
occurs on sweep, successful PUT or deletion of that key.

| Environment setting | Default and allowed range |
| --- | --- |
| `TTL_STATE` | `ttl-state.json`; regular nonsymlink file, with an existing parent directory |
| `TTL_PORT` | 8790; 0–65535, with 0 selecting an ephemeral port |
| `TTL_KEYS` | 256; 1–256 physically retained entries |
| `TTL_VALUE_BYTES` | 16384; 2–16384 canonical JSON bytes per value |
| `TTL_STATE_BYTES` | 8388608; 256–16777216 bytes for the complete checksummed snapshot |
| `TTL_CLOCK` | Unset uses `unix_time()`; optionally a regular file containing a finite JSON timestamp, at most 128 bytes |

The timestamp range is 0–253402214400 Unix seconds. Values may nest at most
16 levels. Listing offsets are 0–256 and limits 1–256 (default 100). A request
body is limited to `TTL_VALUE_BYTES * 6 + 4096` bytes to allow JSON escape
expansion; oversize bodies return 413. Full storage or a snapshot that would
exceed its byte budget returns 507. A clock-only update must fit this budget too.
Storage/clock failures return 500. Invalid initial state or configuration prevents
startup, preserving the original state.

The snapshot contains a version, clock and keyed value/deadline records, with
SHA-256 over canonical JSON. Loading checks the checksum, exact schemas, key and
value bounds, original TTL, write time and computed expiration. Expired records
are valid saved data and never appear in live results. The checksum detects
accidental alteration; it is not authentication. Bounded reads check file metadata
before and after reading. Saving syncs a temporary file, atomically replaces the
snapshot and syncs the parent directory. A lifetime advisory lock on
`TTL_STATE + ".lock"` excludes a second server using that state path, and the
shared HTTP runtime serializes application callbacks. The lock file remains after
exit and must not be removed while a server is running.

A failure or disconnect after replacement may leave the complete new snapshot
committed even when the client receives no success response. Retrying a PUT
sets a fresh TTL; it is not an idempotent operation. The server trusts its parent
directory and does not coordinate with programs that bypass its lock. This
bounded example validates and serializes state per request; it is not a
high-throughput database, and the checks do not simulate power loss.

Both engines pass 653 independently modeled HTTP transitions, 49 invalid-request
and clock checks, 48 malformed-state/configuration checks, capacity and byte/depth
boundaries, concurrent clients and actual wall-clock expiry. Save checks exercise
recoverable errors and real process kills before and after commit, permission
failures, symlink substitution and competing server startup. All eight Python/Rust
write/update/read combinations use the same actual snapshot path, preserving
replacement deadlines and expiration across restarts and clock rollback.

Test-only `TTL_FAULT` injects a recoverable failure at `before_commit` or
`after_commit`. `TTL_PAUSE` pauses at those boundaries for process-kill checks.
Leave both unset during ordinary use. Generated Rust keeps the source functions
and line mapping; its explicit ownership and error handling are more verbose
than the Python.

## 053: Persistent priority work queue

[Four Python modules](053_priority_queue/main.py), 415 substantive lines, implement
a bounded work queue using ordinary `heapq` calls. All application code transpiles
into the standalone Rust executable. The compiler extension consists of generic
min-heap operations; scheduling, retries, cancellation, persistence and validation
remain in readable Python.

```bash
python tools/corpus.py 053
python tools/check_priority_queue.py
```

Copy [queue-job.json](053_priority_queue/queue-job.json) and
[trace.json](053_priority_queue/trace.json) into a working directory. Preview
prints the final report; write mode publishes a new result directory:

```bash
QUEUE_CONFIG=/absolute/work/queue-job.json build/corpus/053/corpus_053
QUEUE_CONFIG=/absolute/work/queue-job.json QUEUE_MODE=write build/corpus/053/corpus_053
```

`QUEUE_CONFIG` defaults to `queue-job.json`; `QUEUE_MODE` defaults to `preview`.
Configuration has exactly `trace`, `state`, `capacity` and `output`. Paths are
relative to the configuration's parent. An empty `state` starts a fresh queue;
otherwise it names an earlier bundle's `state.json`, whose capacity must match
the configuration. Both modes require a previously unused output path. Success
exits 0. Malformed commands/state, bounds and I/O failures log a diagnostic and
exit 2 without publishing an incomplete bundle.

| Command | Required fields and behavior |
| --- | --- |
| `ENQUEUE` | `op`, `id`, `priority`, `payload`: add a new queued job; duplicate IDs and full capacity produce a rejected event |
| `POP` | `op`: remove the earliest queued ticket, mark its job running and increment its attempt count; an empty ready queue produces a rejected event |
| `PEEK` | `op`: inspect the next queued job without claiming it or incrementing attempts |
| `ACK` | `op`, `id`: remove a running job as completed; queued or absent IDs are rejected |
| `RETRY` | `op`, `id`, `priority`: return a running job to queued state with a new priority and arrival sequence, retaining payload and attempt count |
| `CANCEL` | `op`, `id`: remove either a queued or running job; absent IDs are rejected |
| `INSPECT` | `op`: show jobs in pop order, running jobs in ID order, capacity and cumulative counters |

Priorities are signed-64-bit integers, with smaller numbers first. Each successful
enqueue or retry receives the next unique sequence number; equal priorities pop
in sequence order. Thus a retried job follows jobs already waiting at that priority.
For example, enqueue `z` then `a` at priority 5: `z` pops first regardless of ID
sorting. After popping and retrying `z` at 5, `a` comes first. IDs can be reused
after acknowledgement/cancellation; a stale ticket for the old job cannot select
the new one. Cancelled tickets are discarded lazily and periodically compacted
when their physical count exceeds `capacity * 2 + 16`.

The queue retains running jobs across restarts. A POP is a claim, not completion;
ACK completes it, RETRY schedules another attempt and CANCEL removes it. This is
a queue state machine and trace runner: it does not execute payloads, run worker
threads, expire leases or automatically retry running jobs. Rejected business
operations continue the trace with `accepted: false` and a reason such as
`duplicate_id`, `capacity`, `empty`, `not_found` or `not_running`. Structural errors
abort the whole replay before publishing. Every valid command, including rejected
operations and inspections, increments the step counter.

Capacity is 1–256 retained jobs, including running jobs. IDs contain 1–128 UTF-8
bytes, including escaped controls and Unicode. Payloads are opaque JSON, limited
to 16 nesting levels and 16 KiB of canonical representation. State counters and
the lifetime command count are bounded at one billion; sequence numbers continue
across restarts and do not reset when the queue becomes empty.

| Output file | Contents |
| --- | --- |
| `state.json` | Version, capacity, next sequence, logical jobs sorted by ID and cumulative counters, with a canonical SHA-256 checksum |
| `events.jsonl` | One complete result per command, including accepted/rejected state and affected job or inspection |
| `report.json` | Command count, before/after step counts, ordered queued jobs, running jobs and final counters |

Snapshots deliberately omit the physical heap and cancelled tickets. Loading
validates the checksum, exact schemas, unique IDs/sequences, job states, priorities,
payloads, attempt bounds and counter conservation, then uses `heapq.heapify` to
reconstruct the ready heap. A checksum-valid permutation of the stored job array
preserves scheduling order. Saving without commands is byte-identical for normal
snapshots. Splitting a trace into consecutive jobs, each reading its predecessor's
actual state file, produces the same final snapshot and concatenated event bytes
as uninterrupted replay. Checksums detect accidental damage, not malicious edits.

The configuration is at most 64 KiB, traces at most 4 MiB and 2,000 commands,
state input/output at most 8 MiB, and an event stream at most 16 MiB. Input files
must be regular nonsymlink files. Their metadata is checked during reading and
before publication. The writer stages and syncs all output files, then atomically
renames the complete directory without replacing an existing destination. A
recoverable pre-publication error cleans up staging; killing the process may leave
a `.priority-queue-*` directory, which subsequent runs preserve. A failure after
publication may leave the complete output present. Parent directories and external
writers are trusted; power loss is not simulated.

Both engines pass 38 traces, including 32 generated traces, their previews and
unchanged restores. All 22 split points of a representative trace reproduce
uninterrupted results. Checks also cover 54 invalid inputs, 56 state cases,
capacity/byte/depth limits, failure injection, changed inputs, competing
destinations, actual permission failures and process termination. Eight mixed-engine
save/retry/resume combinations preserve running jobs, retried attempts, ID reuse,
sequence counters and exact state/event bytes.

Test hooks `QUEUE_FAIL` and `QUEUE_PAUSE` accept `validated`, `stage`, `state.json`,
`events.jsonl`, `report.json`, `ready` or `published`. `QUEUE_CONTINUE` names a file
that releases a paused process. Leave these unset for normal use. Generated Rust
retains named source functions, source-line comments and direct generic heap calls;
its explicit cloning, error handling and bounds checks remain more verbose than Python.

## 054: Small document search engine

[Seven Python modules](054_document_search/main.py), 419 substantive lines, build
and update an inverted index, execute nested AND/OR queries and rank matching
documents. Every application module transpiles to standalone Rust. The compiler
adds typed set algebra and full Unicode case folding as general operations.

```bash
python tools/corpus.py 054
python tools/check_document_search.py
```

Copy [search-job.json](054_document_search/search-job.json) and
[trace.json](054_document_search/trace.json) into a working directory:

```bash
SEARCH_CONFIG=/absolute/work/search-job.json build/corpus/054/corpus_054
SEARCH_CONFIG=/absolute/work/search-job.json SEARCH_MODE=write build/corpus/054/corpus_054
```

The default `preview` mode prints a summary without writing output. `write` creates
a new immutable directory containing `state.json`, `events.jsonl` and `report.json`.
Configuration has exactly four fields:

```json
{"trace":"trace.json","state":"","capacity":8,"output":"search-run"}
```

Paths resolve relative to the configuration directory. A nonempty `state` names a
previous bundle's snapshot; `capacity` must match it. The output must not exist.

| Command | Fields and behavior |
| --- | --- |
| `PUT` | `document`: exactly `id`, `title`, `text` strings; replace an existing document or add a new one |
| `DELETE` | `id`: remove the document and all its postings; report whether it existed |
| `GET` | `id`: return the original document or null with a `found` flag |
| `SEARCH` | `query`, `offset`, `limit`: return ranked hits, total count, a `more` flag and normalized query terms |
| `INSPECT` | No additional fields; report document, distinct-term and posting counts plus capacity |

A full index rejects a new ID with `accepted:false` and `reason:"capacity"`;
replacement and deletion remain available. Other invalid commands fail the entire
trace without publishing partial output. Successful commands, including misses
and capacity rejections, advance the lifetime step counter.

Tokenization applies NFKC then Unicode 15.1 default case folding. Separators are
U+0000–002F, U+003A–0040, U+005B–0060, U+007B–009F, U+00A0, U+1680,
U+2000–206F and U+3000–303F. Other consecutive scalars form a token. Thus
`Straße` matches `STRASSE`, decomposed accents normalize, fullwidth letters become
ordinary letters, and emoji can be searched. IDs and stored document text retain
their original spelling. There is no stemming, accent removal, phrase matching,
substring matching or language-specific segmentation.

A string query implicitly ANDs its distinct tokens. Empty or punctuation-only
strings match nothing. Objects have exactly one `and` or `or` field with 1–16
child expressions. For example:

```json
{"op":"SEARCH","query":{"and":["HTTP",{"or":["Python","Rust"]}]},"offset":0,"limit":20}
```

Every branch is validated, including branches that cannot affect the result.
Ranking sums weighted occurrences of every distinct query term in a matching
document: title occurrences count three, body occurrences one. All terms from
the query tree contribute, including an unsatisfied branch of an OR expression;
repeated query terms do not boost scores. Ties use ascending original document
IDs by Unicode scalar order. Each hit includes ID, original title, the first 160
body code points, score and sorted matched terms. `count` precedes pagination.

| Bound | Value |
| --- | --- |
| Capacity | 1–128 documents |
| ID / title / body | 1–128 / 0–512 / 0–16384 UTF-8 bytes |
| Tokenization | 128 UTF-8 bytes per token, 4096 tokens per field, 256 distinct terms per document |
| Index vocabulary | 4096 distinct terms |
| Query | Depth 8 from root depth 0, 64 nodes, 64 distinct terms, 1024 UTF-8 bytes per leaf |
| Pagination | Offset 0–128; limit 1–128 |
| Replay | 2000 commands, 1,000,000,000 lifetime steps |
| Files | 64 KiB config; 4 MiB trace; 8 MiB snapshot; 16 MiB events |

Updating a document removes its old posting memberships before adding fresh
weighted counts. Empty posting lists disappear. Snapshots store original
documents and the index, with a canonical SHA-256 checksum. Restore validates
documents and rebuilds the index before comparing every posting. Reordering the
saved document array does not change results. The checksum detects accidental
damage; it does not authenticate the author.

Publication uses regular nonsymlink inputs, metadata rechecks, synced staging
files and an atomic rename that never replaces an existing destination. A handled
error before publication removes its staging directory. A killed process can
leave `.document-search-*` staging, preserved by later runs. A failure after
publication leaves the complete bundle visible. Parent directories and external
writers are trusted; power loss is not simulated.

An independent checker scans each document and tokenizes by scalar comparisons,
without using the application's regex or inverted index. Both engines pass 40
traces (32 generated), 20 split replays, 93 invalid inputs, 36 snapshot cases,
15 capacity/limit cases and 21 publication cases. All eight Python/Rust
writer-updater-reader combinations consume real saved files and produce identical
snapshot/event bytes. Deleted and replaced terms disappear after cross-engine
restoration.

`SEARCH_FAIL` and `SEARCH_PAUSE` accept `validated`, `stage`, `state.json`,
`events.jsonl`, `report.json`, `ready` or `published`. `SEARCH_CONTINUE` names the
file that releases a pause. Leave these test hooks unset for normal use. Generated
Rust keeps named functions, record fields and source-line comments; explicit owned
copies and error checks make it more verbose than the Python source.

## 055: Prefix autocomplete index

[Five Python modules](055_autocomplete/main.py), 381 substantive lines, implement
a recursive trie, usage tracking, ranked prefix suggestions and dictionary export.
All application code transpiles to standalone Rust. The compiler extension supports
self-referential dataclass fields through collections, including `dict[str, "Node"]`.

```bash
python tools/corpus.py 055
python tools/check_autocomplete.py
```

Copy [autocomplete-job.json](055_autocomplete/autocomplete-job.json) and
[trace.json](055_autocomplete/trace.json) into a working directory:

```bash
AUTOCOMPLETE_CONFIG=/absolute/work/autocomplete-job.json build/corpus/055/corpus_055
AUTOCOMPLETE_CONFIG=/absolute/work/autocomplete-job.json AUTOCOMPLETE_MODE=write build/corpus/055/corpus_055
```

The default `preview` prints a summary. `write` creates a new immutable bundle
containing `state.json`, `dictionary.json`, `events.jsonl` and `report.json`.
Configuration has exactly four fields, with paths relative to its directory:

```json
{"trace":"trace.json","state":"","capacity":8,"output":"autocomplete-run"}
```

Set `state` to a previous bundle's snapshot to resume. Its capacity must match
the configuration. The output directory must not exist.

| Command | Fields and behavior |
| --- | --- |
| `PUT` | `term`, `uses`: insert a spelling or replace the spelling and usage count of its normalized key |
| `HIT` | `term`, `amount`: increment an existing term's usage; a missing term remains absent |
| `GET` | `term`: report existence and return its entry or null |
| `DELETE` | `term`: remove the terminal entry and prune branches with no remaining terms |
| `SUGGEST` | `prefix`, `offset`, `limit`: ranked matches, total count, normalized prefix and a `more` flag |
| `EXPORT` | No other fields; emit the current dictionary in normalized-key order |
| `INSPECT` | No other fields; report term count, node count and capacity |

Keys are whole strings normalized with NFKC and Unicode 15.1 default case folding.
There is no tokenization, whitespace collapsing, accent removal or fuzzy matching.
Normalize the query prefix independently, then compare it with normalized keys.
An empty prefix selects all terms. `Straße` and `STRASSE` share one entry;
`café` and `cafe` remain different keys. `PUT` retains the newest original spelling,
while `HIT` preserves that spelling. Spaces and other valid UTF-8 content are allowed.

For example, a trace can insert two completions and record a selection:

```json
[
  {"op":"PUT","term":"Python","uses":3},
  {"op":"PUT","term":"Pytest","uses":4},
  {"op":"HIT","term":"PYTHON","amount":2},
  {"op":"SUGGEST","prefix":"py","offset":0,"limit":10}
]
```

Suggestions sort by descending usage, then ascending normalized key. Hits contain
`key`, original `term` and `uses`; the total count precedes pagination. Exports use
ascending normalized-key order regardless of usage. The final `dictionary.json`
contains that same readable entry array, even if the trace has no `EXPORT` command.

Removing `car` leaves `cart` available. Removing the last word below a node prunes
the empty branch. The root remains, so an empty dictionary has one node. Cached
word and node counts update along the changed path. Suggestions descend directly
to the matching prefix node before traversing its subtree.

A full dictionary rejects a new key with `accepted:false` and `reason:"capacity"`.
Existing keys can still be updated, hit or deleted. Every valid command advances
the lifetime step counter, including misses and capacity rejections. Invalid
commands, usage overflow or excessive trie size abort the trace without publishing
a partial bundle.

| Bound | Value |
| --- | --- |
| Capacity | 1–128 normalized terms |
| Term/prefix | At most 128 Unicode code points and 512 UTF-8 bytes, both before and after normalization; terms must be nonempty |
| Trie | 8192 nodes including the root |
| Usage / hit increment | 0–1,000,000,000 / 1–1,000,000 |
| Pagination | Offset 0–128; limit 1–128 |
| Replay | 2000 commands; 1,000,000,000 lifetime steps |
| Files | 64 KiB config; 4 MiB trace; 8 MiB snapshot; 16 MiB events |

Snapshots contain a canonical checksum, logical entries, capacity, step count and
node count. Restore validates normalized keys, uniqueness and usage bounds, then
rebuilds the trie and checks its node count. Entry order in the input snapshot does
not affect results. The checksum detects accidental damage rather than authenticating
the author. Native records contain owned children; this application makes explicit
copies and returns changed nodes to keep the Python reference behavior consistent.

Publication checks regular nonsymlink inputs and their metadata, syncs staged
files, and atomically renames the complete bundle without replacing a destination.
Handled failures before publication remove staging. A killed process can leave
an `.autocomplete-*` directory that later runs preserve. Failure after publication
leaves the complete bundle visible. Parent directories and external writers are
trusted; power loss is not simulated.

The independent oracle uses a flat dictionary, prefix scans and a set of all
prefixes to compute the expected node count. Both engines pass 41 traces, including
32 generated traces, all 23 splits of the representative trace, 92 invalid inputs,
32 snapshot cases, 16 capacity/limit cases and 22 publication cases. Boundary checks
reach 8192 nodes, 128-character terms and the usage limit. All eight Python/Rust
writer-updater-reader combinations preserve exact snapshots, dictionary exports
and event bytes through pruning, usage updates and restoration.

Test hooks `AUTOCOMPLETE_FAIL` and `AUTOCOMPLETE_PAUSE` accept `validated`, `stage`,
`state.json`, `dictionary.json`, `events.jsonl`, `report.json`, `ready` or `published`.
`AUTOCOMPLETE_CONTINUE` names the file that releases a pause. Leave them unset for
normal use. Generated Rust retains named structs/functions, recursive collection
fields and source-line comments, with explicit owned copies and error checks.

## 056: Bloom-filter ingestion gate

[Four Python modules](056_bloom_gate/main.py), 395 substantive lines, size a Bloom
filter, ingest keys, compare probable duplicates with an exact audit set, and save
the raw bit array with a validated snapshot. All application modules transpile;
there is no application-specific Rust or Python runtime in the resulting binary.

```bash
python tools/corpus.py 056
python tools/check_bloom_gate.py
python tools/check_external_sort.py
python tools/check_ring_recorder.py
python tools/check_interval_browser.py
```

Copy [bloom-job.json](056_bloom_gate/bloom-job.json) and
[trace.json](056_bloom_gate/trace.json) into a working directory. The default mode
previews and validates without writing:

```bash
BLOOM_CONFIG=/absolute/work/bloom-job.json build/corpus/056/corpus_056
BLOOM_CONFIG=/absolute/work/bloom-job.json BLOOM_MODE=write build/corpus/056/corpus_056
```

Paths are relative to the configuration file. Its exact fields are:

| Field | Contract |
| --- | --- |
| `trace` | JSON array of commands, at most 2,000 commands and 4 MiB |
| `state` | Empty string for a fresh filter, or an existing checksummed snapshot up to 8 MiB |
| `expected` | Expected distinct keys, 1–4,096; used for sizing |
| `probability_ppm` | Target false-positive probability in parts per million, 1–999,999 |
| `capacity` | Hard limit on exact audit keys, 1–4,096; independent of `expected` |
| `output` | A new directory whose parent exists; existing destinations are rejected |

The configuration is at most 64 KiB. Inputs must be regular files, with stable
identity/metadata during reading and before publication. Symlinks are rejected.
Keys preserve exact Unicode text, including empty strings and embedded NULs;
there is no normalization. Each key has at most 128 Unicode scalar values and
512 UTF-8 bytes. Lifetime steps/counters are bounded by 1,000,000,000.

Sizing uses `ceil(-n*log(p)/log(2)^2)` bits and
`max(1, floor((m/n)*log(2)+0.5))` hashes, following the usual Bloom-filter sizing
approximation. This probability is a design target, not a guarantee for a specific
input distribution or an overloaded filter. See Broder and Mitzenmacher's
[Network Applications of Bloom Filters](https://www.internetmathematicsjournal.com/article/1393-network-applications-of-bloom-filters-a-survey/attachment/4337.pdf).

For each zero-based hash counter, SHA-256 hashes the bytes
`b"py2rust-bloom-v1\x00" + counter.to_bytes(2, "big") + key.encode()`.
The first seven digest bytes form an unsigned big-endian integer modulo the bit
count. Position `i` is bit `i % 8` in byte `i // 8`, least significant bit first.
The unused high bits of the last byte remain zero. This fixed scheme is versioned
with the snapshot; the filter does not support deletion or changing its sizing.

| Command | Behavior |
| --- | --- |
| `{"op":"INGEST","key":"text"}` | Report probable/exact duplication; insert a new key unless audit capacity is full |
| `{"op":"CHECK","key":"text"}` | Report probable/exact duplication without inserting |
| `{"op":"INSPECT"}` | Return sizing, storage, occupancy and lifetime measurements |
| `{"op":"EXPORT"}` | Return all exact audit keys in Unicode lexicographic order |

Every command produces an event with its lifetime step. Key tests report
`likely_duplicate`, `exact_duplicate` and `false_positive`. Ingestion decisions
are `accepted`, `duplicate` or `refused`; a false positive can still be accepted
because the audit set establishes whether it is actually new. Refusal at capacity
leaves the bits and keys unchanged. A known key producing a negative result is an
error. No command silently treats a Bloom positive as proof of duplication.

Measurements count all tests from both INGEST and CHECK, absent-key tests,
false positives, ingestion attempts, accepted keys, duplicates and refusals.
`measured_false_positive_ppm` is `floor(false_positives*1_000_000/absent_tests)`,
or null when no absent key has been tested. Repeated tests count repeatedly.
Storage reports distinguish actual filter bytes and occupied bits from raw audit
key UTF-8 payload bytes; the latter excludes set/container and JSON overhead.
This audited application stores exact keys for validation, so its total storage
is larger than the standalone Bloom bit array.

Write mode publishes one complete bundle:

- `state.json`: canonical checksummed parameters, bits, sorted audit keys and counters.
- `filter.bin`: the raw bit array, exactly `ceil(bit_count/8)` bytes.
- `keys.json`: canonical sorted exact keys.
- `events.jsonl`: the complete command history for this run, at most 16 MiB.
- `report.json`: the same summary printed to stdout.

Restoration recalculates sizing and rebuilds every bit from the saved keys,
rejecting changed configuration, inconsistent bits/padding, unordered/duplicate
keys, unsupported versions, invalid counters and checksum mismatches. The checksum
detects inconsistency; it does not authenticate a snapshot against a malicious
writer. Reports do not reconstruct historical counters from an event log.

Publication writes and syncs files in a sibling `.bloom-*` staging directory,
rechecks inputs, then renames the directory without replacing another writer's
destination. Handled failures clean up staging. Process termination may leave a
staging directory; a later run preserves it and uses a fresh directory. A failure
after publication leaves the complete bundle visible. Parent directories/external
writers are trusted, and power loss is not simulated.

The independent oracle uses Python's arbitrary-precision integer as a bitset,
`hashlib`, and a separate exact key set. Both engines pass 36 traces (32 generated),
12 restart splits, 68 invalid inputs, 49 snapshot rejection cases, 18 capacity/limit
cases and 23 publication cases. Checks include a deliberately saturated one-bit
filter, 4,096 audit keys, maximum-length Unicode keys, all input byte boundaries,
false-positive counts and inserted-key lookups. All eight Python/Rust
writer-updater-reader combinations preserve the actual snapshot, bit-array and
event bytes across save/resume/check operations.

Fault hooks `BLOOM_FAIL` and `BLOOM_PAUSE` accept `validated`, `stage`, `state.json`,
`filter.bin`, `keys.json`, `events.jsonl`, `report.json`, `ready` or `published`.
`BLOOM_CONTINUE` names the file that releases a pause. Leave these unset normally.
Generated Rust retains named structs/functions, `Vec<u8>` buffers and source-line
comments, with explicit checked operations and owned copies.

## External record sorter (057)

The [four-module Python project](057_external_sort/main.py) sorts complete JSONL
files with stable integer or Unicode string keys. Its application logic—including
run creation, checksummed readers, heap merging, cleanup and publication—transpiles
to Rust. It uses no application-specific Rust or Python runtime in the executable.

Start with `main.py` for the pipeline. `model.py` defines the job, rows and run
metadata; `runs.py` contains batching and merging; `storage.py` handles paths,
ownership and recovery. The project has 499 substantive Python lines. The generated
`build/corpus/057/rust/src/main.rs` retains those named functions and source locations.

```mermaid
flowchart LR
    inputs[JSONL input files] --> batch[Bounded batch]
    batch --> runs[Stable sorted runs]
    runs --> merge[Heap merge passes]
    merge --> bundle[Synced result bundle]
    bundle --> output[Atomic publication]
```

Copy `057_external_sort/sort-job.json` and `records.jsonl` into a working directory,
then run `build/corpus/057/corpus_057` from that directory, or set `SORT_CONFIG` to
an absolute configuration path. Relative input, workspace and output paths resolve
against that configuration's directory. The sample creates `sorted-run/sorted.jsonl`
and `sorted-run/report.json`; the final directory must not already exist.

```json
{
  "inputs": ["records.jsonl"],
  "field": "priority",
  "kind": "integer",
  "chunk_bytes": 4096,
  "record_bytes": 4096,
  "fan_in": 2,
  "max_rows": 1000,
  "memory_mib": 128,
  "output": "sorted-run",
  "workspace": "sort-work"
}
```

All ten fields are required and unknown fields are rejected:

| Field | Contract |
| --- | --- |
| `inputs` | 1–16 regular files; at most 1 GiB of total input metadata sizes |
| `field` | One top-level key, 1–128 Unicode characters and at most 512 UTF-8 bytes |
| `kind` | `integer` for strict signed-i64 values, or `string` for exact Unicode order |
| `chunk_bytes` | 4 KiB–4 MiB of canonical record data per batch |
| `record_bytes` | 256–65,536 bytes, no greater than `chunk_bytes`; bounds physical and canonical records |
| `fan_in` | 2–8 input runs per merge |
| `max_rows` | 1–1,000,000 input records |
| `memory_mib` | 128–1024 MiB Unix process address-space limit |
| `output` | A new result directory with an existing parent |
| `workspace` | A dedicated temporary-work directory with an existing parent |

Records must be JSON objects with the declared key type. LF, CRLF and a final
record without a newline work. Blank rows, malformed UTF-8/JSON, missing keys and
oversized records fail with the input path and one-based physical line number.
The shared JSON adapter's duplicate-object-key behavior is last value wins.
Other fields survive as JSON values in canonical serialization. Repeated input
paths intentionally contribute repeated records. Equal keys retain file-list
order and then physical input order; string keys are neither normalized nor folded.

Each batch is capped at 4096 rows in addition to its byte budget. Before reading
another record, the generator reserves enough space for a maximum-size record.
It writes at most 4096 initial runs. Run records retain the original sequence
number, so ties remain stable through every merge pass. A pass uses at most eight
readers and one writer, while a heap selects the next row. Every write checks
monotonic order; each run reader verifies its expected size, count and SHA-256.
The final file contains the original JSON objects without intermediate metadata.

`chunk_bytes` bounds record data, not total interpreter/native object overhead.
The process separately lowers its actual Unix `RLIMIT_AS` to `memory_mib`, preserving
an inherited tighter bound. The acceptance check sorts a roughly 160 MiB dataset
with a 128 MiB address-space limit, compares its entire output hash with an
independent CPython in-memory stable sort, and measures peak RSS for each engine.
The large generated files are removed after verification; measurements remain in
`build/corpus/057/runs/<engine>/large-file-measurement.json`.

A persistent owner marker binds the workspace to the canonical workspace, output
and configuration paths. A nonblocking advisory lock excludes another cooperating
sorter or cleanup process. On startup, the sorter validates the whole cleanup set
before removing reserved `run-*.jsonl` files and an incomplete result bundle.
Unknown names, unexpected directories and symlinks cause refusal without removal.
An interrupted first marker write can be repaired only when its bytes are a prefix
of the exact expected marker and the directory contains no unrelated entries.
Hard-linked owner markers are rejected; the lock file itself may have hard links.

Handled failures clean up their temporary files. After a killed process, the next
run recovers them automatically. `SORT_MODE=cleanup` performs only that recovery,
without opening input files or removing an already published result. Keep the
owner marker and lock in place. For a different job/output path, use a fresh
workspace. This uses ordinary path checks and cooperative locking; it does not
claim isolation from hostile concurrent filesystem replacements.

The final sorted file and report are synced in a temporary bundle. The sorter
rechecks input/configuration metadata, atomically publishes the bundle without
overwriting an existing destination, and syncs its parent directory. A failure
after publication can return an error while leaving the complete result visible.
Changes after the final metadata check are outside this snapshot guarantee.

The report includes rows and bytes per input, initial run count, merge passes,
peak batch bytes, output size/SHA-256, actual address-space limit and recovered
file count. This milestone checks 38 reference cases, 79 invalid inputs, 19 recovery cases,
six deliberate file mutations and 23 workspace/boundary cases in each engine.
The large test uses 10,240 records, 732 initial runs and four merge passes.
Its measured peak RSS was about 24.53 MiB in Python and 6.84 MiB in Rust;
these are observations for this fixture, not general memory guarantees.
The eight combinations in `tools/check_external_sort.py` pass actual
output files through Python/Rust sorts with different keys and merge geometries,
checking stable ties, preserved source files and byte-idempotent re-sorting.

`SORT_FAIL` / `SORT_PAUSE` are test hooks for `run-open`, `run-written`, `runs-ready`,
`merge-open`, `merge-written`, `pass:N`, `ready` and `published`. `SORT_CONTINUE`
names a file whose existence releases a pause. Leave these unset normally.
Generated Rust preserves named records/functions and source-line comments;
sorting uses a generic shared helper that computes each key once.

## Time-series ring-buffer recorder (058)

The [four-module recorder](058_ring_recorder/main.py) ingests timestamped numeric
samples, retains a rolling window, summarizes or exports inclusive intervals,
and resumes checksummed snapshots. Its 426 substantive Python lines compile
entirely into Rust. The existing packaged compiler builds it without additional
extensions or application-specific Rust.

`model.py` implements the circular buffer, retention and aggregation;
`persistence.py` validates and reconstructs snapshots; `documents.py` handles
bounded input snapshots and atomic publication; `main.py` runs a complete trace.
The generated source is `build/corpus/058/rust/src/main.rs`.

Run the sample without writing files:

```bash
RING_CONFIG="$PWD/examples/corpus/058_ring_recorder/ring-job.json" \
RING_MODE=preview build/corpus/058/corpus_058
```

To save results, copy `ring-job.json` and `trace.json` into a working directory,
set `RING_CONFIG` to that configuration, and use `RING_MODE=write`. Relative paths
resolve against the configuration directory. The destination must be a new directory
with an existing parent, including in preview mode. The default mode is `preview`.

```json
{
  "trace": "trace.json",
  "state": "",
  "capacity": 3,
  "window_ms": 10,
  "output": "ring-run"
}
```

All fields are required; extra fields are rejected. `capacity` is 1–4096 samples;
`window_ms` is 0–31,536,000,000 milliseconds. An empty `state` starts at logical
clock zero with no samples; otherwise it names a prior `state.json`. Its capacity
and window must match the configuration. Input/configuration/snapshot files must
be regular nonsymlink files. A configuration is at most 64 KiB, and the trace and
snapshot are each at most 1 MiB.

A trace is a JSON array of at most 8192 commands:

| Operation | Required fields besides `op` | Result |
| --- | --- | --- |
| `INGEST` | `time_ms`, `value` | Advance the clock, expire old samples, append a numbered sample and report any capacity overwrite |
| `ADVANCE` | `time_ms` | Advance without ingesting and report the number expired |
| `SUMMARY` | `start_ms`, `end_ms` | Count, sum, mean, minimum, maximum and first/last sample times |
| `EXPORT` | `start_ms`, `end_ms` | Retained samples in chronological ingestion order |
| `INSPECT` | None | Capacity, window, current clock, whole-window summary and lifetime counters |

Timestamps are strict integers from 0 through 253,402,300,799,999 milliseconds.
Ingestion and explicit clock advances must be nondecreasing; rollback is rejected.
Repeated timestamps are retained in ingestion order. Query endpoints are inclusive,
may extend beyond the current clock, and must satisfy `start_ms <= end_ms`.

Retention keeps `[clock_ms - window_ms, clock_ms]`: a sample exactly on the lower
boundary remains until the clock advances past it. A zero-width window therefore
keeps samples at the current timestamp. Time expiration happens before capacity
overwrite; a full buffer discards its oldest remaining sample. The implementation
uses a fixed-size slot array, a head index and a count, with index wraparound.

Values are finite JSON numbers with magnitude at most one billion. They are
stored as binary64; negative zero is normalized to positive zero. Summaries use
Neumaier compensated summation to reduce cancellation error. Binary64 rounding
still applies. An empty summary has sum `0.0`; its mean, extrema and endpoint times
are null. The independent acceptance oracle uses `math.fsum`, comparing floating
summaries within four ULPs for its tested traces while requiring exact retained
samples and counters.

Successful write mode creates a complete bundle:

- `state.json`: canonical state and SHA-256 envelope.
- `events.jsonl`: one canonical response per command, capped at 16 MiB.
- `window.jsonl`: the final retained samples, including sequence, timestamp and value.
- `report.json`: before/after command counts and a final recorder inspection.

Snapshots store chronological samples, without exposing physical slot positions.
Restoration reconstructs a fresh ring and validates the checksum, exact field
sets, bounds, chronological timestamps, consecutive retained sequence numbers,
capacity, retention and lifetime accounting. Ingestions equal expired samples plus
overwritten samples plus the retained count. Command counters sum to total steps;
additional checks reject impossible expiration, overwrite and clock histories.
The lifetime command count is capped at one billion. Restoring and continuing a
wrapped buffer yields the same state and event stream as uninterrupted execution.

All inputs are captured and rechecked before publication. The application syncs
result files and their staging directory, publishes the complete directory with
an atomic no-overwrite rename, and syncs its parent. Handled failures remove their
own staging directory. A killed process may leave an unpublished
`.ring-recorder-*` directory; a later run uses a fresh staging name and preserves
that abandoned directory. A failure after publication may leave a complete result
visible while returning an error. These are cooperative filesystem checks, not
protection against hostile concurrent path replacements.

The acceptance check covers 34 traces, including 28 generated traces and 14 split
restarts, 94 invalid inputs, 83 invalid snapshots, 13 publication scenarios and
10 path cases in each engine. Boundary cases cover two complete laps at capacity
4096, maximum trace/input sizes, lifetime-counter saturation and the event-size
limit. `tools/check_ring_recorder.py` passes actual snapshots through all eight
Python/Rust writer-updater-reader combinations, including cancellation-sensitive
sums, exact expiration boundaries and restoration of an empty ring.

Fault hooks `RING_FAIL` and `RING_PAUSE` accept `validated`, `stage`, `state.json`,
`events.jsonl`, `window.jsonl`, `report.json`, `ready` and `published`.
`RING_CONTINUE` names a file that releases a pause. Leave these unset normally.

## Interval-indexed log browser (059)

The [four-module browser](059_interval_browser/main.py) imports event spans,
indexes overlaps, applies updates/deletions, retrieves individual events, and
queries ranges or points with optional text filtering and pagination. All 422
substantive Python lines compile into standalone Rust using the existing compiler.

`index.py` contains typed events, recursive tree nodes and browser operations;
`persistence.py` handles imports and snapshots; `documents.py` protects input
snapshots and publishes result bundles; `main.py` connects the complete pipeline.
Generated Rust is in `build/corpus/059/rust/src/main.rs`.

Run the sample without publishing files:

```bash
INTERVAL_CONFIG="$PWD/examples/corpus/059_interval_browser/interval-job.json" \
INTERVAL_MODE=preview build/corpus/059/corpus_059
```

For saved results, copy the three JSON assets into a working directory, point
`INTERVAL_CONFIG` at its configuration, and set `INTERVAL_MODE=write`. Relative
paths resolve against the configuration directory. The destination must be a
new directory with an existing parent, including in preview mode. The default
mode is `preview`.

```json
{
  "records": "records.json",
  "trace": "trace.json",
  "state": "",
  "capacity": 16,
  "output": "interval-run"
}
```

All configuration fields are required and extra fields are rejected. Capacity
is 1–1024 records. `state` may name a previous `state.json`, or be empty for a fresh
index. `records` may name a JSON event array or be empty to skip importing.
Imports add new IDs and replace existing IDs in restored state; duplicate IDs
within one import are rejected. Imports do not increment the trace step counter.
An over-capacity import fails as a whole, without publishing a partial result.

Every event has exactly these fields:

```json
{
  "id": "request-17",
  "start_ms": 100,
  "end_ms": 250,
  "text": "Request completed",
  "data": {"status": 200}
}
```

IDs are case-sensitive, nonempty strings of at most 64 characters / 256 UTF-8
bytes. Text allows up to 256 characters / 1024 UTF-8 bytes, including empty text.
Opaque JSON data is limited to 4096 canonical UTF-8 bytes and depth eight below
its root. Timestamps are strict signed-64-bit integers; `start_ms <= end_ms`.
The full integer range is supported without computing a potentially overflowing
duration or incrementing a point timestamp.

Spans are **half-open**: `[start_ms, end_ms)`. Touching endpoints do not overlap.
Empty spans are retained and retrievable by ID, but never match an overlap or
point query. Empty query ranges return no hits. Point queries include a span's
start and exclude its end. Results are ordered by `(start_ms, end_ms, id)`.

A trace is an array of at most 2048 commands:

| Operation | Required fields besides `op` | Behavior |
| --- | --- | --- |
| `PUT` | `event` | Add or replace a validated event, returning its previous value; a new ID at capacity returns `accepted: false` |
| `DELETE` | `id` | Remove an event and return it with a `found` flag |
| `GET` | `id` | Retrieve an event, or return `found: false` and null |
| `QUERY` | `start_ms`, `end_ms`, `text`, `offset`, `limit` | Query a half-open range |
| `POINT` | `time_ms`, `text`, `offset`, `limit` | Query one timestamp |
| `INSPECT` | None | Report capacity, record count, step count, tree height and outer bounds |

Query `text` is a Unicode case-folded substring filter; `""` matches all labels.
No normalization, stemming or regular-expression interpretation is applied.
`offset` is 0–1024 and `limit` is 1–1024. Responses include paginated `hits`, total
matching `count`, `more`, and `visited_nodes`. Unknown fields, malformed records
and inverted query bounds abort the trace with its one-based command number.

The index is a balanced binary tree ordered by event rank. Each subtree caches
its minimum start and maximum end, allowing range/point queries to skip disjoint
subtrees. In-order traversal preserves result ordering. Imports and successful
mutations rebuild the tree from sorted records; this keeps tree shape independent
of insertion history and snapshot restoration. Capacity bounds the rebuild cost.
The native subset owns its values and may copy trees: `visited_nodes` counts
examined tree nodes, not total allocation or runtime cost.

Snapshots store records and the lifetime step count, not derived tree metadata.
Restoration checks the SHA-256 envelope, exact schema, version, capacity, unique
IDs, record bounds and step limit before rebuilding the index. Trace commands
increment the step count, including missing lookups/deletions and capacity-refused
puts. The lifetime step limit is one billion.

Write mode publishes four files together:

- `state.json`: canonical checksummed snapshot, with events ordered by ID.
- `events.jsonl`: one canonical command response per line, limited to 16 MiB.
- `records.jsonl`: final events ordered by interval rank, including empty spans.
- `report.json`: import accounting, before/after steps and final index inspection.

Configuration size is limited to 64 KiB; imports and traces to 4 MiB each; snapshots
to 8 MiB. Inputs must be regular nonsymlink files. Their metadata is rechecked
before publishing a synced staging bundle with an atomic no-overwrite rename.
Handled failures remove their own staging directory. A killed process may leave
an unpublished `.interval-browser-*` directory; a subsequent run uses a fresh
staging name and preserves it. Post-publication failures can leave a complete
result visible while returning an error. These are cooperative filesystem checks,
not protection against hostile concurrent path replacements.

Acceptance covers 32 traces, including 28 generated traces and 14 split restarts,
131 invalid inputs, 32 invalid snapshots, 14 publication scenarios and 11 path
cases in each engine. Every query is compared with an independent brute-force
predicate and result ordering. At capacity 1024, tested single-hit queries over
disjoint spans visit at most 11 nodes; out-of-range and empty queries visit zero;
a query covering all spans visits all 1024. Tests also cover cached-bound changes
after updates/deletion, signed-integer extremes, Unicode filters, pagination,
exact byte/depth limits and lifetime-counter saturation.

`tools/check_interval_browser.py` passes actual snapshots through all eight
Python/Rust writer-updater-reader combinations, checking complete versus split
execution, removal of broad spans, point boundaries, empty spans and replacement
imports after restoration.

Fault hooks `INTERVAL_FAIL` and `INTERVAL_PAUSE` accept `validated`, `stage`,
`state.json`, `events.jsonl`, `records.jsonl`, `report.json`, `ready` and `published`.
`INTERVAL_CONTINUE` names a file that releases a pause. Leave these unset normally.

## 060 — Append-only miniature database

The [four-module database](060_mini_database/main.py) implements a durable key-value
store with `GET`, `SET`, `DELETE`, inspection and snapshot compaction. All 398
substantive Python lines compile to standalone Rust using the existing compiler.
`model.py` defines typed state and validation; `storage.py` handles owned files,
locking and initialization; `journal.py` implements framing, recovery and
compaction; `main.py` executes command batches and prints responses. Generated
Rust is in `build/corpus/060/rust/src/main.rs`.

Copy `database-job.json` and `trace.json` into a working directory before running
the sample. It creates a persistent `database` directory beside those files:

```bash
DB_CONFIG=/absolute/path/to/work/database-job.json build/corpus/060/corpus_060
```

The executable runs without Python installed. `DB_CONFIG` defaults to
`database-job.json` in the current directory. Its exact configuration is:

```json
{"database": "database", "trace": "trace.json", "capacity": 16}
```

Paths resolve relative to the configuration file. The database must be a new or
previously initialized directory with an existing parent. Its ownership marker
binds it to its canonical directory path and capacity, so moving or copying the
managed files to another directory is rejected. Configuration and trace files
must remain outside the database. All inputs and managed files must be regular
nonsymlink files; managed files with hard links are rejected. An advisory lock
excludes cooperating writers/readers for the entire batch. Unknown database files
are preserved and cause startup to fail. These checks assume a cooperative local
filesystem; they do not protect against hostile concurrent path replacement.

The trace is a JSON array of commands with exact fields:

| Operation | Fields besides `op` | Response |
| --- | --- | --- |
| `SET` | `key`, `value` | Previous `found`/`value`, then `committed: true` after synchronization |
| `DELETE` | `key` | Previous `found`/`value`, then `committed: true` after synchronization |
| `GET` | `key` | Current `found`/`value`; missing values return null with `found: false` |
| `DUMP` | None | Complete `values` object |
| `INFO` | None | `keys`, configured `capacity`, and `journal_bytes` |
| `COMPACT` | None | Completion after snapshot publication and journal synchronization |

Every response includes the committed mutation `sequence`. `SET` increments it
even when replacing an equal value; `DELETE` increments it even when the key is
absent. Reads and compaction do not increment it. Missing and stored-null values
remain distinguishable. New keys at capacity fail before writing; replacement
at capacity is allowed. The process prints an initial `OPEN` response with the
recovered sequence, number of replayed records, discarded tail byte count and
whether it removed an abandoned `snapshot.next`.

Each mutation is independently committed. A later command error exits with status
2 and its one-based command number, preserving earlier committed records and
responses. The trace is not a transaction. A client losing its connection/process
after a complete commit marker was written but before receiving a response may
find that mutation present on restart. Retrying a command is not deduplicated.

The binary journal has an explicit, interoperable frame format:

| Field | Bytes | Encoding |
| --- | --- | --- |
| Magic | 8 | `PYDB060!` |
| Payload length | 4 | Unsigned big-endian |
| Mutation sequence | 8 | Unsigned big-endian |
| Checksum | 32 | Raw SHA-256 of sequence bytes followed by payload bytes |
| Payload | 1–8192 | UTF-8 JSON `SET` or `DELETE` command |
| Commit marker | 16 | `DONE060!` followed by the same eight sequence bytes |

Writers serialize canonical JSON. The header and payload are synchronized before
writing the marker; the complete marker is synchronized before acknowledging the
mutation. Recovery validates framing, record schemas, checksums and consecutive
sequences. It applies only complete committed records newer than the snapshot.
A valid incomplete final header, payload or marker is truncated and synchronized
before commands begin. Known-invalid magic, lengths, sequences, complete payloads
or marker bytes cause refusal without truncation. SHA-256 detects accidental
corruption; it is not authentication and does not detect every possible deletion
of an otherwise valid journal suffix.

Compaction writes and syncs a checksummed logical snapshot to `snapshot.next`,
atomically replaces `state.json`, syncs the directory, and only then truncates and
syncs the journal. Restart therefore supports both the published snapshot with
its old journal and the published snapshot with an empty journal. Covered journal
records are still validated. An abandoned `snapshot.next` is removed only after
successful snapshot/journal validation. Initialization similarly publishes its
complete ownership marker only after creating and syncing the empty journal;
a valid interrupted prefix can be repaired only while the journal remains empty.
An initialized database with a missing journal is rejected.

Bounds are explicit: capacity 1–256 keys; keys 1–128 characters / at most 512 UTF-8
bytes; values at most 4096 canonical UTF-8 bytes with nesting depth eight; 1024
commands per trace; mutation sequence at most one billion. Configuration, trace,
snapshot and journal limits are respectively 64 KiB, 1 MiB, 4 MiB and 16 MiB.
A full journal refuses new mutations until `COMPACT` is requested. The application
lowers its address-space limit to at most 256 MiB. This is a deliberately bounded
local store with synchronous writes, not an unbounded database server.

Acceptance compares 28 traces (24 generated), 28 split runs, exact persisted
bytes and canonical responses against an independent dictionary/`struct`/`hashlib`
oracle. It covers 117 byte positions of a final frame, 25 append interruptions,
21 compaction interruptions, six initialization interruptions, four recovery
interruptions, lock contention, 90 invalid inputs, 21 damaged journals, 28 damaged
snapshots and 31 path/ownership cases in each engine. Both injected exceptions and
actual process kills are used, including kills after earlier acknowledged writes,
interrupted deletions and replacement of existing snapshots. Tests fill a journal
to exactly 16 MiB (4000 records), reject a further append, then compact and append
successfully. They also exercise exact size/depth/key/count limits and sequence
saturation. These are process-crash tests; physical power-loss behavior depends
on the operating system, filesystem and storage honoring synchronization.

`tools/check_mini_database.py` passes the same actual database directory through
all eight Python/Rust writer-updater-reader combinations. It includes snapshots,
new journal records, killed incomplete commits, cross-engine recovery, compaction,
and reopening by the original writer. Final snapshots, journal bytes and responses
match across all combinations.

Fault hooks `DB_FAIL` and `DB_PAUSE` accept `label:sequence`. Append labels are
`header-part`, `header-written`, `body-part`, `body-written`, `body-synced`,
`commit-part`, `commit-written`, and `commit-synced`. Compaction labels are
`snapshot-part`, `snapshot-written`, `snapshot-synced`, `snapshot-published`,
`snapshot-directory`, `journal-truncated`, and `journal-cleared`. Initialization
labels are `owner-prefix:0`, `journal-created:0`, and `owner-complete:0`; recovery
uses `recovery-truncated` and `recovery-synced` at the recovered sequence.
`DB_CONTINUE` names a file that releases a pause. Leave these hooks unset normally.

## 062 — Dependency build planner

The [four-module planner](062_build_planner/main.py) reads targets and dependency
edges, selects requested targets and their prerequisites, produces deterministic
build layers, and explains cycles. All 357 substantive Python lines compile to
standalone Rust using the existing compiler. `model.py` validates and normalizes
the graph; `planner.py` implements traversal, layering and cycle witnesses;
`documents.py` protects inputs and publishes complete bundles; `main.py` produces
JSON and readable reports. Generated Rust is in
`build/corpus/062/rust/src/main.rs`.

Preview the sample without creating a result directory:

```bash
BUILD_CONFIG="$PWD/examples/corpus/062_build_planner/build-job.json" \
BUILD_MODE=preview build/corpus/062/corpus_062
```

The sample deliberately includes a cyclic request, so it prints all three plans
and exits with status **1**. Exit 0 means every requested plan is ready; exit 1
means at least one selected dependency closure contains a cycle; exit 2 means
invalid input, an I/O error or an injected failure. In write mode, cyclic plans
still publish their complete diagnostic bundle. Target commands are metadata:
the planner does not execute them or invoke a shell.

Copy the three JSON assets into a working directory and use `BUILD_MODE=write`
to save results. `BUILD_CONFIG` defaults to `build-job.json` in the current
directory; `BUILD_MODE` defaults to `preview`. Configuration has exactly:

```json
{"graph": "graph.json", "requests": "requests.json", "output": "build-plan"}
```

Relative paths resolve against the configuration directory. The output must be
a new directory with an existing parent, including in preview mode. Inputs must
be regular nonsymlink files. Graph documents have this exact shape:

```json
{
  "version": 1,
  "targets": [
    {"name": "compile", "command": ["cc", "-c", "main.c"]},
    {"name": "package", "command": []}
  ],
  "edges": [{"target": "package", "requires": "compile"}]
}
```

An edge points from a target to a prerequisite: `target` requires `requires`.
Target names are unique, case-sensitive Unicode strings; no normalization is
applied. Both edge endpoints must exist, and duplicate edges are rejected.
Self-dependencies are valid graph input and produce cycle diagnostics when
selected. An empty command array describes an aggregate target; otherwise its
first argument must be nonempty. Later arguments may be empty. Arguments remain
literal JSON strings, including spaces, quotes and newlines.

The request file is an array:

```json
[
  {"id": "release", "targets": ["package"]},
  {"id": "nothing", "targets": []}
]
```

Request IDs must be unique; every requested target must exist. Repeated target
names in a request are deduplicated and sorted. An empty selection selects
nothing, not the whole graph. Empty graphs and empty request batches are allowed.
All graph input is validated even if no request uses a particular target or edge.

Each plan includes its ID, normalized `requested` targets, transitive `selected`
closure, additional `prerequisites`, `layers`, flattened `order`, `blocked`
targets, status and cycle explanation. Layers contain lexicographically sorted
target names. Every prerequisite is in an earlier layer than its dependent.
Targets appear at their earliest dependency level, assuming no worker/resource
limits; these are dependency layers, not duration estimates. Input target order,
edge order and selection order do not change the plan or exported bytes. Request
records retain their original batch order, and command arguments retain their
original argument order.

Only cycles reachable through the selected prerequisites affect a request.
`blocked` contains exactly the selected targets that belong to or depend on a
cycle. Independent buildable prerequisites still appear in `layers` and `order`.
A cyclic plan provides one deterministic `cycle` witness with its first vertex
repeated at the end, and a `requires_path` from a requested target to that cycle's
first vertex. Each adjacent pair in both lists is an actual target-to-prerequisite
edge. The witness demonstrates one blocking cycle; it does not enumerate every
cycle or strongly connected component. Ready plans have empty witness lists.

Prerequisite traversal uses an explicit work list; layer construction uses
remaining prerequisite counts and reverse edges. Cycle discovery uses an
explicit stack with path positions, so long cycles do not require recursive
application calls. The independent verifier uses transitive closure and longest
paths instead of reproducing these algorithms.

Write mode publishes five files atomically:

- `graph.json`: canonical graph with sorted targets and edges.
- `requests.json`: canonical normalized requests, reusable with the exported graph.
- `plan.json`: the complete report, byte-identical to standard output.
- `plan.txt`: readable layers, literal argument arrays, blocked targets and witnesses.
- `manifest.json`: byte counts and SHA-256 hashes for the other four files.

The report also includes the exported graph's SHA-256 and target/edge counts.
Input metadata is checked before publication; a changed input aborts the write.
Files are synchronized in a staging directory, then the complete directory is
published with an atomic no-overwrite rename. Handled failures remove their own
staging directory. A killed process can leave `.build-plan-*` staging files; a
later run preserves them and uses a fresh name. A failure after publication can
leave a complete bundle visible while returning an error. These are cooperative
filesystem checks, not protection against hostile path replacement.

Bounds: 256 targets, 4096 edges, 128 requests, and 256 supplied target entries per
request before deduplication. Target names and request IDs allow 1–128 characters
and up to 512 UTF-8 bytes. A command allows up to 32 arguments of at most 1024
characters / 4096 UTF-8 bytes each. Names, IDs and arguments must be NUL-free.
Configuration is limited to 64 KiB; graph and request files to 4 MiB each; JSON
and text reports to 16 MiB each. Oversized reports fail before publication.

Acceptance checks all **512 directed graphs on three vertices**, including self
edges, against all eight target subsets: **4096 plans per engine**. Another 32
graphs include 28 generated cases, Unicode names, shared prerequisites, independent
components and empty inputs; 32 shuffled-input reruns must produce identical
bundles. The verifier checks every witness edge and request-to-cycle path,
minimal layers, exact blocked membership, 152 invalid inputs, 14 publication
scenarios and 11 path cases. Boundary tests cover 256-layer chains, 256-vertex
cycles, 4096 edges, maximum argument/name/request sizes, and report overflow.

`tools/check_build_planner.py` exercises all eight Python/Rust
writer-selector-reader combinations using actual exported graph/request paths.
It verifies reselection, unchanged source bundles, byte-identical replanning,
and valid plans after explicitly repairing a cycle in a separate graph fixture.

Fault hooks `BUILD_FAIL` and `BUILD_PAUSE` accept `validated`, `stage`,
`graph.json`, `requests.json`, `plan.json`, `plan.txt`, `manifest.json`, `ready`,
and `published`. `BUILD_CONTINUE` names a file that releases a pause. Leave
these hooks unset normally.

## 063 — Small shift scheduler

The [four-module scheduler](063_shift_scheduler/main.py) reads worker availability
and staffing requirements, searches complete assignments, scores them and explains
infeasible or unfinished searches. All 470 substantive Python lines compile to
standalone Rust using the existing compiler. `model.py` validates typed workers,
shifts and canonical inputs; `solver.py` implements bounded iterative backtracking;
`documents.py` protects inputs and publishes bundles; `main.py` presents and saves
results. Generated Rust is in `build/corpus/063/rust/src/main.rs`.

Preview the sample:

```bash
SHIFT_CONFIG="$PWD/examples/corpus/063_shift_scheduler/shift-job.json" \
SHIFT_MODE=preview build/corpus/063/corpus_063
```

The sample's proven optimum has score **7**: Ben covers the afternoon, while Ada
and Chen cover the morning. Copy the two JSON assets into a working directory
and use `SHIFT_MODE=write` to save the schedule. `SHIFT_CONFIG` defaults to
`shift-job.json` in the current directory; the default mode is `preview`.
Configuration has exactly:

```json
{"problem": "staffing.json", "output": "shift-schedule"}
```

Relative paths resolve against the configuration directory. The output must be a
new directory with an existing parent, including in preview mode. Inputs must be
regular nonsymlink files. A staffing problem has this shape:

```json
{
  "version": 1,
  "rest_minutes": 60,
  "balance_weight": 2,
  "budget": 100000,
  "workers": [
    {
      "id": "Ada",
      "skills": ["support"],
      "availability": [{"start": 480, "end": 1080}],
      "max_minutes": 480,
      "max_shifts": 2,
      "preferences": {"morning": 0}
    }
  ],
  "shifts": [
    {"id": "morning", "start": 480, "end": 720, "required": 1, "skill": "support"}
  ]
}
```

Every shown field is required; unknown fields are rejected. Times are integer
minutes within a 10080-minute planning week, independent of civil dates or time
zones. Shifts and availability use half-open intervals `[start, end)` with
positive length. Each shift lasts at most 1440 minutes. Unordered, overlapping,
duplicate or adjacent availability windows are merged into their union. A shift
must be wholly covered by that union. Worker IDs and shift IDs are unique within
their respective namespaces; names and skills are case-sensitive Unicode strings
without normalization. Duplicate skills are deduplicated.

Every returned complete schedule satisfies all these hard constraints:

- Exactly the required number of distinct workers covers each shift.
- Every assigned worker has the shift's skill and full availability.
- A worker's assigned shifts do not overlap and leave at least `rest_minutes`
  between the earlier end and later start; equality at the boundary is allowed.
- Total assigned duration and shift count stay within that worker's limits.

A zero-staff shift needs no workers. Empty worker or shift lists are allowed;
an empty staffing requirement has an optimal empty assignment with score zero.
Zero worker limits and empty skills/availability are valid and can make the
problem infeasible. Preferences may reference only declared shifts. Missing
preference entries cost zero; explicit costs are nonnegative integers.

The objective is to minimize:

```text
sum(assigned worker/shift preference costs)
  + balance_weight * sum(each worker's assigned shift count squared)
```

Balance concerns shift counts, not minutes. When scores tie, the scheduler chooses
the lexicographically smallest worker-name sequence after sorting shifts by ID
and workers within each shift. Every schedule includes all shifts, including
empty crews for zero-staff shifts. Input worker, shift, skill and availability
order does not change the report, search count or exported bytes.

Search orders shifts by individual eligible-worker count, start time and ID.
Within each shift it enumerates sorted worker combinations, avoiding equivalent
crew permutations. An explicit backtracking stack tracks choices and incremental
scores. Because every additional score contribution is nonnegative, a prefix
strictly more expensive than the best complete schedule can be pruned. Equal
scores remain searchable to preserve deterministic tie-breaking.

`budget` limits attempted eligible-worker choices, including choices rejected
for workload, rest, combination order or score bounds. It is an operation budget,
not a wall-clock deadline. Preprocessing can prove an individual staffing shortage
without spending any attempts. The report distinguishes four outcomes:

| Status | Meaning |
| --- | --- |
| `optimal` | Complete search proves the returned schedule has the lowest score and deterministic tie-break |
| `feasible` | A valid complete schedule was found, but the budget ended before optimality was proved |
| `unsatisfiable` | An individual shortage or completed search proves no complete schedule satisfies the constraints |
| `search_limit` | The budget ended without finding a complete schedule; infeasibility is not established |

`complete_search` is true for `optimal` and `unsatisfiable`; `attempts` records
choices examined. Only found solutions have a complete `schedule` and a non-null `score`
(otherwise the schedule is empty and score is null). Exit status is 0 for an
optimum, 1 for the other three valid outcomes, and 2 for malformed input, I/O errors
or injected failures. Write mode publishes valid diagnostic outcomes as well as
successful schedules.

For a result without a complete schedule, `shortages` lists shifts with too few
individually eligible workers. `diagnostic_prefix` shows the deepest feasible
partial assignment encountered, clearly separate from `schedule`; `frontier`
reports the next shift and each worker's availability, skill, workload or rest
rejections at that prefix. These local diagnostics do not claim to be a minimal
unsatisfiable constraint set or a global proof by themselves. In `search_limit`,
some frontier workers may still be eligible but unexplored.

Write mode atomically publishes:

- `problem.json`: canonical normalized staffing input, usable for another run.
- `schedule.json`: the complete report, identical to standard output.
- `schedule.txt`: readable assignments or diagnostics.
- `manifest.json`: byte counts and SHA-256 hashes of the other three files.

The report includes the exported problem's SHA-256. Input metadata is checked
before publication. A synced staging directory is published with an atomic
no-overwrite rename; handled failures clean up their own staging files. A killed
process can leave a `.shift-schedule-*` directory that later runs preserve. A
post-publication failure can leave a complete bundle visible while returning an
error. These are cooperative filesystem checks, not protection against hostile
path replacement. Rerunning an exported problem starts a new search; it does not
resume a saved search frontier.

Bounds: at most 12 workers, 12 shifts, four workers required per shift, and 24
staffing positions in total. Budget is 1–100000 attempted choices. Each worker
allows at most eight supplied skills, 32 supplied availability windows, 10080
assigned minutes and 12 assigned shifts. Rest is 0–1440 minutes; preference costs
and balance weight are 0–100. Names allow 1–64 characters / at most 256 UTF-8
bytes and must be NUL-free. Configuration is limited to 64 KiB and the staffing
file to 1 MiB. The maximum feasible objective under these bounds is 31200.

Acceptance checks 144 exhaustive availability/staffing combinations and 81
workload-limit combinations, plus 48 other problems including 40 generated cases.
The independent oracle enumerates shift crews with `itertools`, filters complete
assignments and compares score and tie-breaking. All 48 other problems are rerun
with shuffled inputs and must produce identical bundles. Tests also cover 22
successive search budgets, four explicit status/improvement cases, 177 invalid
inputs, 12 publication scenarios and nine path cases. Capacity checks include a
100000-attempt search, 24 staffing positions, exact field/file limits, boundary
rest gaps, merged availability and the maximum score.

`tools/check_shift_scheduler.py` exercises all eight Python/Rust
writer-updater-reader combinations using actual exported problem paths. It
checks identical replanning, rerunning after increasing a limited budget, source
bundle preservation, and a changed optimum after removing a worker's availability.

Fault hooks `SHIFT_FAIL` and `SHIFT_PAUSE` accept `validated`, `stage`,
`problem.json`, `schedule.json`, `schedule.txt`, `manifest.json`, `ready`, and
`published`. `SHIFT_CONTINUE` names a file that releases a pause. Leave these
hooks unset normally.

## 064 — Parcel packing planner

The [four-module planner](064_parcel_planner/main.py) groups items into packages,
respects finite box inventory and capacity rules, saves package manifests, and
reports every unplaced item. All 427 substantive Python lines compile into
standalone Rust using the existing compiler. `model.py` validates typed inputs;
`packing.py` implements the documented heuristic and accounting; `documents.py`
protects inputs and publishes bundles; `main.py` creates reports and exports.
Generated Rust is in `build/corpus/064/rust/src/main.rs`.

Preview the sample:

```bash
PARCEL_CONFIG="$PWD/examples/corpus/064_parcel_planner/parcel-job.json" \
PARCEL_MODE=preview build/corpus/064/corpus_064
```

The sample assigns four items to three packages and explicitly rejects three,
so it prints a `partial` plan and exits with status **1**. Copy the two JSON assets
into a working directory and use `PARCEL_MODE=write` to retain the complete bundle.
`PARCEL_CONFIG` defaults to `parcel-job.json` in the current directory; the default
mode is `preview`. Configuration has exactly:

```json
{"problem": "packing.json", "output": "parcel-plan"}
```

Paths resolve relative to the configuration directory. The output must be a new
directory with an existing parent, including in preview mode. Inputs must be
regular nonsymlink files. A problem has this exact shape:

```json
{
  "version": 1,
  "max_packages": 3,
  "boxes": [
    {
      "id": "small",
      "weight_limit_g": 10000,
      "volume_limit_cm3": 8000,
      "item_limit": 10,
      "tare_g": 300,
      "cost_cents": 100,
      "stock": 3
    }
  ],
  "items": [
    {"id": "book", "destination": "north", "weight_g": 700,
     "volume_cm3": 400, "separate": false}
  ]
}
```

Every shown field is required; extra fields are rejected. Item IDs and box IDs
must each be unique within their own namespace. Destinations are exact,
case-sensitive labels. Names and destinations are Unicode strings without
normalization. All weights, volumes, counts and costs are strict integers;
`separate` must be a JSON boolean. Tare must be strictly below the box's gross
weight limit. Zero stock, zero package allowance and empty item/box lists are
valid inputs.

Each package enforces:

- Sum of item weights **plus one box tare** does not exceed the gross weight limit.
- Sum of item volumes does not exceed the volume limit.
- Item count does not exceed the box's item limit.
- Every item has the same destination.
- An item with `separate: true` occupies its package alone.

Volume is an aggregate capacity measure; the planner does not model dimensions,
orientation, stacking or three-dimensional geometric fit.

The versioned heuristic is `weight-first-first-fit-v1`:

1. Process items by descending weight, then descending volume, then ascending ID.
2. Try existing packages in creation order; use the first compatible package.
3. If none fits, consider empty box types that fit the item and still have stock.
   Choose by ascending cost, then net weight capacity (`weight_limit_g - tare_g`),
   volume capacity, item capacity and box ID.
4. Open that box if the package-count limit permits, consuming one unit of stock.
   Otherwise retain the item in the rejection report.

Existing capacity remains usable after the stock or package-count limit has been
reached. Dedicated packages are never reused. New package IDs are `package-1`,
`package-2`, and so on in creation order. Items within a package retain placement
order; rejections retain processing order. Reordering the input item or box arrays
does not change the plan or exported bytes.

Each rejection contains the complete original item, `eligible_box_types` that
could fit it empty regardless of stock, `available_box_types` that also still have
stock, and one reason with this precedence:

| Reason | Meaning after no existing package accepted the item |
| --- | --- |
| `no_box_fits` | No supplied box type can meet this item's individual weight and volume requirements |
| `stock_exhausted` | Individually fitting types exist, but none has stock left |
| `package_limit` | An available fitting type exists, but no further package may be opened |

This heuristic does not prove minimum package count or cost. A stock/limit
rejection describes this run, not global infeasibility under every possible
arrangement. A tested example packs weights `6, 5, 3, 2, 2, 2` into capacity-10
boxes as `6+3`, `5+2+2`, and `2`, while `6+2+2` and `5+3+2` fit in two boxes.
With stock two, the greedy run explicitly rejects its last item.

The report includes every package's full item manifest, box type, destination,
net/gross weight, volume, cost and remaining capacities. Inventory reports opened
and remaining counts per type. Totals conserve item identities, weight and volume
across assigned and rejected partitions, and include package cost and tare.
`status` is `complete` when every item is assigned and `partial` otherwise.
Exit codes are 0 for complete, 1 for partial, and 2 for invalid input, I/O errors
or injected failures. Partial plans are valid results and are published in write
mode. The planner only plans inventory use; it does not mutate the source stock.

Write mode atomically publishes six files:

- `problem.json`: canonical reusable input with items and box types sorted by ID.
- `plan.json`: the full report, byte-identical to standard output.
- `packages.jsonl`: one complete package manifest per line.
- `rejected.jsonl`: one complete rejected-item record per line.
- `plan.txt`: readable package assignments, totals and rejection reasons.
- `manifest.json`: byte counts and SHA-256 hashes for the other five files.

The report includes the exported problem's SHA-256. Input metadata is checked
before publication; changed inputs abort the write. Files are synchronized in
a staging directory, then published with an atomic no-overwrite rename. Handled
failures remove their own staging files. A killed process can leave a
`.parcel-plan-*` directory, which subsequent runs preserve. Post-publication
failure can leave a complete bundle visible while returning an error. These are
cooperative filesystem checks, not protection against hostile path replacement.

Bounds: 512 items, 16 box types, 0–512 packages, 0–512 boxes in stock per type and
1–512 items per box. Weight and volume fields allow 1–1000000000; tare and cost
allow 0–1000000000, subject to the tare rule. IDs and destinations allow 1–128
characters / up to 512 UTF-8 bytes and must be NUL-free. Configuration is limited
to 64 KiB; the problem to 4 MiB; each generated data file to 8 MiB. Oversized
reports fail before publication. Aggregate weight, volume and cost can exceed
32-bit ranges; tests reach 512000000000 using exact integer arithmetic.

Acceptance checks 256 exhaustive dimension/package-limit cases and 64 exhaustive
destination/separate-item combinations. Another 62 problems include 48 generated
cases and all six box-choice tie-break examples; every one is rerun with shuffled
inputs and must produce identical bundles. The independent oracle recomputes
capacities from item contents instead of relying on cached package totals, and
a separate audit checks identity conservation and every package constraint.
Tests also cover the heuristic counterexample, 162 invalid inputs, 14 publication
scenarios, nine path cases, maximum capacities, exact input limits and rejection
of an oversized output report.

`tools/check_parcel_planner.py` exercises all eight Python/Rust
writer-updater-reader combinations using actual exported problem paths. It also
reads actual rejected-item manifests into a separate fixture with replenished box
stock, then verifies that the original and recovered package manifests together
contain every original item exactly once. Original bundles remain unchanged.

Fault hooks `PARCEL_FAIL` and `PARCEL_PAUSE` accept `validated`, `stage`,
`problem.json`, `plan.json`, `packages.jsonl`, `rejected.jsonl`, `plan.txt`,
`manifest.json`, `ready`, and `published`. `PARCEL_CONTINUE` names a file that
releases a pause. Leave these hooks unset normally.

## 065 — Terrain route visualizer

The [four-module visualizer](065_terrain_routes/main.py) loads a weighted text
grid, finds routes with A*, renders ASCII maps and exports paths and search
statistics. All 397 substantive Python lines compile into standalone Rust using
the existing compiler. `model.py` validates grids and requests; `routing.py`
contains the search and rendering; `documents.py` protects inputs and publishes
bundles; `main.py` assembles reports. Generated Rust is in
`build/corpus/065/rust/src/main.rs`.

Preview the sample:

```bash
TERRAIN_CONFIG="$PWD/examples/corpus/065_terrain_routes/terrain-job.json" \
TERRAIN_MODE=preview build/corpus/065/corpus_065
```

It produces three found routes, one unreachable destination and one blocked
endpoint, so the sample exits with status **1**. Copy `terrain-job.json`,
`grid.txt`, `terrain.json` and `requests.json` to a working directory and use
`TERRAIN_MODE=write` to save the bundle. The default mode is `preview` and the
default configuration is `terrain-job.json` in the current directory:

```json
{
  "grid": "grid.txt",
  "terrain": "terrain.json",
  "requests": "requests.json",
  "output": "terrain-routes"
}
```

Paths resolve relative to the configuration directory. Output must be a new
directory with an existing parent, including in preview mode. Inputs must be
regular nonsymlink files. Configuration and all JSON objects require exactly the
documented fields. The terrain palette has this shape:

```json
{"version": 1, "costs": {".": 1, "~": 5}}
```

`grid.txt` is a rectangular ASCII grid. `#` is an impassable wall; other symbols
must exist in the palette. LF and CRLF are accepted, with or without one terminal
newline. Bare carriage returns and empty/ragged rows are rejected. A space can
be a terrain symbol. Palette keys are single printable ASCII characters except
reserved `#`, `S`, `G`, `*`, `@` and `X`. An empty palette is valid for an all-wall
grid. Costs are strict nonnegative integers, including zero.

`requests.json` is an ordered array with unique Unicode IDs and zero-based
`[row, column]` coordinates:

```json
[
  {"id": "crossing", "start": [0, 0], "goal": [0, 8]},
  {"id": "same place", "start": [3, 4], "goal": [3, 4]}
]
```

Movement is orthogonal with no diagonals or row wrapping. Each move charges the
cost of **entering** its destination cell; the initial cell costs zero. The
heuristic is Manhattan distance times the minimum cost among traversable cells
actually present in the grid. With zero-cost terrain it becomes Dijkstra's
algorithm. Unused palette entries do not affect the heuristic.

The heap orders entries by estimated total cost, then cost so far, then row-major
cell index. Neighbors are visited up, left, right and down. Only strictly cheaper
paths replace a predecessor; equal-cost paths keep the first predecessor. These
rules make the chosen optimal route deterministic across both engines. The
nonnegative, consistent heuristic allows settled cells to remain closed; obsolete
heap entries are discarded and counted. The search stops when the goal is settled.

Each route reports its ID, endpoints, status, blocked endpoint names, cost, step
count, coordinate path and these statistics:

| Field | Meaning |
| --- | --- |
| `pushed` | All heap insertions, including the initial cell and later improvements |
| `popped` | All removed heap entries, including stale entries |
| `expanded` | Distinct settled cells, including the goal when found |
| `stale` | Removed entries already settled or superseded by a cheaper distance |
| `discovered` | Distinct cells assigned a tentative distance |
| `frontier_peak` | Largest heap size, including stale entries still queued |
| `frontier_remaining` | Heap entries left when the search stops |

A `found` path includes both endpoints. A passable start equal to the goal has
cost and steps zero and a one-cell path. `unreachable` means both endpoints are
passable but disconnected; the reachable component is fully explored. `blocked`
reports `start`, `goal`, or both when their cells are walls, with no search.
Unreachable and blocked routes have null cost, zero steps and empty paths.
An empty request array is valid. Exit codes are 0 when every request is found,
1 when any valid request is unreachable or blocked, and 2 for invalid input,
I/O errors or injected faults. Batch counts distinguish all three statuses.

Write mode produces one atomic seven-file bundle:

- `grid.txt`, `terrain.json` and `requests.json`: normalized, reusable inputs.
- `routes.json`: the complete canonical report, identical to stdout, with input
  SHA-256 hashes, grid metadata, status counts and ordered routes.
- `paths.jsonl`: one complete route record per line.
- `routes.txt`: legend and one ASCII map per request. `S` and `G` mark endpoints,
  `@` coincident endpoints, `*` the path and `X` a blocked endpoint. IDs are JSON
  escaped so embedded newlines cannot create misleading map headings.
- `manifest.json`: exact byte lengths and SHA-256 hashes of the other six files.

Inputs are checked again before publication. Files are written and synced in a
private staging directory, then renamed without replacing an existing output.
Handled failures remove their staging directory. A killed process can leave a
staging directory; a new run uses a new name and preserves the abandoned one.

Bounds are 64 rows by 64 columns, 16 terrain symbols, 64 queries, 64 characters
and 256 UTF-8 bytes per nonempty NUL-free ID, and cell costs from 0 through
1,000,000,000. Reads are capped at 64 KiB for configuration and terrain JSON,
8 KiB for raw grid bytes, and 1 MiB for requests. Each generated data file also
has a defensive 16 MiB guard. Current structural limits keep valid outputs below
that guard. Costs and search accounting use checked native integers.

Acceptance checks run independently against Python and Rust. All 226 tiny grid
variants cover 4,896 endpoint queries per engine, with Bellman–Ford relaxation
as the reference. Sixty additional grids cover seeded larger maps, weighted
longer detours, zero costs, isolated goals that drain stale entries, spaces,
escaped IDs, empty requests and exact statistics. Larger maps are checked by an
independent ordinary Dijkstra solver. Sixty LF/CRLF and palette-order variants
produce identical export bytes. Every returned path is checked for endpoints,
adjacency, wall avoidance, cost and cycle freedom; accounting and ASCII maps are
also independently checked.

Boundary checks include a 64×64 open map, all 16 symbols, 256-byte IDs and 64
queries through a 2,078-step maze, each costing 2,078,000,000,000. Both engines
also pass 161 malformed-input cases, exact/over-limit JSON byte checks,
17 publication/interruption cases and 13 path-protection cases.
`tools/check_terrain_routes.py` exercises all eight Python/Rust
writer-updater-reader combinations using actual exported input paths. It then
edits exported terrain costs and opens walls, verifies changed optimal costs and
reachability, and replans the resulting bundle without modifying the originals.

Fault hooks `TERRAIN_FAIL` and `TERRAIN_PAUSE` accept `validated`, `stage`,
`grid.txt`, `terrain.json`, `requests.json`, `routes.json`, `paths.jsonl`,
`routes.txt`, `manifest.json`, `ready` and `published`. `TERRAIN_CONTINUE` names
a file that releases a pause. Leave these hooks unset normally.

## 066 — Dependency impact auditor

The [four-module auditor](066_dependency_impact/main.py) loads a module graph,
computes reverse dependencies and strongly connected groups, and explains which
modules a change can affect. All 400 substantive Python lines compile into
standalone Rust using the existing compiler. `model.py` validates the graph and
change requests; `analysis.py` implements the graph algorithms; `documents.py`
protects inputs and publishes bundles; `main.py` assembles reports and exports.
Generated Rust is in `build/corpus/066/rust/src/main.rs`.

Preview the sample:

```bash
IMPACT_CONFIG="$PWD/examples/corpus/066_dependency_impact/impact-job.json" \
IMPACT_MODE=preview build/corpus/066/corpus_066
```

The sample has eight modules, eight directed edges and seven strongly connected
groups. Two groups are cyclic: mutually dependent `auth`/`models`, and the
self-dependent `tools` module. Changing `db` affects six modules. Copy
`impact-job.json`, `graph.json` and `requests.json` to a working directory and
use `IMPACT_MODE=write` to save the complete bundle. The default mode is `preview`;
the default configuration is `impact-job.json` in the current directory:

```json
{"graph": "graph.json", "requests": "requests.json", "output": "dependency-impact"}
```

Paths resolve relative to the configuration directory. Output must be a new
directory with an existing parent, including in preview mode. Inputs must be
regular nonsymlink files. Configuration and all JSON objects require exactly the
documented fields. A graph has this shape:

```json
{
  "version": 1,
  "modules": ["app", "api", "db"],
  "edges": [
    {"module": "app", "depends_on": "api"},
    {"module": "api", "depends_on": "db"}
  ]
}
```

Edges point from a module to its dependency. Both endpoints must be declared;
duplicate modules and duplicate edges are rejected. Self-loops, cycles, isolated
modules and empty graphs are valid. Names are exact Unicode strings, without
normalization or case folding. The auditor analyzes the supplied graph; it does
not infer imports by executing or scanning modules.

`requests.json` is an ordered array of change sets:

```json
[
  {"id": "database update", "changed": ["db"]},
  {"id": "two edits", "changed": ["api", "db"]},
  {"id": "no changes", "changed": []}
]
```

IDs must be unique. Every changed module must exist. Repeated changed names are
deduplicated; the resulting selection is sorted. An empty change set affects
nothing. Input module order, edge order and the order of names within a change set do
not affect the normalized result. Request order is preserved.

The structural report contains sorted direct dependencies and dependents for
every module. An iterative Kosaraju traversal partitions the graph into maximal
strongly connected groups: each member can reach every other member. Explicit
stacks avoid recursion-depth limits. Groups and their members are sorted; a
group's ID is its smallest member name. IDs are therefore stable for the same
graph, but can change when edits merge or split groups.

Each group reports its members, whether it is cyclic, and its distinct external
dependency and dependent group IDs. A group is cyclic when it contains multiple
members or its sole member has a self-loop. Internal edges are omitted from the
condensed group graph, which is always acyclic. Summary counts include modules,
edges, groups and cyclic groups.

For each request, the auditor reports:

- `changed`: the normalized change set.
- `affected`: changed modules plus every module that transitively depends on one.
- `unaffected`: all remaining modules.
- `groups`: IDs of affected strongly connected groups.
- `explanations`: one shortest dependency-chain witness for each affected module.

Each explanation has `module`, a boolean `changed`, the chosen changed `root`,
`hops`, and `path`. The path runs **from the affected module toward the changed
root**, following dependency edges. A changed module explains itself with zero
hops and a one-element path. Unchanged affected modules have a nonempty chain;
every affected group is included in full.

Explanations minimize edge count. Ties choose the smallest changed root, then the
lexicographically smallest path when read backward from that root. Sorted roots
and sorted reverse neighbors in a multi-source breadth-first traversal establish
these deterministic rules. For example, if `x → a → d → z` and `x → b → c → z`
are equally short, the chosen explanation for a change to `z` is
`x → b → c → z`, since its reverse begins `z, c`. An explanation is one witness;
it does not enumerate every causal root or every possible dependency chain.

Write mode produces one atomic six-file bundle:

- `graph.json` and `requests.json`: canonical, normalized inputs that can be
  supplied directly to another run.
- `impact.json`: the complete report, identical to stdout, including input
  SHA-256 hashes, structural analysis and ordered request results.
- `impacts.jsonl`: one complete impact result per line.
- `impact.txt`: readable change headings, dependency chains and unaffected lists.
  IDs and names are JSON escaped, including embedded newlines.
- `manifest.json`: exact byte lengths and SHA-256 hashes of the other five files.

Every valid audit exits with status 0, including cyclic graphs and empty changes.
Invalid input, I/O errors and injected faults exit with status 2. Inputs are
checked again before publication. The complete bundle is written and synced in
a private staging directory, then renamed without replacing an existing output.
Handled failures remove their staging directory. A killed process may leave a
staging directory; a new run preserves it and uses a fresh name.

Bounds are 256 modules, 4,096 edges, 64 requests, and 256 supplied change entries
per request before deduplication. Names and IDs must contain 1–128 characters,
at most 512 UTF-8 bytes, and no NUL. Configuration reads are capped at 64 KiB;
graph and request reads at 4 MiB each. Canonical impact records together are
limited to 8 MiB, checked before adding each record to the report. Each generated
data file also has a defensive 16 MiB guard. Oversized explanation sets fail
before publication instead of silently dropping affected modules or paths.

Acceptance runs all 512 directed three-module graphs, including self-loops,
with all eight change subsets: 4,096 queries per engine. An independent Warshall
closure checks affected sets and mutual reachability; synchronous path relaxation
checks exact shortest explanation choices. The condensed graph is independently
checked for acyclicity, and each witness for actual edges, endpoints and cycle
freedom. Forty-eight additional graphs cover generated sparse/dense graphs,
disconnected modules, empty inputs, Unicode names, repeated changes and tie rules.
Forty-eight graph/change-order permutations produce byte-identical bundles, and
split request batches preserve individual results.

Both engines also pass 138 malformed-input cases, 256-module chains and cycles,
a combined 256-module/4,096-edge/64-request fixture, 512-byte names, exact and
excess input limits, individual and cumulative explanation-budget rejection,
15 publication/interruption cases and 11 path-protection cases.
`tools/check_dependency_impact.py` exercises all eight Python/Rust
writer-updater-reader combinations using actual exported input paths. It then
breaks cycles and adds dependents in a separate graph, verifies changed groups
and impact chains, and reuses those exports without modifying the originals.

Fault hooks `IMPACT_FAIL` and `IMPACT_PAUSE` accept `validated`, `stage`,
`graph.json`, `requests.json`, `impact.json`, `impacts.jsonl`, `impact.txt`,
`manifest.json`, `ready` and `published`. `IMPACT_CONTINUE` names a file that
releases a pause. Leave these hooks unset normally.

## 067 — Repeated-phrase document auditor

The [four-module auditor](067_phrase_auditor/main.py) tokenizes documents, indexes
n-grams, merges overlapping aligned matches, and reports cross-document repeated
passages with original character positions. All 388 substantive Python lines
compile into standalone Rust using the existing compiler. `model.py` loads and
tokenizes documents; `matching.py` implements indexing, merging and coverage;
`documents.py` protects inputs and publishes bundles; `main.py` assembles exports.
Generated Rust is in `build/corpus/067/rust/src/main.rs`.

Preview the sample:

```bash
PHRASE_CONFIG="$PWD/examples/corpus/067_phrase_auditor/phrase-job.json" \
PHRASE_MODE=preview build/corpus/067/corpus_067
```

The sample finds three repeated passages across four documents. Twelve matching
n-gram windows merge into those three passages; 21 source tokens are covered,
counting each token only once per document. Copy `phrase-job.json` and
`sources.json` to a working directory and use `PHRASE_MODE=write` to save the
bundle. The default mode is `preview`; the default configuration is
`phrase-job.json` in the current directory:

```json
{"documents": "sources.json", "ngram": 3, "output": "phrase-audit"}
```

Paths resolve relative to the configuration directory. Output must be a new
directory with an existing parent, including in preview mode. Inputs must be
regular nonsymlink files. All JSON objects require exactly the documented fields.
The documents file has this shape:

```json
{
  "version": 1,
  "documents": [
    {"id": "draft", "text": "The quick brown fox jumps over the lazy dog."},
    {"id": "quote", "text": "Quick, brown fox jumps over a fence."}
  ]
}
```

Document IDs must be unique. Empty corpora, empty documents and documents shorter
than the n-gram size are valid. IDs are sorted for canonical output; input order
does not affect reports or exported bytes. Repeats are compared between distinct
documents; a document's internal repetition alone produces no match.

The versioned tokenizer `nfc-casefold-ranges-v1` uses maximal runs separated by
these explicit Unicode ranges:

| Separator code points | Examples |
| --- | --- |
| U+0000–U+002F | Controls, spaces and initial ASCII punctuation |
| U+003A–U+0040 | ASCII punctuation after digits |
| U+005B–U+0060 | Brackets, underscore and related ASCII punctuation |
| U+007B–U+009F | Remaining ASCII punctuation and control characters |
| U+00A0, U+1680 | Nonbreaking and Ogham spaces |
| U+2000–U+206F | General punctuation, including typographic spaces and quotes |
| U+3000–U+303F | CJK symbols and punctuation |

Other characters remain in tokens, including combining marks, CJK text and emoji.
This is a reproducible text-matching policy, not linguistic word segmentation.
Each source token is normalized to NFC, case-folded using the shared Unicode
15.1 implementation, then normalized to NFC again. Thus `Straße` matches
`STRASSE`, and decomposed `café` matches `CAFÉ`. Punctuation and whitespace
between tokens do not participate in matching. Normalization is per token;
source text remains unchanged.

Token starts and ends are retained in the original text. Character offsets are
zero-based Unicode code-point indices, with exclusive ends; they are neither
UTF-8 byte offsets nor visual grapheme indices. A passage's excerpt runs from its
first token's start to its last token's end, retaining all intervening source
punctuation and spacing. Both sides of every match therefore retain their own
exact spelling and offsets even when normalized tokens are equal.

The matching algorithm stores normalized token tuples as n-gram keys. Matching
windows between different documents are grouped by document pair and alignment
(the difference between token positions). Overlapping or touching windows on
one alignment merge into a maximal equal token run. Results are sorted by left
document, right document, left token start, right token start and length. A record
contains:

- `left` and `right`: document ID, half-open token range, half-open character range
  and exact original excerpt.
- `length` and `tokens`: the passage length and its normalized tokens.
- `ngram_hits`: the number of matching n-gram windows represented by the passage,
  equal to `length - ngram + 1`.

Different alignments remain separate occurrences. For example, `a a a` against
`a a a a` with size two has six n-gram hits but four maximal aligned passages.
Their coverage is three tokens in the first document and four in the second,
for **seven** covered tokens total. Per-document coverage unions all matching
token intervals across all other documents, so overlap never inflates coverage.
Adjacent coverage intervals merge too. The report distinguishes raw window hits,
merged passages, document pairs and covered tokens.

Write mode produces one atomic five-file bundle:

- `documents.json`: canonical inputs with sorted IDs and unchanged text, reusable
  directly by another run.
- `audit.json`: the complete report, identical to stdout, including the n-gram
  size, tokenizer version, input digest, matches and per-document coverage.
- `matches.jsonl`: one complete passage record per line.
- `audit.txt`: summary counts and readable document/character-range comparisons.
  Names and normalized token lists are JSON escaped.
- `manifest.json`: exact byte lengths and SHA-256 hashes of the other four files.

Every valid audit exits with status 0, including an audit with no matches.
Invalid input, capacity failures, I/O errors and injected faults exit with status
2. Inputs are checked again before publication. The complete bundle is written
and synced in a private staging directory, then renamed without replacing an
existing output. Handled failures remove their staging directory; a killed
process may leave one, which a later run preserves while using a fresh name.

Bounds are 16 documents, 64 KiB of UTF-8 text and 2,048 tokens per document,
8,192 tokens overall, and an n-gram size of 1–16. IDs have 1–128 characters,
at most 512 UTF-8 bytes and no NUL. Normalized tokens are capped at 128 UTF-8
bytes. Reads are capped at 64 KiB for configuration and 2 MiB for source JSON.
The cross-document index allows 100,000 matching window pairs, merging allows
4,096 passage records, and canonical records together may occupy at most 8 MiB.
Each generated data file also has a defensive 16 MiB guard. Exceeding any budget
fails before publication; the auditor never silently truncates its findings.

Independent acceptance checks scan source character ordinals and use a
longest-common-substring dynamic program to find maximal runs, without the
application's regex, n-gram index or merge algorithm. Fifty exhaustive batches
exercise 5,630 document-pair comparisons, covering every pair of binary token
sequences up to length four, with n-gram sizes one through five. They represent
2,480 distinct sequence-pair/size combinations. Fifty-one additional corpora
include 40 generated cases, overlapping repeats, separated passages, empty and
single-document inputs, case-fold expansions, combining characters, Hangul,
Cherokee, emoji, embedded controls and escaped IDs. Every excerpt, token span,
normalization and coverage union is checked; 51 document-order permutations
produce identical bundles.

Both engines also pass 80 malformed-input cases, the combined 8,192-token
fixture, exact and excess document/token/name/read limits, exactly 100,000 hits
and 4,096 merged matches with over-limit rejection, the cumulative record-byte
guard, 13 publication/interruption cases and nine path-protection cases.
`tools/check_phrase_auditor.py` runs all eight Python/Rust writer-updater-reader
combinations against actual exported document paths. It lowers the n-gram
threshold to expose a two-token Unicode passage, checks each original excerpt,
then copies text between exported documents and verifies the new coverage.
Original bundles remain unchanged.

Fault hooks `PHRASE_FAIL` and `PHRASE_PAUSE` accept `validated`, `stage`,
`documents.json`, `audit.json`, `matches.jsonl`, `audit.txt`, `manifest.json`,
`ready` and `published`. `PHRASE_CONTINUE` names a file that releases a pause.
Leave these hooks unset normally.

## 068 — Huffman file compressor

The [four-module compressor](068_huffman/main.py) constructs a canonical Huffman
codebook, packs arbitrary bytes into a checked container, decompresses containers,
and reports exact size and codebook statistics. All 356 substantive Python lines
compile into standalone Rust using the existing compiler. `codebook.py` constructs
and validates codes; `codec.py` packs bits and validates containers; `documents.py`
reads bounded binary inputs and publishes bundles; `main.py` assembles operations
and reports. Generated Rust is in `build/corpus/068/rust/src/main.rs`.

Preview compression of the binary sample:

```bash
HUFFMAN_CONFIG="$PWD/examples/corpus/068_huffman/huffman-job.json" \
HUFFMAN_MODE=preview build/corpus/068/corpus_068
```

The sample contains 4,096 bytes, including all 256 byte values. It produces a
2,122-byte container: 1,528 payload bytes and 594 bytes of metadata/checksums,
saving 1,974 bytes. Copy `huffman-job.json` and `sample.bin` to a working directory
and use `HUFFMAN_MODE=write` to retain the result. The default mode is `preview`;
the default configuration is `huffman-job.json` in the current directory:

```json
{"operation": "compress", "input": "sample.bin", "output": "huffman-result"}
```

To decode the exported archive into a separate result directory, use:

```json
{"operation": "decompress", "input": "huffman-result/archive.phf", "output": "decoded"}
```

Configuration requires exactly these three fields. Paths resolve relative to its
directory. Output must be a new directory with an existing parent, including in
preview mode. Inputs must be regular nonsymlink files. Compression and
decompression both support arbitrary binary data, including NUL and invalid UTF-8.
Only configuration and JSON reports are text.

The encoder counts byte frequencies and repeatedly combines the two smallest
Huffman subtrees. Heap ties use the smallest byte value in each subtree, giving
deterministic lengths. Canonical codes are assigned in ascending length, then
ascending byte value. A single used symbol receives the one-bit code `0`.
An empty file has no codebook or payload. Multi-symbol codebooks must form a
complete prefix code; code lengths are between 1 and 32 bits.

An accumulator packs codes most-significant bit first and fills unused low bits
of the final byte with zero. The application uses its own versioned container
format, `PYHF068!`; it does not produce ZIP or gzip files. All integer header
fields are unsigned, big-endian:

| Offset | Width | Meaning |
| --- | --- | --- |
| 0 | 8 bytes | ASCII magic `PYHF068!` |
| 8 | 4 bytes | Original byte length |
| 12 | 4 bytes | Number of significant payload bits |
| 16 | 2 bytes | Number of codebook entries |
| 18 | 32 bytes | SHA-256 digest of the original uncompressed bytes |
| 50 | 2 bytes per entry | Byte symbol followed by its code length |
| After entries | Ceiling of bit count / 8 | Packed payload |
| Final 32 bytes | 32 bytes | SHA-256 digest of every preceding container byte |

Codebook entries must appear in strictly increasing byte-symbol order. The
canonical assignment makes storing code lengths sufficient. No trailing bytes
are allowed. Every codebook symbol must occur in the decoded result; all entries
are therefore meaningful. The decoder accepts valid externally produced canonical
codebooks even when their lengths differ from this encoder's deterministic choice
or are not optimal for the decoded frequencies.

Before decoding, the application checks the bounded declared output and bit
counts, exact container length, outer checksum, symbol ordering, code lengths,
complete prefix capacity and zero padding. It rejects duplicate symbols,
oversubscribed or incomplete multi-symbol codebooks, and invalid single-symbol
lengths. Decoding then checks each code, stops output growth at the declared
length, rejects unfinished codes and unused entries, and verifies the original
SHA-256 digest. Invalid containers produce no output bundle.

The original-file bound is 1 MiB. Configuration reads are capped at 64 KiB;
container reads at 4,194,898 bytes, allowing 32 bits per original byte plus the
maximum 256-entry header and checksums. These are fixed input/output bounds;
this implementation holds the bounded file in memory. Arithmetic, shifts and
byte writes use the shared runtime's checked operations. The encoder and decoder
both handle empty and single-symbol files explicitly.

Write mode produces one atomic four-file bundle:

- `archive.phf` for compression, or `decoded.bin` for decompression.
- `report.json`: the complete canonical report, identical to stdout.
- `codebook.json`: readable symbol/frequency/length/bit-string records, in byte order.
- `manifest.json`: byte lengths and SHA-256 hashes of the other three files.

The report includes original, container and payload sizes; significant and
padding bit counts; metadata/checksum overhead; saved bytes; both SHA-256 digests;
symbol count; maximum code length; and the complete codebook. `container_ratio_ppm`
is `floor(container_bytes × 1,000,000 / original_bytes)`; it is null for an
empty original. Values above one million and negative
`saved_bytes` correctly report expansion for small or incompressible inputs.
For imported containers, statistics describe the actual incoming codebook.

Valid operations exit with status 0. Invalid input, I/O errors, capacity failures
and injected faults exit with status 2. Inputs are checked again before
publication. Binary outputs and reports are written and synced in a private
staging directory, then renamed without replacing an existing output. Handled
failures clean their staging directory. A killed process may leave one; a later
run preserves it and uses a fresh staging name.

Acceptance compares exact container bytes against an independent encoder built
from sorted leaf-depth maps and string bitstreams. A separate prefix-tree decoder
checks archives. All 121 byte sequences up to length four over a three-byte
alphabet round-trip, as do all 125 histograms with three frequencies from zero
through four. Exhaustive merge-tree enumeration checks the optimal weighted cost
for the tiny multi-symbol cases. Fifty-four additional round trips include all
256 byte values, binary boundaries, UTF-8 text and 40 generated binary files.
Three externally constructed codebooks cover nonoptimal lengths, a complete
32-bit codebook and all 256 fixed-width symbols.

Both engines pass 1 MiB single-symbol and uniform-byte round trips and an
832,039-byte Fibonacci-weighted input that produces a 27-bit code. Malformed-file
checks include every one of 89 truncation boundaries and every single-byte
corruption of a small container, seven malformed codebooks with recomputed outer
checksums, and 19 other invalid containers. They exercise invalid padding,
trailing data, missing/unused codes, output-length mismatches, incomplete payloads
and both checksum layers. There are also 33 malformed configuration cases,
exact/over-limit reads, 24 publication/interruption cases and 18 path-protection
cases across compression and decompression.

`tools/check_huffman.py` runs all eight Python/Rust encoder-decoder-reencoder
combinations using actual archive and decoded-file paths. Recompression is
byte-identical, including reports and manifests. It also imports a valid
nonoptimal external codebook, recompresses the recovered bytes with fewer payload
bits, and decodes the improved archive. Original bundles remain unchanged.

Fault hooks `HUFFMAN_FAIL` and `HUFFMAN_PAUSE` accept `validated`, `stage`,
`archive.phf` or `decoded.bin` for the chosen operation, `report.json`,
`codebook.json`, `manifest.json`, `ready` and `published`. `HUFFMAN_CONTINUE`
names a file that releases a pause. Leave these hooks unset normally.

## 069 — Timetable journey planner

[`069_timetable`](069_timetable/main.py) plans earliest-arrival journeys through a
finite schedule, respecting station transfer times. Its four modules contain 394
substantive Python lines: `model.py` validates and normalizes inputs; `routing.py`
searches and reconstructs journeys; `documents.py` publishes result bundles;
`main.py` runs batches and builds reports. The complete project transpiles to
standalone Rust, with generated source in `build/corpus/069/rust/src/main.rs`.

Preview the overnight sample:

```bash
TIMETABLE_CONFIG="$PWD/examples/corpus/069_timetable/timetable-job.json" \
TIMETABLE_MODE=preview build/corpus/069/corpus_069
```

Three of the five sample requests have routes; two are unreachable. The overnight
A-to-D journey arrives at `2026-10-13T01:05:00.000000+00:00` via `ab`, `bc`, and
`cd`. Two earlier departures are missed because they leave before the required
transfer time. The command exits with status 1 to report the unreachable requests.

Copy `timetable-job.json`, `timetable.json`, and `requests.json` into a working
directory and set `TIMETABLE_MODE=write` to retain the results. The default mode is
`preview`; the default configuration is `timetable-job.json` in the current
directory. Configuration requires exactly these fields:

```json
{"timetable": "timetable.json", "requests": "requests.json", "output": "journey-plan"}
```

Paths resolve relative to the configuration directory. Output must be a new
directory with an existing parent, including in preview mode. Inputs must be
regular nonsymlink files. The timetable has this structure:

```json
{
  "version": 1,
  "stations": [
    {"id": "A", "transfer_seconds": 0},
    {"id": "B", "transfer_seconds": 300}
  ],
  "connections": [
    {
      "id": "ab", "from": "A", "to": "B",
      "departure": "2026-10-12T23:50:00Z",
      "arrival": "2026-10-13T00:10:00Z"
    }
  ]
}
```

Requests are an ordered array of objects with exactly `id`, `from`, `to`, and
`depart_after`. Station IDs, connection IDs, and request IDs must be unique within
their own namespaces. Endpoints must refer to declared stations. Names preserve
case and Unicode spelling; they are not folded or normalized.

Every connection is one explicit service instance with strictly positive elapsed
time. Parallel services and self-loops are allowed. Timestamps require an explicit
RFC3339 offset, support up to six fractional digits, and normalize to UTC with six
fractional digits. Their UTC instants must be in the half-open interval from
2000-01-01 to 2100-01-01. Overnight journeys and offset changes need no special
case. Recurring daily services and through-train identities are outside this
application's scope.

The heap holds earliest known arrival times. A station can board a connection
when its departure is at or after arrival plus that station's transfer time.
The first boarding has no transfer penalty, even if the origin station has a
nonzero transfer setting. Each later leg applies the transfer time. Connections
leaving one microsecond too early are missed; an exactly matching departure can
be boarded. Waiting is allowed.

The objective is earliest arrival. It does not minimize the number of legs among
equally early routes. Connection order is `(departure, arrival, id)`; heap order
is `(arrival, station id)`. Only strictly earlier labels replace a predecessor,
so ties are deterministic and independent of input station/connection order.
The search continues after reaching the destination to report final earliest
arrival times at every reachable station. A request whose endpoints are the same
has an empty journey arriving at its start time, while still reporting reachable
stations.

Each journey records found/unreachable status, final arrival or null, complete
connection legs, transfer count, sorted reachable stations, and search counters.
Legs include the minimum transfer and the earliest permitted boarding time.
Counters report settled stations, heap pushes/pops, discarded stale entries,
considered connections, and missed connections. They describe this algorithm;
they are not counts of all possible journeys.

Write mode publishes one atomic six-file bundle:

- `timetable.json`: canonical normalized stations and connections, reusable as input.
- `requests.json`: normalized requests in their original order, reusable as input.
- `journeys.json`: the complete canonical report, identical to stdout.
- `journeys.jsonl`: one canonical journey record per line.
- `itineraries.txt`: readable journeys with JSON-escaped identifiers.
- `manifest.json`: byte lengths and SHA-256 hashes of the other five files.

The report includes request/found/unreachable counts and SHA-256 hashes of the
normalized input files. Exit status is 0 when every request has a route, including
an empty batch; 1 when any request is unreachable; and 2 for invalid input, I/O
errors, capacity failures, or injected faults. Inputs are rechecked before
publication. Files are synced in a private staging directory and published by a
no-overwrite rename. Handled failures clean their staging directory; killed-process
orphans are preserved while later runs use fresh staging names.

Bounds are 256 stations, 4,096 connections, 64 requests, and transfer times from
zero through 86,400 seconds. Identifiers have 1–128 Unicode characters, at most
512 UTF-8 bytes, and no NUL. Read limits are 64 KiB for configuration, 4 MiB for the
timetable, and 1 MiB for requests. Journey JSONL records have a cumulative 8 MiB
budget, checked before adding each record; individual output files also have a
16 MiB guard. These are bounded in-memory schedules, not an unbounded transit feed.

Acceptance uses independent exhaustive temporal walks for small schedules and a
chronological connection-scan oracle for larger ones. All 192 tiny timetables
run 18 queries each: 3,456 queries per engine. Fifty additional timetables include
40 generated cases; 50 offset/input-order permutations and two split batches
check stable results. Cases cover overnight services, leap day, 24-hour transfers,
first boarding, self-loops, deterministic ties, and an earliest-arrival route that
has more legs than an alternative with the same final arrival.

Both engines check the combined 256-station/4,096-connection/64-request limits,
255-leg journeys, maximum UTF-8 IDs, exact timestamp boundaries, the cumulative
record budget, and exact/over-limit JSON reads. There are 227 malformed-input
cases, 15 publication/interruption cases, and 11 path-protection cases.
`tools/check_timetable.py` runs all eight Python/Rust writer/updater/reader
combinations using actual exported paths. It reuses schedules unchanged, reduces
a transfer time, adds a ferry to an unreachable island, and checks byte-identical
replanning and preservation of the original bundles.

The larger schedules exposed repeated regex compilation in the shared Rust
RFC3339 parser. The runtime now caches that fixed pattern once per process using
`OnceLock`; validation rules are unchanged. A native development-build benchmark
of 2,000 parse/format operations took 5.44 seconds before the change and 0.0085
seconds after it on this machine. This measures the repeated parsing operation,
not overall application speed. Separately, the complete combined-capacity batch
(256 stations, 4,096 connections, 64 requests, each with a 255-leg answer) took
126.34 seconds before and 1.63 seconds after the change, producing identical
4,308,797-byte reports. Timings are local measurements, not performance guarantees.
All 517 compiler/runtime regression tests pass; the implemented applications and
interoperability matrices are refreshed against the changed runtime.

Fault hooks `TIMETABLE_FAIL` and `TIMETABLE_PAUSE` accept `validated`, `stage`,
each of the six output filenames, `ready`, and `published`. `TIMETABLE_CONTINUE`
names a file that releases a pause. Leave these hooks unset normally.

## 070 — Sudoku batch-solving tool

[`070_sudoku`](070_sudoku/main.py) validates and solves batches of 4×4 and 9×9
Sudoku boards with explicit search budgets. Its four modules contain 361
substantive Python lines: `model.py` handles strict input and duplicate-given
diagnostics; `solver.py` searches for up to two solution witnesses;
`documents.py` publishes result bundles; `main.py` coordinates batches and
reports. All application code transpiles into standalone Rust using the existing
compiler. Generated source is in `build/corpus/070/rust/src/main.rs`.

Preview the six-board sample:

```bash
SUDOKU_CONFIG="$PWD/examples/corpus/070_sudoku/sudoku-job.json" \
SUDOKU_MODE=preview build/corpus/070/corpus_070
```

The sample contains two unique boards, one multiple-solution board, one board with
invalid givens, one unsatisfiable board, and one unfinished search. It exits with
status 1 because not every board has a proven unique solution. Copy
`sudoku-job.json` and `boards.json` into a working directory and set
`SUDOKU_MODE=write` to retain the result. The default mode is `preview`; the default
configuration is `sudoku-job.json` in the current directory:

```json
{"boards": "boards.json", "output": "sudoku-results"}
```

These are the only configuration fields. Paths resolve relative to its directory.
Output must be a new directory with an existing parent, including in preview mode.
Inputs must be regular nonsymlink files. The board document has this structure:

```json
{
  "version": 1,
  "boards": [
    {
      "id": "small-example", "box_size": 2, "budget": 1000,
      "rows": [[1, 0, 3, 4], [3, 4, 0, 2], [2, 1, 4, 0], [0, 3, 2, 1]]
    }
  ]
}
```

`box_size` is 2 for a 4×4 grid or 3 for a 9×9 grid. Zero denotes a blank; the other
values must be integers from 1 through the side length. Booleans and floating
point values are rejected. Row and column counts must exactly match the grid.
Board IDs must be unique, nonempty, NUL-free, at most 128 Unicode characters and
512 UTF-8 bytes. IDs preserve their spelling; board order is preserved.

Malformed structure is a batch input error. Duplicate nonzero givens in a row,
column, or box instead produce an `invalid` result for that board while the batch
continues. Diagnostics list every conflicting unit/value and every involved
cell, using zero-based row/column/unit coordinates. Box numbers increase left to
right, then top to bottom. A conflict can correctly appear in several units.

For valid givens, the solver uses iterative depth-first search. At each state it
chooses a blank cell with the fewest legal values, breaking ties by row then
column. Values are visited in ascending order. Each branch owns a copy of the
small board. A state counts against the budget when popped for inspection,
including solved states and dead ends. Duplicate-given validation precedes search
and consumes no search nodes.

Results distinguish five cases:

| Status | Evidence |
| --- | --- |
| `invalid` | At least one duplicate-given diagnostic; search was not started. |
| `unsatisfiable` | Search exhausted all branches without a solution. |
| `unique` | Search exhausted all branches and found exactly one solution. |
| `multiple` | Two distinct valid solutions were found; further search stops. |
| `search_limit` | The budget ended with unexplored states and fewer than two solutions. |

A zero budget therefore leaves even a valid completed board as `search_limit`;
a one-node budget proves that completed board unique. Finding one solution before
the budget expires does not prove uniqueness. Its witness is retained in the
unfinished result. `complete_search` means all branches were exhausted; multiple
solutions can be proven without exhausting them. The application does not count
all solutions or claim a lexicographically minimal solution.

Each result includes the budget, up to two full solution grids, diagnostics, and
statistics: visited states, expanded states, dead ends, maximum inspected depth,
and remaining frontier size. These counters are deterministic for the same board
and budget. The input grid stays unchanged. Reusing an exported board or splitting
a batch does not alter that board's result.

Bounds are 64 boards, 100,000 visited states per board, and a combined declared
budget of 1,000,000 states. Configuration reads are capped at 64 KiB and board
reads at 1 MiB. Each output file also has an 8 MiB guard. Search uses fixed finite
grids and explicit pending states, avoiding recursive application calls. Budgets
bound search work, not elapsed wall time.

Write mode publishes an atomic five-file bundle:

- `boards.json`: canonical original boards and budgets, reusable as input.
- `results.json`: the complete canonical report, identical to stdout.
- `results.jsonl`: one canonical result per line.
- `diagnostics.txt`: readable status, search work, diagnostics, and solution grids.
- `manifest.json`: byte lengths and SHA-256 hashes of the other four files.

The report includes counts by status and the SHA-256 hash of normalized
`boards.json`. Exit status is 0 when every board is proven unique, including an
empty batch; 1 for any other valid board result; and 2 for malformed input, I/O
errors, capacity failures, or injected faults. Input metadata is checked again
before publication. Files are synced in a private staging directory and renamed
without replacing an existing output. Handled failures clean staging; a killed
process's staging directory is preserved while a later run uses a fresh name.

Acceptance enumerates all 288 valid 4×4 completions independently of the solver,
then filters them against givens. It checks all 625 assignments of zero through
four to one four-cell block and 256 erased-cell patterns. A separate exact-cover
solver verifies 9×9 classifications. Eighty generated boards cover both sizes,
and 30 small-board budget cases check exact node boundaries and retained first
solutions. Eleven additional budget cases include a difficult unique 9×9 puzzle
that needs 2,232 visited states and 115 dead ends, and a consistent but
unsatisfiable 4×4 puzzle that requires branching. A budget of 2,231 must not claim
uniqueness for the difficult puzzle.

Other checks cover complete duplicate diagnostics, empty batches, reordered and
split batches, maximum IDs and batch budgets, exact/over-limit file reads,
106 malformed inputs, 13 publication/interruption cases, and nine path-protection
cases. `tools/check_sudoku.py` exercises all eight Python/Rust writer/updater/reader
combinations through actual exported paths. It uses exported solutions as new
givens, fixes an invalid board, raises an exhausted budget, and checks identical
repeated results while preserving the original bundles.

Fault hooks `SUDOKU_FAIL` and `SUDOKU_PAUSE` accept `validated`, `stage`, each of
the five output filenames, `ready`, and `published`. `SUDOKU_CONTINUE` names a file
that releases a pause. Leave these hooks unset normally.

## 071 — Access-log analyzer

[`071_access_log`](071_access_log/main.py) parses a documented Common Log Format
profile, filters requests by UTC time, and reports counts and ranked paths. Its
four modules contain 424 substantive Python lines: `parser.py` frames and parses
lines; `aggregate.py` computes summaries; `documents.py` publishes binary-safe
bundles; `main.py` coordinates sources, windows, and reports. Every module
transpiles into standalone Rust. Generated source is in
`build/corpus/071/rust/src/main.rs`.

Preview the two-source sample:

```bash
ACCESS_CONFIG="$PWD/examples/corpus/071_access_log/access-job.json" \
ACCESS_MODE=preview build/corpus/071/corpus_071
```

The sample has six lines: five valid requests and one malformed line. Four
requests fall inside the window, with 170 total response-body bytes; the request
at exactly 11:00 UTC is excluded. The command exits with status 1 because it
reports a malformed line. Copy `access-job.json`, `sources.json`, `front.log`, and
`api.log` to a working directory and set `ACCESS_MODE=write` to retain results.
The default mode is `preview`; default configuration is `access-job.json` in the
current directory:

```json
{
  "sources": "sources.json",
  "start": "2026-10-12T10:00:00Z",
  "end": "2026-10-12T11:00:00Z",
  "top": 5,
  "output": "access-report"
}
```

Configuration requires exactly these fields. Either time boundary can be null;
otherwise it is a strict RFC3339 timestamp with explicit offset and at most six
fractional digits. Boundaries normalize to UTC. Start is inclusive and end is
exclusive; equal boundaries select no requests, while reversed boundaries are
rejected. `top` is an integer from zero through 100. Configuration paths resolve
relative to its directory. Output must be new and have an existing parent,
including in preview mode.

The source manifest requires exactly `version` (1) and `files`:

```json
{"version": 1, "files": [{"name": "front", "path": "front.log"}]}
```

Each file entry has exactly `name` and `path`. Log paths resolve relative to the
source manifest, which may be in a different directory from the configuration.
Source names and canonical file paths must be unique. Names are nonempty,
NUL-free, and bounded at 128 Unicode characters and 512 UTF-8 bytes. Every input
must be a regular nonsymlink file. Empty source lists and empty logs are valid.

The log profile follows the field layout described in
[Apache's Common Log Format documentation](https://httpd.apache.org/docs/2.4/logs.html#common):

```text
host ident user [DD/Mon/YYYY:hh:mm:ss +HHMM] "METHOD target HTTP/1.1" status bytes
```

Separators are single ASCII spaces. Host, identity, user, and request-target tokens
are nonempty and contain no spaces or quotes. Unicode text is preserved. Method
names use ASCII HTTP token characters and preserve case. Protocols have the form
`HTTP/d.d`, with one digit on each side of the dot. Status is three ASCII digits
from 100 through 599. Body size is an unsigned decimal signed-64-bit integer, or
`-` for zero bytes; decimal input is capped at 4,096 characters. Leading zeros
are accepted. No Combined Log Format suffix, custom fields, or quoted-token escape
decoding is provided by this profile.

Dates require two-digit day/time fields, a four-digit year, a case-sensitive
English month abbreviation, and a signed four-digit offset. Calendar values and
offset ranges are checked; leap seconds are rejected. UTC results must remain
within years 0001–9999. Output timestamps use six fractional digits and `+00:00`.
The parser uses the shared `regex_capture` adapter for numbered fields, then
validates dates and integers in Python application code.

Files are framed by LF. One immediately preceding CR is removed for CRLF; an
unterminated final line is also processed. A trailing LF creates no extra line.
Blank lines are malformed. Bare CR, ASCII controls, and DEL are rejected inside
logical lines. Invalid UTF-8 is recorded per line rather than aborting the file.
Diagnostics use stable reason codes: `utf8`, `control`, `format`, `timestamp`,
`status`, or `bytes`, in that validation order.

Every valid record includes source name, one-based line number, parsed fields,
normalized timestamp, and a `selected` flag. The `path` grouping key is the
literal request-target prefix before its first `?`. It preserves percent escapes,
case, Unicode spelling, fragments, authority-form targets, and absolute-URL
prefixes; it performs no URI normalization. Duplicate requests count separately.
Malformed lines are reported even when no valid requests fall inside the window.

Summaries cover selected requests only: request count, body-byte total, 4xx and
5xx counts, distinct hosts, first/last timestamps, full status/method/UTC-hour
counts, distinct path count, and the requested number of top paths. Path ranking
uses decreasing request count, then literal path order; each row includes bytes
and error count. Integer totals cannot silently overflow: a selected byte sum
above signed-64-bit range rejects the analysis before publication. Filtered
requests do not contribute to that sum.

Bounds are eight source files, 1 MiB per file, 4 MiB combined log bytes, 10,000
logical lines across all sources, and 8,192 bytes per logical line excluding its
LF/CRLF delimiter. Both configuration and source-manifest reads are capped at
64 KiB. Canonical valid and malformed JSONL records share a 16 MiB export budget,
checked before retaining each record. Output files also have a 32 MiB guard.
Capacity failures reject the job; malformed lines within those bounds are retained
as diagnostics. This implementation holds its bounded inputs and records in memory.

Write mode publishes one atomic bundle:

- `source-0.log`, `source-1.log`, …: byte-for-byte copies of the original inputs.
- `sources.json`: source names and relative exported filenames, reusable as input.
- `report.json`: the complete canonical report, identical to stdout.
- `records.jsonl`: every valid parsed record, including those outside the window.
- `invalid.jsonl`: source, line number, reason, and hex bytes of each malformed
  logical line; original line delimiters remain available in the copied logs.
- `summary.txt`: the report as readable, escaped JSON with a short heading.
- `manifest.json`: byte lengths and SHA-256 hashes of all the other files.

The report includes raw-log SHA-256 hashes keyed by source name. Logs retain their
source order and record order; aggregates are independent of input order. A new
configuration can refer directly to an exported `sources.json`, whose log paths
resolve beside it. No log data is decoded and re-encoded during source export.

Exit status is 0 when all lines parse, including empty inputs; 1 when malformed
lines are reported; and 2 for invalid configuration, I/O errors, capacity failures,
byte-total overflow, or injected faults. Inputs are checked again before
publication. Files are synced in a private staging directory and renamed without
replacing an existing output. Handled failures clean staging. An interrupted
process can leave a staging directory; later runs preserve it and use a fresh name.

Acceptance uses an independent delimiter parser and Python calendar arithmetic,
then `Counter`/grouped-list aggregation. It checks a hand-labeled sample, all 500
status codes, all 77 method-token characters, every byte value embedded in a target,
45 labeled malformed lines, 18 calendar cases, 43 time windows, nine equivalent
offset windows, and 11 framing cases. Forty generated batches and 40 source/line
permutations test counts, raw hashes, Unicode keys, query grouping, and deterministic
ranking. Additional checks cover exact/over-limit byte totals, excluded huge
responses, long zero-prefixed byte counts, and ranking limits from zero to 100.

Both engines also pass the declared input/output limits, 107 malformed configurations,
18 publication/interruption cases, and 14 path-protection/relative-manifest cases.
`tools/check_access_log.py` runs all eight Python/Rust writer/updater/reader
combinations using actual exported manifests and log files. It adds a request,
widens the time window, reproduces byte-identical bundles, and preserves the
original source bytes and earlier output bundles.

The shared compiler/runtime extension is `regex_capture(pattern, text, full_match)`.
It returns numbered group text and half-open Unicode character spans, distinguishes
unmatched groups from empty captures, and supports both first search results and
whole-input matching. The API and its limits are documented in the
[service subset](../../doc/service-subset.md). Native pattern reuse keeps repeated
log parsing from rebuilding the same regex for each line. The complete compiler/
runtime regression suite now has 526 passing tests, including capture vectors,
limits, recoverable errors, argument order, and concurrent pattern/mode isolation.

Fault hooks `ACCESS_FAIL` and `ACCESS_PAUSE` accept `validated`, `stage`, any actual
output filename, `ready`, and `published`. `ACCESS_CONTINUE` names a file that
releases a pause. Leave these hooks unset normally.

## 072 — Small static-site builder

[`072_static_site`](072_static_site/main.py) turns a manifest and Markdown files
into a linked HTML site. Its 455 substantive Python lines are split across five
modules: recursive inline parsing, block/heading parsing, layout/link validation,
file publication, and orchestration. All five modules transpile; the generated
Rust is `build/corpus/072/rust/src/main.rs`. The executable requires no Python
runtime, JavaScript build system, web framework, or network connection.

Preview the two-page sample:

```bash
SITE_CONFIG="$PWD/examples/corpus/072_static_site/site-job.json" \
SITE_MODE=preview build/corpus/072/corpus_072
```

Copy `site-job.json`, `site.json`, `home.md`, and `guide.md` to a working directory
and set `SITE_MODE=write` to create `built-site`. Open its `index.html` in a browser.
Every page has links to the other pages and its own heading contents, with a
responsive stylesheet stored beside the HTML. The sample includes nested
bold/italic text, code, escaped HTML, duplicate headings, and a Unicode heading.

`SITE_CONFIG` defaults to `site-job.json`; `SITE_MODE` defaults to `preview`.
Configuration requires exactly `site` and `output`. Both paths resolve relative
to the configuration file. Output must be new and have an existing parent, also
in preview mode. The site manifest requires exactly these fields:

```json
{
  "version": 1,
  "title": "Field notes",
  "pages": [
    {"id": "index", "title": "Home", "source": "home.md"},
    {"id": "guide", "title": "Guide", "source": "guide.md"}
  ]
}
```

Each page requires exactly `id`, `title`, and `source`. IDs are unique, one to 64
ASCII lowercase letters, digits, or hyphens, with no leading hyphen. They become
flat filenames such as `guide.html`. Site/page titles contain one to 128 Unicode
characters, at most 512 UTF-8 bytes, with no ASCII controls or DEL. Source paths
resolve relative to the manifest directory; canonical source paths must be unique.
All inputs must be regular nonsymlink files. The first manifest page is the entry
page, and manifest order determines navigation order. Empty Markdown is valid.

This is a defined Markdown subset, not a CommonMark implementation:

- Headings start at column zero with one to six `#` characters and one space.
  Closing `#` characters remain ordinary heading text.
- Nonblank ordinary lines form paragraphs; adjacent lines join with one space.
  Blank lines, headings, lists, and fences end a paragraph.
- Consecutive `- ` lines make a flat unordered list; empty list items are valid.
- A line beginning with three backticks opens a code fence. Its optional language
  consists of up to 32 ASCII letters, digits, underscores, or hyphens. Only an
  exact three-backtick line closes it. Code contents are escaped literal text.
- `**text**` means bold, `_text_` means italic, and backticks delimit inline code.
  Balanced bold and italic spans can nest. A matching delimiter closes the current
  span; single asterisks are literal. Inline code does not interpret markup.
- `[label](target)` creates a link. Labels can contain formatting and inline code,
  but cannot contain another link. Destinations end at the next closing parenthesis.
- A backslash escapes the next character outside code, including brackets and
  formatting delimiters. Escape literal underscores/brackets when necessary.
  Unclosed spans, links, code, fences, and trailing escapes reject the build.

CRLF becomes LF for parsing, while exported source bytes remain unchanged. Bare
CR, NUL, other ASCII controls except tab/LF, DEL, and invalid UTF-8 are rejected.
Source HTML and character references are escaped in every text context; HTML is
never passed through. Titles, heading IDs, labels, URLs, and code are also escaped
for their output context. No raw-HTML blocks, embedded images, automatic URL links,
ordered/nested lists, tables, include directives, or arbitrary template execution
are part of this subset.

Heading IDs use the plain text after inline parsing: NFKC normalization followed
by case folding, ASCII letters/digits and non-ASCII characters retained, other
runs replaced by hyphens, and the base truncated to 64 characters. Empty bases
become `section`. A page-wide used-ID set adds `-2`, `-3`, and further suffixes
until the ID is unused, including collisions with literal suffixed headings.
Duplicate IDs never silently replace an earlier heading. Generated contents use
percent-encoded fragments and preserve the original display text.

Internal destinations are a page ID, `page#heading-id`, or `#heading-id` on the
current page. They use raw heading IDs as recorded in `report.json`, including
Unicode; the generated URLs encode their fragments. Matching is case-sensitive.
Every internal page/fragment is checked after all pages are parsed, so forward
links, self-links, and cycles work. Unknown pages/anchors reject the whole build.
Explicit `http://` and `https://` destinations use the shared HTTP URL validation
profile and preserve their original spelling in HTML. Credentials, invalid hosts,
invalid ports/percent escapes, spaces, backslashes, and unsafe URL characters are
rejected. External destinations are syntax-checked without fetching them.

Bounds are 1–32 pages, 64 KiB per Markdown file, 1 MiB combined source bytes,
4,096 lines per page (including the final empty split after a trailing LF),
8,192 UTF-8 bytes per line and per complete inline block, 256 headings per page,
and 12 levels of inline nesting. A link label consumes one nesting level.
Configuration and site manifests each have a 64 KiB read limit. The builder also
checks a 16 MiB total export budget before publication. Inputs and rendered pages
are retained in memory within these bounds.

Write mode publishes one complete directory:

- `<id>.html` and `style.css`: the linked site, usable directly from disk.
- `source-0.md`, `source-1.md`, …: original Markdown bytes, including CRLF.
- `site.json`: a reusable manifest with relative paths to those exported sources.
- `report.json`: page titles, source hashes, heading IDs/text/levels, original link
  destinations, and the entry filename; identical to canonical JSON on stdout.
- `manifest.json`: byte lengths and SHA-256 hashes for every other output file.

Point another job at the exported `site.json` to rebuild the site, or edit exported
Markdown before rebuilding into a new directory. Python and native Rust reproduce
the same bytes. Exit status is 0 on success and 2 for malformed inputs, broken
links, I/O/limit failures, or injected faults. Inputs are rechecked before commit.
Files are synced in a private staging directory and atomically renamed without
replacing existing output. Handled failures clean staging; a killed process may
leave an orphan that subsequent runs preserve while using a fresh staging name.

Acceptance checks hand-authored HTML goldens, DOM structure/attributes and every
local link, 13 labeled cases, 17 Unicode/collision headings, 60 generated three-page
sites from independently rendered markup trees, all 64 directed three-page link
graphs, page order changes, and Unicode fragments. Both engines pass 130 invalid
inputs, exact/over-limit capacity cases, 18 publication/interruption cases, and
14 path-protection/relative-manifest cases. `tools/check_static_site.py` exercises
all eight Python/Rust builder/updater/reader combinations against actual exported
Markdown, adds a duplicate heading and formatted paragraph, and checks repeatable
output while preserving the earlier bundles.

The shared compiler extension is direct `for character in text` iteration, emitted
as Rust Unicode scalar iteration. Four targeted tests cover Unicode boundaries,
combining marks, empty strings, single evaluation, reassignment of the source,
nested loops, break/continue/return, and error propagation. The compiler/runtime
regression suite now has 530 passing tests.

## 073 — Template rendering engine

[`073_template_renderer`](073_template_renderer/main.py) renders named HTML jobs
from a project manifest, template files and JSON data. Its 468 substantive Python
lines span five modules: syntax parsing, include-graph validation, rendering and
scope handling, file publication, and orchestration. All five compile into
`build/corpus/073/rust/src/main.rs`; the native executable needs no Python runtime.
The existing compiler and shared runtime required no changes for this application.

Preview the sample:

```bash
TEMPLATE_CONFIG="$PWD/examples/corpus/073_template_renderer/template-job.json" \
TEMPLATE_MODE=preview build/corpus/073/corpus_073
```

Copy `template-job.json`, `project.json`, `page.txt`, `item.txt`, and `data.json` to
a working directory and select `TEMPLATE_MODE=write` to create `rendered`. Open
`rendered/index.html` to see the escaped title, included list items, conditions and
preserved outer binding. `TEMPLATE_CONFIG` defaults to `template-job.json` and
`TEMPLATE_MODE` to `preview`. Configuration requires exactly `project` and `output`,
resolved relative to the configuration file. Output must be new with an existing
parent, including in preview mode.

The project manifest requires exactly these fields:

```json
{
  "version": 1,
  "templates": [
    {"id": "page", "source": "page.txt"},
    {"id": "item", "source": "item.txt"}
  ],
  "jobs": [
    {"id": "index", "template": "page", "data": "data.json", "steps": 1000}
  ]
}
```

Template/job entries require exactly the displayed fields. Each template ID and
job ID is unique within its own list: 1–64 ASCII letters, digits or underscores,
starting with a letter or underscore. Job IDs become flat `<id>.html` filenames.
Source/data paths resolve relative to the project manifest. Template source paths
must be unique after canonicalization. All inputs are regular nonsymlink files;
UTF-8 and JSON validation use the shared runtime contract. Job data must be a JSON
object. Duplicate JSON keys keep their last value, matching `json_loads`; signed
64-bit integers and finite binary64 numbers are supported.

Templates support this defined language:

- `{{ user.name }}` resolves a dotted object path and HTML-escapes the scalar value.
  Null becomes empty text; booleans and numbers use canonical JSON spelling.
  Arrays and objects cannot be substituted directly. Escaping covers `&`, `<`,
  `>`, double quotes and apostrophes; inserted values are not parsed as templates.
- `{% if enabled %}...{% else %}...{% endif %}` selects one branch; `else` is
  optional. Null, false, zero and empty strings/arrays/objects are false. Unvisited
  branches do not resolve their variables.
- `{% for item in items %}...{% endfor %}` iterates an array. Its binding is local
  to each iteration and visible to included templates. Nested bindings restore
  the outer value; loop bodies do not run for empty arrays.
- `{% include item %}` renders a static, unquoted template ID in the current scope.
  Every include edge is validated before rendering, including unused templates
  and inactive branches. Missing targets and cycles reject the entire project;
  cycle errors include a witness chain and the closing edge's source location.

Dotted expressions contain ASCII identifiers and total at most 256 characters;
there are no calls, arithmetic, indexing, assignments, dynamic includes or filters.
Outer token whitespace is stripped. Command words use ASCII spaces, including
repeated spaces; internal tabs are unsupported. Text outside tokens is preserved
verbatim, including CRLF and literal HTML. This renderer is for trusted templates:
scalar escaping does not validate JavaScript, CSS or URL contexts. There is no
raw-block syntax to quote literal opening `{{` or `{%` delimiters.

Syntax, missing-value, include and step errors identify the template ID plus a
one-based line and Unicode character column. LF starts a new line; tabs count as
one character. Each visited syntax node costs one step and each loop iteration
costs one additional step, even for an empty loop body. Included nodes consume the
caller's remaining budget. Empty templates can render with a zero budget.

Bounds are 1–32 templates and jobs, 64 KiB per template, 1 MiB combined template
bytes, 1 MiB per data file, and 4 MiB combined template/data bytes. Reusing a data
file for multiple jobs counts its bytes for every read. Configuration and project
manifests each have a 64 KiB limit. The compiled project has at most 4,096 syntax
nodes, including literal nodes and inactive branches. Parsing allows 12 nested
blocks, include chains contain at most 12 templates, rendering allows 24 nested
calls, and each loop accepts at most 256 items. Each job allows 0–10,000 steps and
at most 1 MiB of UTF-8 output. Total exported content, before `manifest.json`, is
limited to 16 MiB. Input and output buffers remain in memory; these bounds do not
promise a fixed execution time. Generated Rust uses the compiler's owned-value
semantics, so deeply repeated rendering can copy template/scope collections.

Write mode atomically publishes `<id>.html` files, exact `source-N.txt` and
`data-N.json` input bytes, a reusable `project.json` with relative exported paths,
a canonical `report.json`, and a checksum `manifest.json` for all other files.
Stdout matches `report.json`: it records each job's template, steps, output bytes
and SHA-256. Point a new configuration at the exported project to rebuild it,
or edit its template/data files and rebuild into a fresh directory.

Exit status is 0 on success and 2 for validation, rendering, I/O and injected
failures. Files are synced in a private staging directory; input metadata is
rechecked before an atomic no-overwrite rename. Handled failures clean staging.
A killed process may leave an orphan that later runs preserve while choosing a
fresh staging name. An error after publication leaves the complete output intact.

Both engines pass 12 hand-labeled rendering cases, duplicate-key handling, 120
scope/truth cases using 15 distinct truth values, 60 independently generated
syntax trees, 20 one-step-short budgets, and all 512 directed three-template graphs
(25 acyclic and 487 with checked cycle witnesses/locations). Acceptance also
checks 36 located errors, 132 invalid inputs, exact/over-limit capacities, 18
publication/interruption cases and 16 path cases. Capacity checks combine a
4,096-node project with 8,225 rendering steps and run all 32 jobs at 10,000 steps.
`tools/check_template_renderer.py` exercises all eight Python/Rust
writer/updater/reader combinations using actual exported projects, then changes
both included markup and JSON data and verifies byte-identical rebuilt bundles.
A separate package check compiles all five modules using the extracted compiler
wheel and writes/rebuilds the sample with Python unavailable.

Fault hooks `TEMPLATE_FAIL` and `TEMPLATE_PAUSE` accept `validated`, `stage`, any
actual output filename, `ready`, and `published`. `TEMPLATE_CONTINUE` names a file
that releases a pause. Leave these hooks unset normally.

## 074 — Expression calculator with variables

[`074_expression_calculator`](074_expression_calculator/main.py) runs arithmetic
scripts against saved numeric variables. Its 388 substantive Python lines span
five modules: tokenization, checked numeric operations, precedence evaluation,
file publication, and session orchestration. All five compile to readable Rust
in `build/corpus/074/rust/src/main.rs`; the native binary runs without Python.
The compiler and shared runtime required no changes for this application.

Preview the example, including a failed assignment followed by successful reads:

```bash
CALC_CONFIG="$PWD/examples/corpus/074_expression_calculator/calculator-job.json" \
CALC_MODE=preview build/corpus/074/corpus_074
```

Copy `calculator-job.json`, `session.json` and `expressions.txt` to a working
directory and set `CALC_MODE=write` to publish `calculated`. `CALC_CONFIG` defaults
to `calculator-job.json`; `CALC_MODE` defaults to `preview`. Configuration requires
exactly `state`, `script` and `output`, resolved relative to the configuration file:

```json
{"state": "session.json", "script": "expressions.txt", "output": "calculated"}
```

State requires exactly `version: 1` and a `variables` object containing numbers.
Variable names are 1–64 ASCII letters, digits or underscores, beginning with a
letter or underscore. Both configuration and state use the shared JSON contract:
integer values fit signed 64 bits, floating values are finite binary64, booleans
are distinct from numbers, and duplicate keys keep their last value. Inputs must
be regular nonsymlink files. Output must be new with an existing parent, also in
preview mode.

Each nonblank, noncomment line is an expression or `name = expression`:

- Numbers use JSON decimal spelling: `12`, `0.5`, `1e-3`. Leading zeros, `.5`, `1.`,
  hexadecimal, digit separators, infinities and NaNs are unsupported. Signed
  literals include `-9223372036854775808`; positive integers above the signed
  range are rejected before further arithmetic.
- Parentheses group expressions. Unary `+` and `-` bind most tightly, followed by
  `*`, `/`, `//` and `%`, then `+` and `-`. Binary operators associate to the left.
- Integer `+`, `-`, `*`, `//` and `%` preserve integer values and check every
  result for overflow. Floor division and remainder require integer operands;
  their negative-operand behavior follows Python. `/` produces a floating value,
  including an accurately rounded quotient for two integer operands.
- Mixed numeric `+`, `-`, `*` and `/` use binary64 arithmetic after integer-to-float
  conversion. Overflow/nonfinite results are expression errors; finite underflow
  and signed zero are preserved. Division by zero is always an expression error.
- `#` begins a comment. ASCII space, tab and CR are whitespace; CRLF script bytes
  are preserved in exports and normalized to LF for evaluation. Names and syntax
  are case-sensitive. Strings, calls, comparisons, powers and chained assignments
  are outside this language.

The parser evaluates operands as it recognizes them; it never calls Python
`eval`. Assignments commit only after the entire statement validates. A malformed
expression, undefined variable, arithmetic error or failed new-variable allocation
adds an error record and leaves the session unchanged. Later lines continue.
Errors include one-based character columns, and records include their source line
number and text. Empty/comment lines have no record. Comment text can contain
Unicode; variable names remain ASCII.

The session supports 256 variables. Configuration and state are limited to 64 KiB
each, scripts to 1 MiB and 256 LF-separated lines, each line to 4,096 UTF-8 bytes,
and each expression to 512 tokens excluding the end marker. A trailing LF adds
an empty line to the line count. The recursive parser allows depth 32, including
unary, parenthesis and recursive right-operand calls. Flat operator chains are
processed iteratively. Whole-script size/line errors reject the job; line/token/
nesting errors are recoverable expression errors. Total exported bytes before
`manifest.json` are capped at 4 MiB, including expansion from JSON escaping.

The canonical JSON report on stdout records `version`, per-line `records`,
`errors` and the final `variables`. Write mode publishes these files together:

- `state.json`: the final numeric session, ready to use with another script.
- `initial-state.json` and `script.txt`: exact input bytes for reproducible replay.
- `report.json`: the same canonical report as stdout.
- `manifest.json`: byte lengths and SHA-256 hashes of every other output file.

To continue, point the next configuration's `state` at the exported `state.json`
and supply a new script/output directory. To replay a job, use its exported
`initial-state.json` and `script.txt`; both engines reproduce identical bundles.
Exit status 0 means the job produced a report, which may contain expression errors.
Exit status 2 means configuration/state/script validation, I/O, an export limit
or an injected fault prevented normal completion.

Files are synced in private staging; input metadata is rechecked before an atomic
no-overwrite rename. Handled failures clean staging. A killed process may leave
an orphan that later runs preserve while selecting a fresh staging name. Failures
after publication leave the complete output intact.

Acceptance compares both engines with an independent Python-AST evaluator using
checked arithmetic: 36 directed expressions and 24 generated sessions totaling
1,536 expressions. It verifies 26 located failures followed by successful reads
and assignments, 72 invalid inputs, exact/over-limit bounds, full-session updates,
CRLF/comments, 14 publication/interruption cases and 12 path-protection cases.
`tools/check_calculator.py` checks all eight Python/Rust writer/updater/reader
combinations against actual exported files, including replay, continued variables,
failed assignments and unchanged earlier bundles. A separate check uses the
extracted compiler wheel to build the complete project, replay its bundle and
continue its session with Python unavailable.

Fault hooks `CALC_FAIL` and `CALC_PAUSE` accept `validated`, `stage`, any actual
output filename, `ready`, and `published`. `CALC_CONTINUE` names a file that releases
a pause. Leave these hooks unset normally.

## 075 — INI-style configuration editor

[`075_ini_editor`](075_ini_editor/main.py) edits quoted configuration values,
expands named references and publishes a reproducible document bundle. Its 399
substantive Python lines span five modules: parsing/writing, set/delete edits,
dependency expansion, file publication and orchestration. All five transpile into
`build/corpus/075/rust/src/main.rs`; the executable requires no Python runtime.
The existing compiler and shared runtime required no changes.

Preview the example:

```bash
INI_CONFIG="$PWD/examples/corpus/075_ini_editor/ini-job.json" \
INI_MODE=preview build/corpus/075/corpus_075
```

Copy `ini-job.json`, `settings.ini` and `edits.json` to a working directory and
select `INI_MODE=write` to create `edited`. `INI_CONFIG` defaults to `ini-job.json`
and `INI_MODE` to `preview`. Configuration requires exactly `source`, `edits` and
`output`, resolved relative to the configuration file:

```json
{"source": "settings.ini", "edits": "edits.json", "output": "edited"}
```

Inputs are regular nonsymlink files. The output directory must be new and have an
existing parent, including in preview mode. Documents use this INI subset:

```ini
# Global fallback
host = "localhost"

[server] ; section comment
port = "8080" # inline comment
url = "http://${host}:${port}/"
literal = "$${host} costs $$5"
```

Names are case-sensitive, 1–64 ASCII letters, digits, underscores or hyphens,
starting with a letter or underscore. Keys before the first section belong to
the implicit global section. Duplicate section headers and duplicate keys within
one section are errors. Sections and keys preserve their document order.

Every value is a double-quoted JSON string: escaped quotes, backslashes, control
characters and Unicode escapes follow the shared JSON decoder. Raw strings,
unquoted numbers/booleans, multiline values and continuations are unsupported.
ASCII spaces/tabs may surround names, `=` and strings. Raw control characters are
rejected except tab and LF; CRLF input is normalized to LF for rewriting. Unicode
is supported in string values and comments; names remain ASCII.

The comment policy is explicit: full-line `#`/`;` comments and blank lines retain
their text, whitespace and order. Section/value lines use canonical spacing and
JSON quoting. Their inline comments retain their marker/content, with surrounding
spaces/tabs trimmed and exactly one preceding space. Replacing a value preserves
its inline comment. Deleting a key deletes that whole key line, including its
inline comment, while leaving neighboring full-line comments and section headers.
New keys are appended within their section, before the next section header; new
sections append with a separating blank line. Global insertions remain before the
first section, even after other edits have added sections. Rewriting an already
canonical document without edits is byte-stable.

`edits.json` is an ordered JSON array of exact operations:

```json
[
  {"op": "set", "section": "server", "key": "port", "value": "9090"},
  {"op": "set", "section": "client", "key": "endpoint", "value": "${server.url}"},
  {"op": "delete", "section": "server", "key": "literal"}
]
```

Use an empty `section` for global keys. `set` replaces or creates a key and creates
its section when needed. `delete` requires an existing key. All edits form one
transaction: the entire resulting document is reparsed and expanded before
publication. Unknown fields/operations, missing deletion targets, invalid values
or post-edit capacity/reference failures reject the job without changing inputs.
A batch can repair an existing missing reference or cycle; syntax errors and
duplicate keys must be fixed in the input before it can be parsed.

References use `${key}` for a key in the current section, falling back to a global
key only when that local key is absent. `${section.key}` selects an explicit
section, and `${.key}` selects the global section. `$$` produces a literal dollar;
other lone dollar signs stay literal. For example, `$${host}` produces literal
`${host}` and is not expanded again. Values inserted from other keys are already
resolved and are not reparsed. Expansion never reads environment variables.

Every final key is checked, including unused values. Missing/invalid references
identify their owning qualified key. Cycles report a dependency chain ending in
a repeated key. Expansion runs in dependency order and resolves each key once;
a 256-key acyclic chain works without recursive application calls. Syntax errors
report one-based source lines. Qualified keys in JSON reports use `section.key`,
with `.key` for global entries.

Limits are 64 KiB each for job configuration and edit JSON, 1 MiB each for source
and rewritten INI, 2,048 logical lines, 65,536 UTF-8 bytes per physical line,
64 named sections, 256 keys and 256 edits. One final LF terminates the last line
without adding another blank line; additional blank lines are retained. Decoded
raw values are limited to 8,192 UTF-8 bytes. Each value permits 512 dollar tokens,
counting escaped/lone dollars and references. An expanded value is at most 65,536
bytes and all expanded values together at most 1 MiB. Export content before the
checksum manifest is limited to 8 MiB, including JSON-escaping expansion. These
bounds limit input/output size; they do not guarantee a fixed execution time.

Write mode publishes six files together:

- `settings.ini`: canonical edited text, retaining unexpanded references.
- `values.json`: resolved string values, ready for another application's use.
- `report.json`: version, key count, raw and expanded values; identical to stdout.
- `input.ini` and `edits.json`: exact original bytes for replay.
- `manifest.json`: byte lengths and SHA-256 hashes of every other file.

Use exported `settings.ini` with new edits to continue editing, or exported
`input.ini`/`edits.json` to replay the job. Exit status is 0 on success and 2 for
validation, reference, I/O, capacity or injected failures. Input metadata is
rechecked before an atomic no-overwrite rename of synced staging files. Handled
failures clean staging; a killed process may leave an orphan preserved by later
runs. An error after publication leaves the complete bundle intact.

Both engines pass 10 hand-labeled documents, 60 generated edit/reparse cases and
all 512 three-key dependency graphs, including 487 checked cycle witnesses.
Acceptance includes 27 located syntax/reference failures, 92 invalid inputs,
exact/over-limit capacities, a full 256-key chain, 15 publication/interruption
cases and 12 path-protection cases. A separate capacity probe exercises 32,768
references alongside 512 KiB of literal values. `tools/check_ini_editor.py` covers
all eight Python/Rust writer/updater/reader combinations using actual exported
files, with comment retention, scoped-variable changes, global insertion,
byte-identical replay and unchanged earlier bundles. The extracted compiler-wheel
check builds all five modules and performs native write/replay/reparse operations
with Python unavailable.

Fault hooks `INI_FAIL` and `INI_PAUSE` accept `validated`, `stage`, any actual
output filename, `ready` and `published`. `INI_CONTINUE` names a file that releases
a pause. Leave these hooks unset normally.

## 076 — Minimal command shell

[Five Python modules](076_command_shell/main.py), 365 substantive lines, implement
a batch shell: `quoting.py` parses commands, `planning.py` validates jobs and resolves
executables, `execution.py` controls status/recovery, and `documents.py` captures
inputs and publishes results. All five transpile into native Rust; the shared
runtime supplies a general process primitive. There is no application-specific Rust.

The included job runs the native `printf` and `tr` utilities. To try it from the
checkout, choose a fresh output directory in `shell-job.json`, then run:

```bash
SHELL_CONFIG=examples/corpus/076_command_shell/shell-job.json \
  SHELL_MODE=plan build/corpus/076/corpus_076
SHELL_CONFIG=examples/corpus/076_command_shell/shell-job.json \
  SHELL_MODE=run build/corpus/076/corpus_076
```

`plan` is the default: it prints resolved argv arrays, complete environments and
input sizes without executing commands or writing captures. `run` processes jobs
in order and publishes stdout, separate stderr files, original job bytes, a
canonical `report.json`, and a SHA-256 `manifest.json` in the new output directory.
The default job path is `shell-job.json`. Relative cwd/output/input paths resolve
against its parent; cwd must exist. Inputs are bounded snapshots of regular,
nonsymlink files. Output must not exist, including a dangling symlink.

Each job has a unique ASCII `name`, `command`, `input` path (empty means no stdin),
and `environment` object. The top-level environment is merged with per-job
replacements. Parent process variables are not inherited. Bare executables require
an explicit PATH of 1–32 nonempty absolute directories; names containing `/` resolve
against cwd. Resolution skips directories/nonexecutable files and preserves argument
bytes. Environment overrides are JSON fields; inline `NAME=value` is not special.

The quoting profile is deliberately small and explicit:

- Single/double quotes preserve spaces and empty arguments; adjacent quoted and
  unquoted fragments concatenate. An unquoted `|` separates pipeline stages.
- Outside single quotes, backslash escapes the next character; inside double
  quotes it only removes itself before `"` or `\`. This matches Python's POSIX
  `shlex` lexer for this profile. Escaped whitespace is an argument character.
- `$HOME`, wildcards and `#` are literal. There is no variable/command expansion,
  comment syntax, globbing, redirection, background execution, `cd` or job control.
  Unquoted `; & < >` and backticks/newlines are rejected. Quoted versions are literal.

All command syntax, input snapshots, job fields and environment values are checked
before executing the first job. Executable lookup happens per job, so a missing
program is a recoverable job error. Programs run concurrently within each pipeline;
stdout is connected directly to the next process and the final stdout is captured.
Arbitrary bytes are preserved without text decoding. Programs can have normal OS
side effects: plan/run is not a transactional sandbox, and captures cannot roll back
commands. The copied `job.json` preserves input bytes/paths, but is not automatically
replayed and does not include external input files or executable binaries.

Each finished job reports all stage exit codes, with negative signal numbers.
With `pipefail:true`, job status is the rightmost nonzero stage (0 if all succeed);
otherwise it is the final stage's status. Signals convert to shell status `128+N`.
An ordinary failed stage still waits for the other stages, bounded by the deadline.
The shell continues after normal failures: timeout status is 124 and lookup/spawn/
output errors are 125. SIGINT/SIGTERM during a pipeline clean up children, produce
130/143 and skip remaining jobs. The program returns the last executed job status.
Invalid configuration or publication failure returns 2. Runtime-error partial
captures are discarded; successful nonzero exits retain their captured bytes.

| Bound | Value |
| --- | --- |
| Configuration | 1 MiB JSON, strict fields, version 1 |
| Jobs / name | 1–64 / 1–64 ASCII identifier characters, starting with a letter |
| Command / stages / arguments | 1–8192 UTF-8 bytes / 1–8 / 1–128 per stage |
| Environment | At most 256 names, 1–128 ASCII identifier characters each, 64 KiB including separators/terminators per job |
| Input | 16 MiB per job, 32 MiB across snapshots |
| Captures | 0–16 MiB combined final stdout/stderr per job, 32 MiB across successful jobs |
| Deadline | 1–60000 ms per pipeline |

Captured files are synced in a private staging directory before an atomic no-replace
rename. An existing destination is preserved. Handled prepublication failures remove
staging; an uncatchable termination can leave `.shell-*` staging. Parent directories
and command binaries are trusted. Linux main-thread execution and default SIGCHLD
are required. Group cleanup covers ordinary children and descendants that remain
in those groups; it does not contain programs that deliberately escape groups or
change credentials. See the [shared process contract](../../doc/service-subset.md#foreground-native-process-pipelines).
Python reference execution requires 3.11+; native execution requires no Python.

The independent checker compares 128 generated command lines with `shlex`, then
checks their actual native child argv bytes. It also checks a 1 MiB concurrent pipe
with 128 KiB stderr, arbitrary binary stdin, eight stages, early-reader SIGPIPE,
pipefail/final-stage policies, environment/cwd handling, five recovered failures,
orphan cleanup and both interrupts with skipped follow-up jobs. It rejects 54 bad
inputs, two invalid modes, six lookup failures and four existing-output kinds.
`tools/check_command_shell.py` checks all eight writer/transformer/reader engine
combinations, passing actual stdout and stderr paths between runs. Native checks
run with PATH/PYTHONHOME/PYTHONPATH set to `/nonexistent`; the job explicitly names
its native fixture programs. The fixtures are QA tools, never linked into the app.
A supplemental whole-application capacity probe runs 64 jobs with two 16 MiB
inputs and 32 MiB of captures, checks recovery at the aggregate output limit,
and rejects input one byte beyond the aggregate limit. Both engines pass.

## Extensions established by these applications

- Concurrent foreground Linux process pipelines with explicit argv/environments,
  binary streams, deadlines, output bounds, signal cancellation and child cleanup.
- Borrowed fixed-tuple field reads, avoiding full-buffer copies for each byte lookup.

- Direct Unicode string iteration with single evaluation, source reassignment and ordinary loop control.
- Numbered regex captures, Unicode character spans, empty/unmatched groups and bounded native pattern reuse.

- Cached native RFC3339 validation patterns for repeated timestamp parsing.

- Stable sorting with named fallible key functions and reverse direction.
- Typed list concatenation with explicit ownership and evaluation order.
- Process-local Unix address-space limits that preserve tighter inherited bounds.

- Typed bytearray construction, checked indexed mutation/growth, byte membership and integer iteration.
- Natural logarithms and checked downward integer rounding through `math.log` and `math.floor`.

- Self-recursive records through typed collections and quoted type references across project imports.

- Typed set union, intersection, difference and symmetric difference with independent results.
- Unicode 15.1 full default case folding, with expansions and no Python runtime dependency.

- Generic typed min-heaps through five standard `heapq` operations, including stable tuple priorities.

- Integer and floating true division, with once-rounded exact integer ratios.

- Exact mixed integer/float JSON scalar ordering and checked numeric JSON sums.

- Unicode NFC/NFD/NFKC/NFKD normalization, including the `unicodedata.normalize` spelling,
  and lexicographic sorting of nested typed list/tuple sequences.
- Recoverable `try`/`except Exception`, optional exception binding and `else`,
  assertions with messages, returns through nested protected blocks, and bare
  re-raising with active-error restoration across nested handlers.
- Typed-list insertion with clamped signed indices, index-before-value evaluation,
  length calculation after both arguments, and preserved resource aliases.
- Homogeneous variadic tuples, immutable tuple dictionary/set keys, ordered composite
  keys and borrowed record collection reads with owned results.
- Scoped buffered binary line readers, bounded line chunks with explicit LF/EOF
  completion, exact logical byte positions and shared-alias cleanup.
- Chained comparisons with single evaluation of middle operands and lazy later
  operands, plus Python set inclusion ordering, including sets inside lists/tuples.
- Integral Unix timestamp conversion, portable UTC date formatting and Unicode
  reverse substring search through the ordinary one-argument `str.rfind` method.
- Empty typed `list()`/`dict()`/`set()`, list `extend()`/`copy()`, two-argument
  scalar `min()`/`max()`, and JSON-container string membership.
- Hexadecimal byte conversion, strict structural JSON equality, canonical paths,
  and native process exit status.
- Unique Cargo executable names for safe reuse of a shared build cache.
- Binary HTTP clients, custom request/response headers, verified private-CA TLS,
  and list item assignment with Python evaluation order and negative indices.
- Checked integer floor division/remainder with Python sign rules, stable list
  sorting (including ordered tuples), reversal, and dictionary/set copies.
- Unicode regex input and literals with ASCII shorthand classes, constant-time
  byte comparison and the `hmac.compare_digest` spelling, and corrected membership
  conversions for typed and JSON-element collections.
- List/dictionary/set `clear()` and checked `ceil()` / `math.ceil()`, preserving
  integer arguments exactly. Local Python/Rust modules take precedence over
  supported standard-library fallback imports, except built-in `sys` and `time`.
- Bounded streaming HTTP responses with typed poll callbacks, transport-driven
  backpressure, cancellation on disconnect, and reserved connection capacity.
- Scoped `with` statements for binary files and streaming HTTP readers, seek,
  truncate and sync, file identity and no-clobber hard links, and incremental
  SHA-256 with immutable hash snapshots.
- Native HTML5 link extraction, relative HTTP(S) URL resolution and normalized
  origins, verified with a 258-case URL matrix and complete local-site crawls.
- Bounded Retry-After parsing with numeric delays, all three HTTP date forms,
  rolling two-digit years, calendar validation and preserved fractional clocks;
  binary chunk joining without intermediate text decoding.
- Original incoming HTTP request targets for queries with repeated parameters;
  application-supplied Cache-Control values replace the shared server default.
- Bounded native worker callbacks with isolated JSON inputs, ordered results,
  checked callback signatures, and joined workers on normal and error paths.
- Scoped TCP listeners and streams in service/project modules, bounded accept,
  absolute read/write deadlines, half-close and explicit close; byte concatenation,
  clamped slices, and checked big/little-endian integer conversion.
- Unix socket readiness snapshots, nonblocking accept/read/partial-write calls,
  configurable send-buffer hints, byte substring search, checked list removal
  and dictionary/JSON-object key deletion.
- Insertion-ordered iteration over typed dictionary keys and checked ASCII
  decimal-string conversion, including the `int(text)` spelling.
- Scoped UDP sockets with numeric IPv4/IPv6 source addresses, explicit truncation,
  empty datagrams, bounded receive/send calls and shared-handle cleanup.
- Signed integer `&`, `|`, `^`, `~`, `<<` and `>>`, with checked left-shift
  overflow, recoverable negative counts and Python-compatible large right shifts.

- Typed dataclass records with scalar defaults, ordered constructor evaluation,
  named field updates, nested types and project imports; owned-value semantics.
- Typed list slices, insertion-ordered dictionary-key snapshots and numeric
  `float` conversion; canonical base64, legacy SHA-1 digest bytes and repeating XOR.
- Iteration over nonempty fixed tuples with identical element types, evaluating
  the tuple expression once and preserving the existing owned-value/resource-handle semantics.

- Scoped Unix listeners/streams, bounded I/O, readiness, partial writes,
  stale-socket recovery and cleanup of owned socket paths.
- Typed conditional expressions with single condition evaluation and lazy branches.

- Explicit Unix metadata observations, bounded sorted directory names and UTF-8
  symlink targets, with all traversal and aggregation in Python.
- Borrowed reads and length checks of named collections, preserving owned results
  and expression evaluation, including side effects in tuple-length expressions.

- Atomic Linux no-overwrite renames and scoped, nonblocking Unix advisory file
  locks, with planning and recovery implemented entirely in Python.
- `set(typed_list)` for integer, string and boolean values, evaluating the list once.

- Indexed `append`/`extend` for lists inside named typed lists or dictionaries.
- Borrowed nested collection reads and membership, with owned returned values
  and needle-before-container evaluation order.

- Exclusive private directory creation, symlink creation and permission/mtime restoration.
- Lazy three-argument `range`, including negative steps and signed integer boundaries.

- Literal `None` identity tests on JSON/None values, with single evaluation.
- Borrowed named-dictionary `get` with eager key/default evaluation before lookup.

- Atomic replacement of distinct regular files, with caller-controlled staging and directory sync.
- Typed `list()` conversion from lists, sets and dictionaries, borrowing named inputs.
- Canonical JSON with interoperable 17-digit binary64 formatting for stable content IDs.

The exact supported semantics and remaining restrictions are documented in the
[service subset](../../doc/service-subset.md). These checks provide evidence for
the implemented applications; they do not prove arbitrary Python compatibility.

## 077: Python source-outline browser

[Five Python modules](077_source_outline/main.py), 435 substantive lines, load a
project manifest and publish a static HTML source browser. All project handling,
qualified names, docstring cleanup, import resolution, HTML escaping, checksums
and publication transpile into Rust. A shared native parser provides ordinary
statement records; source is never imported or executed. The executable needs
no Python runtime.

```sh
python tools/corpus.py 077
python tools/check_source_outline.py
OUTLINE_CONFIG=examples/corpus/077_source_outline/outline-project.json build/corpus/077/corpus_077
```

The sample browses the application's own five modules and writes
`build/source-outline-demo/index.html`. Open that file in a browser. The output
must not already exist; use another output path for a subsequent run.

A manifest has `version: 1`, an `output` directory and a `modules` array. Each
module has an ASCII dotted `name`, a UTF-8 `.py` `source` path and an optional
boolean `package`; package defaults to whether the source is named `__init__.py`.
Paths are relative to the manifest. Up to 32 uniquely named modules and unique
source paths are accepted, at most 128 KiB/4,096 lines per source and 1 MiB total.
Module names are at most 128 characters. Input files must be regular nonsymlinks.
The output parent must exist. Bundles are limited to 16 MiB before their checksum
manifest and published through a private staging directory and atomic no-replace
rename. Existing files, directories and symlinks are preserved.

Module pages list functions, async functions, classes, type aliases, decorators,
docstrings and imports, followed by escaped source with line anchors. The project
index lists every definition, including nested and conditional definitions;
browser Find can search that index. Relative imports resolve using package
identity. Imports link to known modules or unique top-level definitions; ambiguous
or unknown symbols may link to their known module, and external imports are
marked unresolved. This is static source navigation, not runtime import execution.

Each bundle also contains a machine-readable `report.json`, original source
bytes, a portable `project.json` that rebuilds from those exported source files,
and `manifest.json` with file sizes and SHA-256 hashes. Package identity survives
export even though the source files are stored together. Rebuilding the exported
project yields byte-identical files. Eight mixed Python/Rust producer/rebuilder
combinations consume the actual exported paths and check all links and checksums.

Acceptance independently compares against CPython's AST and docstring extraction,
including decorated generic classes, nested async/function scopes, Unicode names,
exception groups, pattern matching, conditional definitions and relative imports.
It parses its own real application sources, checks BOM/CRLF/CR handling, escaped
HTML, ambiguous imports, malformed inputs, no execution and preserved existing
outputs. The native parser profile and its limits are documented in the
[service subset](../../doc/service-subset.md#native-python-statement-parsing).
## 078: Regex batch rewrite tool

[Five Python modules](078_regex_rewrite/main.py), 406 substantive lines, read a
JSON job, preview every file, apply ordered literal replacements, and restore
exact original bytes and metadata from a durable backup. The same complete
project runs as Python or a standalone native Rust executable.

```bash
python tools/corpus.py 078
python tools/check_regex_rewrite.py
rewrite_demo="$(mktemp -d)"
cp examples/corpus/078_regex_rewrite/rewrite-job.json examples/corpus/078_regex_rewrite/sample.txt "$rewrite_demo/"
REWRITE_CONFIG="$rewrite_demo/rewrite-job.json" build/corpus/078/corpus_078
REWRITE_MODE=apply REWRITE_CONFIG="$rewrite_demo/rewrite-job.json" build/corpus/078/corpus_078
REWRITE_MODE=restore REWRITE_BACKUP="$rewrite_demo/backup" build/corpus/078/corpus_078
```

`REWRITE_MODE` defaults to `preview`. Preview prints the complete JSON report and
writes nothing, even when a backup already exists. Apply requires a fresh backup
path. Restore uses `REWRITE_BACKUP` and the saved report; it does not need the job
configuration. Configuration paths are relative to the job file's directory.
Use explicitly listed regular files: there is no recursive discovery or globbing.

The job has exactly `version: 1`, `files`, `backup` and `rules`. Each rule has a
unique ASCII `name`, a `pattern` and a `replacement`. Rules run in listed order;
a later rule sees the previous rule's output. Patterns use common ASCII syntax:
literals, flat classes/ranges, groups, alternation, greedy/lazy repetitions,
ASCII shorthand classes and boundaries, and `^`, `$`, `\A`, `\Z` anchors.
Escape literal brackets inside classes and literal braces. Extension groups,
backreferences, possessive repetitions, class set operations and engine-specific
escapes are rejected. Every replacement is literal, including `$1`, `\1`, Unicode
and newlines. `$` recognizes the position before one final LF, while `\Z` is
strictly the end of input. CRLF bytes are preserved unless a rule changes them.

Every rule and every input file is validated before any backup or source write.
Zero-width matches are rejected, including an empty match following a nonempty
one. The complete transformed batch is held within explicit limits:

| Limit | Value |
| --- | --- |
| Job / audit JSON | 1 MiB each |
| Explicit files | 1–64 |
| Rules | 1–32 |
| Original / intermediate / final file | 65,536 UTF-8 bytes |
| Pattern | 1–512 ASCII bytes; group nesting at most 32 |
| Replacement | At most 4,096 UTF-8 bytes |
| Rule name | 1–64 ASCII letters, digits, underscores or hyphens; starts with a letter |

Inputs must be UTF-8 without NUL. Special permission bits, symlink inputs,
duplicate paths and hard-link aliases among the listed inputs are rejected.
Output size is calculated before allocating replacement text. Each file's report
contains before/after hashes and sizes, 160-character previews, original mode and
nanosecond timestamp, and per-rule match counts, hashes, sizes and change flags.

Apply publishes the whole backup directory before replacing the first source.
`N.before` and `N.after` contain exact bytes; `report.json` records paths and
metadata; `job.json` preserves the submitted configuration. `state.json` records
prepared, applying, applied, interrupted, restoring or restored progress. Each
source replacement is atomic and synced. The entire batch is not one atomic
filesystem transaction: a failure can leave a partially applied batch, with all
originals already backed up. `REWRITE_FAIL=N` injects such an interruption after
N files for reproducible recovery checks.

Restore validates every original backup and every current file before making
changes. A current file must contain either its original or planned replacement
bytes. Corrupt originals or later content edits stop the whole restore before
source writes. It then restores each file's bytes, ordinary permission bits and
exact modification timestamp, including pre-epoch values. Repeating restore is
supported. Backup receipts are local trusted data, not signed archives; moving
them does not rewrite their absolute source paths. Replacements create new
inodes, so unlisted hard links, ownership, ACLs and extended attributes are outside
this tool's preservation contract. Cooperating operations share a backup lock;
metadata checks detect intervening changes but do not lock unrelated writers.

The native regex assertion engine has a recoverable backtracking budget; see the
[shared regex semantics](../../doc/service-subset.md#language-and-semantic-contract).
Acceptance checks use an independent CPython `re` oracle, verify literal Unicode
and CRLF output, reject 62 invalid cases without writes, test three interruption
boundaries and preserve existing backups. Eight Python/Rust apply→restore→reapply
combinations consume actual complete and interrupted backups.

## 079: Tiny automation-language interpreter

[Six Python modules](079_automation_language/main.py), 443 substantive lines,
implement a lexer, typed recursive AST, checked expression evaluator and lexical
execution scopes. The complete Python application transpiles to Rust. Its tiny
domain language is interpreted by that native program; it contains no Python
interpreter, host-language `eval`, dynamic imports or shell execution.

```bash
python tools/corpus.py 079
python tools/check_automation_language.py
AUTOMATION_CONFIG=examples/corpus/079_automation_language/automation-job.json build/corpus/079/corpus_079
```

The sample emits `[-1, 4, -9, 16, -25, 55]` and leaves `total = 55`, `next = 6`.
The JSON job has exactly `version: 1`, `program`, `steps` and `output`. Paths are
relative to the job file. Output must be a new directory. The default job name
is `automation-job.json`; override it with `AUTOMATION_CONFIG`.

Statements are separated by newline or semicolon; the final separator before a
closing brace or end of input is optional. A hash starts a comment through the
end of its line. CRLF and CR are normalized for source coordinates; the exported
source retains every original byte. Expressions and opening braces stay on the
statement's header line. `else` may follow the closing brace immediately or on
the next line.

```text
let name = expression
set name = expression
emit expression
if expression { statements } else { statements }
repeat expression { statements }
```

`else` is optional. Conditions are integers: zero is false and every other value
is true. `let` declares in the current scope and rejects duplicate declarations
in that scope. `set` changes the nearest existing declaration. Each conditional
branch and each repeat iteration opens a fresh local scope; outer variables can
be updated with `set`. Local declarations disappear when the block exits, including
on failure. A repeat count is evaluated once and must be nonnegative.

Expressions contain decimal signed 64-bit integers, ASCII variable names,
parentheses, unary `+`/`-`, multiplication, floor division `//`, remainder `%`,
addition, subtraction and comparisons `== != < <= > >=`. Precedence follows that
list from high to low. Binary operators associate left to right; comparison
chains require explicit parentheses. Comparisons return 0 or 1. Integer division
and remainder use Python's floor rules. Arithmetic overflow, division by zero and
undefined names are recoverable source-located errors. The minimum signed integer
is representable; floating values and strings are outside this small grammar.

The interpreter charges one step per executed statement and one per repeat
iteration, including an empty iteration. A budget of zero can execute an empty
program but cannot execute a statement. Exhaustion stops before the next charged
operation. Expression work is bounded separately by source/token/AST limits.
The entire program is parsed before execution, so malformed syntax in an
unselected branch is still rejected.

| Limit | Value |
| --- | --- |
| Job / program input | 65,536 / 32,768 UTF-8 bytes |
| Tokens, excluding end marker | 4,096 |
| Nested blocks / expression parser recursion | 16 / 32 |
| Whole AST height | 64 |
| Identifier | 1–64 ASCII letters, digits or underscores; first character is not a digit |
| Declarations in one scope | 128 |
| Step budget | 0–10,000 |
| AST / report JSON output | 1 MiB / 2 MiB |

Keywords `let`, `set`, `emit`, `if`, `else` and `repeat` are reserved. UTF-8 comments
are allowed; source locations use one-based line and Unicode character columns,
with a tab counting as one character. NUL, invalid UTF-8, unsupported tokens,
symlink inputs and existing output destinations are rejected.

A complete result directory is staged, synced and atomically published:

- `program.auto`: exact submitted program bytes.
- `ast.json`: flat preorder nodes with kind, value, source location, parent index
  and child index. Flat storage supports deep syntax within the JSON depth limit.
- `report.json`: status, error, consumed steps, final global variables, emitted
  integers and an ordered trace of assignments, branches and loop iterations.
- `job.json`: a portable replay job using `program.auto` and the same step budget.

Successful execution exits 0. Runtime errors exit 1 and publish a report retaining
completed global updates and emissions; active local scopes are unwound. Invalid
configuration or syntax exits 2 without publishing a result. Input files are never
changed. Replaying an unchanged export yields byte-identical source, AST, report
and replay job in a new directory.

Acceptance compares 160 generated programs with an independent CPython-AST
arithmetic and lexical-environment oracle. It checks 42 boundaries under a
256 MiB address-space limit, 24 invalid configurations without writes, exact AST
positions and five source diagnostics. Eight Python/Rust producer→replayer→replayer
combinations consume actual exported files for both successful runs and budget
exhaustion. All application logic remains Python source compiled into native Rust.

## 080: Stateful syntax-highlighting exporter

[Five Python modules](080_syntax_highlighter/main.py), 440 substantive lines,
lex a small configuration language and export a complete, self-contained HTML
bundle. The whole project compiles to a native Rust executable. Source is displayed
as text, never evaluated. This is a documented configuration grammar, not a Python
syntax highlighter.

```bash
python tools/corpus.py 080
python tools/check_syntax_highlighter.py
HIGHLIGHT_CONFIG=examples/corpus/080_syntax_highlighter/highlight-job.json build/corpus/080/corpus_080
```

The sample writes `build/highlight-demo/index.html`. A job has exactly `version: 1`,
`files`, `theme` and `output`. Each file has a unique `label` and a `source` path.
Paths are relative to the job file; output must be a new directory. Themes are
`light` and `dark`. The default job is `highlight-job.json`; override it with
`HIGHLIGHT_CONFIG`.

The lexer recognizes ASCII identifiers, lowercase `true`, `false`, `null`, decimal
numbers with optional fraction and exponent, punctuation, whitespace, single or
double quoted strings, triple quoted multiline strings, hash line comments and
nested `/* ... */` block comments. A backslash escapes the next character inside
a string without interpreting it. Ordinary strings end at a newline even after a
backslash; triple quoted strings can span lines. Signs are separate punctuation.
A malformed numeric candidate, unsupported character or unfinished string/comment
becomes an error token with a diagnostic. Other tokens continue to render.

CRLF and CR are normalized to LF for lexing and display. Token offsets are
zero-based Unicode character offsets with an exclusive end; line and column
numbers are one-based. A tab counts as one character. Tokens cover the entire
normalized input, including comments and whitespace. Original files are exported
byte for byte, with download links distinct from their highlighted pages.

| Limit | Value |
| --- | --- |
| Job / individual source | 65,536 bytes |
| Files / aggregate source | 16 / 262,144 bytes |
| Tokens per file / aggregate | 8,192 / 32,768 |
| Label | 1–80 Unicode characters, no NUL, CR or LF |
| Nested block comments | 8 |
| Generated files, excluding checksum manifest | 16 MiB |

Inputs must be regular UTF-8 files without NUL. Leaf symlinks, duplicate paths,
hard-link aliases among listed sources, existing output paths and exceeded limits
are rejected. Source metadata is rechecked before publication. Files are staged,
synced and published as one new directory; inputs are never changed.

The result includes an index, stylesheet, one numbered HTML page and exact source
copy per input, a token/diagnostic JSON report, a portable replay job and a SHA-256
manifest of every other output file. All source and labels are HTML-escaped. Pages
use local links and CSS without JavaScript or remote assets. Diagnostics link to
their token positions. Exit 0 means no lexical diagnostics; exit 1 publishes a
complete bundle with diagnostics; exit 2 rejects invalid configuration, source or
resource limits without publishing output.

Acceptance uses explicit independent token fixtures plus 240 seeded fragments,
checks every Unicode coordinate and manifest checksum, reconstructs exact source
text through an HTML parser, resolves all links and rejects 41 invalid cases
without writes. Eight Python/Rust producer→replayer→replayer combinations yield
byte-identical bundles for both themes. Simultaneous file, byte, label and token
limits pass under a 512 MiB address-space limit in both engines. HTML verification
is structural; no automated browser rendering was performed.

## 081: Recurring reminder daemon

[Four Python modules](081_reminder_daemon/main.py), 406 substantive lines,
implement fixed-interval reminders, a polling loop and durable progress. The
complete application transpiles to a standalone native Rust executable. Its
reminders go to the local log; there is no email, push service or shell command.

```bash
python tools/corpus.py 081
python tools/check_reminder_daemon.py
REMINDER_CONFIG=examples/corpus/081_reminder_daemon/reminder-job.json build/corpus/081/corpus_081
REMINDER_CONFIG=examples/corpus/081_reminder_daemon/reminder-job.json REMINDER_MODE=inspect build/corpus/081/corpus_081
```

The sample replays a short clock trace and writes `build/reminder-demo-state.json`.
Repeated execution resumes that state, so it does not repeat consumed occurrences.
A job contains exactly `version: 1`, `store` and `reminders`. Each reminder has a
unique `id`, `message`, `start`, `every` and `policy`. `start` is an integer UTC Unix
timestamp; `every` is a positive interval in seconds. Scheduling is anchored to
`start + N * every`, independent of polling delay and daylight-saving time.
Reports and log events include readable UTC timestamps alongside epoch seconds.

For each reminder, all scheduled times at or before the effective clock are due:

| Policy | Due occurrences |
| --- | --- |
| `all` | Emit up to 16 oldest occurrences per tick; leave the rest due for subsequent ticks. |
| `latest` | Emit the latest due occurrence once; count earlier ones as skipped. |
| `skip` | Consume all due occurrences, emitting one only if it is scheduled exactly at the effective clock. |

Repeated clock values can drain an `all` backlog. The effective clock is the
maximum of the current observation and the previously saved clock. Rollback does
not move deadlines backward or re-emit consumed occurrences. Reminders execute in
configuration order; each reminder's scheduled events are chronological. Global
sequence numbers follow that processing order, not a cross-reminder timestamp sort.

| Environment | Behavior |
| --- | --- |
| `REMINDER_CONFIG` | Job path, default `reminder-job.json`. |
| `REMINDER_MODE=trace` | Default. Read all supplied integer clock values before writing state. |
| `REMINDER_TRACE` | Trace path relative to the job, default `clock.json`. |
| `REMINDER_MODE=run` | Poll the real Unix clock, rounded down to whole seconds. |
| `REMINDER_POLLS` | Stop after 1–100,000 ticks; default 0 keeps polling. |
| `REMINDER_INTERVAL_MS` | Sleep 10–60,000 ms between ticks; default 250. |
| `REMINDER_STOP` | Optional path relative to the job. Its existence stops the next polling iteration. |
| `REMINDER_MODE=inspect` | Validate existing state and print its report without changing the saved file. |

Stop-file observation can take up to one polling interval plus the current tick.
Exit 0 means a successful trace, finite run, stop-file shutdown or inspection.
Invalid inputs and I/O failures exit 2. Earlier completed ticks remain committed
if a later tick fails. The summary is printed to stdout; due events are JSON
records prefixed `INFO:REMINDER` on stderr. A checksum envelope stores progress,
cumulative emitted/skipped counts, the clock high-water mark and the most recent
256 events. Each event records its sequence, reminder ID/message, scheduled and
observed times, and lateness.

State is atomically replaced and synced before logging the tick's events. A crash
after this commit can omit some terminal log lines; restart does not repeat them.
The retained state history provides receipts for those events until they age out.
This is not an exactly-once external notification service or an unlimited audit
log. A nonblocking advisory lock excludes cooperating writers for the entire run;
the `.lock` file remains after shutdown. Configuration is fixed for a process and
must exactly match saved reminders on restart. Use a separate store for a changed
schedule. State and lock must be regular files without hard-link aliases; leaf
symlinks and overlaps with configuration/trace inputs are rejected. Checksums
catch accidental corruption; local state is trusted, not authenticated.

| Limit | Value |
| --- | --- |
| Reminders | 1–32 |
| ID | 1–32 ASCII characters, starts with a letter; then letters, digits, `_` or `-` |
| Message | 1–256 UTF-8 bytes, no ASCII control characters |
| Start / observed clock | 0–4,102,444,799 seconds (1970 through 2099 UTC) |
| Interval | 1–31,536,000 seconds |
| Job / trace file | 65,536 bytes each |
| Trace | 0–1,000 ticks |
| Snapshot / retained events | 1 MiB / 256 |
| Cumulative ticks | At most 1,000,000,000,000 |

The next scheduled time can extend into 2100; it remains representable and is
shown in reports. `REMINDER_FAULT` injects a recoverable failure at `before_commit`,
`after_commit` or `after_log`. `REMINDER_PAUSE` pauses at the same boundaries for
up to 30 seconds for process-termination and competing-writer tests.

Acceptance uses an independent range-based interval oracle, exact hand-checked
policy outcomes, 120 generated ticks for 12 reminders across eight restarts,
Unicode messages, leap-day and end-range boundaries, 55 invalid inputs and 27
corrupt or changed snapshots. It kills real processes at three boundaries,
checks lock exclusion and verifies an unbounded polling loop stops on a newly
created stop file. Maximum reminder/message sizes pass under 256 MiB. Eight
Python/Rust writer→restarter→restarter combinations consume actual saved snapshots
and reproduce identical final state and event streams.

## 082: Cron schedule explorer

[Five Python modules](082_cron_explorer/main.py), 393 substantive lines, parse a
numeric five-field cron subset, explain its selected values and find upcoming UTC
runs. The complete application compiles to native Rust using the existing typed
collections and datetime adapters. It explores schedules; it does not install a
crontab or execute commands.

```bash
python tools/corpus.py 082
python tools/check_cron_explorer.py
CRON_CONFIG=examples/corpus/082_cron_explorer/cron-job.json build/corpus/082/corpus_082
```

The sample writes `build/cron-demo`. A job has exactly `version: 1`, `start`, `days`,
`limit`, `schedules` and `output`. Each schedule has a unique `id` and an
`expression`. The default job is `cron-job.json`; override it with `CRON_CONFIG`.
Output is relative to the job file and must be a new directory.

`start` is an RFC3339 timestamp with an explicit offset and up to six fractional
second digits. It is normalized to UTC. The search window includes `start` and
excludes `start + days * 86400 seconds`. Runs occur at exact minute boundaries;
a fractional start skips the preceding minute. Date arithmetic supports Gregorian
years 0001–9999, including non-leap centuries. A window whose end exceeds that
range is rejected. All search and presentation use UTC, without DST transitions.

The five fields are separated by spaces or tabs:

| Field | Numeric range |
| --- | --- |
| Minute | 0–59 |
| Hour | 0–23 |
| Day of month | 1–31 |
| Month | 1–12 |
| Day of week | 0–7; both 0 and 7 mean Sunday, 1 means Monday |

A field accepts `*`, an integer, an ascending inclusive range (`9-17`), a comma
list (`1,3,5`), or a step on a wildcard/range (`*/15`, `9-17/2`). Numeric lists may
include ranges and stepped ranges. Steps begin at the range's lower value and
must be positive and no larger than the field width. A step on a single integer
is rejected. One- or two-digit ASCII numbers are accepted, including leading
zeroes. Duplicate values are deduplicated; Sunday aliases normalize to 0.
Wildcards cannot be combined with comma lists. Named months/weekdays, macros,
wrapping ranges, seconds, command fields and `L`, `W`, `#`, `?` extensions are
outside this subset and produce diagnostics.

Minute, hour and month must all match. For day-of-month and day-of-week, both
must match if either field begins with `*` (including `*/N`); otherwise either
matching field is sufficient. The JSON explanation exposes this as `day_rule`
`and` or `or`, along with each field's numeric set and `starred` flag. This follows
the relevant [Cronie matching rule](https://github.com/cronie-crond/cronie/blob/master/src/cron.c)
and [star-flag parsing](https://github.com/cronie-crond/cronie/blob/master/src/entry.c)
for the accepted grammar. Thus `0 9 1 * 1` means the first of the month or Monday;
`0 9 */2 * 1` means Mondays whose day-of-month is selected by the step. A numeric
full range such as `1-31` is still a restricted field for this rule.

Schedules are searched independently in chronological order. Up to `limit` runs
are retained for each. `more` is true only after finding one additional matching
run inside the window; `next_omitted` identifies that run. Reaching exactly the
limit with no further match leaves `more` false. No runs in the window is a valid
result and does not claim the expression can never match outside that window.
The implementation checks calendar days before enumerating selected hours and
minutes, so an impossible date does not require scanning every minute.

An invalid expression gets its own explanation and does not suppress other
schedules. Diagnostics identify a one-based field number and Unicode character
column at the beginning of the invalid list component (or the offending field
for wildcard-list errors). A missing field points just after the expression;
an extra field points at the sixth token. Tabs count as one character. Source
expressions are preserved in JSON and JSON-quoted in the text report.

| Limit | Value |
| --- | --- |
| Job file | 65,536 bytes |
| Schedules | 1–16 |
| ID | 1–32 ASCII characters; letter first, then letters, digits, `_` or `-` |
| Expression | At most 256 UTF-8 bytes |
| Search window | 1–3,660 days |
| Retained runs | 1–1,000 per schedule; at most 16,000 total |
| Output files, excluding manifest | 8 MiB |

The complete result is staged, synced and atomically published as a new directory:

- `report.json`: normalized window, field explanations, runs, weekdays, search
  day counts, truncation details and expression diagnostics.
- `report.txt`: readable explanations and scheduled UTC times.
- `schedule.csv`: `id,utc,weekday`, grouped by input schedule and chronological
  within each schedule; Sunday is 0.
- `cron-job.json`: portable replay job with a normalized start and `rebuilt` output.
- `manifest.json`: exact byte sizes and SHA-256 checksums of the other four files.

Exit 0 means all expressions are valid. Exit 1 publishes a complete bundle that
includes invalid-expression diagnostics. Exit 2 rejects a bad job, input or I/O
operation. Leaf symlink inputs and existing output paths are rejected; source
metadata is rechecked before publication. The input job is never changed.

Acceptance compares 16 explicit and 80 generated expressions with an independent
minute-grid `datetime` oracle. It checks 30 exact diagnostics, nine calendar/offset
boundaries, the eight-year leap-day gap around 2100, impossible February dates,
exact truncation behavior and 42 invalid jobs without writes. Maximum job,
expression, ID, window and output-count limits pass under 256 MiB. CSV rows and
checksums are verified. Eight Python/Rust producer→replayer→replayer combinations
consume actual exported jobs and produce byte-identical bundles for successful
and diagnostic-containing inputs.

## 083: HTTP activity timer journal

[Five Python modules](083_activity_timer/main.py), 423 substantive lines, implement
a local HTTP service for named activity sessions. The entire application compiles
to native Rust. Active intervals and completed durations are saved before a
successful response, and remain available after restart.

```bash
python tools/corpus.py 083
python tools/check_activity_timer.py
TIMER_STATE=build/activity-state.json build/corpus/083/corpus_083
```

In another terminal:

```bash
curl -s http://127.0.0.1:8793/start -H 'Content-Type: application/json' -d '{"id":"coding-1","name":"Coding"}'
curl -s http://127.0.0.1:8793/pause -H 'Content-Type: application/json' -d '{"id":"coding-1"}'
curl -s http://127.0.0.1:8793/report
```

The [HTTP request collection](083_activity_timer/requests.http) also demonstrates
resume, stop, individual queries and downloadable exports. The server binds to
loopback. `TIMER_PORT` defaults to 8793; 0 selects an available port and announces
it on stdout. `TIMER_STATE` defaults to `activity-state.json` in the working
directory; its parent directory must exist.

| Request | JSON body / query | Result |
| --- | --- | --- |
| `POST /start` | `{"id":"coding-1","name":"Coding"}` | Create a running session; 201. |
| `POST /pause` | `{"id":"coding-1"}` | Close the active interval and pause; 200. |
| `POST /resume` | `{"id":"coding-1"}` | Open another interval on a paused session; 200. |
| `POST /stop` | `{"id":"coding-1"}` | Permanently stop a running or paused session; 200. |
| `GET /session?id=coding-1` | No body | One session with its intervals and totals. |
| `GET /report` | No body or query | All sessions plus totals by activity name and overall totals. |
| `GET /export` | No body or query | The same complete report as a downloadable `activity.json`. |

A session ID is unique for the lifetime of its journal and cannot be reused after
stop. Activity names can repeat across IDs; report groups use exact case-sensitive
names. Multiple sessions can run simultaneously. Aggregates sum their durations,
so overlapping activities are counted independently.

The transition graph is running→paused→running, with running or paused→stopped.
Paused time is excluded. Stopping a paused session does not create another active
interval. Zero-length intervals are retained when an activity is immediately
paused or stopped. Queries report completed duration, current active duration and
their sum in integer milliseconds, plus numeric totals in seconds. Session views
include creation/update/stop timestamps, the current open interval when running,
and every completed `{start_ms,end_ms}` interval. Reports order sessions by ID
and activity groups by name.

Invalid JSON, fields or values return 400; absent sessions or routes return 404;
wrong methods return 405. Existing IDs and illegal transitions return 409.
Oversized bodies return 413, and session/interval capacity returns 507. These
rejections leave the saved journal unchanged. At the interval limit a paused
session can still be stopped, but cannot resume. Stopped sessions remain in the
journal; choose a new state file to begin a separate journal.

The service samples both clocks in milliseconds. On startup it keeps the larger
of the saved logical clock and current UTC wall clock, then records a fresh
process-local monotonic baseline. For each successful operation, its logical clock
is the larger of the current wall clock and the previous logical clock plus elapsed
monotonic time. This prevents negative durations on wall-clock rollback and lets
timers continue advancing while that wall clock is behind. Forward wall-clock
corrections advance the logical clock. Across restarts, active sessions include
downtime to the extent that the wall clock advances beyond the saved logical
clock; paused sessions do not. Monotonic readings from an old process are never
used as the new process's baseline. Successful reads also persist the clock used
in their response, so later observations cannot shrink reported elapsed time.

All timestamps are Unix-epoch milliseconds on this logical clock. They are not
independent measurements of civil UTC when a wall-clock correction has occurred.
The service supports wall/logical time from 1970 through 2099. Durations are
stored as integers and converted to seconds only in reports.

| Limit / setting | Value |
| --- | --- |
| `TIMER_SESSIONS` | 1–128 sessions; default 128 |
| `TIMER_INTERVALS` | 1–256 completed intervals per session; default 256 |
| ID | 1–32 ASCII characters; letter first, then letters, digits, `_` or `-` |
| Activity name | 1–128 UTF-8 bytes; no ASCII control characters |
| Request body | At most 4,096 bytes |
| Saved journal | At most 8 MiB |
| Wall / logical timestamp | 0–4,102,444,799,999 ms |

A checksum envelope stores sessions, interval totals and clock progress. Loading
validates field types, statuses, interval order, opening/closing timestamps and
recomputed sums. The snapshot is atomically replaced and synced. The server holds
an advisory `.lock` for its lifetime, and the HTTP adapter serializes callbacks,
so competing requests cannot overwrite each other's transitions. State, lock and
injected-clock files must be regular files without hard-link aliases; leaf
symlinks and overlapping paths are rejected. The lock file remains after shutdown
and must not be removed while a writer is running. State is trusted local data;
its checksum detects accidental corruption, not malicious alteration.

Storage or clock failures return 500. A failure after commit can leave the
transition saved even though no successful response arrived. The error asks the
caller to inspect state before retrying. A pre-commit failure preserves the old
journal. Process termination leaves the last committed snapshot; restart reloads
it and rebases the clocks. Invalid startup settings or corrupt state exit 2.

For deterministic checks, `TIMER_CLOCK` can point to a JSON file containing exact
integer `wall_ms` and `mono_ms` samples. Monotonic samples must not decrease while
one server process runs, but may reset on restart. Replace the file atomically
when changing samples. `TIMER_FAULT` injects a request-commit failure at
`before_commit` or `after_commit`; `TIMER_PAUSE` pauses at those points for up to
30 seconds to test process termination. These hooks do not affect startup rebasing.

Acceptance compares 295 HTTP requests against an independent event-history oracle,
checks 51 invalid requests/clocks and 43 corrupt-state/configuration cases, and
verifies exact grouped exports. Twelve publication checks include killed
processes, competing writers, actual permission errors and live corruption.
Forty concurrent mutation requests cover independent sessions and contested IDs
and transitions. Production wall and monotonic clocks are exercised too. A native
and Python process each load/export all 128 sessions and 32,768 intervals under a
256 MiB address-space limit. Eight Python/Rust writer→restarter→restarter
combinations consume the same saved journal and produce identical snapshots and
reports, including pause preservation, clock rollback and active downtime.

## 084: Rotating log router

[Seven Python modules](084_log_router/main.py), 489 substantive lines, implement
bounded live-log reads, severity and substring filters, JSONL output segments,
saved input positions and restart recovery. All seven modules compile into the
native executable using the existing shared runtime.

```sh
python tools/corpus.py 084
python tools/check_log_router.py
mkdir -p build/router-demo
cp examples/corpus/084_log_router/{router-job.json,application.txt,worker.txt} build/router-demo/
ROUTER_CONFIG=build/router-demo/router-job.json build/corpus/084/corpus_084
```

The [example configuration](084_log_router/router-job.json) reads two input files
and writes general, alert and request records into `build/router-demo/routed`.
Relative input/output paths are resolved beside the configuration file. Their
parent directories must already exist. The output directory is created if absent
and is owned exclusively by this router; unknown files cause an error.

Input lines are UTF-8 `LEVEL message` records ending in LF or CRLF. Supported
levels, in increasing order, are `DEBUG`, `INFO`, `WARNING`, `ERROR`, and
`CRITICAL`. Empty messages and tabs are accepted; other ASCII controls are
rejected. Level names and substring filters are case sensitive. Each complete
line is sent to every matching route. Unmatched lines still advance the saved
input position and increase the filtered count. An incomplete final line is
left unread until its newline arrives, including a partial UTF-8 character.

Output records contain `source`, cumulative `line`, input `generation`, byte
`offset`, `level`, and `message`. The router writes canonical JSON followed by LF
to `<route>.0.jsonl`, `<route>.1.jsonl`, and subsequent segments. Rotation happens
before the next record would exceed `segment_bytes`. Segments are retained.
Reaching the configured segment count rejects the entire pending batch without
advancing its input positions. Start a separately configured output directory
when the retained archive is full; changing an existing saved policy is rejected.

| Limit | Contract |
| --- | --- |
| Input sources / output routes | 1–4 each |
| Source and route identifiers | ASCII letter followed by at most 15 letters, digits, `_` or `-` |
| Complete physical input line | At most 1,024 bytes, including its newline |
| Input file | At most 64 MiB |
| Lines read per source per poll | `batch_lines`: 1–64 |
| Substring filter | At most 128 UTF-8 bytes |
| Segment size | `segment_bytes`: 4,096–16,384 bytes |
| Retained segments per route | `segments`: 1–8; at most 32 files overall |
| Configuration / control document | 64 KiB / 2 MiB |
| Retired input identities | At most 32 per source |
| Directory scan during input rotation | At most 256 entries |

The producer must append to input files and close an old file before publishing
its replacement. Rename the old file within the same directory and retain it
until the router has drained it. Saved device/inode identities let the router
find that file during a rename gap, drain complete lines, and switch to the new
file on a later poll. A partial old tail prevents switching. Newly observed
growth postpones the switch. Deleted old files, reused identities, copy/truncate
rotation and edits to committed input prefixes cause errors rather than silent
skips. Previously consumed prefixes are rehashed on each poll; this favors
integrity over throughput for the bounded files in this example.

`state.json` contains the policy, input identities and offsets, prefix hashes,
segment inventory and counts. Before writing output, `pending.json` durably saves
the old/new states and exact append payloads. Recovery first validates all files:
committed prefixes must match and any suffix must be a byte prefix of its planned
append. It then restores the full planned appends, syncs them, atomically replaces
the state, and finally removes the plan. Restart can finish an append split inside
a UTF-8 sequence. Repeating recovery does not add duplicate records. The plan
contains the payload, so completing it does not require rereading the input;
subsequent prefix verification still reports a changed source.

The exact-once property applies to committed output records after successful
completion/recovery. A reader observing files during a write can see a partial
record, and a recovered append can be rewritten. This example does not promise
exactly-once delivery to an external tailing consumer. Checksums detect accidental
corruption; saved state is trusted local data. Noncooperative external writes and
hostile directory replacement are outside the ownership contract.

An advisory `<output>.lock` excludes concurrent router processes. Keep that lock
file while any router is running. Sources, controls, segments and the lock must
be regular files without hard-link aliases; leaf symlinks are rejected. The
reserved `control.tmp` is an atomic-publication staging file and can be overwritten
after interruption. Corrupt documents, unexpected files, invalid settings, storage
errors and full output archives exit 2. A failure can leave a valid recovery plan;
restart using the same policy after addressing the reported problem.

`ROUTER_POLLS` defaults to 1; use 0 to keep polling or 1–100,000 for a finite run.
`ROUTER_INTERVAL_MS` defaults to 250 and accepts 10–60,000. Optional `ROUTER_STOP`
names a file, resolved from the working directory; its presence stops polling
after startup recovery. Each committed poll logs its input count. On normal exit,
stdout contains a JSON report of cursors, output metadata and filtered count.

Tests can inject `ROUTER_FAULT` at `planned`, `partial-N`, `file-N`, `state`, or
`cleared`. `N` is the zero-based position of an affected filename in sorted order.
`ROUTER_PAUSE` pauses at the same checkpoints for up to 30 seconds and prints
`PAUSED <label>`, allowing the checks to kill a process during a real partial write.

Acceptance uses an independent expected-record oracle, exercises LF/CRLF,
Unicode, filtering, fanout, incomplete tails, bounded batches and renamed inputs,
and compares Python with native Rust. It includes 23 publication/recovery checks,
23 invalid-input/file cases, 25 invalid configurations and 26 corrupt controls.
Boundary checks reach 256 input lines per poll, 64 MiB inputs, 64 KiB configuration,
32 retired identities, 256 scanned entries and 128-byte filters. Aliased files,
competing writers, real daemon stop behavior and interrupted control publication
are covered. All 32 output segments are exercised under a 256 MiB address-space
limit. Eight Python/Rust writer→recovery→reader combinations consume actual saved
plans, partial output files and input cursors across process restarts.

## 085: Job deadline inspector

[Five Python modules](085_deadline_inspector/main.py), 386 substantive lines,
inspect expected jobs and actual completion events at an explicit observation
time. The complete project compiles into a native Rust executable using the
existing date/time, JSON, enum and filesystem support.

```sh
python tools/corpus.py 085
python tools/check_deadline_inspector.py
mkdir -p build/deadline-demo
cp examples/corpus/085_deadline_inspector/{deadline-job.json,jobs.json,events.json} build/deadline-demo/
DEADLINE_CONFIG=build/deadline-demo/deadline-job.json build/corpus/085/corpus_085
```

The [sample configuration](085_deadline_inspector/deadline-job.json) names a job
list, an event list, an observation timestamp and a new output directory. Paths
are relative to the configuration file; their parent directories must exist.
Each job has an ASCII `id`, a human-readable `label`, a `deadline`, and integral
`grace_seconds`. Each event has `job` and `completed_at` fields. The sample
produces one on-time job, one late job, one missing job and one pending job, and
returns exit status 1 because late/missing results exist.

Timestamp offsets follow the numeric-offset interpretation in
[RFC 3339 §4.2](https://www.rfc-editor.org/rfc/rfc3339.html#section-4.2).
The application accepts Gregorian years 0001–9999, explicit `Z` or numeric offsets,
upper/lowercase `T` and `Z`, and zero to six fractional digits. It rejects leap
seconds, excess fractional precision, invalid calendar dates and UTC conversions
outside the supported years. Numeric offsets range through ±23:59. `-00:00` is
accepted as a known UTC instant with unknown local offset, following
[§4.3](https://www.rfc-editor.org/rfc/rfc3339.html#section-4.3); the normalized export
uses UTC `+00:00`. These are timestamp offsets, not named timezone or DST rules.

The report uses the earliest distinct completion at or before `observed_at`.
Input order does not affect that choice. Repeated events for the same job and
instant are counted as duplicates, including timestamps written with equivalent
offsets. Different completion times remain distinct: a later retry does not make
an earlier successful completion late. Events after the observation time are
reported as future events and excluded from the current classification. They
remain in the exported inputs for a later inspection. Unknown job IDs, duplicate
job definitions and malformed records reject the whole input with exit status 2.

| Status | Rule |
| --- | --- |
| `on_time` | Earliest observed completion is at or before `deadline + grace_seconds` |
| `late` | Earliest observed completion is after that cutoff |
| `missing` | No observed completion, and observation time is at or after the cutoff |
| `pending` | No observed completion, and observation time is before the cutoff |

A completion exactly at the cutoff is on time. An unfinished job exactly at the
cutoff is missing with zero lateness. `lateness_us` is the exact positive distance
from cutoff to completion for late jobs, or from cutoff to observation time for
missing jobs. It is zero for on-time and pending jobs. Computation uses integral
Gregorian days, seconds and microseconds, with no floating-point epoch conversion.
Grace periods are 0–604,800 seconds, inclusive; a cutoff outside years 0001–9999
is rejected. The observation time is supplied explicitly, making reports replayable.

The bundle contains:

- `report.json`: classifications, normalized UTC times, exact lateness, counts
  of observed/future/duplicate events, and status totals.
- `jobs.csv`: the same per-job values with quoted fields, escaped quotes and CRLF
  record endings; labels can contain commas and newlines.
- `report.txt`: a readable explanation for each job, in input job order.
- `jobs.json`, `events.json`, and `deadline-job.json`: normalized replay inputs,
  preserving completion events and duplicates. The replay config uses a new
  `replayed` output directory beside these files.
- `manifest.json`: each other bundle file's byte count and SHA-256 digest.

Exit status 0 means the report contains only on-time/pending jobs. Status 1 means
the report was produced successfully and includes late or missing jobs. Status 2
means invalid input or an I/O/publication failure. On normal publication, stdout
contains the JSON report. Errors are logged on stderr; timestamp errors include
the source field, such as `events[2].completed_at`.

Inputs are bounded snapshots of unaliased regular files. Leaf symlinks, hard-link
aliases, shared configuration/job/event paths and changes during reading or
before publication are rejected. The application creates a private staging
directory, syncs every file, rechecks the inputs, then publishes the entire bundle
with a no-replace directory rename. Existing output files, directories and dangling
symlinks are preserved. Concurrent processes targeting the same directory produce
one winning publication; the others fail without changing it. This ownership
contract assumes no hostile directory replacement or noncooperative edits after
the final input check.

If killed before publication, the target is absent and a complete staging directory
may remain under `.deadline-*`. A new run uses a fresh staging directory and leaves
that orphan intact. If interrupted after publication, the complete bundle remains;
a later attempt refuses to replace it. Therefore an error after publication can
coexist with a valid report. Inspect the target before rerunning with a new output.

| Bound | Maximum |
| --- | --- |
| Job definitions / completion events | 256 / 4,096 |
| Configuration / jobs / events files | 64 KiB / 256 KiB / 512 KiB |
| Job ID | 32 ASCII characters, starting with a letter |
| Label | 256 UTF-8 bytes, nonempty and without NUL |
| Generated bundle before manifest | 4 MiB |

For failure tests, `DEADLINE_FAULT=staged` fails before publication and
`DEADLINE_FAULT=published` fails after the target is durable. `DEADLINE_PAUSE`
uses the same checkpoints, prints `PAUSED <label>` and waits up to 30 seconds.
Optional `DEADLINE_RELEASE` names a file whose appearance resumes the paused run,
allowing deterministic tests of input changes during staging.

Acceptance compares 61 explicit jobs and 512 generated jobs with an independent
Python `datetime`/`timedelta` oracle. Cases cover one-microsecond boundaries,
leap years and century exceptions, pre-epoch dates, years 0001/9999, equivalent
positive/negative offsets, duplicate events and future-event activation.
It rejects 108 invalid timestamps and 45 invalid documents. Boundary tests reach
all three byte limits, 256 jobs, 4,096 events, 32-character IDs and 256-byte labels
under a 256 MiB address-space limit, plus 4,096 distinct events for one job.
Seventeen failure/alias checks include process kills, live input changes, actual
permission failures and preservation of existing targets. Eight simultaneous
publishers produce exactly one complete bundle. Eight Python/Rust producer→replay→
inspector combinations consume the exported inputs, reproduce identical reports
and then activate a future completion at its exact microsecond.

## 086: cross-timezone appointment converter

The six Python modules in [`086_timezone_converter`](086_timezone_converter/main.py)
load appointments, resolve named zones, apply explicit policies and export equivalent
schedules. All six modules transpile into one standalone Rust executable. The
shared runtime supplies only generic TZif resolution and projection primitives;
validation, policies, report formatting, snapshots and publication remain Python.

```bash
python tools/corpus.py 086
python tools/check_timezone_converter.py
TIMEZONE_CONFIG="$PWD/examples/corpus/086_timezone_converter/timezone-job.json" \
  build/corpus/086/corpus_086
```

The sample reads `/usr/share/zoneinfo` and writes a new `converted` directory beside
its configuration. It includes an ordinary meeting, both choices for a repeated
New York autumn time, a shifted spring appointment and a spring appointment left
for review. Its targets are UTC, Berlin and Yekaterinburg. Expected exit status is 1
because the review appointment remains rejected. Change `output` to a fresh path
to run again; existing reports are preserved.

The JSON configuration requires `version: 1`, `tzdata`, `targets`, `appointments`
and `output`. Paths are relative to the configuration file, and parents must exist.
`tzdata` is either a directory containing named TZif files or an exported
`zones.json` object mapping exactly the requested zone names to base64 TZif bytes.
Each appointment requires `id`, `label`, `local`, `zone`, `ambiguity` and `gap`.
Local timestamps use `YYYY-MM-DDTHH:MM:SS` with an optional 1–6-digit fraction,
uppercase `T` and no offset. UTC and local dates must stay in years 0001–9999.

| Condition | Policies |
| --- | --- |
| Unique local time | Use its one UTC instant |
| Fold: the clock repeats a local time | `reject`, `earlier`, or `later` UTC instant |
| Gap: the clock skips a local time | `reject`, `shift_backward`, or `shift_forward` by the offset change |

A New York skipped `02:30` can shift to `01:30` or `03:30`. Lord Howe's half-hour
change shifts `02:15` to `01:45` or `02:45`. Apia's skipped day shifts to the previous
or following day. These choices preserve the position within the skipped interval;
they do not clamp every appointment to the transition boundary. Repeated times
retain both candidates, and rejected times retain their alternatives for review.

`report.json` preserves the original appointments and policies, normalized
resolution, selected UTC/local time, destination times, exact integral offsets,
abbreviations, DST flags and counts. It records SHA-256 for every TZif file.
`report.txt` gives a readable schedule. `schedule.csv` includes quoted labels,
CRLF records and a row for each destination or unresolved appointment. Invalid
calendar timestamps and projection overflows become `invalid` rows; invalid
configuration fields, policies, missing zones or malformed TZif data reject the
whole job before publication.

The bundle also contains `timezone-job.json`, `zones.json` and `manifest.json`.
The first two replay the original appointments with the exact rules used in the
report, writing to a fresh `replayed` directory. The manifest records each other
file's size and SHA-256. Replay does not read the original timezone directory.
TZif itself has no database release identifier, so the report identifies its
actual bytes instead of inferring a version. The tested system database is 2026c;
future reports can intentionally use newer rules by loading newer input files.

Exit 0 means every appointment converted. Exit 1 means publication succeeded
with rejected or invalid appointments. Exit 2 means invalid configuration, I/O
failure or publication failure. A successful publication prints JSON to stdout;
process errors are logged to stderr.

Zone names use nonempty ASCII letter/digit/underscore/plus/minus components
separated by `/`; dots, empty components and absolute paths are rejected. Directory
mode resolves aliases, requires targets to stay inside the canonical timezone
root, and snapshots regular files. Read-only hard links are supported. Configuration
and bundle leaf symlinks are rejected. The exact file metadata is checked again
before publication; directory symlinks are resolved at load time. This snapshot
contract assumes no hostile path replacement or noncooperative edits after the
final check.

Publication uses a private `.timezone-*` directory, synced files, an input recheck,
a no-replace rename and a parent-directory sync. Competing publishers produce one
winner. A process killed before publication can leave an orphan staging directory;
a new run leaves that orphan untouched. A failure after publication can coexist
with a complete report. `TIMEZONE_FAULT=staged|published` and
`TIMEZONE_PAUSE=staged|published` expose those test checkpoints. A pause prints
`PAUSED <label>` and waits up to 30 seconds; an optional `TIMEZONE_RELEASE` file
resumes it.

| Bound | Maximum |
| --- | --- |
| Appointments / targets / distinct zones | 256 / 8 / 16 |
| Configuration / base64 rule bundle | 256 KiB / 1.5 MiB |
| Each TZif file | 64 KiB |
| Zone name / local timestamp | 128 ASCII characters / 64 UTF-8 bytes |
| Appointment ID / label | 32 ASCII characters starting with a letter / 256 UTF-8 bytes |
| Generated bundle before manifest | 4 MiB |

Rules follow the [shared TZif profile](../../doc/service-subset.md#named-timezones-from-explicit-tzif-data),
including versions 1–3, POSIX time without leap seconds, 3–7-character abbreviations
and future transitions from footer rules. Python and Rust use the same explicit
bytes. The reference oracle independently uses Python `zoneinfo`; its results are
compared with native execution with all Python paths disabled.

Acceptance covers 37 explicit appointments, 48 microsecond transition-boundary
cases, 512 generated appointments, 19 invalid local timestamp shapes and three
year-range overflows. It rejects 47 invalid configurations, rule files and bundles.
Capacity checks reach 256 appointments, eight targets, 16 zones, both input byte
limits, 32-character IDs and 256-byte labels under a 256 MiB address-space limit;
a separate valid TZif fixture reaches exactly 64 KiB. Fifteen failure/alias checks
include real process kills, changed configuration/rule/bundle inputs, allowed zone
aliases, escaping links and actual permission failures. Eight competing writers
produce one complete report. Eight Python/Rust writer→replayer→reader combinations
consume exported TZif bytes after removal of the original directory, reproduce
identical bundles and then change policies and destination order.

## 087: debounced directory watcher

[Seven Python modules](087_directory_watcher/main.py), 465 substantive lines,
compile into one standalone Rust executable. The application scans a directory,
collapses repeated observed edits into quiet-window events, preserves observed
renames/deletions, and resumes its pending events and retained journal after restart.
It uses existing filesystem, hashing, timer, JSON and file-locking primitives;
this application requires no new shared runtime code.

```bash
python tools/corpus.py 087
python tools/check_directory_watcher.py
mkdir -p build/watcher-demo/observed
cp examples/corpus/087_directory_watcher/watch-job.json build/watcher-demo/
cp examples/corpus/087_directory_watcher/observed/welcome.txt build/watcher-demo/observed/
WATCH_CONFIG="$PWD/build/watcher-demo/watch-job.json" \
  WATCH_POLLS=0 WATCH_STOP="$PWD/build/watcher-demo/stop" \
  build/corpus/087/corpus_087
```

Edit, rename or delete files under `build/watcher-demo/observed` while the command
runs. Create `build/watcher-demo/stop` from another terminal to stop it. Remove that
stop file before restarting. Pending events remain in the checkpoint when stopped;
they are not forced out early. Without `WATCH_POLLS=0`, the default command takes
one observation, saves it and exits.

The configuration requires `version: 1`, `root`, `output`, `debounce_ms` and
`retain`. Paths are relative to the configuration file. `root` must exist, and
`output` must have an existing parent. The output directory and its sibling
`.lock` file must be outside the observed tree and must not enclose it or overlap
the configuration. State binds the canonical root path/identity and the debounce
and retention settings. Change these by starting a fresh output directory; they
cannot silently reinterpret an existing journal.

Each observation hashes regular files and records type, identity, permissions,
size and modification time. Symlinks are leaf entries with recorded targets;
links are never followed while scanning. A same-size edit is detected even if
its mtime was restored, because the content hash changes. Directory size, link
count and mtime are omitted from event comparisons to avoid redundant parent
modifications when children change. Directory permission changes remain visible.
The configured root itself is an anchor rather than a reported entry.

The scanner bounds entries, depth, file sizes and total bytes. It rechecks metadata
for the root and every observed entry after reading the tree, excluding access
time. If a scan fails or overlaps a change, it retries up to three times with
short waits. An unsuccessful observation does not advance the saved snapshot.
A file edit after a completed scan belongs to the next observation, even if it
occurs while the current checkpoint is being published.

| Observed condition | Journal behavior |
| --- | --- |
| New path | Queue `created`; subsequent edits update its final image and quiet deadline |
| Changed path | Queue `modified`; repeated edits retain the first before-image and latest after-image |
| Quiet interval reached | Emit the pending event at `last_ms + debounce_ms <= clock_ms` |
| Rename or deletion | First emit pending changes for affected paths, then emit the lifecycle event immediately |
| Replacement at the same path | Debounce a modification with the old and new identity/content images |
| Clock rollback | Clamp to the last durable observation time; never move event times backward |

A new edit first observed exactly at the quiet deadline starts a new pending event
after the prior one is emitted. An observed creation followed by an observed
deletion remains two events, even within one quiet window. Rename replacement
preserves the overwritten destination's deletion. Rename cycles and moves with
simultaneous content edits retain before/after images. Moving a directory reports
its path and each observed descendant path separately.

Rename inference uses unique matching device/inode/type identities in successive
snapshots. Regular-file identities must have one link on both sides. Ambiguous
hardlinks produce deletion/creation events instead of an inferred rename. Polling
cannot observe operations that happen entirely between scans, distinguish every
instance of inode reuse, or reconstruct the syscall order of a rename cycle.
Events describe the observed net movement in deterministic path order.

`output/state.json` is the authoritative, checksummed checkpoint. It contains the
snapshot, pending events, logical clock, next event ID and retained journal.
Every event records `id`, `kind`, `path`, `previous_path`, `before`, `after`,
`first_ms`, `last_ms` and `emitted_ms`. Pending events use ID/emission time zero;
IDs are assigned only when events enter the durable journal. Initial files are
queued as creations on the first observation.

After each committed observation, stdout receives one JSON object containing
`clock_ms`, `observed_entries`, the pending count, `first_id`, `next_id` and the
retained `events`. An unchanged observation can repeat retained events; consumers
use IDs to avoid processing them twice. `first_id` exposes retention gaps. A poll
that produces more events than the retention setting can discard the oldest
ones from the same poll. The checkpoint still advances every assigned ID.

An exclusive nonblocking file lock covers the process lifetime. Publication writes
and syncs `control.tmp`, atomically replaces `state.json`, then syncs the directory.
The snapshot, pending map and journal advance together. A process killed before
replacement leaves the previous checkpoint intact; an orphan temporary file is
ignored and safely reused. After replacement, the complete new state remains.
A retry does not assign duplicate IDs to unchanged observations. A failure after
commit can therefore leave valid new state even though the command returns an error.

Startup checks the envelope hash, schema, limits, pending/snapshot consistency,
parent directories, contiguous journal IDs, event times and root/settings binding.
Unknown output files, symlink or hardlink aliases for control files, and a replaced
root are rejected. The state directory is owned by the watcher; cooperating writers
must use its lock. Journal integrity checks are for corruption detection, not an
authentication mechanism for edits made outside that ownership contract.

| Setting or bound | Supported range |
| --- | --- |
| `debounce_ms` / retained events | 0–60,000 / 1–256 |
| Entries below root / relative path depth | 256 / 16 components |
| Relative path / symlink target | 1,024 UTF-8 bytes each |
| Regular file / total bytes read per scan attempt | 1 MiB / 4 MiB |
| Configuration / checkpoint document | 64 KiB / 2 MiB |
| `WATCH_POLLS` | 0 for continuous, otherwise 1–100,000; default 1 |
| `WATCH_INTERVAL_MS` | 10–60,000; default 250 |
| `WATCH_NOW_MS` | Optional explicit 0–9,000,000,000,000,000 observation time; requires one poll |
| Assigned event IDs | 1–999,999,999,999 |

Normal observations use Unix milliseconds, clamped against the persisted clock.
Poll waits use a monotonic clock and check `WATCH_STOP` in short increments, even
when the configured interval is 60 seconds. The stop path must be outside the
observed tree and state directory. An invalid input, failed stable scan or storage
error exits with status 2 and logs on stderr; normal completion/cancellation exits 0.
FIFO, socket, device and other special entries are rejected without reading them.

For deterministic interruption tests, `WATCH_FAULT=scanned|staged|committed`
raises at those checkpoints. `WATCH_PAUSE` uses the same labels, prints
`PAUSED <label>` and waits up to 30 seconds; a `WATCH_RELEASE` file resumes it.
The `scanned` hook runs after reading entries and before their final metadata
validation, allowing tests to force a bounded rescan.

Acceptance compares exact state and reports with an independent filesystem/event
model: 21 explicit debounce observations, 12 rename/alias observations and 161
seeded observations producing 169 events with a 17-event retained journal. It
rejects 24 invalid configurations, 12 invalid process settings and 31 corrupt
states, including documents with recomputed checksums but invalid structure.
Capacity checks reach 256 entries, 4 MiB per scan, the 1 MiB file limit, 16-level
and 1,024-byte paths, 1,024-byte link targets and both control-file byte limits
under a 256 MiB address-space limit. Eight interruption/scan checks, eight rejected
lock contenders and 15 path/permission checks cover actual process kills and I/O
failures. Live tests exercise debounce, cancellation, pending-event restart and
cancellation during a 60-second wait. Eight Python/Rust writer→replayer→reader
combinations copy real checkpoint files and resume them while preserving the
original checkpoint inputs.

## 088: discrete-event scheduler simulator

[Seven Python modules](088_scheduler_simulator/main.py), 414 substantive lines,
compile into one standalone Rust executable. The program simulates arrivals,
FIFO waiting queues, identical workers and job deadlines. Its event calendar uses
`heapq`; workload generation, state transitions, statistics and report publication
are application Python. It requires no new compiler/runtime extension and uses no
Python runtime in the generated executable.

```bash
python tools/corpus.py 088
python tools/check_scheduler_simulator.py
mkdir -p build/scheduler-demo
cp examples/corpus/088_scheduler_simulator/scheduler-job.json build/scheduler-demo/
SCHEDULER_CONFIG="$PWD/build/scheduler-demo/scheduler-job.json" \
  build/corpus/088/corpus_088
```

The sample writes a fresh `build/scheduler-demo/simulation` report directory. Change
`output` to a new path to run again; existing results are never replaced. Paths are
relative to the configuration file, and output parents must already exist. The
configuration requires exactly `version: 1`, `workers`, `queue_capacity`, `workload`
and `output`. Integers are strict JSON integers, excluding booleans and fractions.

An explicit workload is `{"mode":"explicit","jobs":[...]}`. Each job has exactly
`id`, `arrival`, `service` and `deadline`. IDs are unique ASCII identifiers matching
`[A-Za-z][A-Za-z0-9_-]{0,31}`. Input jobs may be out of chronological order; their
original array positions break simultaneous-event ties. All times are integer
simulation ticks. A deadline is absolute and cannot precede arrival.

A generated workload requires `mode: "generated"`, `seed`, `count`, and inclusive
`[minimum,maximum]` ranges named `gap`, `service` and `slack`. The first arrival is
the first sampled gap after tick zero. Each subsequent arrival adds its gap to
the preceding arrival. Each deadline is arrival plus sampled slack. IDs are
`job_1`, `job_2`, and so on. The draw order is gap, service, slack for each job,
including constant-width ranges. The portable generator is Park-Miller
`state = (16807 * state) % 2147483647`; rejection sampling removes modulo bias.
The report records the algorithm version, seed, final state and total draws.
This generator supports reproducible simulation, not security tokens.

At every tick, the scheduler applies these phases:

1. Complete all running jobs finishing now, in original job-index order. Finishing
   exactly at the deadline is `on_time`; finishing later is `late`.
2. Expire queued jobs whose deadline is now, in original job-index order. A queued
   job cannot start at its deadline, even if a worker just became free.
3. Dispatch the existing FIFO queue to idle workers, choosing the lowest worker
   number first. Workers are numbered from zero.
4. Handle new arrivals in original job-index order. Zero-slack jobs immediately
   expire. Other jobs start on an idle worker, join the queue if space remains,
   or become `rejected` when all workers and queue slots are occupied.

Service times are positive. Running work is nonpreemptive and finishes even if
its deadline passes. Queue capacity counts waiting jobs only, so capacity zero
still allows immediate starts. A queued job takes precedence over a simultaneous
new arrival. The simulation drains all jobs to one terminal outcome and never
sleeps or uses wall-clock time. Future deadline entries for already completed
jobs do not extend its final horizon.

Each trace record contains `sequence`, `tick`, `job`, resulting `status`, assigned
`worker`, and counts for `pending`, `queued`, `running` and `terminal`. Those four
counts sum to the total job count after every transition. Jobs retain their input
fields plus final `status`, `started`, `finished` and `worker`. Never-started jobs
use `-1` for start and worker. Expired/rejected jobs have a real finish tick.

Statistics cover the interval from tick zero through the last terminal transition.
`busy_ticks` is the integral of occupied workers; `queue_ticks` is the integral
of waiting jobs, including jobs that expire while queued. Summary ratios store
exact integer `numerator` and `denominator`: worker utilization, mean queue size,
and mean waiting/response time for completed jobs. A zero denominator denotes an
undefined ratio for an empty population or zero-duration simulation. No floating
point rounding affects the simulation or exported statistics.

| Setting or bound | Supported range |
| --- | --- |
| Jobs / workers / queue capacity | 0–512 / 1–32 / 0–512 |
| Explicit arrival / deadline | 0–1,000,000,000 / arrival–2,000,000,000 |
| Service time | 1–1,000,000 |
| Generated gap and deadline slack | 0–1,000,000 |
| Seed | 1–2,147,483,646 |
| Generator draws | At most 65,536, including rejected draws |
| Input JSON / report data before manifest | 256 KiB / 4 MiB |

The immutable output bundle contains `summary.json`, `jobs.json`, `trace.jsonl`,
`report.txt`, `scheduler-job.json`, `resolved-job.json` and `manifest.json`.
`scheduler-job.json` repeats the original workload settings with output `replayed`;
`resolved-job.json` records the exact generated jobs as an explicit workload.
Replaying resolved jobs yields the same trace and outcomes, with generator metadata
set to `none`. The manifest records each other file's byte count and SHA-256.

Publication writes and syncs all files in a unique sibling staging directory,
checks that the input metadata is unchanged, then renames the directory without
replacement and syncs its parent. Competing publishers produce one complete
winner. Input symlinks, hardlinks and non-regular files are rejected; existing
output directories, files and dangling symlinks are preserved. A process killed
before publication can leave an unreferenced staging directory; later runs ignore
it. A failure after publication leaves the complete result intact. Normal
completion exits 0, including simulations with rejected/expired/late jobs; invalid
input or failed publication exits 2 and logs the error on stderr.

`SCHEDULER_FAULT=staged|published` injects a failure at the publication boundaries.
`SCHEDULER_PAUSE` uses the same values, prints `PAUSED <label>` and waits for the
`SCHEDULER_RELEASE` file for up to 30 seconds. These hooks support actual kill and
input-change tests.

Acceptance uses a separate scanning model, without the application's heap, and
independently integrates every emitted trace. It covers 41 explicit workloads,
nine seeded workloads and their identical reruns, ten actual generator-state
vectors, forced rejection sampling, 90 malformed inputs, 512 jobs, 32 workers,
511 simultaneously queued jobs, 1,535 trace records and exact input byte bounds
under a 256 MiB address-space limit. Fifteen publication/alias checks include real
process kills and changed input, plus eight competing publishers. Eight
Python/Rust producer→replayer→resolved-reader combinations consume the actual
exported configuration files and verify identical traces and preserved inputs.

## 089: structured-log redactor

[Seven Python modules](089_log_redactor/main.py), 330 substantive lines, validate
JSONL records, mask selected string fields and export counts. The complete project
transpiles to standalone Rust. Its shared runtime addition is the generic
`json_loads_unique` helper; target traversal, ordered masking, size accounting,
audit aggregation and publication remain Python application code.

```bash
python tools/corpus.py 089
python tools/check_log_redactor.py
mkdir -p build/redactor-demo
cp examples/corpus/089_log_redactor/{redactor-job.json,sample.jsonl} build/redactor-demo/
REDACTOR_CONFIG="$PWD/build/redactor-demo/redactor-job.json" \
  build/corpus/089/corpus_089
```

The sample masks a demonstration token and email addresses in nested fields and
writes a fresh `build/redactor-demo/sanitized` directory. Existing results are
preserved; change `output` to a fresh path before repeating the command. Relative
paths resolve against the configuration file, and parent directories must exist.

The configuration requires exactly `version: 1`, `input`, `output`, `missing`,
`targets` and `rules`. Every target is an array of object keys and nonnegative
array indices. For example, `["context","token"]` selects a nested object value;
`["recipients",0,"email"]` selects an email field in the first array entry.
Empty object keys are valid. Keys containing dots have their literal meaning.
Duplicate targets and ancestor/descendant target pairs are rejected.

Records must be JSON objects. A selected value must be a string. `missing: "skip"`
counts absent keys and out-of-range indices without changing that record;
`missing: "error"` aborts the batch. A wrong container type or non-string selected
value always aborts. Only selected string values change; unselected values and
JSON types are preserved semantically. Output uses canonical JSON formatting,
including the subset's normalized finite binary64 representation.

Each rule requires exactly `kind`, `pattern` and `replacement`. `kind` is `literal`
or `regex`. Rules apply to every present target in their configured order; later
rules see the previous rule's result. Matches are non-overlapping. Replacement
strings are literal, including dollar signs and backslashes. Unicode text is
supported; regex shorthand classes and boundaries have ASCII semantics. Patterns
use the shared Python/Rust regex subset, which excludes extension groups and
backreferences. A regex matching empty input is rejected during configuration;
any zero-width match encountered on actual field text aborts processing.

Both configuration and records reject duplicate decoded object keys, including
escaped spellings of an existing key. They also reject malformed UTF-8, invalid
JSON, unpaired surrogates, integers outside signed 64-bit range, non-finite numbers
and nesting beyond 64 levels. A key may appear in separate sibling objects.
Empty input is valid and produces zero records. LF and CRLF lines and a final
record without a newline are accepted; blank lines are invalid.

Any invalid record aborts publication of the whole batch. The output bundle has
exactly four files: `redacted.jsonl`, `audit.json`, `report.txt` and `manifest.json`.
It contains no raw input, rejected-record quarantine, raw rule configuration or
input-file hashes. The manifest hashes only the other sanitized output files.
Audit entries identify rules and targets by zero-based positions, without
including patterns, replacement strings, field paths or matched substrings.

The audit records total and changed records; present, missing and finally changed
selected fields; match counts; input/output bytes; and per-rule/per-target counts.
A replacement equal to its match contributes matches but no changed fields. Rules
that change a field and then restore its original value contribute per-rule
changes while leaving the final field and record change counts at zero.

| Setting or bound | Supported range |
| --- | --- |
| Records / rules / targets | 0–1,024 / 1–32 / 1–32 |
| Target components / array index | 1–16 / 0–4,095 |
| Target key / pattern / replacement | 128 / 512 / 256 UTF-8 bytes |
| Configuration / input snapshot | 64 KiB / 4 MiB |
| Physical input line, including LF or CRLF | 64 KiB |
| Selected field after each rule | 64 KiB |
| Canonical output record, including LF | 256 KiB |
| Sanitized JSONL output | 4 MiB |
| Cumulative rule matches | 1,000,000 |

Expansion is checked before constructing each field replacement. Record and
cumulative output bounds are checked before appending output. The audit and
manifest are additional bounded metadata outside the 4 MiB JSONL limit.

Input/configuration files must be unaliased regular files. Publication writes and
syncs only sanitized output in a unique sibling staging directory, verifies that
both input snapshots remain unchanged, renames without replacing any existing
output, and syncs the parent. Concurrent publishers produce one complete winner.
A killed process can leave a sanitized staging directory; later runs ignore it.
Failure after the rename leaves the complete result intact.

Successful execution prints the numeric audit as JSON and exits 0. Failures exit 2
and report only one fixed phase message: `Redactor configuration failed`,
`Redactor input processing failed`, or `Redactor publication failed`. Exception
text, data values, patterns and file paths are never copied into diagnostics.
`REDACTOR_FAULT=staged|published` injects publication failures. `REDACTOR_PAUSE`
uses the same labels, prints `PAUSED <label>` and waits up to 30 seconds for the
`REDACTOR_RELEASE` file. These hooks support actual kill and input-change tests.

Acceptance uses an independent `re.ASCII`/literal oracle for transformations and
all counters, and a decimal-based canonical-number oracle. It covers 15 explicit
workloads, 300 generated records, identical reruns, literal replacement
metacharacters, nested arrays/objects, Unicode values, ordered reversals and no-op
rules. It rejects 71 invalid configurations and 26 invalid record/target cases.
Capacity tests reach every documented count/byte limit, including exact 4 MiB
input/output under a 256 MiB address-space limit, and reject one-past-limit cases.
Twenty publication/alias checks include real process kills and changed inputs;
eight competing writers produce one winner. Sensitive fixture strings are absent
from all published files, staged files and diagnostics. Eight Python/Rust
producer→replayer→reader combinations consume actual sanitized files, confirm
idempotence for the fixture rules and mask a newly appended sensitive record.

## 090: checkpointed batch worker

[Six Python modules](090_batch_worker/main.py), 386 substantive lines, process
JSONL jobs in bounded batches. Every module transpiles to Rust; the existing
shared compiler/runtime handles the project without additions. Jobs are pure
text and integer transformations, so uncommitted work may be recomputed after a
crash while durable results contain each job exactly once.

```bash
python tools/corpus.py 090
python tools/check_batch_worker.py
mkdir -p build/batch-demo
cp examples/corpus/090_batch_worker/{batch-job.json,jobs.jsonl} build/batch-demo/
BATCH_CONFIG="$PWD/build/batch-demo/batch-job.json" BATCH_LIMIT=1 \
  build/corpus/090/corpus_090
BATCH_CONFIG="$PWD/build/batch-demo/batch-job.json" \
  build/corpus/090/corpus_090
```

The first command processes two sample jobs and pauses. The second resumes and
writes `build/batch-demo/completed/report.json`. Further runs validate and preserve
the completed state/report. Change `output` to start a new independent run.

Configuration requires exactly `version: 1`, `input`, `output` and `batch_size`.
Paths resolve against the configuration file; parent directories must exist.
The output is an exclusively owned directory. A sibling `.lock` file guards the
whole run with a nonblocking process lock. Input/configuration must be unaliased
regular files outside the output. Control-file symlinks, hard links, special
files, unknown output files and conflicting worker processes are rejected.

Each input line requires exactly `id`, `text` and `values`. IDs are unique ASCII
names matching `[A-Za-z][A-Za-z0-9_-]{0,31}`. Text is a Unicode string and values
are signed integer samples. Every job is validated before any checkpoint is
created. Duplicate JSON keys, booleans/floats in integer fields, malformed UTF-8,
blank lines and unknown fields are errors. Empty input, LF/CRLF and a final line
without LF are supported.

A job normalizes text with `NFC(NFC(text).casefold())`, splits words on Python
whitespace, and returns the normalized text, character/UTF-8 byte counts, word
count and exact word frequencies. Punctuation remains part of a word. Numeric
results contain sample count, exact sum, minimum and maximum; empty extrema are
null. Sum/count also represents an exact mean without floating-point rounding.
The aggregate report sums jobs, characters, bytes, words, samples and values.
All permitted numeric sums fit signed 64-bit integers.

The authoritative `state.json` is one checksummed envelope containing input
binding, completed-prefix count, ordered results and aggregate totals. State and
results are written/synced together to `control.tmp`, atomically replaced and the
output directory synced before a progress event is printed. Input/configuration
metadata are rechecked immediately before every commit. A process kill before
replacement leaves the old prefix intact; a kill after replacement retains the
new prefix. Existing uncommitted staging is ignored and overwritten on resume.

The binding includes the exact input-byte SHA-256, byte count, job count and
transformation version. It excludes batch size and absolute paths. Therefore an
actual checkpoint can move to another directory/runtime, and batch size can
change on resume. Input changes, including whitespace-only changes, are rejected.
Saved-state validation checks schema, binding, cursor/result length, IDs/order,
text counts/frequencies, numeric bounds and aggregate consistency. The checksum
detects accidental corruption; it does not authenticate externally edited state.

After the final checkpoint, `report.json` is derived from durable state and
atomically published. Report publication can be retried independently after a
crash. A report without a complete matching checkpoint is rejected. Final state
and report bytes are independent of batch size, execution engine and interruption
position. Completed reruns preserve both files and remove any owned stale staging.

| Bound | Limit |
| --- | --- |
| Jobs / batch size | 0–256 / 1–64 |
| Job ID / source text | 32 ASCII characters / 2,048 UTF-8 bytes |
| Samples per job / sample magnitude | 128 / 1,000,000,000 |
| Configuration / complete input | 64 KiB / 1 MiB |
| Job line, excluding LF but including any CR | 16 KiB |
| Normalized text / canonical result | 8 KiB / 32 KiB |
| Checkpoint / final report | 8 MiB each |

`BATCH_LIMIT=1..256` pauses after that many committed batches; `0` runs to
completion. `BATCH_STOP` names a separate regular stop file checked between
batches. Cancellation retains the last committed prefix and returns normally;
completion takes precedence when all jobs are already durable. Stop-file removal
allows resume. Status lines contain `status`, `completed`, `total` and `summary`.
Normal phases are `progress`, `paused`, `cancelled` and `complete`; failures exit 2.
Consumers can deduplicate repeated progress observations by input binding and
completed prefix.

For interruption tests, `BATCH_FAULT` and `BATCH_PAUSE` accept `phase:completed`
labels: `initial:0`, `computed:N`, `staged:N`, `committed:N`, `report-staged:N` and
`report-published:N`. A pause emits its label and waits up to 30 seconds for the
`BATCH_RELEASE` file. The checkpoint-write phases also apply to the initial empty
checkpoint. These hooks leave the ordinary transaction order unchanged.

Acceptance compares against an independent normalization/Counter/integer oracle.
Four workloads, including 64 generated jobs, run with batch sizes 1, 2, 7 and 64.
Both engines recover from actual kills and injected failures at all 14 tested
boundaries, with identical final bytes. Checks cover cancellation, limited runs,
30 invalid configurations, 33 invalid jobs/input documents, 5 invalid settings,
26 rechecksummed invalid states, 6 malformed states and 5 binding/report failures.
There are 22 alias/ownership cases, two mid-commit input-change guards, eight
rejected competing workers and a recovered real permission failure. Capacity
checks exercise 256 jobs, maximum text/sample bounds under a 256 MiB address-space
limit, exact input/configuration/line/checkpoint bounds and oversized rejection.
Eight Python/Rust writer→replayer→reader combinations consume actual killed-worker
checkpoints, discard uncommitted staging, change batch sizes and produce identical
state/report files while preserving the earlier checkpoint copies.

## 091: process-based test runner

[Six Python modules](091_process_runner/main.py), 392 substantive lines, validate
command suites, run each test, compare exit codes/output, and publish a complete
report with raw binary captures. Every application module transpiles to Rust.
The generic shared `process_run` API adds structured outcomes and retained partial
captures to the existing native pipeline engine; test policy stays in Python.

```bash
python tools/corpus.py 091
python tools/check_process_runner.py
mkdir -p build/runner-demo
cp examples/corpus/091_process_runner/runner-job.json build/runner-demo/
RUNNER_CONFIG="$PWD/build/runner-demo/runner-job.json" \
  build/corpus/091/corpus_091
```

The sample runs `/usr/bin/printf`, `/usr/bin/printenv` and `/usr/bin/false` with
explicit environments. All three pass their expectations, including the expected
nonzero exit. Results appear in `build/runner-demo/test-results`. Choose a fresh
`output` for another run; an existing output is rejected before any command starts.
The native runner and these sample children need no Python runtime.

Configuration requires exactly `version: 1`, `output`, `environment` and `tests`.
Each test requires `id`, `argv`, `cwd`, `environment`, `stdin`, `timeout_ms`,
`max_output` and `expect`. IDs are unique ASCII names matching
`[A-Za-z][A-Za-z0-9_-]{0,31}`. Executable and working-directory paths resolve
against the configuration directory. The executable may be missing, which becomes
a reported `spawn_error`; its parent directory must resolve. Cwd must already be
a directory. Arguments are passed directly without shell expansion.

The suite environment is copied and overlaid with the test environment. This
merged map replaces the parent's environment, including PATH and HOME. Names are
ASCII identifiers; values may contain Unicode but not NUL. `stdin` has `encoding`
(`utf8` or canonical padded `base64`) and `data`. The entire suite, every input and
every expectation are validated before the first command starts. Unknown fields,
duplicate JSON keys, invalid types, invalid regexes and exceeded budgets reject
the suite without launching its commands.

`expect` requires `exit_code`, `stdout` and `stderr`. A negative expected exit code
matches a child terminated by that signal. Each stream expectation has `mode` and
`value`: `ignore` with an empty value; `utf8` for exact encoded text; `base64` for
exact bytes; `contains` for an encoded-text byte substring; or `regex` for a full
UTF-8 text match using the shared Python/Rust ASCII-class regex subset. Invalid
UTF-8 fails a regex assertion. Empty strings and empty captures are valid.

Tests run sequentially and continue after mismatches, nonzero exits, spawn errors,
timeouts and output limits. A test passes only when it exits and all expectations
match. Expected nonzero exits can therefore pass. Results distinguish `exited`,
`timeout`, `output_limit`, `spawn_error`, `interrupted` and unexpected
`runtime_error`. `failed_checks` identifies the execution outcome and individual
exit/stdout/stderr mismatches. The shared process API uses nonblocking pipes,
an absolute deadline and process groups, including cleanup of ordinary descendants
and descendants retaining pipe ends after their leader exits. Direct children are
reaped. Deliberate process-group escapes are outside this foreground contract.

Timeout/output-limit/interrupt results retain the prefixes captured before
cancellation. The combined stdout/stderr budget is exact; observing an extra byte
reports `output_limit` and retains the full allowed prefix. The split of a shared
budget between concurrently ready streams may vary. SIGINT/SIGTERM received while
running a command cleans that command's group, records its partial output, skips
the remaining tests, and publishes an interrupted report.

The output bundle has `report.json`, `report.txt`, `manifest.json`, and two raw
files (`<id>.stdout`, `<id>.stderr`) per executed test. Skipped tests have no capture
files. Stream metadata includes byte count, SHA-256 and a preview of at most 512
Unicode characters when the complete capture is valid UTF-8. Raw files preserve
all captured bytes. Report records retain original argv/cwd spellings, outcomes
and assertion failures; environment values are not copied into reports. Captured
program output can of course contain values printed by the command itself.
The manifest independently describes every report/capture file's size and digest.

Publication writes/syncs a unique sibling staging directory, checks that the
configuration snapshot is unchanged, then atomically renames without replacing
an existing output. Command side effects are not rolled back by a later report
publication failure. A kill during staging may leave an orphan staging directory;
a later run ignores it. A failure after publication leaves the complete bundle.
Concurrent publishers have exactly one winner.

| Bound | Limit |
| --- | --- |
| Tests / ID | 0–32 / 32 ASCII characters |
| Configuration | 2 MiB |
| Arguments / resolved argv bytes with terminators | 1–128 / 64 KiB per command |
| Merged environment entries / key / total bytes | 256 / 128 characters / 64 KiB |
| Cwd | 4,096 UTF-8 bytes |
| Stdin per command and summed across the suite | 1 MiB |
| Timeout per command / sum of timeouts | 1–60,000 ms / 120,000 ms |
| Capture per command / sum of capture budgets | 0–1 MiB / 8 MiB |
| Output expectation / regex | 64 KiB / 4 KiB UTF-8 bytes |

Successful tests and their outcomes are printed as one JSON event each, followed
by the summary after publication. Exit status is 0 for a passing suite, 1 for
failed tests, 2 for validation/publication failure, and 130/143 for a reported
SIGINT/SIGTERM interruption. An empty suite publishes a passing zero-test report.
`RUNNER_FAULT=staged|published` injects publication failure. `RUNNER_PAUSE` uses the
same labels and waits up to 30 seconds for `RUNNER_RELEASE`, supporting real kill
and changed-input tests.

Checks use independently compiled native children and an independent report/
assertion oracle. An 18-test mixed suite has seven expected failures and verifies
continued execution, binary captures, environment isolation, cwd, literal argv,
regex matching, signal exits, timeout and output-limit cleanup. Another 64 generated
binary jobs run across two suites. Both engines verify parent-signal cancellation,
skipped remaining commands, publication faults/kills, changed input, alias guards,
permission recovery and competing publishers. Capacity checks include 32 tests,
8 MiB capture under a 256 MiB address-space limit, 1 MiB stdin/capture, 128 argv
entries, 120,000 ms configured budget, exact 2 MiB configuration and oversize
rejection. Mixed-runtime checks pass actual failed-suite reports and raw captures
through eight Python/Rust writer→replayer→reader combinations.

## 092: incremental build executor

[Five Python modules](092_build_executor/main.py), 455 substantive lines, validate
a dependency manifest, fingerprint inputs, run serial native commands, and persist
successful build results. All graph, freshness, cache, and reporting policy is
Python source transpiled into Rust. This application uses the existing shared
process and filesystem APIs without compiler/runtime changes.

```bash
python tools/corpus.py 092
python tools/check_build_executor.py
mkdir -p build/executor-demo/artifacts
cp examples/corpus/092_build_executor/build-job.json build/executor-demo/
cp examples/corpus/092_build_executor/source.txt build/executor-demo/
BUILD_CONFIG="$PWD/build/executor-demo/build-job.json" \
  build/corpus/092/corpus_092
# Repeat unchanged to see both targets cached; edit source.txt to rebuild both.
```

The sample invokes `/usr/bin/cp` twice to demonstrate a source→artifact→artifact
chain. Outputs appear under `artifacts`, with cache/report files in `.build-state`.
Both the executable and its sample child commands run without Python.

The configuration requires exactly `version: 1`, `state`, and `targets`. Each target
requires `id`, `inputs`, `dependencies`, `output`, `argv`, `environment`,
`timeout_ms`, and `max_output`. IDs and input binding names match
`[A-Za-z][A-Za-z0-9_-]{0,31}`. Inputs map binding names to relative file paths;
dependencies list target IDs. All dependencies must exist and form an acyclic
graph. Execution repeatedly selects the lexicographically first ready target.
Manifest row order does not affect this order or cache identity.

Paths resolve against the configuration's directory. Data/state paths must remain
inside that workspace, and their parents must already exist. Empty components,
`.` and `..` are rejected. Inputs and outputs must be regular files without
symlinks or hard-link aliases; an output may initially be absent. Outputs must be
unique, must not overlap inputs, and must not overlap the owned state directory or
its sibling lock. Output and state directories must share a filesystem.

Arguments are literal strings except for whole arguments `{input:name}`,
`{dependency:id}`, and `{output}`. The first two substitute absolute paths to
declared inputs or successful dependency outputs. `{output}` substitutes a fresh
staging path in the state directory and is required. The command must create that
one output. The executable resolves against the workspace; PATH lookup and shell
expansion are not performed. `environment` completely replaces the child's
inherited environment. The executor is a build tool, not a command sandbox:
commands must be trusted to write only their staging output and intended side
effects. Declare every relevant source/tool as an input; changes to undeclared
files or external tools are not part of the freshness model.

Freshness always hashes file contents, including when size and mtime are unchanged.
File fingerprints contain byte length, mode, and SHA-256. A recipe hash covers the
original target configuration, including arguments, environment and limits. Each
cache signature covers the recipe, named direct input fingerprints, and dependency
signatures/output fingerprints. A source or recipe change propagates through
consumers. Recreating a missing or damaged output with identical content and
signature leaves otherwise valid consumers cached. Touching only mtime also leaves
the cache valid. Cached outputs are not rewritten. Removed target entries are
pruned; their old output files are retained.

Reports classify targets as `cached`, `rebuilt`, `failed`, or `blocked`. Rebuild
reasons distinguish `no_cache`, `changed_recipe`, `changed_inputs`,
`changed_dependencies`, `missing_output`, and `changed_output`. Failures preserve
structured command outcomes, bounded stdout/stderr as base64, and an error message.
A failing target blocks its consumers while independent targets continue. An
interrupt during a command stops further execution; previous entries for skipped
targets remain available for freshness checking on the next run.

An exclusive nonblocking sibling lock covers the complete build. Before launching
a command, its old cache entry is removed and the new cache is durably committed.
A successful output is scanned and synced, checked against input/configuration
metadata guards, and atomically replaces the published artifact. Only then is its
successful cache entry committed. Failures before replacement preserve the previous
artifact. A crash between artifact replacement and cache commit causes a rebuild
on resume. Dependency failures remove dependent cache entries. The executor uses
the shared process-group cleanup for timeouts, output limits and SIGINT/SIGTERM;
deliberate group escapes and an uncatchable parent kill during child execution are
outside that cleanup guarantee.

The checksummed `cache.json` is structurally validated on every run. Checksums
detect corruption, not authenticated tampering. Owned state contains only
`cache.json`, `report.json`, `control.tmp`, and `artifact.tmp`; unknown files and
aliased control files are rejected. Incomplete regular staging files are safely
reused or removed. An invalid nonempty staging directory is not recursively
deleted and requires manual cleanup. Configuration/input/output mutation during
publication is detected with metadata guards; these checks assume a cooperative
workspace and do not provide isolation from hostile concurrent filesystem changes.

The latest completed run's report is atomically replaced after the final cache
commit. It includes the cache digest, every target record, and counts. A crash can
leave an older report; its digest can be compared with the cache, and rerunning
produces a fresh report. This is current-run reporting rather than replay of a
partially published historical report. JSON target events and the final summary
also appear on stdout. Exit codes are 0 for success, 1 for failed/blocked targets,
2 for validation/control/publication errors, and 128 plus a reported interrupt
signal. An empty graph succeeds with zero counts.

| Bound | Limit |
| --- | --- |
| Targets / direct inputs per target / dependencies | 16 / 8 / 16 (at most 15 in a valid 16-target graph) |
| ID or input binding | 32 ASCII characters |
| Configuration / cache or report | 256 KiB / 2 MiB |
| Each source or accepted artifact | 4 MiB, hashed in 64 KiB chunks |
| Relative path | 1,024 UTF-8 bytes, 16 components |
| Arguments / argument size | 64 / 1,024 UTF-8 bytes |
| Resolved argv including terminators | 64 KiB per command |
| Environment entries / key / total including terminators | 32 / 128 ASCII characters / 16 KiB |
| Per-command timeout / sum of configured timeouts | 1–60,000 ms / 120,000 ms |
| Combined stdout/stderr capture | 0–64 KiB per command |

`BUILD_FAULT` injects failure and `BUILD_PAUSE` waits for `BUILD_RELEASE` (up to
30 seconds). Labels include `produced:ID`, `published:ID`, and `staged:LABEL` or
`committed:LABEL`, where LABEL is `initial`, `invalidate:ID`, `success:ID`,
`blocked:ID`, `final`, or `report`. These hooks support repeatable interruption and
concurrent-edit checks.

Acceptance compares actual child invocation logs, output bytes, cache entries,
reasons, and reports against an independent content/dependency model. Fourteen
edit sequences cover branch invalidation, same-size/restored-mtime edits, mode and
recipe changes, missing/corrupt output, row reordering and target removal/readdition.
Nine command/output failure modes preserve old artifacts and invalidate failed
and blocked entries. Tests kill real processes at 12 publication boundaries, check
parent-signal descendant cleanup, changed inputs/configuration/staging, competing
builders, aliases, invalid manifests/caches and permission recovery. Capacity
checks exercise 16 targets, 15-way fan-in, 8 inputs, 64 arguments, a full 16 KiB
environment, 4 MiB input/artifact under a 256 MiB address-space limit, and exact
configuration/cache byte limits. Eight Python/Rust writer→replayer→reader
combinations copy real cache and artifact files, reuse all unchanged targets with
zero child invocations, then rebuild exactly the affected branch after an edit.

## 093: local process supervisor

[Five Python modules](093_process_supervisor/main.py), 384 substantive lines, start
native services concurrently, capture their logs, apply bounded restart backoff,
publish live status, and shut down all owned process groups. The complete
application transpiles to standalone Rust. A generic shared `ProcessPool` supplies
nonblocking child ownership and pipe operations; service policy stays in Python.

```bash
python tools/corpus.py 093
python tools/check_process_supervisor.py
mkdir -p build/supervisor-demo
cp examples/corpus/093_process_supervisor/supervisor-job.json build/supervisor-demo/
SUPERVISOR_CONFIG="$PWD/build/supervisor-demo/supervisor-job.json" \
  build/corpus/093/corpus_093
```

The sample runs `/usr/bin/printf` alongside `/usr/bin/sleep`, retains the greeting,
and stops the sleeper at a two-second deadline. Inspect
`build/supervisor-demo/supervisor-session/status.json` and the two raw log files
per service. Choose a fresh `state` name for another run. An existing session is
rejected; prior reports and logs are never silently overwritten. The supervisor
and its sample commands do not require Python at runtime.

Configuration requires exactly `version: 1`, `state`, `stop`, `run_ms`, `grace_ms`,
and `services`. State and stop are sibling names in the configuration directory,
matching `[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}`. They must not collide with each other,
the configuration, or the sibling `state.lock`. Existing configuration, lock and
stop files must be regular files without symlink or hard-link aliases. An
exclusive nonblocking lock is held for the complete session.

Each service requires `id`, `argv`, `cwd`, `environment`, `restarts`, `backoff_ms`,
`max_backoff_ms`, and `log_bytes`. IDs are unique names matching
`[A-Za-z][A-Za-z0-9_-]{0,31}`. Executable/cwd paths resolve against the configuration
directory; cwd must exist, and executable parents must resolve. A missing
executable becomes an attempt with `spawn_error`. Arguments are passed literally,
without shell expansion or PATH search. The environment completely replaces the
parent's environment; stdin is `/dev/null`. Every service definition is validated
before any service is launched.

Services start in ID order and run concurrently. Successful exits remain `exited`.
Nonzero exits, signal exits and spawn failures consume attempts and may restart.
`restarts` counts additional attempts after the first. After failed attempt N, the
delay is `min(backoff_ms * 2**(N-1), max_backoff_ms)`, measured from observed failure
using the monotonic clock. Exhaustion leaves the service `failed`; independent
services continue. An empty service list completes immediately.

The loop polls each live child once per cycle, reading at most 8 KiB from each
stream, and sleeps 10 ms between cycles. Each stream retains its first `log_bytes`
bytes across all attempts. Further bytes are drained and counted as discarded,
so a full log does not block the child or prevent another service from restarting.
Raw `.stdout` and `.stderr` files preserve NUL and invalid UTF-8. There is no
implied ordering between the two streams. No retry log is silently reset.

`status.json` is an atomic snapshot, refreshed at roughly 100 ms intervals and at
phase transitions. It contains phase/reason, elapsed time, received signal, and
sorted service records: state, PID, attempt count, next scheduled time, most recent
exit/error, attempt history and per-stream retained/seen/discarded counts. Internal
pool handles are not published. The history records each attempt's start/end time,
exit kind/code and scheduled retry delay. Final snapshots add log SHA-256 digests
after syncing the files. Measurements vary between runs; status transfer checks
preserve the actual bytes rather than expecting identical timestamps.

Creating the configured stop file, receiving SIGINT/SIGTERM, or reaching `run_ms`
starts shutdown. Pending backoff is cancelled. All live groups receive TERM,
then KILL after `grace_ms` if still present. The loop drains remaining pipe data;
after one additional second it closes any remaining handles and records
`forced_close`, which explicitly allows incomplete capture. On normal leader exit,
the pool kills remaining descendants in that group before completing pipe draining
and reaping the leader. Parent signal handlers are restored when the pool closes.
Exceptions during configuration checks, logging or status publication also close
the scope and clean owned groups. Deliberate group escapes and an uncatchable
parent kill during service execution are outside this ownership guarantee.

This is a foreground session, not a system boot service manager. Logs/status left
by a killed supervisor are inspection artifacts; this application does not recover
ownership of old PIDs or resume a session. Do not treat an old `running` status as
proof that a process is still alive. A fresh session directory is required after
an interruption. Cooperative workspace ownership is assumed: commands are trusted
programs, not sandboxed workloads. Regular-file checks and configuration/staging
metadata guards detect the tested accidental aliases and concurrent edits.

Exit status is 0 when services complete or are deliberately stopped without an
exhausted failure, 1 if any service exhausted its attempts, 2 for validation or
session I/O errors, and 128 plus the received signal for reported parent
interruption. Normal operation is quiet on stdout; status and logs are files.
An already present stop file produces a completed session with zero launches.

| Bound | Limit |
| --- | --- |
| Services / ID | 0–8 / 32 ASCII characters |
| Configuration / status snapshot | 256 KiB each |
| Extra retries / maximum attempts | 0–8 / 9 per service |
| Initial / maximum backoff | 1–10,000 ms; maximum must be at least initial |
| Session deadline / TERM grace | 1–60,000 ms / 0–2,000 ms |
| Arguments / each argument | 1–64 / 1,024 UTF-8 bytes |
| Resolved argv including terminators | 64 KiB |
| Environment entries / key / total bytes | 32 / 128 ASCII characters / 16 KiB |
| Retained log bytes | 0–64 KiB per service per stream; at most 1 MiB total |

`SUPERVISOR_FAULT` injects a failure at `cycle`, `staged:PHASE`, or
`committed:PHASE`. PHASE is `running`, `stopping`, or `finished`.
`SUPERVISOR_PAUSE` uses the same labels and waits up to 30 seconds for the
`SUPERVISOR_RELEASE` file. These are test hooks; a paused loop temporarily delays
normal polling and shutdown handling.

Acceptance uses independently compiled native services recording launch/exit
monotonic timestamps and real PIDs. It checks exact attempts and backoff, concurrent
lifetimes, failure recovery/exhaustion, spawn failures, binary capture, graceful
TERM, forced KILL, closed pipes, orphan descendants, output flooding, stop files,
parent signals and cancellation during backoff. Real kills at four publication
boundaries are deliberately placed before children start or after they exit.
Changed configuration/staging, permission failures and eight competing supervisors
are also exercised. Capacity checks launch 72 actual attempts across eight
services and retain a full 1 MiB of logs under a 256 MiB address-space limit.
Eight Python/Rust writer→replayer→reader combinations pass actual status files and
binary logs through supervised native copy commands, including a failed service's
report, and verify the original files remain unchanged.

## Rust-import validation workbench (094)

[Six Python modules](094_rust_imports/main.py), 414 substantive source lines,
implement a bounded inspection application. It imports the adjacent
[numeric](094_rust_imports/native_numbers.rs),
[text/binary](094_rust_imports/native_text.rs), and
[structured-value](094_rust_imports/native_values.rs) Rust adapters with ordinary
`from module import function` statements. The whole-project compiler generates
checked wrappers and copies the native sources automatically. No binding generator,
CPython extension, interpreter or separate Rust build step is needed.

The small adapters exercise the native boundary. Case validation, independent
reference semantics, error classification, comparisons, replay export and atomic
publication are Python application code. Generated Rust retains readable source
names and file/line comments in `build/corpus/094/rust/src/main.rs`.

Build and run the complete source project with the existing project command:

```bash
py2rust-project run examples/corpus/094_rust_imports \
  --name rust-import-workbench --offline
```

The default `imports-job.json` is relative to the project working directory.
`IMPORTS_CONFIG` selects another configuration. Output paths resolve beside that
configuration. Output must be a fresh directory; repeat runs should choose a new
`output` value. A configuration has exactly these fields:

```json
{
  "version": 1,
  "output": "inspection",
  "cases": [
    {"id": "unicode", "operation": "unicode", "arguments": {"text": "Hello, 世界🙂"}, "expect": null},
    {"id": "checked_argument", "operation": "narrow", "arguments": {"value": 256},
     "expect": {"kind": "error", "code": "integer_range"}},
    {"id": "next_call", "operation": "add", "arguments": {"left": 20, "right": 22},
     "expect": {"kind": "value", "value": 42}}
  ]
}
```

| Operation | Arguments | Native behavior / expected result |
| --- | --- | --- |
| `narrow` | `value`: signed integer | Checked conversion to `u8`; values outside 0–255 produce `integer_range` |
| `unsigned` | `value`: signed integer | Negative input makes the adapter return `u64::MAX`; the wrapper rejects that result |
| `double` | `value`: signed integer | Computes in `i128`; the wrapper checks conversion back to signed 64 bits |
| `add` | `left`, `right`: integers | Checked addition; a Rust `Result` error becomes `overflow` |
| `invert` | `value`: boolean | Boolean negation |
| `unicode` | `text`: string | Character count, UTF-8 byte length, and reversal by Unicode scalar values |
| `bytes` | `data`: canonical base64 | Reverse bytes and XOR each with `0xa5`; returns base64 and byte count |
| `accept` | `text`: string | Prefixes `accepted:`; exactly `deny` returns a Rust error classified as `rejected` |
| `unit` | `text`: string | A native `()` result becomes JSON null |
| `float` | `mode`: `finite`, `nan`, `inf`, `negative_inf` | Returns 1.25 or exercises the finite-result check |
| `nested` | Same modes | Returns a list/nested tuple; non-finite values in either nested position are rejected |
| `json` | `mode`: `finite`, `wide` | Returns nested JSON or tests rejection of an unsigned integer outside signed 64 bits |
| `roundtrip` | `value`: bounded JSON | Owned structured JSON passes through the Rust adapter |

Every case is checked against the independent Python reference implementation.
`expect: null` adds no extra assertion; a value/error envelope adds an explicit
expected result. Known native errors retain their original message alongside the
semantic code. An unknown error becomes `unexpected` and fails the comparison.
Expected errors count as passing cases, and the application continues with later
calls. Exit status is 0 for all comparisons passing, 1 for a published mismatch
report, and 2 for configuration or publication errors.

The output bundle contains `report.json`, `report.txt`, `replay.json` and a
`manifest.json` with byte lengths and SHA-256 hashes. Reports bind the original
configuration bytes by hash and retain inputs, reference/observed results and both
comparison flags. The replay file exports reference expectations and selects a
fresh `replayed` output directory. It can be used directly as `IMPORTS_CONFIG`.
A deliberately wrong user expectation stays visible in the original report; the
exported reference expectation corrects that mismatch on replay.

The entire configuration is validated before native calls. Limits are 64 cases,
256 KiB configuration, 1,024 UTF-8 bytes per text argument, 1,024 binary bytes,
and 4,096 canonical bytes / eight levels / 256 nodes per JSON value. All canonical
argument objects together are limited to 96 KiB, keeping replay files within the
256 KiB input limit; the maximum-budget replay is tested end to end. Integers are
signed 64-bit and booleans are distinct from integers. IDs are unique ASCII names
of 1–32 characters. Unknown/duplicate fields and noncanonical base64 are rejected.

Input must be an unaliased regular file and remain unchanged during inspection.
Publication syncs a private sibling staging directory, then renames without
replacing existing output. A crash before rename leaves no final report directory;
a crash after rename leaves the complete bundle. Abrupt termination can leave a
hidden `.imports-*` staging directory for manual removal. `IMPORTS_FAULT` and
`IMPORTS_PAUSE` expose the `staged`/`published` boundaries for deterministic tests;
`IMPORTS_RELEASE` supplies the pause-release path.

`tools/corpus.py 094` verifies 220 independent semantic cases, recovery followed by
successful native calls, four intentional expectation mismatches, 39 invalid
configurations, seven malformed documents, capacities and filesystem/publication
failures. `tools/check_rust_imports.py` transfers actual replay files through all
eight Python/Rust writer–replayer–reader combinations and round-trips saved report
JSON. CPython comparison runs explicitly load test shims from
`tools/corpus_checks/native_reference/runner.py`; those files are outside the
application and are never linked into its native executable. The verifier hashes
the adapters and the complete static dependency closure of those shims.

## Project code-metrics browser (095)

[Six Python modules](095_code_metrics/main.py), 462 substantive source lines,
discover Python files, calculate structural metrics, resolve source links and
publish a self-contained HTML browser, JSON report and original-source archive.
Every module transpiles. The generated executable calls the shared Rust statement
parser and needs no Python runtime; analyzed files are never imported or executed.

The sample analyzes the application itself:

```bash
py2rust-project run examples/corpus/095_code_metrics \
  --name code-metrics --offline
```

Open the resulting `examples/corpus/095-code-metrics-report/index.html` in a browser.
The overview lists modules and definition metrics. Module pages show import
classifications and escaped source with stable line anchors. Oversized functions
are highlighted. Browser Find searches each page. No network service or external
frontend dependency is needed for the generated pages.

`METRICS_CONFIG` selects another configuration; the default is `metrics-job.json`
in the working directory. Paths resolve beside that configuration:

```json
{
  "version": 1,
  "root": "source",
  "output": "inspection",
  "package": "",
  "exclude": ["vendor", "__pycache__"],
  "thresholds": {"lines": 40, "statements": 25, "depth": 3}
}
```

`root` is an import search root. With an empty `package`, `pkg/tools.py` is named
`pkg.tools`, and `pkg/__init__.py` is named `pkg`. A nonempty prefix such as
`my_package` names the root package and prefixes all discovered modules. A root
`__init__.py` requires a nonempty prefix. Namespace prefixes are inferred from
discovered modules. Module paths and the optional prefix use ASCII Python
identifiers; source text and definition names support Unicode.

Hidden entries and named exclusions are skipped. Exclusions identify whole path
components, normally dependency or cache directories. Other directories are
traversed deterministically, ordinary non-Python files are ignored, and every
included `.py` file is parsed. Symlinks and special entries in the traversed tree
are rejected; Python inputs must also be unaliased regular files. The report
directory must be fresh and outside the source root. Repeated runs should select
a new `output` path.

Metrics have these precise meanings:

| Field | Meaning |
| --- | --- |
| Module `lines` | Physical lines after BOM removal and CR/LF normalization; a final newline adds no empty line |
| Module `statements` / `kinds` | Every statement in the AST, including nested scopes and docstring expressions |
| Definition `start_line` / `lines` | Inclusive span from the first decorator, or the definition line, through its final source line |
| Definition `line`, `column`, `end_line`, `end_column` | The declaration's AST location; columns are UTF-8 byte offsets |
| Scope `statements` / `kinds` | Statements owned by the nearest function/class scope; nested declarations count, their bodies do not |
| Scope `control_statements` | Owned `if`, loop, `try`, `with` and `match` statements, including async/star forms |
| Scope `max_depth` | Statement nesting relative to the scope body; direct body statements have depth zero |
| `flags` | Function values strictly greater than the configured `lines`, `statements` or `depth` thresholds |

Classes have scope metrics but are not flagged as oversized functions. Nested
functions, classes and methods have separate records and qualified names.
Conditional redefinitions retain distinct records and source locations.
Comprehensions, boolean operators and lambda expressions do not add statements
or control counts. This is structural counting, not cyclomatic complexity.
Type aliases are counted as statements, rather than as function/class definitions.

Import links are syntactic candidates, not an emulation of Python's runtime import
machinery. `local_module` links an unambiguous discovered module; `namespace`
identifies an inferred namespace prefix. `local_member` and `local_wildcard` link
the known base module without claiming that a particular exported attribute
exists. Multiple files with the same module name produce `ambiguous` links.
`missing_local`, `outside_root` and `external` retain unresolved references with
explicit classifications. Names, aliases, lexical scopes and source locations
remain available in the JSON report.

The bundle contains `index.html`, one `module-N.html` per source file,
`report.json`, `sources.json` and `manifest.json`. The report records exact input
byte lengths and SHA-256 hashes. The source archive stores each relative path and
its original bytes as base64, preserving BOMs and line endings, plus the analysis
settings. The manifest binds every output file by length and hash. Identical
source archives and settings produce identical bundles across both engines.

Before publication, the application rechecks the selected source inventory and
all input metadata. Added, removed, renamed or changed Python files prevent a
report from being committed; changes inside excluded directories are allowed.
A synced sibling staging directory is renamed without replacing existing output.
Process termination before rename leaves no final bundle; after rename it leaves
the complete bundle. Abrupt termination can leave a hidden `.metrics-*` staging
directory for manual cleanup. `METRICS_FAULT`, `METRICS_PAUSE` and
`METRICS_RELEASE` expose deterministic `staged` and `published` test boundaries.

| Capacity | Limit |
| --- | ---: |
| Configuration bytes | 65,536 |
| Python modules | 64 |
| Bytes per module / project | 131,072 / 1,048,576 |
| Physical lines per module | 4,096 |
| AST statements per module / project | 4,096 / 32,768 |
| Traversed entries / directory depth | 4,096 / 8 |
| Exclusions | 16 |
| Package-prefix / module-name characters | 128 / 256 |
| Rendered report bundle, before manifest | 16 MiB |

The shared parser also enforces its documented token, expression and nesting
limits. Thresholds accept 0–4,096 for lines/statements and 0–64 for depth. Empty
source roots are valid. Malformed configuration, syntax, encoding, unsupported
entries, exceeded budgets or publication failures exit with status 2. Successful
analysis prints a compact JSON summary and exits with status 0; oversized-function
flags are report findings and do not make the run fail.

`tools/corpus.py 095` compares both engines with an independent CPython AST oracle
and a hand-labeled 12-module fixture. It checks nested ownership, decorator spans,
async constructs, Unicode byte locations, comprehensions, import ambiguity,
threshold boundaries and non-execution of source side effects. HTML is parsed to
check metric cells, exact source text, escaping and every internal link. Additional
checks cover 30 invalid configurations, four malformed documents, nine invalid
sources, 13 filesystem/permission cases, publication faults and source-tree
mutations, capacities and seven capacity overflows.

`tools/check_code_metrics.py` consumes actual exported source archives through all
eight Python/Rust writer–replayer–reader combinations. It reconstructs the files,
reruns analysis and requires every HTML, JSON and archived source byte to match.
The current session verified HTML structurally; automated visual preview was
unavailable because the browser policy blocks local-file URLs.

## Local package constraint resolver (096)

[Six readable Python modules](096_package_resolver/main.py) implement a bounded
package resolver, lock verifier and portable report bundle. All application logic
transpiles into Rust; the resulting Linux x86-64 executable requires no Python
runtime. Package entries are data: the resolver never downloads or executes them.

Run the complete sample project with one command:

```bash
py2rust-project run examples/corpus/096_package_resolver \
  --name package-resolver --offline
```

The sample creates `examples/corpus/096_package_resolver/resolution/`. Its newest
Client version conflicts with Extension's Http requirement. Backtracking selects
Client 1.0.0, Extension 2.0.0 and Http 1.5.0 after eight visited states and two failed
branches. `report.txt` explains the rejected branches; `lock.json` records the
solution. Output directories must be fresh: choose another `output` for a new run.

`RESOLVER_CONFIG` selects a JSON request; its default is `resolver-job.json` in the
working directory. Paths resolve beside the request. A resolve request is:

```json
{
  "version": 1,
  "mode": "resolve",
  "index": "package-index.json",
  "output": "resolution",
  "roots": {"Client": "*", "Extension": "*"},
  "max_steps": 500,
  "max_conflicts": 32
}
```

An index has `version: 1` and a `packages` object. Each package maps to a list of
releases, each with exactly `version` and `dependencies`. Dependencies map package
names to requirements. Names are case-sensitive ASCII letters followed by letters,
digits, `_` or `-`, up to 32 characters. All releases are validated, including
unreachable releases. Empty indexes, empty roots and empty release lists are
allowed. A missing package reference becomes a conflict only when reachable.

Versions use three nonnegative decimal components, without leading zeros, each
at most 2,147,483,647. They sort numerically, so 1.10.0 is greater than 1.9.0.
These are stable triples from [Semantic Versioning](https://semver.org/);
prerelease and build suffixes are explicitly unsupported. Requirements support:

| Syntax | Meaning |
| --- | --- |
| `*` | Any listed version |
| `1.2.3`, `=1.2.3` | Exact version |
| `>`, `>=`, `<`, `<=` followed immediately by a triple | Numeric comparison |
| `^1.2.3` | At least 1.2.3, below 2.0.0 |
| `^0.2.3` | At least 0.2.3, below 0.3.0 |
| `^0.0.3` | At least 0.0.3, below 0.0.4 |
| `~1.2.3` | At least 1.2.3, below 1.3.0 |
| `>=1.0.0 <2.0.0` | All terms must hold |
| `1.0.0 || >=2.0.0 <3.0.0` | Any clause may hold |

Full-triple caret and tilde ranges follow the documented
[node-semver conventions](https://github.com/npm/node-semver#caret-ranges-123-025-004).
The grammar allows ordinary ASCII spaces, at most four OR clauses and four terms
per clause. It rejects tabs, newlines, partial versions, wildcards inside versions,
commas, hyphen ranges and other unsupported operators. It does not claim complete
SemVer or npm requirement compatibility.

Each search state owns its chosen-version dictionary. Incoming constraints are
rebuilt from roots and chosen releases; branches do not share mutable candidate
state. Search picks the unresolved package with the fewest candidates, breaks ties
by package name, then tries the greatest numeric version first. This deterministic
policy does not promise a globally newest solution. Every selected release must
satisfy all incoming requirements, and every selected package must be reachable
from a root. Cycles are allowed when their constraints are satisfiable.

`max_steps` bounds visited states, including the initial empty state. A nonempty
remaining frontier at that limit produces `budget_exhausted`, not a claim of
unsatisfiability. `unsatisfiable` requires exhausting the entire frontier.
`statistics` records states, total failed branches, retained conflicts and pending
states. `next_state` contains the next unevaluated assignment only on budget
exhaustion. A resolved result may still have unexplored alternatives.

Each retained conflict records the branch assignment, failing package, ordered
requirement sources, admissible versions and rejected versions with the indices
of requirements they violate. These explain individual failures; they are not a
minimal unsatisfiable core. `max_conflicts` limits retained detail while the total
conflict count continues to increase.

A successful resolution writes `lock.json` and a runnable `verify.json` request:

```json
{"version": 1, "mode": "verify", "index": "index.json", "output": "verified", "lock": "lock.json"}
```

Verification checks every locked release, all roots and dependency constraints,
the exact reachable closure, and the SHA-256 of the original index bytes. Even
semantically equivalent index reformatting changes that identity. Extra packages,
including disconnected dependency cycles, fail verification. Invalid lock schemas
are input errors; well-formed but invalid locks produce a report with explicit
`unknown_release`, `missing_package`, `constraint`, `unreachable_package` or
`index_digest` findings. Unknown releases prevent further closure checks for that
lock. Verification uses the roots recorded in the lock; callers must separately
compare those with any independently trusted project requirements.

Every completed bundle contains the exact original `index.json`, `report.json`,
`report.txt`, a runnable `replay.json`, and a hash/length `manifest.json`. Valid
solutions also contain `lock.json` and `verify.json`. Invalid locks are preserved
as `input-lock.json` so replay reproduces their failure; unsatisfiable and
budget-exhausted searches issue no lock. Replay requests use a fresh `replayed`
output directory beside the exported index.

Inputs must be unaliased regular files. The application reads bounded snapshots,
rechecks their metadata before publication, syncs a sibling staging directory,
and renames it without replacing existing output. Caught publication errors clean
up staging. Killing the process before rename can leave a hidden `.resolver-*`
directory, but no partial final bundle; after rename the final bundle is complete.
`RESOLVER_FAULT`, `RESOLVER_PAUSE` and `RESOLVER_RELEASE` expose deterministic
`staged` and `published` test boundaries.

| Capacity | Limit |
| --- | ---: |
| Configuration / lock bytes | 65,536 each |
| Index bytes | 524,288 |
| Packages / roots / locked packages | 16 each |
| Releases per package / dependencies per release | 8 each |
| Requirement characters | 256 |
| Search states | 1–10,000 |
| Retained conflicts | 1–128 |
| Report bundle before manifest | 4 MiB |

Exit status is 0 for `resolved` or `valid_lock`, 1 for `unsatisfiable` or
`invalid_lock`, 3 for `budget_exhausted`, and 2 for malformed inputs, exceeded
input/output limits or publication errors. Completed semantic outcomes print
exactly their status name; operational errors go to stderr.

`tools/corpus.py 096` compares Python and Rust with independent interval and
exhaustive assignment oracles. It checks 120 generated repositories, numeric
ordering and range boundaries, cycles, backtracking, input-order invariance, every
retained conflict, lock closure and exact index identity. It also exercises the
10,000-state budget, full input capacities, malformed documents, filesystem
permissions and atomic publication under faults, kills and input/output races.
The 4 MiB report cap is a defensive guard; the tests do not claim to reach that
cap with an otherwise valid bounded index.

`tools/check_package_resolver.py` consumes actual exported indexes, locks and
replay requests across all eight Python/Rust writer–verifier–replayer combinations.
It requires identical solution locks and identical replay bundles for resolved,
unsatisfiable and invalid-lock outcomes. No application-specific Rust adapter is
used, and native acceptance runs with Python environment paths disabled.

## Source-header checker (097)

[Five Python modules](097_source_headers/main.py), 446 substantive source lines,
inspect a supplied manifest, group precise file/line findings, export proposed byte
splices and produce corrected copies. All five modules transpile into Rust. The
Linux x86-64 executable uses no Python runtime, imports no inspected source and
never modifies its input files.

Build and run the sample as a complete project:

```bash
py2rust-project run examples/corpus/097_source_headers \
  --name source-headers --offline
```

The sample exits with status **1** because it finds an outdated year and a missing
header. Open `examples/corpus/097_source_headers/inspection/report.txt` for the
three findings. The bundle includes executable requests for the subsequent steps:

```bash
HEADERS_CONFIG="$PWD/examples/corpus/097_source_headers/inspection/apply.json" \
  examples/corpus/097_source_headers/.py2rust/rust/target/debug/source-headers
HEADERS_CONFIG="$PWD/examples/corpus/097_source_headers/inspection/applied/recheck.json" \
  examples/corpus/097_source_headers/.py2rust/rust/target/debug/source-headers
```

Both steps exit 0. Corrected files appear under `inspection/applied/files/demo/`.
Each run requires a fresh output directory. `HEADERS_CONFIG` selects another
request; otherwise the program uses `headers-job.json` in its working directory.
Request paths resolve beside that request. Apply-mode source paths resolve beside
the patch document.

A check request contains exactly these fields:

```json
{
  "version": 1,
  "mode": "check",
  "output": "inspection",
  "policy": {
    "year": 2026,
    "owners": ["Example Team", "Another Team"],
    "licenses": ["MIT", "Apache-2.0"]
  },
  "files": [
    {"name": "src/client.py", "path": "original/client.txt", "style": "hash"},
    {"name": "src/socket.rs", "path": "original/socket.txt", "style": "slash"}
  ]
}
```

`name` is the logical file name used in findings and exported directory trees;
`path` identifies the actual input file. Paths are relative and reject empty,
`.` and `..` components, backslashes and ASCII control characters. Names, resolved
input paths and file/directory prefixes must not collide. Comment style is
explicit rather than inferred from the extension. Empty manifests are valid.

The header grammar is two adjacent lines at the start of the file after its
protected preamble:

```text
# Copyright (c) 2020-2026 Example Team
# SPDX-License-Identifier: MIT
```

`slash` uses `//` instead of `#`. The column, spelling and spaces shown are part
of the format. Years are four decimal digits, either a single year or a range.
The start must be at least 1900, the end must be between the start and the configured
current year, and the end must equal that current year for a clean result.
The configured year is explicit, so replay does not depend on the system clock.
Owners and license labels must match their configured allowlists exactly.
License labels are literal identifiers of up to 64 ASCII letters, digits, dots,
plus signs or hyphens; compound expressions are outside this grammar.

The protected preamble consists of an optional UTF-8 BOM, an optional first-line
shebang, and a UTF-8 encoding declaration in one of the first two physical lines
for `hash` style. A second-line declaration is recognized when the first line is
blank or a hash comment. Non-UTF-8 declarations are rejected. The checker handles
line comments and blank lines before the first source-code line. Block comments
and headers embedded later in the program are outside this leading-header policy.

Within that initial comment area, comment text beginning with `copyright` or
`spdx-license-identifier`, case-insensitively, is treated as a header marker. The
checker reports missing markers, malformed formatting, duplicate markers,
misplaced fields, unlisted owners/licenses, invalid year ranges and outdated years.
Each existing marker points to its actual one-based physical line. A missing
field points to the insertion line immediately after the preamble; for an empty
file that is line 1. Findings are also grouped by kind in the JSON report.

Suggested corrections retain an allowed owner/license from the first corresponding
marker and a valid starting year. Otherwise they choose the first configured
owner/license and the current year. They remove duplicate markers and place the
canonical pair immediately after the preamble. Other comments, blank lines and
source bytes retain their original order and exact contents. New header lines
use the first existing LF or CRLF convention, defaulting to LF; mixed line endings
elsewhere are preserved. A shebang without a terminating newline receives a
newline before the inserted header. Bare carriage returns, NUL bytes and invalid
UTF-8 are rejected.

A header marker inside the protected encoding/shebang preamble receives
`header_in_preamble` and requires a manual change. The checker exports no edit
for that file, copies it unchanged in apply mode and retains its finding on
recheck. This avoids relocating the encoding declaration or silently removing
part of the protected preamble.

`patches.json` contains the declared policy and one record per file, including
unchanged files. Each record binds the original and resulting bytes with SHA-256.
An edit stores a half-open **byte** range, the exact removed bytes, and replacement
bytes as canonical base64. UTF-8 boundaries are preserved. Apply mode rereads the
source, checks its hash, independently recomputes the correction under the declared
policy, and requires the proposed edit and result hash to match. It rejects stale
sources and altered edits before publishing any output. It never treats an
arbitrary replacement as an authorized header correction.

Every bundle contains `report.json`, `report.txt`, `patches.json`, `apply.json`,
`replay.json`, `sources/<logical-name>` and a hash/length `manifest.json`. Apply
bundles additionally contain `files/<logical-name>` and `recheck.json`. Replay
checks the original source snapshots; recheck checks the corrected copies.
`summary.violations` counts the original findings; `summary.remaining` counts
findings in the inspected inputs for check mode and in corrected copies for apply
mode. Manual findings remain visible. `changed_files` counts proposed or applied
byte changes, and rechecking corrected files yields zero further changes.

Inputs must be unaliased regular files. Before publication their metadata is
rechecked. The application writes and syncs a fresh sibling staging tree, then
renames it without replacing existing output. Caught failures remove nested
staging files/directories. Killing a process before rename can leave a hidden
`.headers-*` tree for cleanup, but no partial final bundle; after rename the final
bundle is complete. `HEADERS_FAULT`, `HEADERS_PAUSE` and `HEADERS_RELEASE` expose
`staged` and `published` test boundaries.

| Capacity | Limit |
| --- | ---: |
| Request bytes | 65,536 |
| Patch document bytes | 4 MiB |
| Files | 32 |
| Bytes per original/corrected file | 65,536 |
| Total original/corrected bytes | 1 MiB each |
| Physical lines per original/corrected file | 4,096 |
| Logical-name characters / components | 240 / 8 |
| Physical-path characters / components | 256 / 9 |
| Bytes per path component | 240 |
| Owner choices / license choices | 1–8 each |
| Owner characters / license-label characters | 128 / 64 |
| Configured year | 1900–9999 |
| Report bundle before manifest | 8 MiB |

Exit status is 0 when no findings remain, 1 when findings remain, and 2 for malformed
requests, unsupported input text, stale/tampered patches, exceeded budgets or
publication errors. Completed checks print their JSON summary. Errors go to stderr.
An edit whose corrected source would exceed the byte limits is rejected. Generated
headers are rechecked before any bundle is published.

`tools/corpus.py 097` checks 27 hand-labeled files and 64 generated byte-preservation
cases, including BOMs, encoding declarations, shebangs, LF/CRLF mixtures, Unicode,
missing/duplicate/misplaced headers, exact line numbers and year boundaries. It
also checks apply/recheck idempotence, malformed inputs, stale/tampered patches,
full input capacities, filesystem permissions and publication faults, kills and
races. The 8 MiB bundle cap is a defensive guard, not a claimed tested boundary.
`tools/check_source_headers.py` exchanges actual snapshots and edits across all
eight Python/Rust check–apply–recheck combinations and requires exact corrected
bytes, preserved manual conflicts and identical replay bundles.

This application added general `str.strip`, `str.lstrip` and `str.rstrip` support
with optional string character sets or `None` to the shared compiler/runtime.
The corresponding regression tests check 609 Unicode/string vectors, operand
evaluation order, exception recovery and rejected argument types/keywords.

## Transfer benchmark harness (098)

[Six Python modules](098_transfer_bench/main.py), 492 substantive source lines,
compile into one standalone executable. The same executable runs the controller,
sender and receiver roles. Its policy, framing, byte checks, aggregation and report
comparison are all written in Python and transpiled. The application uses existing
shared TCP, process-pool, clock, hashing, JSON and filesystem support.

From the repository root, one command transpiles, builds and runs the supplied
4 KiB and 1 MiB workloads, with three repetitions each:

```sh
py2rust-project run examples/corpus/098_transfer_bench \
  --name transfer-bench --offline
```

Open `examples/corpus/098_transfer_bench/measurements/report.txt`. The resulting
binary and its child workers run without Python. For another measurement, change
`output` to a fresh destination, or run the exported replay request once:

```sh
TRANSFER_CONFIG="$PWD/examples/corpus/098_transfer_bench/measurements/replay.json" \
  examples/corpus/098_transfer_bench/.py2rust/rust/target/debug/transfer-bench
```

`TRANSFER_CONFIG` selects the request, defaulting to `transfer-job.json` in the
working directory. The supplied request assumes the default debug build location
and the executable name shown above. A custom Cargo output/name or release build
requires adjusting its two worker command paths. No Python process is launched
when both commands select the native executable.

### Configuration and module responsibilities

`main.py` runs suites and exports reports. `model.py` validates workloads and
commands and constructs reproducible payload bytes. `workers.py` implements both
network roles. `execution.py` owns the child processes and their failure boundary.
`analysis.py` validates imported reports, aggregates measurements and compares
compatible cases. `documents.py` checks input snapshots and publishes complete
bundles atomically. Generated Rust retains module/function names and Python source
location comments; it is formatted with `rustfmt`.

A benchmark request has exactly these fields:

```json
{
  "version": 1,
  "mode": "benchmark",
  "output": "measurements",
  "sender": {"argv": ["/absolute/path/transfer-bench"], "environment": {}, "cwd": "."},
  "receiver": {"argv": ["/absolute/path/transfer-bench"], "environment": {}, "cwd": "."},
  "repetitions": 3,
  "cases": [
    {"id": "small", "size": 4096, "seed": 17, "send_chunk": 257,
     "receive_chunk": 1024, "timeout_ms": 3000}
  ]
}
```

Each payload byte at offset `i` is `(i * 31 + seed) % 256`. Case IDs are unique
ASCII identifiers: a letter followed by letters, digits, underscores or hyphens.
Unknown object fields, duplicate JSON keys and booleans in integer fields fail
validation. Paths are resolved beside the request. `argv[0]` names an executable
path directly; other arguments are preserved and no shell is involved. The
explicit worker environment replaces inherited variables. The controller adds
`TRANSFER_ROLE`, `TRANSFER_CASE`, `TRANSFER_PORT` and `PYTHONUNBUFFERED`; names
beginning with `TRANSFER_` and `PYTHONUNBUFFERED` are reserved.

| Bound | Accepted range |
| --- | --- |
| Request / imported report / emitted report | 64 KiB / 1 MiB each / 1 MiB |
| Cases / repetitions per case | 1–16 / 1–4 |
| Case ID / seed | 1–32 ASCII characters / 0–255 |
| Payload size | 0–1,048,576 bytes |
| Send and receive chunk sizes | 1–65,536 bytes |
| Active attempt deadline | 1–15,000 milliseconds |
| Sum of case deadlines times repetitions | At most 120,000 milliseconds |
| Worker command | 1–32 arguments; 8,192 UTF-8 bytes including terminating NULs |
| Worker environment | At most 32 entries; 8,192 bytes including `=` and NULs |
| Environment name | ASCII letter/underscore, then letters/digits/underscores; at most 64 characters |
| Captured worker output | 8,192 bytes total across stdout and stderr, per worker |

The argument byte count uses the normalized executable path. Timeouts are upper
bounds, not recommended settings: allow time for process startup and scheduling.
Only one sender/receiver pair runs at a time. Both command arrays are trusted
local programs; the controller checks their reports, while the supplied workers
perform the exact network-byte validation. This is a loopback benchmark.

### Wire protocol, timing and failures

The receiver binds an ephemeral port on `127.0.0.1` and prints `READY <port>`.
The controller passes that port to the sender. The 77-byte header contains
`P2RB1`, the payload length as an unsigned 8-byte big-endian integer, and the
64-byte lowercase ASCII SHA-256 hex digest. The sender then writes the fixture
and half-closes its connection. The receiver checks the complete header, every
payload byte and EOF, and replies with `OK` followed by the 64-byte digest before
half-closing. Both sides honor the configured chunk sizes, tolerate fragmentation
and reject truncated frames, extra bytes and mismatched content. Each successful
worker prints one JSON result after its readiness line, if applicable.

All durations use monotonic clocks, floor to whole microseconds and clamp to at
least one microsecond. Payload generation and its initial hashing happen before
the worker timers start. The sender interval includes connection establishment,
transmission and acknowledgment through EOF. The receiver interval starts after
accept and includes receiving/validating bytes and sending/half-closing the reply.
The controller's `wall_us` starts before pool creation and includes both process
lifetimes, worker startup, report validation and cleanup. It excludes final bundle
publication. Active workers share an attempt deadline; validation and bounded
cleanup can extend the reported wall interval beyond that deadline.

Each case records raw runs and medians of successful wall, sender and receiver
durations. For an even sample count, the middle two integers are averaged with
floor division. `sender_Bps` and `receiver_Bps` are payload size times 1,000,000,
divided by the corresponding median duration, also floored. Empty payload rates
are zero. Cases without successful runs have null timing/rate fields. These are
application-level payload rates: worker implementation, startup, framing and
validation affect measurements. The suite makes no throughput guarantee and does
not require matching timings between Python and Rust.

Missing executables, invalid readiness, nonzero exits, malformed/incorrect worker
reports, stderr, excess output and deadlines produce failed run records. Every
failure includes its phase and reason. Both owned process groups are cleaned up,
including cooperative descendants. SIGINT/SIGTERM produces a final interrupted
run, stops remaining trials and exits 130. Other failed suites exit 1; successful
suites exit 0. Request, input or publication errors exit 2. A failed worker's raw
stdout/stderr is not exported. Uncatchable controller termination and deliberately
escaped process groups are outside cooperative cleanup.

### Comparing and replaying measurements

A comparison request names two benchmark reports:

```json
{
  "version": 1,
  "mode": "compare",
  "output": "comparison",
  "baseline": "first/report.json",
  "candidate": "second/report.json"
}
```

Both reports are validated, including run identities, worker results, duration
bounds, complete coverage or a final interruption, and independently recalculated
statistics. A case is `comparable` only when every workload field matches and all
requested trials in both reports succeeded. Repetition counts may differ. The
wall change is `(candidate - baseline) * 1,000,000 // baseline`, in parts per
million; positive means slower, negative means faster. Other rows report
`incompatible`, `unavailable`, `missing_baseline` or `missing_candidate` and have
null changes. A valid comparison exits 0 even when some rows cannot be compared.

Bundles contain `report.json`, readable `report.txt`, `replay.json` and a hash/size
`manifest.json`. Comparison bundles also preserve the exact input bytes as
`baseline.json` and `candidate.json`, and replay resolves these local copies.
Benchmark replay preserves normalized worker paths and environment; the selected
worker executables must still be available. Replay writes to a fresh `replayed`
directory. Measured durations naturally change when rerunning a benchmark.

Inputs must be unaliased regular files. They are checked before/after reading and
again before publication. Output must be fresh. Files are synced in a sibling
staging directory, then published with a no-replace rename and parent sync.
Caught failures remove unpublished staging. A hard kill can leave hidden staging;
the final directory is absent or complete. `TRANSFER_FAULT`, `TRANSFER_PAUSE` and
`TRANSFER_RELEASE` provide the staged/published test checkpoints.

`tools/corpus.py 098` runs 100 actual transfers per engine, including empty,
one-byte, fragmented and 1 MiB cases, case/repetition capacity and replay. It also
uses 14 independent socket-peer scenarios, median/ppm oracles, 107 invalid
requests/reports, 15 worker failure modes, deadline and signal cleanup checks,
publication races/kills, 22 guarded filesystem cases and exact input byte limits.
`tools/check_transfer_bench.py` runs all eight controller/sender/receiver engine
combinations, totaling 64 further transfers, then compares actual reports with the
other engine and replays each comparison. The packaged compiler builds all six
modules and repeats complete native acceptance with Python unavailable.

## Environment configuration validator (099)

[Five Python modules](099_environment_validator/main.py), 465 substantive source
lines, compile into one standalone Rust executable. The complete schema parser,
environment validation, dependency evaluation, redaction and reporting run without
Python. The application uses existing shared JSON, environment, collection,
filesystem and hashing support; it needs no custom Rust adapter.

Run the supplied network-service configuration schema with one command:

```sh
APP_TLS=true APP_TOKEN='"local-test-token"' APP_LOG_LEVEL='"debug"' \
  py2rust-project run examples/corpus/099_environment_validator \
  --name environment-validator --offline
```

Open `examples/corpus/099_environment_validator/configuration/report.txt` for the
result. Host, port and timeout use schema defaults. TLS, the token and log level
come from the environment. The token displays as `<redacted>`. Plain strings must
be JSON encoded, including their double quotes; booleans and numbers use JSON
spelling. Running the command without these variables validates the supplied
schema's defaults and leaves the optional token missing.

`SETTINGS_CONFIG` selects a request, defaulting to `settings-job.json` in the
working directory. The request has exactly these fields; paths resolve beside it:

```json
{"version": 1, "schema": "schema.json", "output": "configuration"}
```

Output must be fresh. To revalidate using the original schema and a newly supplied
environment, consume the exported recheck request:

```sh
APP_TLS=false APP_TOKEN='"local-test-token"' \
  SETTINGS_CONFIG="$PWD/examples/corpus/099_environment_validator/configuration/recheck.json" \
  examples/corpus/099_environment_validator/.py2rust/rust/target/debug/environment-validator
```

This writes `configuration/rechecked` and exits 1: a present token requires TLS to
be true. The original output is preserved. Recheck requests refer to the original
schema by absolute path; that file must remain available. They contain no saved
environment values, and the next run reads the environment again.

### Schema and scalar rules

The schema contains `version: 1` and a `fields` array. Each field requires `name`,
`env` and `type`; unknown fields and duplicate JSON object keys are rejected.
For example:

```json
{
  "version": 1,
  "fields": [
    {"name": "port", "env": "APP_PORT", "type": "integer",
     "default": 8080, "minimum": 1, "maximum": 65535},
    {"name": "tls", "env": "APP_TLS", "type": "bool", "default": false},
    {"name": "token", "env": "APP_TOKEN", "type": "string", "secret": true,
     "min_length": 8, "requires": [{"field": "tls", "equals": true}]}
  ]
}
```

| Field option | Meaning |
| --- | --- |
| `name` | Unique ASCII letter followed by letters, digits or underscores; 1–32 characters |
| `env` | Unique uppercase ASCII letter/underscore followed by uppercase letters, digits or underscores; 1–64 characters; `SETTINGS_` prefix is reserved |
| `type` | `string`, `integer`, `number` or `bool` |
| `required` | Missing values without a default produce a diagnostic; defaults to false |
| `secret` | Public values always display as `<redacted>`; defaults to false |
| `nullable` | Permit explicit JSON null; defaults to false |
| `default` | Used only when the variable is absent; must satisfy the field's scalar rules |
| `choices` | Optional nonempty list of 1–16 distinct allowed scalar values |
| `minimum`, `maximum` | Inclusive numeric bounds, valid only for numeric fields |
| `min_length`, `max_length` | Inclusive Unicode code-point lengths for strings; defaults 0 and 1024 |
| `requires` | Up to eight prerequisite rules, each with exactly `field` and `equals` |

`integer` accepts signed 64-bit JSON integers, including the exact endpoints.
`number` accepts those integers and finite binary64 values. Integer fields reject
`1.0` and `1e0`; neither numeric type accepts booleans. Bounds for integer fields
must themselves be integers. Mixed integer/float comparisons preserve exact
ordering rather than first rounding integers to binary64. NaN, infinities,
integer overflow, malformed encodings and invalid Unicode are rejected.

Absent variables, empty environment strings and JSON `""` are distinct. An
absent field uses its default, if any; a default satisfies `required`. A present
empty environment string is malformed JSON. JSON null requires `nullable` and,
when choices are specified, must also be included in the choices. Null bypasses
numeric bounds and string lengths. Arrays and objects are not scalar values.
Choices use scalar JSON equality: 1 and 1.0 are the same numeric choice, while
booleans remain distinct. Every choice/default is checked against its type and
bounds before environment evaluation begins.

A present/defaulted field that passes local validation must satisfy every
prerequisite: the target must be valid and its internal value must equal the
predicate. Missing optional fields do not activate their prerequisites. A failed
prerequisite marks the dependent field invalid; this propagates through further
dependents. Unknown targets, self references, duplicate targets, invalid predicate
values and cycles reject the schema. Dependency predicates must themselves satisfy
the target field's scalar constraints. Schema field order does not affect results.
Diagnostics within a field follow its declared prerequisite order.

### Reports, redaction and limits

`schema.py` normalizes fields and orders prerequisites. `evaluation.py` reads each
mapped environment variable once, validates local values and evaluates the graph.
`reports.py` builds public records. `documents.py` snapshots inputs and publishes
the output directory. `main.py` connects the complete workflow. Generated Rust
preserves function/module names and source locations and is formatted by rustfmt.

The bundle contains:

- `report.json`: field status (`valid`, `missing`, `invalid`), origin (`environment`,
  `default`, `absent`), redacted values, effective valid settings and diagnostics.
- `report.txt`: the same effective state and diagnostic codes in readable form.
- `schema-summary.json`: names, variable mappings, types, flags, default presence
  and prerequisite names. It omits actual defaults, choices, bounds and predicate
  values. This is a description, not a runnable schema.
- `recheck.json`: a request referring to the original external schema and a fresh
  `rechecked` destination. It carries no environment snapshot.
- `manifest.json`: byte counts and SHA-256 digests of the exported files.

Only valid fields enter the effective configuration. Invalid/missing public fields
have null report values. Secret fields display `<redacted>` in every state,
including missing, malformed, defaulted and dependency-invalid states. Validation
uses their original internal values, so redaction does not alter dependency
semantics. Diagnostics contain field/variable names and fixed codes, never failed
values or expected predicates. Fatal request/schema/filesystem errors emit only
`configuration request rejected`, avoiding exception text that could include input.
The original schema and environment remain private inputs; staging contains only
the public artifacts. Public fields are deliberately visible. Names, types,
presence, origins and dependency outcomes remain visible for secret fields.

Diagnostic codes are `required`, `json`, `size`, `null`, `type`, `range`, `length`,
`choice` and `dependency`. A scalar field reports its first local failure; a locally
valid field can report multiple unmet prerequisites. Missing required fields retain
status `missing` and carry a `required` diagnostic. `summary.defaulted` counts
fields whose origin is a default, including those later rejected by dependencies.

Schemas allow 1–32 fields, with up to eight prerequisites and 16 choices per field.
Strings allow at most 1024 Unicode code points. Present raw environment values
are limited to 4096 UTF-8 bytes each and 65,536 bytes in aggregate; missing fields
consume no byte budget. A per-value overflow becomes a `size` diagnostic. Aggregate
overflow rejects the request before publication. Requests are at most 64 KiB,
schemas at most 256 KiB, and each exported report document at most 256 KiB.

Exit 0 means valid configuration; exit 1 means a published report contains
validation errors; exit 2 means a request, schema, input or publication error.
Stdout normally contains only the summary counts. Inputs must be unaliased regular
files, checked before/after reading and before publication. Files are synced in a
sibling staging directory and published using no-replace rename and parent sync.
Caught failures remove unpublished staging. A hard kill can leave hidden staging,
with the final directory either absent or complete. `SETTINGS_FAULT`,
`SETTINGS_PAUSE` and `SETTINGS_RELEASE` expose the staged/published test checkpoints.

Acceptance runs use an independent scalar/dependency oracle: nine hand scenarios,
24 presence/default/null combinations, 240 scalar/type/encoding cases, 288 generated
fields, a 32-field cascade, eight prerequisites, large mixed-number boundaries and
capacity checks. Secret scans cover 12 setting/error paths, three secret-bearing
schema failures, stdout, stderr, exported bytes and unpublished staging. Checks
also cover 59 invalid schemas, seven invalid requests, 14 invalid encodings,
publication faults/races/kills and 14 filesystem protections. Eight mixed-engine
validation/recheck combinations consume actual exported requests, change the
supplied secret, verify the resulting dependency failure, and restore the original
report with the original environment. The packaged compiler independently builds
all five modules and repeats complete native acceptance with Python unavailable.

## Text diff and patch utility (100)

[Six Python modules](100_text_patch/main.py), 416 substantive source lines, compile
into one standalone Rust executable. Line segmentation, LCS alignment, context
hunks, strict patch validation, exact-byte reconstruction and publication are all
transpiled Python. Existing typed lists, integer arithmetic, JSON, Unicode,
hashing and filesystem operations supply the shared runtime support.

The supplied example changes a network-service note containing both CRLF and LF,
and adds a Unicode line without a final newline. From the repository root:

```sh
py2rust-project run examples/corpus/100_text_patch \
  --name text-patch --offline
```

Exit status 1 means the diff found changes. Open
`examples/corpus/100_text_patch/comparison/diff.txt` for the review. Each line is
JSON quoted, making CRLF, LF, lone CR, tabs, NULs and a missing final terminator
visible without altering their bytes. The header uses zero-based line offsets.
This readable review accompanies a versioned JSON patch; it is not GNU patch
syntax.

Apply the exported patch and check the corrected copy against the original target:

```sh
PATCH_CONFIG="$PWD/examples/corpus/100_text_patch/comparison/apply.json" \
  examples/corpus/100_text_patch/.py2rust/rust/target/debug/text-patch
PATCH_CONFIG="$PWD/examples/corpus/100_text_patch/comparison/check-applied.json" \
  examples/corpus/100_text_patch/.py2rust/rust/target/debug/text-patch
```

Both commands exit 0. The first writes `comparison/applied/result.txt`; the second
writes a diff with no hunks to `comparison/checked`. Every output destination must
be fresh. The binary needs no Python runtime. `PATCH_CONFIG` defaults to
`patch-job.json` in the working directory; relative paths resolve beside that
request.

### Requests and exact line semantics

A diff request contains exactly:

```json
{
  "version": 1, "mode": "diff", "base": "before.txt", "target": "after.txt",
  "context": 3, "output": "comparison"
}
```

An apply request contains exactly:

```json
{
  "version": 1, "mode": "apply", "base": "before.txt", "patch": "patch.json",
  "output": "applied"
}
```

Inputs must be valid UTF-8. LF, CRLF and lone CR each terminate a line, and the
terminator is retained in that line's token. An unterminated suffix is a final
line; an empty file has no lines. BOMs, combining characters, NULs and other valid
Unicode remain unchanged. Unicode separators such as U+0085, U+2028 and U+2029
are ordinary content in this format. There is no Unicode or newline normalization.
Changing only a line terminator is therefore a real line replacement.

`alignment.py` computes a suffix LCS table. Equal tokens are matched immediately;
when deletion and insertion preserve the same LCS length, deletion wins. This
produces a deterministic minimum insertion/deletion script. Context is the number
of neighboring script operations around changes; adjacent changes and touching
context windows merge. The unchanged lines surrounding each merged change group
have the requested context, limited by file boundaries. With zero context, changes
separated by an unchanged line form separate hunks.

`text_model.py` provides exact segmentation and file identities. `patching.py`
checks and reconstructs patches. `reports.py` exports the review and follow-up
requests, `documents.py` handles input snapshots/publication, and `main.py` runs
the complete workflow. Generated Rust preserves readable module/function names
and source location comments and is formatted with rustfmt.

### Patch format and validation

A patch has exactly `version: 1`, `format: "line-lcs"`, `context`, `before`, `after`
and `hunks`. Each identity contains the file's byte count, token count, lowercase
SHA-256 digest and final `ending` (`none`, `lf`, `crlf` or `cr`). Each hunk contains
zero-based `old_start`/`new_start`, `old_count`/`new_count`, and an `ops` array.
Each operation contains `op` (`" "` for context, `"-"` for removal or `"+"` for
addition) and one complete line token in `text`, including its terminator.

Application verifies the base's exact identity before processing hunks. It rejects
unknown keys, duplicate JSON keys, boolean/noninteger indices, out-of-range
positions/counts, unordered or overlapping hunks, invalid operations, empty or
multi-line tokens, mismatched context/removals and inconsistent new offsets.
Every hunk must contain a change. Reconstructed tokens must retain canonical line
boundaries, so an unterminated token cannot silently merge with a following token.
The result must match the declared target identity.

Finally, the utility recomputes the canonical diff from the base and reconstructed
result. Nonminimal edits, alternative LCS ties, missing context and otherwise
noncanonical hunk layouts are rejected even if they could produce the same result.
This gives both engines one deterministic patch format. SHA-256 binds a patch to
its declared contents; the format does not authenticate who created the patch.
Ordinary JSON whitespace/key ordering is accepted, and apply preserves the exact
input patch bytes in its output bundle.

The source files are preserved. A changed patch cannot be reapplied to its result
because that result no longer matches the original base identity. An empty patch
against its unchanged base remains valid.

### Bundles, limits and verification

Diff bundles include the exact `base.txt` and `target.txt`, canonical `patch.json`,
`diff.txt`, `report.json`, `apply.json`, `replay.json`, `check-applied.json` and a
hash/size `manifest.json`. Apply bundles contain the exact base and input patch,
`result.txt`, the review/report, `replay.json`, `recheck.json` and the manifest.

Diff replay regenerates the original patch from the exported inputs. Apply replay
recreates the corrected copy. The apply bundle's `recheck.json` regenerates the
diff from its exported base/result and should reproduce the original canonical
patch. The original diff bundle's `check-applied.json` instead compares
`applied/result.txt` against `target.txt` and should report zero changes. Each
follow-up uses a fresh destination and consumes actual exported files.

Reports include before/after identities, the exact patch-byte digest and counts
of removed, added and common lines, hunks and alignment-table cells. Diff exits 1
when bytes differ and 0 when identical. Successful apply exits 0. Invalid requests,
stale/tampered patches, input errors and publication failures exit 2 with an error
on stderr. Normal stdout contains only the statistics.

| Bound | Limit |
| --- | --- |
| Each input/result text | 65,536 UTF-8 bytes and 1024 line tokens |
| Context | 0–16 |
| LCS table | At most 1,050,625 integer cells; quadratic time/space in token counts |
| Patch parser | At most 1024 hunks and 2048 operations in total |
| Request | 64 KiB |
| Input patch / each exported file | 1 MiB |

Inputs must be unaliased regular files. They are checked before/after reads and
again before output publication. Complete files are synced in a sibling staging
directory, then published with no-replace rename and parent sync. Caught failures
clean unpublished staging. A hard kill can leave hidden staging; the final
directory is absent or complete. `PATCH_FAULT`, `PATCH_PAUSE` and `PATCH_RELEASE`
expose staged/published checkpoints for the acceptance tests.

`tools/corpus.py 100` verifies 16 hand fixtures at four context settings, eight
context-merge boundaries, all 225 pairs of binary sequences up to three tokens,
and 40 seeded Unicode pairs. Small scripts are checked against an independent
shortest-edit search; minimality is also checked with a forward two-row LCS oracle.
Tests cover exact diff/apply/check/replay bytes, 49 malformed patches, five
noncanonical layouts, three stale bases, request/encoding errors, capacity
boundaries, publication races/failures/kills and 24 filesystem protections.

The maximum 1,050,625-cell table and 2048-operation replacement run under a 192 MiB
process memory limit in both engines. Additional fixtures cover 512 isolated hunks,
64 KiB text containing escaped control characters, and exact 64 KiB/1 MiB request
and patch boundaries. `tools/check_text_patch.py` exercises all eight diff/apply/check
engine combinations across six fixtures, using exported patches and requests.
Every corrected file matches its original target byte for byte, its final check
has no changes, and regeneration/replay matches the original artifacts. The
packaged compiler independently builds every module and repeats native acceptance
with Python unavailable.

## 102: Inventory reservation ledger

[Five Python modules](102_inventory_ledger/main.py), 466 substantive source lines,
compile into one native executable. `model.py` owns stock/order transitions;
`ledger.py` owns accepted identities and audit replay; `storage.py` locks, snapshots,
stages and commits; `reports.py` exports balances and follow-up requests; `main.py`
coordinates a complete batch. There are no handwritten Rust application adapters.
Generated Rust retains module/function names and Python source locations and is
formatted with rustfmt.

Run the shipped request once from the repository root:

```bash
py2rust-project run examples/corpus/102_inventory_ledger \
  --name inventory-ledger --offline
```

It records six transactions, exits 0 and writes `inventory.json` plus `report/`
beside `inventory-job.json`. The resulting on-hand/reserved/available quantities
are bolt 100/10/90, nut 48/6/42 and washer 70/0/70. `order1` remains active;
`order2` is cancelled. The executable in `.py2rust/rust/target/debug/inventory-ledger`
runs without Python. Each report destination must be fresh. To repeat a batch,
choose a new `output`; accepted IDs make the transactions idempotent.

`INVENTORY_CONFIG` selects the request, defaulting to `inventory-job.json` in the
working directory. Paths resolve relative to that request. An apply request has
exactly these fields:

```json
{
  "version": 1,
  "mode": "apply",
  "store": "inventory.json",
  "output": "report",
  "items": ["bolt", "nut", "washer"],
  "expected_revision": null,
  "operations": [
    {"id": "delivery", "op": "receive", "items": {"bolt": 12, "nut": 8}},
    {"id": "hold", "op": "reserve", "order": "order1", "items": {"bolt": 5, "nut": 2}}
  ]
}
```

An absent store initializes stock at zero, including with an empty batch.
Existing stores must have the same item catalog. `expected_revision` is either
null or the exact current accepted-event count; a stale revision fails the entire
request before mutation. A verification request contains only `version: 1`,
`mode: "verify"`, `store` and `output`. It requires an existing ledger, replays its
complete history, and exports results without replacing the store.

### Transactions and invariants

Item, transaction and order identifiers match `[A-Za-z][A-Za-z0-9_-]{0,31}`.
Quantities are exact integers: booleans, strings and floating values such as `1.0`
are rejected. Transaction objects permit only the documented fields.

| Operation | Additional fields | Behavior |
| --- | --- | --- |
| `receive` | `items` | Add positive quantities to on-hand stock. |
| `reserve` | `order`, `items` | Allocate positive available quantities to a new order. |
| `release` | `order`, `items` | Remove positive quantities from an active order's allocations. |
| `cancel` | `order` | Release all remaining allocations and close the order. |
| `reconcile` | `items` | Replace listed on-hand counts with nonnegative absolute counts. |

Each listed item must exist in the catalog. An `items` object must be nonempty.
Available stock is on-hand minus the sum of active allocations. Every accepted
transaction preserves nonnegative on-hand, reserved and available counts.
Reconciliation below existing reservations and any over-release are rejected.
A failed multi-item transaction leaves every item unchanged. Releases and
cancellations affect reservations, not on-hand stock; this example has no
shipment/consumption operation.

A partially released order remains active. Full release produces status
`released`; cancellation produces `cancelled`. Closed orders retain empty item
maps, remain in the ledger and cannot reuse their identifiers. An accepted
transaction ID repeated with the same validated content is a `duplicate`, even
after the order has closed. Reusing it for different content is rejected.
Validation precedes duplicate lookup. Rejected attempts do not reserve IDs and
can be corrected and resubmitted later.

Operations run in request order. Domain rejections are reported individually and
later operations continue. The accepted subset is committed together with one
atomic file replacement. Exit 0 means no rejected operations; exit 1 means one
or more domain rejections, possibly alongside committed changes. Invalid
requests, corrupt stored ledgers, revision conflicts, lock contention and
persistence failures exit 2. Normal stdout contains only accepted/duplicate/
rejected counts; errors go to stderr.

### Audit, persistence and recovery

The ledger stores its sorted catalog, revision, current state, head digest and
accepted audit events. Each record binds its sequence, previous digest, original
transaction and resulting state digest. SHA-256 covers canonical UTF-8 JSON plus
a final LF. Every invocation independently replays the accepted history and
requires the cached state to match exactly, including integer types. Duplicate
JSON keys, inconsistent hashes and invalid domain history are rejected. This
chain detects inconsistency; it does not authenticate an author who could rewrite
and recompute the complete history.

Writers and verifiers take the same nonblocking advisory lock at `store + ".lock"`.
The lock file is retained, and the kernel releases ownership on process exit.
Cooperating processes therefore serialize changes. The request and store must
be unaliased regular files and are checked before/after reads and before commit.
An absent store is published with no-replace rename; an existing store is replaced
atomically. These checks do not provide a compare-and-swap guarantee against an
uncooperative writer changing paths between the final check and rename.

Reports and any new ledger are staged and synced first. The ledger is committed
and its parent synced before the complete report directory is published with
no-replace rename and parent sync. Consequently an interruption or error after
commit can leave a committed ledger without a report. Retry with the same
accepted IDs, `expected_revision: null` or the updated revision, and a fresh
report destination. Those IDs become duplicates; their stock changes are not
applied again. A stale explicit revision remains a conflict. Rejected operations
may have a different result when retried against changed state.

Caught failures attempt to remove unpublished temporary files. Permission failures
can prevent cleanup. A hard kill may leave hidden `.inventory-state-*` or
`.inventory-report-*` entries; the application does not garbage-collect them.
They do not become ledger history or partial final reports. Failure after report
publication leaves a complete report. `INVENTORY_FAULT`, `INVENTORY_PAUSE` and
`INVENTORY_RELEASE` expose `locked`, `prepared`, `committed` and `published`
checkpoints for verification.

### Export and limits

Each report contains `ledger.json`, `report.json`, readable `report.txt`,
`replay.json`, `continue.json` and a size/SHA-256 `manifest.json`. The JSON report
contains revisions, balances, retained order states, per-operation outcomes and
the exact exported snapshot digest. An empty batch, all-duplicate/rejected batch
or verify request preserves an existing store's bytes and inode, including JSON
whitespace. The exported copy preserves those bytes too.

`replay.json` verifies the exported `ledger.json` and writes `replayed/`.
`continue.json` provides an empty apply request with that snapshot's revision and
`continued/` as destination; replace its `operations` to extend the snapshot.
This creates an independent branch of the exported state. To continue the live
ledger, use the original store path instead. An exported manifest describes the
original bundle and will no longer describe a snapshot after continuation changes
its ledger; the new continuation report includes an updated manifest.

| Bound | Limit |
| --- | --- |
| Catalog / items per operation | 32 |
| Each quantity / on-hand count | 1,000,000,000 |
| Retained orders, including closed orders | 128 |
| Operations per batch | 128 |
| Accepted history events | 512; existing accepted IDs may still be retried |
| Request | 256 KiB |
| Stored ledger / each exported file | 2 MiB |

`tools/corpus.py 102` compares both engines with an independent Counter-based
accounting model and audit oracle. Checks cover the hand-written mixed batch,
16 incremental restarts, 295 seeded attempts over 12 batches, malformed operations
and requests, 21 tampered ledgers, exact capacity boundaries, eight caught faults
and eight hard kills per engine, input/output races, competing writers/verifiers
and filesystem permissions/aliases. `tools/check_inventory_ledger.py` exercises
all eight writer/continuation/verifier engine combinations using exported files
and requests, including recovery in another engine after a committed hard kill.
The packaged compiler builds all five modules and repeats full native acceptance
with Python unavailable.

## 103: Dimensional unit converter

[Seven Python modules](103_unit_converter/main.py), 457 substantive source lines,
compile into one native executable. `units.py` defines the catalog and dimension
arithmetic, `parsing.py` parses compound expressions, `conversion.py` converts
quantities, `notebook.py` validates retained results and identifiers, and
`documents.py`, `reports.py` and `main.py` handle the complete file workflow.
Generated Rust retains module/function names and source locations. No handwritten
Rust application adapters are used.

The application introduced shared support for `float(str)` and `abs(int/float)`;
see the [numeric subset contract](../../doc/service-subset.md). These are normal
compiler/runtime capabilities available to other complete applications.

```bash
py2rust-project run examples/corpus/103_unit_converter \
  --name unit-converter --offline
```

The shipped request converts ten quantities, including 90 km/h to 25 m/s,
compound force/electrical units, volume, temperature and temperature differences.
It writes `report/` beside `units-job.json` and exits 0. `report.txt` is readable;
`notebook.json` contains the full numeric explanations. Values use binary64 and
full-precision canonical scientific notation, so results can show ordinary
floating-point rounding. The generated executable in
`.py2rust/rust/target/debug/unit-converter` runs without Python.

`UNITS_CONFIG` selects the request, defaulting to `units-job.json` in the working
directory. Paths resolve beside that request. Every output destination must be
fresh. A conversion request contains exactly:

```json
{
  "version": 1,
  "mode": "convert",
  "notebook": null,
  "output": "report",
  "conversions": [
    {"id": "speed", "quantity": "90 km/h", "to": "m/s"},
    {"id": "force", "quantity": "12 kg*m/s^2", "to": "N"}
  ]
}
```

`notebook` is null for a new notebook or the path to a previous `notebook.json`.
A verification request has only `version: 1`, `mode: "verify"`, a non-null
`notebook` path and `output`. Verification recomputes every retained conversion.

### Grammar, dimensions and numeric behavior

A quantity starts with an ASCII decimal number, followed by one or more spaces
or tabs and a unit expression. Decimal forms accept signs, decimal points,
scientific exponents and underscores between digits. NaN, infinity, hexadecimal
numbers, Unicode digits and malformed spellings are rejected. Numeric underflow
from a nonzero spelling to zero is rejected. Signed zero is normalized to zero.

The unit grammar is:

```text
expression = factor (('*' | '/') factor)*
factor     = primary ('^' signed_integer)?
primary    = symbol | '1' | '(' expression ')'
```

Multiplication and division associate from left to right. Powers bind to one
primary. Thus `m/s/s` is `m*s^-2`, while `m/(s/s)` is `m`. Multiplication must be
explicit, and repeated powers need parentheses: `(m^2)^2` is valid; `m^2^2` is
rejected. Spaces and tabs may separate tokens. Unknown symbols, implicit
multiplication, numeric coefficients inside expressions and other characters are
rejected, even when a zero power could cancel their dimensions.

Dimension vectors follow `m, kg, s, A, K, mol, cd`. Products add exponents,
division subtracts them and powers multiply them. Source and destination vectors
must match before a converted value is calculated. Reports include each side's
factor, offset, dimension vector and normalized SI expression, plus the base
value, converted value and reverse-conversion error.

The explicit catalog has 45 case-sensitive symbols:

| Quantity | Symbols |
| --- | --- |
| Length | `m`, `km`, `cm`, `mm`, `um`, `nm`, `in`, `ft`, `yd`, `mi` |
| Time | `s`, `ms`, `us`, `min`, `h`, `d` |
| Mass | `kg`, `g`, `mg`, `lb` |
| Current, amount, luminous intensity | `A`, `mA`, `mol`, `cd` |
| Temperature | `K`, `degC`, `degF`, `delta_degC`, `delta_degF` |
| Volume, frequency | `L`, `mL`, `Hz` |
| Derived mechanics/electrical units | `N`, `Pa`, `kPa`, `bar`, `atm`, `J`, `kJ`, `W`, `kW`, `C`, `V`, `ohm` |
| Dimensionless | `1` |

The catalog uses [SI base and derived unit definitions](https://www.nist.gov/pml/special-publication-811/nist-guide-si-chapter-4-two-classes-si-units-and-si-prefixes)
and [NIST SP 811 conversion factors](https://www.nist.gov/pml/special-publication-811/nist-guide-si-appendix-b-conversion-factors/nist-guide-si-appendix-b8).
Customary length units use the international foot. Prefixes are explicitly listed;
there is no automatic prefix expansion. ASCII spellings such as `um`, `ohm` and
`degC` are intentional. The bundle's `units.json` exposes every definition.

`degC` and `degF` carry offsets and must appear alone after surrounding whitespace
is trimmed. They cannot occur in products, powers or parentheses. `delta_degC`
and `delta_degF` represent temperature differences and can occur in expressions,
such as `delta_degF/min`. Temperature values are converted algebraically, including
negative values. Conversion uses `base = value * source.factor + source.offset`
and `result = (base - target.offset) / target.factor`.

The application checks the reverse conversion with tolerance
`max(1e-12, abs(input) * 1e-12)`. Conversions that exceed that error are rejected.
This tolerance describes floating-point computation; it does not model measurement
uncertainty. Exact conversion factors are represented as binary64 in the program
and checked independently against rational definitions in the acceptance suite.

### Notebooks and publication

Each notebook contains exactly `version: 1` and an `entries` array. Every entry
retains its original request and the complete result. Imported entries are
recomputed and compared in canonical JSON, including numeric types and all
explanation fields. Duplicate imported IDs, changed results, extra fields and
inconsistent dimensions are fatal errors. This is consistency checking, not
authentication of a notebook's author.

Conversion IDs match `[A-Za-z][A-Za-z0-9_-]{0,31}`. Repeating a successful ID with
the same validated request is a duplicate. Different request text under that ID
is rejected, including mathematically equivalent but differently spelled requests.
Rejected attempts reserve no ID. They appear in the report and do not become
notebook entries. Other valid rows in the same batch still succeed.

Inputs are preserved. A successful run publishes a new complete notebook bundle;
it does not replace the imported notebook. The bundle contains `notebook.json`,
`report.json`, `report.txt`, `units.json`, `replay.json`, `continue.json` and a
size/SHA-256 `manifest.json`. `replay.json` verifies the exported notebook and
writes `replayed/`. `continue.json` is an empty conversion request using that
notebook and `continued/` as output; fill in its `conversions` to extend the history.
Both follow-ups consume the actual exported notebook. Old bundles remain intact.

Files are bounded, unaliased regular inputs. Their snapshots are checked before
and after reads and again before publication. Complete output files are written
and synced in a sibling staging directory, then published with no-replace rename
and parent sync. An existing or competing output is preserved. Caught failures
attempt cleanup; denied cleanup or hard termination can leave hidden `.units-*`
staging. Final output is absent or complete. `UNITS_FAULT`, `UNITS_PAUSE` and
`UNITS_RELEASE` expose `staged` and `published` checkpoints for acceptance checks.

Exit 0 means no rejected conversions. Exit 1 means some rows were rejected, with
all successful rows included in the completed bundle. Exit 2 means a request,
import or publication failure; a failure after publication can leave a complete
bundle. Normal stdout contains conversion/duplicate/rejection counts.

| Bound | Limit |
| --- | --- |
| Quantity text / each unit expression | 256 / 128 characters |
| Unit tokens / parenthesis depth | 96 / 8 |
| Individual power / accumulated dimension magnitude | 8 / 32 |
| Unit factor at every intermediate step | `1e-100` through `1e100` in binary64 |
| Input/result magnitude | Zero or `1e-100` through `1e100` |
| Conversions per request / retained entries | 64 / 256 |
| Request / imported notebook / each exported file | 64 KiB / 1 MiB / 1 MiB |

Intermediate limits apply before later cancellation. Previously accepted IDs can
still be retried when the notebook has reached its entry limit.

`tools/corpus.py 103` checks both engines against an independent rational-factor,
dimension-vector and AST oracle: 28 hand conversions, 13 golden identities, all
45 catalog units, 384 generated compound conversions and 384 reverse conversions
using their actual results. It also checks malformed inputs, 17 altered notebooks,
numeric types, exact size/capacity limits, publication races/interruption and
filesystem protections. `tools/check_unit_converter.py` exercises all eight
writer/continuation/verifier combinations with exported notebooks and requests.
The packaged compiler builds all seven modules and repeats native acceptance
with Python unavailable.

## 104: Series/parallel circuit calculator

[Five Python modules](104_circuit_calculator/main.py), 381 substantive source lines,
compile into one standalone Rust executable. `model.py` validates a recursive
`Node` dataclass, `reduction.py` computes every subtree, `reports.py` explains the
results, and `documents.py` and `main.py` implement the input and publication
workflow. Every application module is transpiled; there are no native adapters.
The generated Rust retains module/function names and Python source locations.

This application added one-argument `min(sequence)` and `max(sequence)` to the
shared compiler. Typed lists and homogeneous tuples of integers, finite floats,
strings and booleans work, including recoverable empty-input errors, single
collection evaluation and first-item tie handling. See the
[numeric/collection contract](../../doc/service-subset.md).

```bash
py2rust-project run examples/corpus/104_circuit_calculator \
  --name circuit-calculator --offline
```

The supplied six circuits include a 650-ohm series chain, a 75-ohm parallel pair,
a nested 25-ohm circuit and open/short branches. The command writes `report/`
beside `circuit-job.json`; choose a new output directory for another run. The
native executable in `.py2rust/rust/target/debug/circuit-calculator` runs without
Python. `CIRCUIT_CONFIG` selects a different request; relative paths resolve beside
that request. The default request is:

```json
{"version": 1, "mode": "solve", "input": "networks.json", "output": "report"}
```

A network document contains exactly `version: 1` and `cases`. Each case has a
unique ASCII `id` and a `tree`. For example:

```json
{
  "version": 1,
  "cases": [{
    "id": "parallel_pair",
    "tree": {
      "id": "pair", "kind": "parallel",
      "children": [
        {"id": "left", "kind": "resistor", "ohms": "100"},
        {"id": "right", "kind": "resistor", "ohms": "300"}
      ]
    }
  }]
}
```

This is an ideal DC resistor tree. The five node kinds are `resistor`, `open`,
`short`, `series` and `parallel`. Resistors contain exactly `id`, `kind` and `ohms`;
open/short leaves contain only `id` and `kind`; groups contain `id`, `kind` and
`children`. Node identifiers are unique within each circuit and match
`[A-Za-z][A-Za-z0-9_-]{0,31}`. Unknown fields are rejected. Arbitrary graphs,
voltage sources, reactive elements and transient simulation are outside this
application's scope.

Resistance is an ASCII decimal **string in ohms**, allowing a sign, decimal point,
exponent and underscores between digits. Whitespace is rejected. Zero, including
negative zero, denotes a short. Nonzero resistance must parse as a finite binary64
value in `1e-100..1e100`. Negative values, nonfinite names, overflow, out-of-range
values and nonzero decimal spellings that underflow to zero are rejected. Explicit
open circuits use an `open` state and JSON `null` resistance, not infinity.

- Series: an open branch makes the group open; shorts add zero resistance; all
  shorts produce a short.
- Parallel: a short branch makes the group short; open branches contribute no
  conductance; all opens produce an open circuit.
- Every branch is validated and every subtree is reduced, even when another
  branch determines an open/short result. Invalid components cannot be hidden
  behind a simplifying branch.

For finite series groups the scale is the largest child resistance and the
calculation is `scale * sum(R / scale)`. For finite parallel groups it is the
smallest resistance and the calculation is `scale / sum(scale / R)`. Compensated
sums reduce rounding loss. The positive resistance and tree-size bounds keep all
intermediate values finite, including extreme resistance ratios. Values use
binary64 arithmetic and full-precision canonical JSON; ordinary floating-point
rounding is visible. The acceptance oracle uses exact rational series sums and
reciprocal parallel sums and checks every positive result to relative tolerance
`2e-13`.

Each solved circuit records a postorder list of every reduction, with child IDs,
child equivalents, the selected rule, scale, normalized terms and normalized sum.
The root equivalent, node count and step ordering are checked independently. A
bad tree produces a per-case diagnostic and later circuits still run. Malformed
requests, document envelopes, case identities and duplicate case IDs reject the
whole request before publication.

The output bundle contains:

- `archive.json`: original cases and all recomputable results, including rejected
  cases.
- `networks.json`: portable source circuits.
- `report.json` and `report.txt`: totals, archive digest and readable reductions.
- `replay.json`: a `verify` request that loads the actual archive and recomputes
  every result, requiring byte-identical canonical result data, including numeric
  types. This validates consistency; it is not an authenticity signature.
- `solve.json`: a request to solve the exported networks again.
- `manifest.json`: sizes and SHA-256 hashes for the other files.

Verification also replays rejected cases and their diagnostics. Editing a source
network and solving it creates a fresh archive; imported files are preserved.
Each destination must be absent. Inputs are bounded, unaliased regular files and
are checked for changes around reads and before publication. The complete bundle
is synced in a staging directory, renamed without replacing an existing target,
and its parent is synced. Caught errors attempt staging cleanup; a hard kill or
cleanup permission failure can leave a `.circuit-*` directory. The final bundle
is absent or complete. A failure after publication can leave a complete bundle
and a nonzero exit status. `CIRCUIT_FAULT`, `CIRCUIT_PAUSE` and `CIRCUIT_RELEASE`
expose the `staged`/`published` boundaries for recovery tests.

Exit statuses are **0** for all circuits solved, **1** for a published report with
one or more rejected trees, and **2** for a request, archive or publication error.
The request/source version is a strict integer; booleans and floats are rejected.

| Bound | Limit |
| --- | --- |
| Cases per document | 1–16 |
| Nodes per circuit | 256 |
| Tree depth, root at zero | 16 |
| Children per series/parallel group | 2–16 |
| Identifier / resistance spelling | 32 / 64 characters |
| Request / network document | 64 KiB / 1 MiB |
| Imported archive / each exported file | 4 MiB |

`tools/corpus.py 104` checks both engines against 16 analytic circuits and 384
seeded circuits, including 192 branch-permutation pairs and 4,914 generated
reduction nodes. It checks 46 invalid trees, continued calculation after errors,
malformed requests/documents, 15 tampered archives, exact limits, two caught
publication failures, two hard kills, three input/output races and filesystem
protections. `tools/check_circuit_calculator.py` runs all eight writer/replayer/
resolver engine combinations on actual exported files, then edits an exported
network and replays the new result in another engine. The packaged compiler
repeats native acceptance with Python unavailable.

## 105: Telemetry trend analyzer

[Six Python modules](105_telemetry_analyzer/main.py), 458 substantive source lines,
compile into a standalone Rust executable. `model.py` validates samples and
settings, `statistics.py` computes stable moments, `analysis.py` manages windows
and gaps, `reports.py` exports results, and `documents.py` and `main.py` handle the
complete file workflow. All six modules are transpiled with readable names and
source locations in the Rust output; no native application adapters are used.

The application added shared `math.sqrt` / `math_sqrt` support and
`datetime_unix_microseconds`. The latter converts a supported UTC timestamp to an
exact signed integer without rounding through floating-point seconds. Negative
fractional timestamps and the full supported calendar are covered by regression
tests. The square-root operation supports nonnegative finite inputs, preserves
signed zero and reports negative arguments as recoverable errors.

```bash
py2rust-project run examples/corpus/105_telemetry_analyzer \
  --name telemetry-analyzer --offline
```

The supplied input has latency, constant-value and empty series. It produces a
`report/` directory beside `trend-job.json`, containing a concise text report and
full per-sample explanations. Choose a fresh destination for subsequent runs.
The resulting `.py2rust/rust/target/debug/telemetry-analyzer` runs without Python.
`TREND_CONFIG` selects a request; paths resolve beside that request. Its schema is:

```json
{"version": 1, "mode": "analyze", "input": "telemetry.json", "output": "report"}
```

A source document contains exactly `version`, `settings` and `series`:

```json
{
  "version": 1,
  "settings": {"window": 4, "warmup": 3, "gap_us": 3000000, "sigma": 3},
  "series": [{
    "id": "latency_ms",
    "samples": [
      {"at": "2026-01-01T00:00:00Z", "value": 10},
      {"at": "2026-01-01T00:00:01Z", "value": 11},
      {"at": "2026-01-01T00:00:02Z", "value": 9},
      {"at": "2026-01-01T00:00:03Z", "value": 50}
    ]
  }]
}
```

Series IDs are unique and match `[A-Za-z][A-Za-z0-9_-]{0,31}`. Samples contain
exactly `at` and `value`. Timestamps use strict RFC3339 with an explicit offset
and at most six fractional digits. They are normalized to UTC and must be
strictly increasing within each series. Equivalent instants with different
offsets are duplicates. The application rejects unordered data instead of
silently reordering observations. Calendar years 0001–9999 are supported when
the normalized UTC instant remains in that range.

Values may be JSON numbers or ASCII decimal strings. Decimal strings allow a
sign, exponent and underscores between digits, with no whitespace. Values are
interpreted as binary64: zero is allowed and nonzero magnitudes must lie in
`1e-100..1e100`. Signed zero is normalized to positive zero. Nonfinite values,
booleans and other JSON types are rejected. Decimal strings additionally reject
nonzero spellings that underflow to zero. Numeric JSON tokens have already been
converted by the JSON parser; a token that underflows to zero is consequently
handled as zero. JSON integers follow the shared signed-64-bit input limit.

The windows are based on **sample count**, not elapsed duration. Before testing a
sample, the baseline contains at most the preceding `window` observations from
the current segment. The current sample is excluded from its own baseline. A
gap occurs only when the integer elapsed microseconds are **greater than**
`gap_us`; equality is not a gap. A gap resets the baseline before that sample is
tested. Every value, including an outlier, then enters the trailing window.

Outlier decisions are explicit:

- Fewer than `warmup` baseline samples produces `warming`, with no score.
- A constant baseline produces `within` for an unchanged value or
  `constant_shift` for a changed value. Its threshold is zero and its z-score is
  null, avoiding division by zero.
- Otherwise, `abs(deviation) > sigma * standard_deviation` produces `outlier`;
  equality produces `within`. The reported binary64 deviation and threshold
  determine the decision. A neighboring input can round onto the threshold during
  arithmetic; the acceptance suite includes this case and values beyond it.

Statistics use **population variance**. Empty series have zero samples and
segments, null moments and no gaps/outliers. A single value has zero variance.
Compensated sums compute the mean, while a centered two-pass calculation computes
variance. The center is represented as an origin plus a small mean offset, so
values such as `1e16` and `1e16 + 2` correctly produce variance `1`, even though
their mathematical mean is not representable as one binary64 value. Decisions
also use that split center. Each sample exposes its normalized timestamp, elapsed
time, segment, baseline index bounds and moments, decision, and resulting window
bounds and moments. Series totals include statistics over all valid samples
across every segment.

These are floating-point statistics, not arbitrary-precision results. Canonical
JSON retains full binary64 precision. The independent oracle interprets the
parsed input floats as exact rational values and uses an 80-digit decimal square
root. It checks variance and standard deviation to relative tolerance `2e-12`,
mean to the larger of eight result ULPs and `5e-15` times the largest input
magnitude, and the split center to `2e-14` times the window span. Exact analytic
fixtures additionally check cancellation, small variance at large offsets,
threshold equality, warmup boundaries and microsecond timing.

Malformed settings, envelopes and series identities reject the whole request.
An invalid sample rejects its complete series with a diagnostic; later independent
series still run. Unknown fields are rejected. Empty documents (`series: []`) are
valid. Exit status **0** means every series was analyzed, **1** means a complete
report includes rejected series, and **2** means a request, archive or publication
failure. Detected outliers and gaps are ordinary results and do not cause failure.

The exported bundle contains `archive.json` (original source and recomputable
results), `telemetry.json` (portable source), `report.json`, `report.txt`,
`replay.json`, `analyze.json` and `manifest.json`. Replay recomputes actual imported
source and requires byte-identical canonical results, including numeric types
and rejected-series diagnostics. Reanalysis uses the exported source directly.
This checks consistency, not authenticity. Editing exported settings or samples
and analyzing again produces a fresh archive; imported files are preserved.

Inputs must be bounded, unaliased regular files. The complete output is synced in
a staging directory, checked against unchanged input snapshots, renamed without
replacing an existing destination, and its parent is synced. Caught failures
attempt cleanup. A hard kill or cleanup permission failure can leave a
`.trend-*` directory; the final output is absent or complete. Failure after
publication can leave a complete output with a nonzero exit status.
`TREND_FAULT`, `TREND_PAUSE` and `TREND_RELEASE` expose the `staged` and `published`
checkpoints for recovery tests.

| Bound | Limit |
| --- | --- |
| Series / total samples | 8 / 4,096 |
| Window / warmup | 2–256 / 2–window |
| Gap threshold | 1–86,400,000,000 microseconds |
| Sigma multiplier | 0.1–20 |
| Identifier / numeric string / timestamp spelling | 32 / 64 / 40 characters |
| Request / source | 64 KiB / 2 MiB |
| Imported archive / each exported file | 16 MiB |

`tools/corpus.py 105` checks both engines against eight hand-written series,
five threshold-boundary cases and 128 generated series containing 4,096 samples,
including 64 power-of-two scaling pairs, 256 gaps and 492 outliers. Every window,
center, score and index boundary is checked independently. Coverage includes
47 invalid series, continued processing and replay of rejections, malformed
settings/requests, 18 tampered archives, full capacity, publication interruptions,
races and filesystem permissions. `tools/check_telemetry_analyzer.py` exercises
all eight writer/replayer/analyzer combinations using actual exported artifacts,
then changes settings and appends a sample before replaying the new result in
another engine. The packaged compiler repeats full native acceptance with Python
unavailable.


## 106: Electricity-tariff simulator

[Five Python modules](106_tariff_simulator/main.py), 423 substantive source lines,
compile as one standalone Linux x86-64 Rust executable. Application policy,
validation, band/tier allocation, comparison and reports are all Python source.
The shared `Rational` runtime provides exact arithmetic; there are no native
application adapters.

```bash
mkdir -p /tmp/tariff-example
cp examples/corpus/106_tariff_simulator/{tariff-job.json,usage.json} /tmp/tariff-example/
TARIFF_CONFIG=/tmp/tariff-example/tariff-job.json \
  py2rust-project run examples/corpus/106_tariff_simulator \
  -o build/tariff-example --name tariff-simulator --offline
cat /tmp/tariff-example/report/report.txt
```

The request contains exactly `version: 1`, `mode` (`simulate` or `verify`),
`input` and `output`. Paths are relative to the request file. `TARIFF_CONFIG`
defaults to `tariff-job.json`. Output must be a new directory.

A source document contains exactly `version: 1`, `period`, `intervals` and
`tariffs`. The shipped [usage.json](106_tariff_simulator/usage.json) is a complete
example with three fictional tariffs. All tariffs use the same abstract currency.

- `period` has RFC3339 `start` and `end` with explicit offsets. Times normalize
  to UTC and must represent whole seconds. The period is positive and at most
  31 days; endpoints are inclusive start, exclusive end.
- Each interval contains `start`, `end` and `kwh`. Intervals are positive-length,
  ordered, disjoint and contained in the period. Gaps and zero consumption are
  allowed. Energy is distributed uniformly over each interval's duration.
- Each tariff contains a unique ASCII `id`, one fixed period `fee`, daily UTC
  `bands`, and chronological cumulative-energy `tiers`. Bands contain
  `start_second` and `rate` (currency/kWh); starts increase strictly from zero
  through at most 86399. A band runs until the next start or UTC midnight.
- Tiers contain `up_to_kwh` and `surcharge` (currency/kWh). Finite thresholds
  increase strictly from zero; exactly the last tier has a null threshold.
  The tier surcharge adds to the current band's rate. Tier consumption begins
  at zero at the explicit billing-period start and continues across days and gaps.
- Decimal inputs are strings with up to nine integer digits and six fractional
  digits, no sign, leading zeros (except zero), whitespace or exponent. Maximums
  are 1,000,000 kWh per interval, 1,000,000 currency units for the fee, 1,000 for
  each rate/surcharge, and 256,000,000 kWh for a finite tier threshold.

Each interval is split at band boundaries. Exact rational energy in each segment
is then split at tier thresholds. No segment or allocation is rounded. The fee
is added once and only the final bill is rounded to two decimal places, ties to
even. Splitting a uniform interval into equivalent valid input intervals
preserves the exact total. Comparison uses exact totals, followed by identifier
for deterministic tie ordering; all exact cheapest ties are reported. Displayed
rounded totals may tie even when exact prices differ.

The archive stores normalized segment times, interval and band indices, exact
energy and charge fractions, and each tier allocation's energy, rate and cost.
Fraction fields have canonical decimal-string `numerator` and positive
`denominator`. Empty consumption produces the fixed fee. Zero-energy segments
remain visible with empty allocations. Malformed definitions reject the entire
request before any bill directory is published.

Limits are 256 intervals, eight tariffs, 16 daily bands and eight tiers per
tariff. Request/source inputs are at most 64 KiB/2 MiB; imported archives and
individual exports are at most 16 MiB. Validation precedes calculation. The
shared rational bounds comfortably cover these application limits.

The output includes `archive.json`, `usage.json`, `report.json`, `report.txt`,
`manifest.json` and usable `replay.json`/`simulate.json` requests. Verification
recomputes the source and compares canonical results, including numeric types.
This proves consistency, not authenticity. Inputs stay unchanged. Input snapshots
must be unaliased regular files and are rechecked before publication. Files are
synced in a staging directory and published with a no-replace rename. Caught
failures attempt cleanup; a hard kill can leave a `.tariff-*` staging directory.
The final directory is absent or complete. Exit 0 means success; exit 2 means
validation/I/O failure, including an injected failure after complete publication.
`TARIFF_FAULT`, `TARIFF_PAUSE` and `TARIFF_RELEASE` exercise staged/published boundaries.

`tools/corpus.py 106` checks both engines against hand-calculated bills, 24 seeded
schedules with 96 tariffs and 768 intervals, 3,518 time segments and 3,874 tier
allocations. An independent `Fraction` oracle intersects time ranges and
cumulative-energy ranges. Twelve equivalent partitionings preserve exact bills.
Checks include five rounding ties/boundaries, 28-digit denominators, 126 invalid
sources, altered archives, all resource limits, offset/calendar boundaries,
real permission failures, publication races and killed processes.
`tools/check_tariff_simulator.py` exchanges actual archives and exported requests
across eight Python/Rust writer/replayer/simulator combinations, edits consumption
and tariff prices, and verifies the changed ranking and replay.

## 107: Recipe and shopping-list scaler

[Six Python modules](107_recipe_scaler/main.py), 441 substantive source lines,
transpile together into one Rust executable. The application resizes recipes,
converts mass, volume and count units exactly, and combines a seven-day plan into
a shopping list. All validation, arithmetic, grouping, provenance and export
policy are Python source; this application has no native adapter modules.

From the repository root, copy the supplied source and request into a fresh
working directory and build/run the whole project with one command:

```bash
mkdir -p /tmp/recipe-example
cp examples/corpus/107_recipe_scaler/{recipe-job.json,cookbook.json} /tmp/recipe-example/
RECIPE_CONFIG=/tmp/recipe-example/recipe-job.json \
  py2rust-project run examples/corpus/107_recipe_scaler \
  -o build/recipe-example --name recipe-scaler --offline
cat /tmp/recipe-example/report/shopping.txt
```

The compiled executable accepts the same `RECIPE_CONFIG` environment variable
and needs no Python installation. The default request is `recipe-job.json` in
the current directory. Paths are resolved relative to the request directory;
the output directory must not exist. Success prints a JSON summary and exits 0;
errors are logged to stderr and exit 2.

A request has exactly `version: 1`, `mode`, `input` and `output`. Mode `plan`
reads a cookbook; `verify` recomputes an exported archive and checks the complete
cached result, including numeric types, before publishing another bundle.
The [sample cookbook](107_recipe_scaler/cookbook.json) has three recipes and four
plan selections, producing seven shopping rows.

The cookbook has exactly `version: 1`, `week_start`, `recipes` and `plan`:

- `week_start` is a valid `YYYY-MM-DD` date anchoring seven consecutive days. It
  need not be Monday; all seven dates must fit years 0001–9999.
- Each recipe has `id`, `title`, `servings`, and `ingredients`. IDs are unique
  ASCII identifiers matching `[A-Za-z][A-Za-z0-9_-]{0,31}`.
- Each ingredient has `name`, `quantity`, and `unit`. Servings and quantities are
  strings: unsigned decimal (`1.25`), fraction (`5/4`) or mixed quantity
  (`1 1/4`, with exactly one space and a proper fractional part). Denominators
  are positive; servings are positive and ingredient quantities may be zero.
  Signs, exponent notation, Unicode digits and other whitespace are rejected.
- Each plan selection has `day` (integer 0–6), an existing `recipe` ID, and
  positive `portions` in the same exact quantity grammar. Repeated recipes,
  repeated days, zero-ingredient recipes and empty plans are supported.

Supported units and their exact base-unit factors are:

| Dimension | Base | Factors |
| --- | --- | --- |
| Mass | g | mg = 1/1000, g = 1, kg = 1000 |
| Volume | mL | mL = 1, cL = 10, L = 1000 |
| Count | piece | piece = 1, dozen = 12 |

Unit symbols are case-sensitive. There are no density conversions: an ingredient
measured in grams and millilitres remains in separate shopping rows. Quantities
use reduced rational arithmetic throughout; output is an integer or `n/d`, never
a rounded decimal.

Ingredient identity is NFKC normalization, collapsed whitespace, then Unicode
case folding. Thus `MILK` and fullwidth `ｍｉｌｋ`, or `Straße` and `STRASSE`, share
an identity. Shopping rows sort by identity and base unit, using the first
normalized display name. Original names, units, ingredient order and plan order
are preserved in scaled recipes. Every shopping contribution points to its plan
selection, recipe ID and original ingredient index. Titles/names have 1–100
Unicode characters before and after display normalization. Non-whitespace C0/C1
controls remaining in normalized display names are rejected.

Bounds are 32 recipes, 256 total ingredients, 64 plan selections, 256 characters
per numeric spelling and 8,192 numeric characters across the complete input.
Every recipe is validated, including unused recipes. Requests are at most
64 KiB, cookbook files 2 MiB, and imported archives and individual exports 16 MiB.
Generated scaled recipes must satisfy the same input schema and numeric bounds;
an otherwise valid source that would produce an unusable scaled export fails
before publication. A shopping total may be larger than an individual recipe
quantity: the acceptance test checks an exact total with a 7,396-digit denominator.

The output directory contains `cookbook.json`, `archive.json`, `report.json`,
`shopping.txt`, a byte-count/SHA-256 manifest, and actual `replay.json` and
`plan.json` requests. Every selection also has `scaled-N.json` and
`scaled-N-job.json`: a single-recipe cookbook and a usable request for that
scaled yield. Consume the exported request unchanged to retain that yield, or
edit its source's plan `portions` to scale again. Restoring the original yield
recovers the original ingredient quantities exactly, including nonterminating
fractional factors.

Publication checks regular unaliased input snapshots, synchronizes staged files,
rechecks the input stamps, then uses a no-replace directory rename. An existing
output is preserved. Caught errors attempt staging cleanup; a hard kill before
publication can leave a `.recipe-*` staging directory, while the final output
remains absent or complete. These checks assume a cooperative local filesystem;
they do not promise race-free traversal through hostile parent directories.

`tools/corpus.py 107` checks both engines against hand totals and an independent
`Fraction` oracle over 128 seeded recipes, 256 selections and 2,048 contributions.
It restores 48 generated scaled recipes, checks 16 equivalent split selections,
153 invalid sources, strict archive tampering, exact/over-limit inputs, all
16,384 contributions in a maximum plan, interruption/retry and path permissions.
`tools/check_recipe_scaler.py` exercises all eight Python/Rust writer, replayer
and planner combinations using actual exported requests and recipes, including
changed units/quantities/portions and reverse scaling to each original yield.

## 108: Tournament standings manager

[Five Python modules](108_tournament_standings/main.py), 387 substantive source
lines, transpile into one Rust executable. The application validates registered
teams and fixtures, recomputes a standings table, and exports reusable fixture
files. All application policy is in Python source; there are no native adapters.
The existing compiler supports the required records, nested collections, keyed
sorting, integer arithmetic, JSON and filesystem operations.

From the repository root:

```bash
mkdir -p /tmp/tournament-example
cp examples/corpus/108_tournament_standings/{tournament-job.json,fixtures.json} /tmp/tournament-example/
TOURNAMENT_CONFIG=/tmp/tournament-example/tournament-job.json \
  py2rust-project run examples/corpus/108_tournament_standings \
  -o build/tournament-example --name tournament-standings --offline
cat /tmp/tournament-example/report/table.txt
```

The compiled executable accepts the same `TOURNAMENT_CONFIG` variable and runs
without Python. Its default request is `tournament-job.json` in the current
directory. Each request has exactly `version: 1`, `mode`, `input` and `output`;
paths are relative to the request file's directory. Mode `rank` reads a fixture
source. Mode `verify` recomputes an archive and checks every cached field, with
strict JSON numeric types. The output directory must be new. Success prints a
JSON summary and exits 0; failures log to stderr and exit 2.

The [sample fixture file](108_tournament_standings/fixtures.json) contains four
teams, six scheduled fixtures and five completed results. Source fields are
exactly `version: 1`, `title`, `teams` and `fixtures`:

- Teams contain a unique `id` and display `name`.
- Fixtures contain a unique `id`, distinct registered `home` and `away` team IDs,
  and `home_score` and `away_score`.
- Both scores being null means unplayed. Otherwise both must be integers from
  0 through 10,000; booleans, floats, strings and a single null are rejected.
- Each unordered team pair may appear once, in either orientation. Missing
  pairings are allowed and counted as unscheduled. This is a single round robin;
  a home-and-away season is outside this example's format.
- Team and fixture IDs are case-sensitive ASCII strings matching
  `[A-Za-z][A-Za-z0-9_-]{0,31}`. Names are labels, so two teams may share a name.

A win earns three points, a draw one, and a loss zero. The sporting order is
points, goal difference, then goals scored, all descending. Teams equal on all
three share a competition rank: `1, 1, 3`, rather than receiving separate ranks.
Ascending team ID gives these tied rows a deterministic display order. There is
no head-to-head or alphabetical-name tie breaker. The `leaders` array means
teams currently sharing rank 1; it does not declare a finished-season champion.

Every registered team appears, including teams with no completed matches.
Empty, partially scheduled and entirely unplayed seasons are valid. The results
include possible pairings, scheduled/played/unplayed/unscheduled counts, draws,
and each team's played/won/drawn/lost, goals for/against/difference, points and
rank. Per-team contributions identify each completed fixture, opponent, score,
points and outcome in the input fixture order. Reordering fixtures may reorder
this provenance while leaving sporting metrics unchanged.

Titles and names contain 1–100 Unicode characters, both before and after NFKC
normalization and whitespace collapse. Original spelling is preserved in JSON;
the text table uses the normalized, single-line display. C0/C1 controls remaining
after that normalization are rejected. Limits are 32 teams and 496 fixtures,
with a 64 KiB request, 2 MiB source and 16 MiB archive/individual-export limit.
The maximum schedule contains 992 team contributions. A team can score 310,000
goals and earn 93 points within these limits; all arithmetic remains integral.

The output bundle contains `fixtures.json`, `standings.json`, `archive.json`,
`table.txt`, `report.json`, a byte-count/SHA-256 manifest, and usable `rank.json`
and `replay.json` requests. Edit the actual exported fixture scores and run its
ranking request to recompute the entire table. The request's output must still
be a new directory. Changing a result can create or break shared ranks; reverting
scores restores the original archive exactly. Input files are preserved.

Publication reads bounded regular unaliased files, checks their metadata before
and after reading, synchronizes staged files, rechecks the inputs and performs
a no-replace directory rename. Existing output is preserved. Caught failures
attempt staging cleanup; a hard kill may leave a `.tournament-*` directory while
the final output remains absent or complete. The checks assume cooperative local
parent directories, not hostile concurrent path traversal.

`tools/corpus.py 108` checks nine hand seasons, every tie-break level, and three
edits that create, break and restore ties. Its independent oracle scans fixtures
separately for each team and assigns ranks by counting strictly stronger teams.
It also checks conservation of wins/losses, goals and points. Thirty-two seeded
seasons contain 1,084 scheduled fixtures and 789 played matches; every season is
reordered, reversed home/away, edited through a real export and replayed. Other
checks cover 132 invalid sources, strict archive tampering, all resource
boundaries, 32 simultaneous tied leaders, interruptions, retries and permissions.

`tools/check_tournament_standings.py` runs all eight Python/Rust writer, replayer
and ranker combinations. Each consumes actual exported files, creates and breaks
a shared second place, replays the revised table, and restores the original
season. Packaged native acceptance and the one-command CLI build are also checked.

## 109: Warehouse movement simulator

[Five Python modules](109_warehouse_simulator/main.py), 403 substantive source
lines, transpile into one Rust executable without native adapters. The application
validates a grid and command program, simulates robot movement and single-box
pushes, and exports a complete trace with reusable continuation and rewind
programs. The compiler now supports direct nested list assignments such as
`grid[row][column] = "@"`, including negative indices and ordered bounds checks.
The generated Rust updates the corresponding owned grid in place.

From the repository root:

```bash
mkdir -p /tmp/warehouse-example
cp examples/corpus/109_warehouse_simulator/{warehouse-job.json,program.json} /tmp/warehouse-example/
WAREHOUSE_CONFIG=/tmp/warehouse-example/warehouse-job.json \
  py2rust-project run examples/corpus/109_warehouse_simulator \
  -o build/warehouse-example --name warehouse-simulator --offline
cat /tmp/warehouse-example/report/layout.txt
```

The executable uses the same `WAREHOUSE_CONFIG` variable and runs without Python.
The default request is `warehouse-job.json` in the current directory. Requests
contain exactly `version: 1`, `mode`, `input` and `output`, with paths relative to
the request's directory. Mode `simulate` reads a program; `verify` recomputes an
archive and checks every cached field, including strict JSON numeric types. The
output directory must be new. Success prints a JSON summary and exits 0; failures
log to stderr and exit 2.

The [sample program](109_warehouse_simulator/program.json) has exactly
`version: 1`, `title`, `grid` and `commands`. Grid rows are equal-width strings
using `#` for walls, `.` for floor, `@` for the single robot and `$` for boxes.
Commands are `up`, `down`, `left`, `right` and `undo`. The entire program is
validated before simulation. Grid boundaries need not contain walls.

A move enters floor or pushes one adjacent box onto floor. A wall, an edge or a
second box prevents movement. Each successful forward move adds one compact undo
record. Undo restores that move's complete previous geometry, including a pushed
box, and removes its record. Blocked moves leave geometry and history unchanged;
undo with empty history is also blocked. There is no redo operation.

Every trace entry contains its zero-based command index, command, action, reason
and resulting state. Actions are `move`, `push`, `undo_move`, `undo_push` and
`blocked`; block reasons are `boundary`, `wall`, `box_boundary`, `box_wall`,
`box_chain` and `empty_history`. A successful action has an empty reason. States
include the grid, robot coordinates, row-major box coordinates and history depth.
Coordinates are zero-based `[row, column]`. The summary separately counts walks,
pushes, successful undos and blocked commands; walks exclude pushes. The active
command list contains the successful directions still represented in undo history.

The bundle has 14 files, including a byte-count/SHA-256 manifest:

- `archive.json`, `program.json`, `trace.json`, `report.json` and `layout.txt`
  preserve the original program, full results, summary and final text layout.
- `replay.json` verifies the archive; `simulate.json` reruns the original program.
- `continuation.json` starts from the original grid and replays only active
  successful moves. Its `continue-job.json` request recovers the same final
  geometry and undo depth. Append commands to this exported program to continue.
  The shorter trace and event counters differ from the original when it contained
  blocked or undone moves.
- `rewind.json` appends one undo per active move to that compact continuation.
  Its `rewind-job.json` request restores the exact original grid and empty history.
- `layout.json` starts from the final grid with no commands. Its `restart-job.json`
  request starts a new history at that geometry.

Bounds are 32 rows, 32 columns, 64 boxes, 2,048 commands and 1,024 active undo
records. Attempting a 1,025th active move fails before publication. The command
limit accommodates a full 1,024-move continuation followed by its complete rewind;
every exported program is validated against the input schema. Titles contain
1–100 Unicode characters before and after NFKC normalization and whitespace
collapse. Original spelling is retained in JSON; text output uses the normalized
display, rejecting any remaining C0/C1 controls. Requests are at most 64 KiB,
source programs 2 MiB, and archives and individual exports 16 MiB.

Publication checks regular unaliased input snapshots, synchronizes staged files,
rechecks input metadata and uses a no-replace directory rename. Existing output
is preserved. Caught failures attempt staging cleanup; a hard kill may leave a
`.warehouse-*` directory while the final output stays absent or complete. The
checks assume cooperative local parent directories.

`tools/corpus.py 109` checks 12 hand programs, pushes in all four directions,
every block reason, and actual exported requests. An independent oracle uses
coordinate sets and complete prior-state snapshots instead of the application's
mutable grid and inverse move records. Twenty-four seeded programs and their
rotations cover 8,448 trace steps, with state invariants checked after every step.
Checks also cover 68 invalid sources, 13 archive mutations, maximum grids and
history, a full 2,048-command rewind, byte limits, interrupted publication, retries
and path permissions. `tools/check_warehouse_simulator.py` exercises all eight
Python/Rust writer, replayer and simulator combinations, editing real continuation
exports and restoring original layouts. Packaged native acceptance and the
one-command whole-project CLI build are checked separately.

## 110: Population simulation runner

[Six Python modules](110_population_simulator/main.py), 431 substantive source
lines, transpile into one Rust executable with no native adapters. The application
integrates exponential and logistic growth, compares parameter sets, and exports
full-precision series, CSV and a shared-scale SVG plot. It uses the existing
compiler's floating-point arithmetic, records, JSON and filesystem support.

From the repository root:

```bash
mkdir -p /tmp/population-example
cp examples/corpus/110_population_simulator/{population-job.json,experiment.json} /tmp/population-example/
POPULATION_CONFIG=/tmp/population-example/population-job.json \
  py2rust-project run examples/corpus/110_population_simulator \
  -o build/population-example --name population-simulator --offline
```

Open `/tmp/population-example/report/plot.svg` to view the comparison. The native
executable accepts the same `POPULATION_CONFIG` variable and runs without Python.
Its default request is `population-job.json` in the current directory. Requests
contain exactly `version: 1`, `mode`, `input` and `output`, with paths relative to
the request directory. Mode `simulate` reads an experiment; `verify` recomputes an
archive and checks every cached field. Output must be a new directory. Success
prints a JSON summary and exits 0; failures log to stderr and exit 2.

An experiment contains exactly `version: 1`, `title`, `timestep`, `steps` and
`cases`. Each case contains a unique ASCII `id`, a display `name`, `model`,
`initial`, `rate` and `capacity`:

- `exponential` solves `dN/dt = rate * N`; capacity must be null.
- `logistic` solves `dN/dt = rate * N * (1 - N/capacity)`; capacity is positive.
- Rates may be positive, zero or negative. Logistic runs may start above capacity.
  Positive-rate populations approach capacity from either side. A negative rate
  above capacity can approach a finite-time singularity and fail the stage guard.
- IDs match `[A-Za-z][A-Za-z0-9_-]{0,31}`. Names and titles preserve their original
  Unicode spelling in JSON. Labels in SVG use NFKC and collapsed whitespace,
  escape XML characters, and shorten visible text with full text in tooltips.

Integration uses classical fourth-order Runge–Kutta with a fixed timestep. Time
points are computed as `index * timestep`, including the initial state at time
zero. Every intermediate stage and final step must have a finite population
between zero and `1e100`. The stage factor must satisfy
`abs(rate) * timestep * max(1, N/capacity) <= 0.05` for logistic models, or
`abs(rate) * timestep <= 0.05` for exponential models. The initial state is checked
even for zero-step experiments. A failing stage rejects the complete job before
publication; populations are never silently clamped. This guard defines an
accepted numerical domain, not a universal mathematical error guarantee.

Inputs use JSON numbers, with booleans and numeric strings rejected. Timestep is
`1e-9..1e6`; rate is zero or has magnitude `1e-12..1000`; initial population is zero
or `1e-9..1e12`; logistic capacity is `1e-9..1e12`. Steps range from 0 through 2,048,
with 1–16 cases, giving at most 32,784 points. Titles allow 1–100 characters and
names 1–60, before and after display normalization. Remaining C0/C1 controls and
U+FFFE/U+FFFF are rejected. Requests are at most 64 KiB, sources 2 MiB, and archives
and individual exports 16 MiB.

Every result includes its complete values, initial/final population, minimum,
maximum, change and final difference from the first case. Input case order is
preserved; reordering cases changes the comparison baseline without changing the
individual trajectories. The SVG uses one linear scale across all cases, starts
the population axis at zero, distinguishes curves by color and includes an
initial-point marker so a zero-step experiment remains visible. Coordinates round
to the nearest pixel; numeric exports retain full binary64 precision. A single
shared scale can visually flatten small populations beside much larger ones.

The nine-file bundle contains `experiment.json`, `archive.json`, `series.json`,
`series.csv`, `plot.svg`, `report.json`, a byte-count/SHA-256 manifest, and actual
`replay.json` and `simulate.json` requests. Edit the exported experiment and run
its simulation request to compare new parameters or timesteps. The output must
still be a new directory. Archive verification uses canonical binary64 values
and strict JSON types: even a one-ULP change to a cached population is rejected.
The mixed-engine checks establish exact replay on the tested Linux x86-64 build;
they do not establish bitwise numerical identity on every platform.

Publication checks bounded regular unaliased input snapshots, synchronizes staged
files, rechecks metadata and performs a no-replace directory rename. Existing
outputs are preserved. Caught failures attempt staging cleanup; a hard kill may
leave `.population-*` staging while final output remains absent or complete. The
checks assume cooperative local parent directories.

`tools/corpus.py 110` compares every generated point with independent 70-digit
Decimal closed-form exponential or logistic solutions. The tested error bound is
`2e-5 * abs(exact) + 1e-13 * abs(initial) + 1e-110`. Nine hand experiments cover
constant, zero, equilibrium, growth, decay and above-capacity cases. Four refinement
checks halve the timestep at the same horizon and reduce final error by more than
a factor of ten. Twenty-four generated experiments contain 96 series and 7,648
primary points; checks reorder parameters, scale populations/capacities, replay
actual edited exports, and reproduce suffixes exactly from exported midpoints.
CSV and parsed SVG coordinates are checked against every result point.

Other checks cover 123 invalid sources, strict archive tampering, maximum series,
exact/over-limit inputs, unstable steps, interrupted publication, retries and
permissions. `tools/check_population_simulator.py` exercises all eight Python/Rust
writer, replayer and simulator combinations, changes rates and timestep, replays
the revised results and restores the original experiment and plot. Packaged
native acceptance and the one-command whole-project build are checked separately.

## PNG structure inspector (111)

```bash
python -m py2rust.compiler.project run examples/corpus/111_png_inspector \
  -o build/png-demo --name png-inspector --offline
```

The project contains six readable Python modules and no Rust adapter. Its generated
Rust executable uses no Python runtime. `PNG_CONFIG` selects a request, defaulting
to `png-job.json`. Relative paths are resolved against that request's directory.
The request has exactly `version: 1`, `mode`, `input` and `output`; modes are
`inspect` for a PNG file and `verify` for an exported archive. Output must be a new
directory. The sample writes `report` beside its request.

Inspection follows the [PNG specification](https://www.w3.org/TR/2025/REC-png-3-20250624/)
for the implemented structural profile: the signature, bounded chunk framing,
ASCII type letters and reserved bit, CRC-32 of each type plus payload, required
critical chunks, duplicate singleton chunks, selected ordering constraints,
consecutive IDAT chunks, unknown critical chunks and bytes after IEND. Each chunk
records its exact offset, length, type bytes, property bits, stored and calculated
CRC, payload SHA-256 and interpreted metadata.

Decoded metadata includes IHDR dimensions and color/depth combinations, PLTE
entry count, tRNS samples/alpha, gAMA, sRGB, pHYs, tIME, Latin-1 tEXt and
uncompressed UTF-8 iTXt. Keywords and text framing are validated. Compressed text
and color profiles retain their identifying fields and compressed byte counts.
Other ancillary payloads remain opaque. The `unchecked` list identifies these
omissions and metadata skipped after the decoding budget. This is a bounded
structure inspector; pixel values, deflate streams, APNG semantics and all
ancillary extensions are not validated. Exit zero means the implemented checks
found no errors, rather than proving that an image can be decoded.

Malformed images still produce a complete forensic report and exit **1**. Invalid
requests, resource limits, unsafe paths, altered archives and publication failures
exit **2**. Successful inspections exit **0**. Findings contain precise offsets,
short diagnostic codes and details. Scanning stops at an incomplete chunk or the
first IEND; the summary counts scanned and remaining bytes.

Limits are 16 MiB per PNG, 4,096 scanned chunks, a 64 KiB decoded metadata budget,
64 KiB per request and 64 MiB per archive or individual export. IHDR, PLTE and IEND
remain structurally interpreted after the metadata budget is exhausted. Original
bytes are preserved even when their content is unchecked. Publication writes
bounded blocks, synchronizes staging and rechecks input snapshots before a
no-replace directory rename. Inputs must be regular unaliased files. Caught
failures clean staging; a hard kill can leave `.png-*` staging. Parent directories
are assumed to be cooperative local directories.

The eight-file bundle contains `image.png`, `archive.json`, `chunks.json`,
`report.json`, escaped `report.html`, a byte-count/SHA-256 `manifest.json` and
actual `inspect.json`/`replay.json` requests. An archive stores canonical lowercase
source hex and every computed finding. Verification recomputes all fields and
rejects changed values or JSON types. The exported image can be edited and
inspected under a new output name; a malformed image's archive is replayable too.

`tools/corpus.py 111` checks independently constructed PNG fixtures with Python's
`struct` and `zlib`, all 15 color/depth combinations, IDAT rechunking, selected
metadata, escaped HTML, malformed chunks and every proper byte prefix of a small
image. It also checks strict archive tampering, exact and exceeded resource
limits, interrupted publication, concurrent changes, retries and permissions.
`tools/check_png_inspector.py` exchanges reports across all eight Python/Rust
writer, replayer and inspector combinations, edits exported metadata, replays CRC
findings and restores the original binary and report.

## Mono PCM WAV analyzer and normalizer (112)

```bash
python -m py2rust.compiler.project run examples/corpus/112_wav_analyzer \
  -o build/wav-demo --name wav-analyzer --offline
```

Seven Python modules implement the complete application; the generated Rust
executable needs no Python interpreter. `WAV_CONFIG` selects a request, defaulting
to `wav-job.json`. Relative paths use the request's directory. The sample writes
`report` beside its request. Processing requests contain exactly `version: 1`,
`mode: "process"`, `input`, `output` and `settings`. Verification requests contain
`version: 1`, `mode: "verify"`, `input` and `output`, with settings loaded from the
archive. Output must be a new directory.

The accepted profile is little-endian RIFF/WAVE, integer PCM format 1, one channel
and 16-bit signed samples. It checks the outer size, each chunk and its word
padding, unique format/data chunks, sample alignment, rate and byte-rate/block
relationships. Format and data chunks may appear in either order. The format
payload must be 16 or 18 bytes; the extra two-byte `cbSize` field is ignored for
PCM. Ancillary chunks remain opaque but retain exact offsets, sizes, padding
counts, IDs as hex and payload SHA-256. Nonzero pad bytes are accepted. These
choices follow the relevant [RIFF framing](https://learn.microsoft.com/en-us/windows/win32/xaudio2/resource-interchange-file-format--riff-)
and [PCM format fields](https://learn.microsoft.com/en-us/windows/win32/api/mmeapi/ns-mmeapi-waveformatex).
Stereo, other sample widths, compressed audio, extensible formats, RIFX and RF64
are outside this application's declared mono signed16 scope.

Settings choose one of two exact schemas:

- `{"method":"peak","target":30000}` scales the largest absolute sample to a
  target of 1–32,767. Empty input and silence use gain 1/1.
- `{"method":"gain","numerator":3,"denominator":2}` applies a nonnegative
  rational gain. The numerator is 0–1,000,000; the denominator is 1–1,000,000.

Each sample is scaled using integer arithmetic, rounded to the nearest integer
with ties away from zero, then clamped to −32,768…32,767. `clipped_low` and
`clipped_high` count rounded samples that required clamping; fractional values
which round back into range do not count as clamped. There is no dithering or
resampling. Changed-sample counts compare the final PCM values with the original.
The signed16 encoding uses low-order bytes first, as specified in
[ITU-R BS.1352-4, Attachment 1](https://www.itu.int/dms_pubrec/itu-r/rec/bs/R-REC-BS.1352-4-202305-I!!PDF-E.pdf).

Input and output statistics include sample count, minimum/maximum, absolute peak,
exact integer sum and sum of squares, mean, RMS and duration. Empty minimum and
maximum are null; other empty statistics are zero. Mean, RMS and duration use
binary64; 70-digit Decimal RMS comparisons check the acceptance fixtures. Cached
archive values use strict JSON types and exact canonical values on the tested
Linux x86-64 Python/Rust build. A one-ULP change to cached RMS is rejected.

The waveform SVG shows input and output on the same full signed16 scale. At most
256 min/max buckets cover all samples in contiguous, nonempty intervals; tooltips
show exact index spans and extrema. Empty input is labeled. CSV retains every
original and output sample, so the preview's reduced resolution loses no exported
data. The SVG was rendered and visually checked for the sample, empty input and
the maximum-size alternating-extreme waveform.

Limits are 262,144 samples, 1,024 chunks, 1–384,000 Hz, 2 MiB per source WAV,
64 KiB per request, and 16 MiB per archive or individual export. Processing keeps
bounded inputs in memory. Invalid files, requests, resource limits and altered
archives exit 2 before publication; successful processing, including reported
clipping, exits 0.

The nine-file bundle includes `original.wav`, `normalized.wav`, `archive.json`,
`report.json`, `samples.csv`, `waveform.svg`, a byte-count/SHA-256 `manifest.json`
and actual `process.json`/`replay.json` requests. Normalized output is a canonical
PCM file containing only format and sample chunks; the original preserves all
ancillary data. Edit the settings in `process.json` and choose a new output name
to change gain or peak. Its input can also be changed to `normalized.wav` to
process the actual exported output. Verification recomputes all processing and
cached results from the archive's original bytes and settings.

Publication uses bounded writes, synchronized staging, rechecked regular
unaliased input snapshots and a no-replace directory rename. Existing outputs
are preserved. Caught errors clean staging; hard kills can leave `.wav-*` staging
while the final directory remains absent or complete. Parent directories are
assumed to be cooperative local directories.

Acceptance checks all 65,536 signed16 inputs under five gain policies with an
independent 50-digit Decimal rounding oracle. Thirteen hand cases, three chunk
layouts and 24 generated cases cover empty/silent audio, half ties, signed
extremes, reversed samples, exact clipping, edited exports and peak-normalization
idempotence. Python's `wave` module reads every normalized output; every CSV
sample, chunk provenance field and parsed SVG envelope is checked. Other checks
cover 50 proper byte prefixes, 31 additional malformed WAV cases, 57 invalid
requests/settings, 25 altered archives, exact/exceeded limits, publication
interruptions and filesystem protections. `tools/check_wav_analyzer.py` exercises
all eight Python/Rust writer, replayer and analyzer combinations.

## BMP thumbnails and contact sheets (113)

```bash
python -m py2rust.compiler.project run examples/corpus/113_bmp_thumbnails \
  -o build/bmp-demo --name bmp-thumbnails --offline
```

Six readable Python modules (413 substantive lines) implement the complete
application. All six transpile to Rust; the resulting Linux x86-64 executable
runs without Python. The shipped five-image project writes `report` beside its
request. `BMP_CONFIG` selects a request, defaulting to `bmp-job.json`.

A request has exactly `version: 1`, `mode: "build"` or `"verify"`, `input` and
`output`. Input/output paths are relative to the request. A build project has
`version: 1`, `settings`, and `images`, each with `name` and `path`. Image paths
are relative to the project. Names allow 1–64 Unicode codepoints, require a
non-whitespace character and exclude C0/C1 controls. Duplicate display names
are allowed; generated filenames use indexes. Output must be a new directory.

The parser accepts 24-bit uncompressed BMP with 12-byte CORE, 40-byte INFO,
108-byte V4 or 124-byte V5 DIB headers. It validates the BM signature, actual
file size, reserved fields, positive width, height, one plane, depth, BI_RGB,
image-size fields, offsets, optional palette extent and complete padded rows.
Positive heights store rows bottom-up; negative Windows heights store top-down.
CORE heights are unsigned. Row stride rounds up to a multiple of four bytes;
nonzero padding, gaps and trailing data are allowed and preserved in originals.
These rules follow Microsoft's [file header](https://learn.microsoft.com/en-us/windows/win32/api/wingdi/ns-wingdi-bitmapfileheader),
[CORE header](https://learn.microsoft.com/en-us/windows/win32/api/wingdi/ns-wingdi-bitmapcoreheader),
[INFO header](https://learn.microsoft.com/en-us/windows/win32/api/wingdi/ns-wingdi-bitmapinfoheader),
[V4](https://learn.microsoft.com/en-us/windows/win32/api/wingdi/ns-wingdi-bitmapv4header)
and [V5](https://learn.microsoft.com/en-us/windows/win32/api/wingdi/ns-wingdi-bitmapv5header) definitions.

RGB values are processed without color management. V5 linked/embedded profile
extents must be bounded and disjoint from pixel data; the application neither
opens linked profile paths nor interprets ICC content. Profile fields are ignored
for other color-space tags. Compressed BMP, other depths and other DIB sizes
are outside this declared profile. Output uses a canonical 40-byte INFO header,
bottom-up BGR triples, zero padding and no ancillary metadata.

Settings contain exactly these fields:

| Setting | Values |
| --- | --- |
| `box_width`, `box_height` | 1–256 pixels |
| `columns` | 1–8; reduced to the number of images when smaller |
| `margin`, `gap` | 0–32 pixels |
| `fit` | `"contain"` or `"stretch"` |
| `background` | Three strict integer RGB channels, each 0–255 |

Contain mode preserves aspect ratio using the smaller box/source scale, floors
each dimension with a minimum of one pixel, and centers the result with floor
positioning. Stretch fills the box. Both allow upscaling. Nearest-neighbor
sampling maps target pixel centers to source cells:
`source_x = floor((x + 1/2) * source_width / target_width)`, and similarly for y.
Exact boundary ties select the right/bottom pixel. Empty final-row cells retain
the chosen background.

Limits are 1–16 images; 1–1,024 pixels per source axis; 262,144 pixels and 2 MiB
per image; 1,048,576 combined source pixels; 8 MiB combined source bytes;
64 KiB per request/project; and 32 MiB per verification archive. Sheets are
bounded to 4,096 per axis and 2,097,152 pixels. Given the other layout bounds,
the maximum reachable sheet area is 1,835,008 pixels (2,048 × 896); the width
and area checks are additional defensive bounds. Each export is bounded to
32 MiB, also above the reachable generated size. Invalid inputs exit 2 before
publication; successful builds/replays exit 0.

The bundle has ten shared files plus two BMPs per image: original `source-i.bmp`
and usable `thumbnail-i.bmp`; `sheet.bmp`; an escaped, self-contained HTML
preview; `project.json` referencing originals; `thumbnails.json` referencing
thumbnails; `archive.json` preserving exact original bytes as lowercase hex;
`report.json`; `rebuild.json`, `retile.json`, `replay.json`; and a byte-count/SHA-256
manifest. Rebuild/retile requests can be edited and run directly with `BMP_CONFIG`.
Verification decodes originals and recomputes every metadata field, placement,
pixel and hash before comparing cached results using strict JSON types.
Retiling the actual thumbnails with the same settings preserves sheet pixels.

Publication uses bounded writes, synchronized staging, snapshot rechecks for
the request, project and every image, and a no-replace directory rename. Caught
errors remove staging; a hard kill may leave `.bmp-*` staging. The final output
is absent or complete, and existing outputs are preserved. Parent directories
are assumed to be cooperative local directories.

Acceptance uses independent struct-packed BMPs, RGB grids and Fraction-based
sampling. It compares every canonical output byte, pixel, metadata field,
manifest entry and HTML link. Coverage includes 56 header/orientation/padding
variants, four manually specified pixel goldens, four profile placements,
20 generated projects, thumbnail idempotence and edited/reordered/renamed
projects. It rejects all 78 proper prefixes of a fixture, 49 other malformed
BMPs, 70 invalid requests/projects/settings and 23 altered archives. Exact and
exceeded input bounds, publication faults/kills, six input/output races and
29 filesystem checks are included. `tools/check_bmp_thumbnails.py` runs eight
Python/Rust writer, replayer and builder combinations using actual exported
requests and restores the original image/layout after edits.

The sample, maximum-area sheet and a tiny sampling-tie fixture were rendered and
visually inspected. ImageMagick independently decoded all five original sample
BMPs, five thumbnails and the sheet into RGB bytes matching the reference grids.
The HTML preview was checked structurally; browser rendering was not assessed.

## P6 PPM image-filter pipeline (114)

```bash
python -m py2rust.compiler.project run examples/corpus/114_ppm_filters \
  -o build/ppm-demo --name ppm-filters --offline
```

Seven Python modules (442 substantive lines) implement the complete application.
Every module transpiles into native Rust; the executable runs without Python.
`PPM_CONFIG` selects the request, defaulting to `ppm-job.json`. The shipped 10-bit
sample runs crop, invert and channel threshold, writing `report` beside its
request. Relative input/output paths use the request directory.

Processing requests contain exactly `version: 1`, `mode: "process"`, `input`,
`output` and `pipeline`. Verification requests contain `version: 1`,
`mode: "verify"`, `input` and `output`, loading the pipeline from the archive.
Output must be a new directory. A pipeline is an ordered array of 0–32 filters;
an empty pipeline emits a canonical copy.

The accepted profile is one raw P6 image, with ASCII decimal width, height and
Maxval. All six ASCII whitespace bytes and `#` header comments ending before
CR or LF are supported. Numeric tokens have 1–5 digits, including leading zeros.
After Maxval and any immediately adjacent comment, exactly one whitespace byte
ends the header. Subsequent bytes are raster data, even when they are LF, CR,
space or `#`; CRLF after Maxval is not silently consumed as a pair. Maxval is
1–65,535: samples use one byte below 256, otherwise two bytes in big-endian order.
Rows run top-to-bottom, pixels left-to-right, with RGB channels. Every sample
must be at most Maxval and the raster size must be exact. Plain P3, concatenated
images and trailing data are outside this bounded profile. These framing rules
follow the [P6 specification](https://netpbm.sourceforge.net/doc/ppm.html) and its
[comment definition](https://netpbm.sourceforge.net/doc/pbm.html).

Filters use exact integer sample values and preserve Maxval:

| Filter | Exact fields and behavior |
| --- | --- |
| Crop | `{"op":"crop","x":1,"y":2,"width":10,"height":8}` selects a positive rectangle entirely within the current image. Coordinates are zero-based; no implicit clipping. |
| Invert | `{"op":"invert"}` replaces each channel with `Maxval - value`. |
| Channel threshold | `{"op":"threshold","value":128,"mode":"channel"}` independently maps each channel to Maxval when at least the threshold, otherwise zero. |
| Mean threshold | `{"op":"threshold","value":128,"mode":"mean"}` maps the whole pixel to white when its arithmetic channel mean is at least the threshold, otherwise black. |

Thresholds are integers from zero through Maxval. Mean comparison uses the
exact sum against three times the threshold, without intermediate rounding.
Operations act on stored sample codes; there is no gamma conversion, weighted
luminance calculation or adaptive thresholding. Crop coordinates refer to the
output of the preceding filter. Inversion twice restores samples, thresholding
is idempotent, and valid nested crops compose. Reordering filters can change
results.

Limits are 1–1,024 per image axis, 262,144 pixels, a 64 KiB header, 2 MiB source
input, 64 KiB request, 16 MiB archive, and 16 MiB per export. The largest valid
source is 1,638,400 bytes under the pixel/header/depth bounds; the source and
export byte limits are additional defensive bounds. A processing budget counts
original pixels plus the input pixel count of each operation, capped at
4,194,304. Header dimensions and exact raster length are checked before allocating
the decoded sample array. Invalid requests, files, filters, bounds and changed
archives exit 2 before publication; successful processing/replay exits 0.

The nine-file bundle contains `original.ppm`, `filtered.ppm`, `preview.svg`,
`histogram.csv`, `archive.json`, `report.json`, usable `process.json` and
`replay.json` requests, and a byte-count/SHA-256 manifest. The original retains
its exact header/comments. Filtered PPM uses a canonical LF-delimited header and
the original sample depth. JSON contains exact full-resolution histograms for
each RGB channel before and after processing, header/file/raster provenance,
per-step dimensions, operations and raster hashes. CSV lists every sample value
with a nonzero input or output count. Each channel histogram sums to its image's
pixel count.

The SVG compares original and filtered images, sampling at most 128 × 128 pixels
per panel. It labels original dimensions and Maxval and maps code values to
8-bit display channels with nearest rounding. PPM and CSV preserve the complete
data. To reuse the actual output, edit `process.json` to read `filtered.ppm`,
change the pipeline and choose a new output name. Verification recomputes every
result from original bytes and pipeline, comparing canonical values with strict
JSON types.

Publication uses synchronized staging, regular unaliased input snapshots, bounded
writes and a no-replace directory rename. Caught errors remove staging; hard
kills may leave `.ppm-*` directories while the final output is absent or complete.
Existing outputs are preserved. Parent directories are assumed to be cooperative
local directories.

Acceptance uses separate regex/struct parsing, RGB grids, Counter histograms and
Fraction arithmetic. It checks exact output bytes, every histogram/CSV entry,
SVG sample position/color and manifest. It covers every 16-bit value in each
channel under three pipelines; 42 depth/header/boundary cases; four manual
pixel goldens; and 18 generated pipelines with inversion, crop composition and
threshold identities. Further checks cover malformed files, strict schemas,
altered archives, exact/exceeded bounds, publication interruptions and filesystem
protections. `tools/check_ppm_filters.py` exercises all eight Python/Rust writer,
replayer and processor combinations, including real filtered-output reuse and
restoration of the original source/pipeline.

The sample, maximum-size/depth image and a mean-threshold tie fixture were
rendered and visually checked. ImageMagick independently decoded six input/output
PPMs spanning Maxval 2, 1,023 and 65,535; scaled 16-bit RGB bytes matched the
exact reference without quantization differences in these fixtures.

## PPM sprite-atlas packer (115)

```bash
python -m py2rust.compiler.project run examples/corpus/115_sprite_atlas \
  -o build/atlas-demo --name sprite-atlas --offline
```

Seven Python modules (492 substantive lines) implement the complete application.
Every module transpiles to Rust, including the packing, pixel copying, extraction,
serialization and preview. The Linux x86-64 executable needs no Python runtime.
The shipped six-sprite example writes `report` beside its request. `ATLAS_CONFIG`
selects the request, defaulting to `atlas-job.json`.

A request contains exactly `version: 1`, `mode: "pack"` or `"verify"`, `input`
and `output`. Relative paths use the request directory. A packing manifest has
`version: 1`, `settings` and `sprites`; each sprite has `name` and `path`, with
paths relative to the manifest. Names must be unique, non-whitespace strings of
1–64 Unicode codepoints without C0/C1 controls. Uniqueness is exact and case
sensitive. The output must be a new directory.

Sprites use the bounded single-image P6 profile documented for application 114,
including comments, exact header/raster separation, big-endian 16-bit samples
and Maxval 1–65,535. Here each source axis is bounded to 256. All sprites must
have the same Maxval, preserving their raw sample values and bit depth. Mixing
Maxval values is rejected. There is no rotation, rescaling or color conversion.
Original files preserve their exact headers; extracted sprites use canonical P6.

Settings contain exactly:

| Setting | Values |
| --- | --- |
| `width` | Fixed atlas width, 1–1,024 pixels |
| `max_height` | Maximum permitted height, 1–1,024 pixels |
| `padding` | Background gutter on each side of every sprite, 0–16 pixels |
| `order` | `"height"` or `"input"` |
| `background` | Three strict integer RGB channels, each 0–Maxval |

Height order sorts by descending sprite height, then descending width, then
ascending Unicode name. Input order follows the manifest. The first-fit shelf
algorithm scans shelves in creation order and places each padded rectangle in
the first shelf with sufficient height and remaining width. If none fits, it
creates a shelf below the existing ones. Content starts one padding inset from
the padded rectangle's upper-left corner. Shelf height is set by its first
rectangle; unused shelf space remains background. Actual atlas height is the sum
of shelf heights. All padded rectangles are disjoint and within the atlas.

This is a deterministic packing heuristic, not an optimal-layout solver. It can
reject a height limit even when another arrangement would fit. For example,
4×4, 2×2 and 2×2 sprites with zero padding need two shelves under this rule;
a 6×4 canvas could hold them with a different arrangement. Such a rejection
publishes nothing. The behavior is tested explicitly.

Limits are 1–64 sprites, 256 per source axis, 65,536 pixels per source,
1,048,576 combined source pixels, 512 KiB per source file, 8 MiB combined source
bytes, 64 KiB per P6 header and per request/manifest, and 32 MiB per verification
archive or export. The largest valid source is 458,752 bytes under the other
bounds; individual source/export byte limits are additional defensive checks.
The atlas is at most 1,024 × 1,024. Invalid inputs, unsupported layouts and altered
archives exit 2 before publication; successful packing or replay exits 0.

The bundle contains eleven shared files plus two files per sprite:
`original-i.ppm` preserves the source, and `extracted-i.ppm` is read back from
actual atlas pixels. Shared files are `atlas.ppm`, `coordinates.json`,
`preview.svg`, `sprites.json`, `extracted.json`, `archive.json`, `report.json`,
`repack.json`, `pack-extracted.json`, `replay.json` and `manifest.json`.
Coordinates include original indexes/names, content bounds, shelf indexes and
source/raster/extracted-file hashes. The report includes shelf extents, image
depth, source/background pixel counts and complete atlas hashes. The manifest
records exact byte counts and SHA-256 values for every other exported file.

The supplied requests are directly runnable. Repack uses original files;
pack-extracted uses actual atlas extractions. Both retain names, ordering and
layout settings. Editing the layout and choosing a new output directory produces
a new atlas. Replay recomputes all packing, pixels and metadata from original
bytes in the archive and compares cached fields using strict JSON types.
Repacking extracted sprites with identical settings reproduces the atlas pixels.

The self-contained SVG samples at most 128 × 128 cells. Sprite outlines use
actual atlas coordinates, and hover labels escape sprite names. PPM and JSON
retain full-resolution pixels and placement data. Publication uses synchronized
staging, snapshot checks for the request, manifest and every sprite, and a
no-replace directory rename. Caught errors remove staging. A hard kill can leave
`.atlas-*` staging while the final output remains absent or complete. Parent
directories are assumed to be cooperative local directories.

Acceptance independently builds RGB grids, checks padded-rectangle intersections,
compares every output pixel and background cell, and extracts every sprite back
from the exported atlas. Two manually specified layouts, 24 depth/padding/order
cases and 20 generated projects cover shelf reuse, sorting ties, permutation
invariance, Unicode labels and edited layouts. Nine raster-start bytes include
whitespace and `#`. Checks also reject 23 proper byte prefixes, 39 other malformed
images, 63 invalid requests/manifests/settings, three packing-policy failures and
24 altered archives. Exact/exceeded resource limits, faults, kills, six input/output
races and 29 filesystem checks are exercised. `tools/check_sprite_atlas.py` runs
all eight Python/Rust writer/replayer/builder combinations with actual exported
requests, extraction reuse and restoration of original layout/pixels.

The shipped sample, maximum padded atlas and input-order shelf fixture were
rendered and visually inspected. ImageMagick independently decoded fifteen
original, extracted and atlas PPMs, including 16-bit maximum-size output; every
normalized RGB sample matched the reference exactly.

## SVG metrics dashboard (116)

```bash
python -m py2rust.compiler.project run examples/corpus/116_svg_dashboard \
  -o build/dashboard-demo --name svg-dashboard --offline
python tools/corpus.py 116
python tools/check_svg_dashboard.py
```

The shipped six-chart network dataset writes `report` beside `dashboard-job.json`.
Open `report/index.html` in a browser or use `report/dashboard.svg` directly.
`DASHBOARD_CONFIG` selects another request. Building needs the development
Python environment; the resulting Linux x86-64 executable runs independently.
Seven readable Python modules, 497 substantive lines, provide all application
logic. No native adapter modules or compiler/runtime changes are needed.

The render request has exactly `version: 1`, `mode: "render"`, `input`, `output`
and integer `columns` from 1 through 3. Paths are relative to the request's
parent. The dataset has exactly `version: 1`, a nonblank `title`, and `charts`:

```json
{
  "version": 1,
  "title": "Network metrics",
  "charts": [
    {
      "id": "traffic",
      "title": "Traffic change",
      "kind": "bar",
      "unit": "MiB",
      "points": [
        {"label": "Monday", "value": -20},
        {"label": "Tuesday", "value": 60}
      ]
    }
  ]
}
```

Each chart has precisely these fields; `kind` is `bar` or `line`. Chart IDs are
unique nonblank strings of at most 32 Unicode code points. Dataset/chart titles
are nonblank and at most 120 characters; units may be empty and are at most 32.
Point labels may be empty or repeated and are at most 120 characters. C0/C1
controls, surrogates and code points ending in FFFE/FFFF are rejected. All user
text is XML-escaped, including tooltips and the HTML title. Unknown or duplicate
JSON fields and booleans in numeric fields are rejected.

Values are finite binary64 numbers, including integers converted to binary64;
zero is permitted and nonzero absolute values must be between 1e-12 and 1e12.
The original JSON bytes, including integer spellings and negative zero, are kept
in the exported data. Computed point values are consistently floating point.
The X axis uses evenly spaced categories, not numeric/time coordinates.

Bar domains include zero. Nonconstant line domains receive 5% of their raw span
as padding at each end. A zero/empty domain becomes [-1, 1]; a nonzero domain
whose span is at most 1e-12 of its largest magnitude receives 5% of that magnitude
at each end. The target interval is the padded span divided by four. Steps are
rounded upward to a decimal 1, 2 or 5 times a power of ten, with comparisons in
binary64. Endpoints are rounded outward to step multiples, including a final
containment check against floating-point multiplication. Ticks have exact
integer-derived decimal labels, using scientific notation for long or tiny
values; plotting coordinates round to the nearest pixel. Near a step boundary,
binary64 rounding can choose either adjacent step. These are linear chart scales,
not logarithmic axes or exact-decimal measurements.

Cards are 640×380 with a 434×200 plot; the dashboard uses up to the requested
column count and scrolls horizontally when the browser is narrow. Empty charts
and empty dashboards have explicit messages. Zero-height bars have visible
markers. At most six categorical labels are shown per chart. Long visible labels
are shortened and clipped to their boxes; full labels and point values remain
in SVG title tooltips and JSON metadata. Rendering uses available system fonts;
emoji appearance depends on the viewer and installed fonts.

Limits are 12 charts, 128 points per chart, 64 KiB request, 2 MiB dataset and
16 MiB archive/export. The bundle has eight files: `dashboard.svg`, `index.html`,
`data.json`, `archive.json`, `report.json`, `render.json`, `replay.json` and
`manifest.json`. HTML is self-contained and includes the SVG, with no scripts or
external resources. The manifest covers the other seven files with byte counts
and SHA-256. The archive retains source bytes, requested columns and full
computed geometry. The report provides readable JSON for the same results.

Run the exported `render.json` to render the exported data again, or edit a copy
of the data/request to change the charts or layout. `replay.json` uses a verify
request with exactly `version`, `mode`, `input` and `output`. Verification
recalculates all chart geometry and rejects any cached change, including a
one-ULP value change or a change from float to integer. Output names must be new;
inputs are single-link regular files. Publication uses fsynced staging, input
snapshot checks and a no-replace directory rename. Parents are cooperative.
A killed process may leave `.dashboard-*` staging; the final bundle is absent
or complete. Fault injection uses the `DASHBOARD_FAULT`, `DASHBOARD_PAUSE` and
`DASHBOARD_RELEASE` variables at `staged` and `published` boundaries.

Acceptance checks enumerate decimal scale candidates independently, use Decimal
pixel geometry, parse all generated SVG/HTML, and verify the complete export
manifest. There are 112 boundary/degenerate cases, four hand-calculated pixel
fixtures, 20 generated datasets with 7,075 points, reversal/relayout/restoration
checks and four scale-covariance cases. Malformed requests/data, escaped markup,
Unicode, maximum-size replay, altered archives, two caught faults, two process
kills, three input/output races and 14 filesystem cases are covered. The matrix
uses all eight Python/Rust writer/replayer/renderer combinations, exchanges the
actual exported requests, changes data and layout, and restores the original
SVG/HTML bytes. The sample, empty, maximum, escaping and narrow-domain native
SVGs are also rendered independently for visual review.

## Terminal task dashboard (117)

```bash
python -m py2rust.compiler.project run examples/corpus/117_terminal_dashboard \
  -o build/terminal-demo --name terminal-dashboard --offline
python tools/corpus.py 117
python tools/check_terminal_dashboard.py
```

The sample watches six network tasks for five frames and writes `report` beside
`tasks-job.json`. Change `TASK_DASHBOARD_CONFIG` to select another request.
Building uses Python; the resulting Linux x86-64 executable runs independently.
Seven Python modules (465 substantive lines) provide the complete application,
with no native adapter modules. `model.py` validates tasks, `layout.py` formats
cells, `records.py` validates replay, `session.py` manages refresh and cleanup,
`documents.py` publishes files, `reports.py` exports bundles and `main.py` wires
the project together.

A watch request has exactly these fields:

```json
{
  "version": 1,
  "mode": "watch",
  "input": "tasks.json",
  "output": "report",
  "columns": 80,
  "refreshes": 5,
  "interval_ms": 1000
}
```

Paths are relative to the request's parent. Output must be new. Columns range
from 1 to 200; refreshes from 1 to 64; the interval from 20 to 60,000 ms; the
product of interval and count may not exceed one hour. There is no delay after
the final frame. Snapshot writers should atomically replace the input file:

```json
{
  "version": 1,
  "sequence": 7,
  "title": "Network tasks",
  "tasks": [
    {"id": "upload", "label": "Upload 東京 screenshots", "state": "running", "done": 5, "total": 10}
  ]
}
```

Snapshots have at most 128 tasks, unique nonblank IDs up to 32 code points and
nonblank titles/labels up to 120 code points. Sequence is a nonnegative signed
64-bit integer. Each task has exactly `id`, `label`, `state`, `done` and `total`.
States are `queued`, `running`, `done` or `failed`; integer progress satisfies
0 ≤ done ≤ total ≤ 1,000,000,000. Queued tasks have zero completed work; done
tasks have done equal to total. Done tasks show 100%, including zero work;
other zero-total tasks show unknown progress. Other percentages round down.
Unknown/duplicate fields, booleans in integer fields, terminal controls and bidi
formatting are rejected. Both request and snapshot are limited to 64 KiB.

The first valid snapshot becomes current. Higher sequences replace it; identical
same-sequence snapshots are unchanged. Lower sequences and changed content at
the same sequence are reported while retaining the previous state. Missing,
unreadable, changing and invalid input also retain the last valid state. Before
any valid state arrives, the screen says “Waiting for tasks”. Any recoverable
snapshot problem makes the watch exit 1 after exporting its observations;
success exits 0 and a fatal request/publication failure exits 2.

An ANSI-capable stdout TTY gets alternate-screen rendering with a hidden cursor.
Size is queried for every frame, leaving one physical column and row unused to
avoid wrapping/scrolling. Width is capped by the requested columns; height by
132 rows. At least one cell is used even for a zero/one-column reported size.
Full layouts (50+ cells) show ID, state, percentage, bar and label. Compact
layouts (24–49) show a state symbol, percentage and label. Narrower layouts show
a symbol and clipped label; one-cell layouts show only the symbol. Task order
is preserved, and a footer counts hidden tasks when height allows it.

Clipping preserves Unicode 16 extended grapheme clusters and uses `~` to mark
truncation. Ambiguous characters are narrow; detached combining clusters get a
dotted circle. Actual glyph widths depend on the terminal and fonts. Redirected
output contains complete plain frames with no escape sequences. Empty, `dumb`
and `unknown` TERM values also select plain output; a TTY still limits the width.
The reference and Rust runtime always encode UTF-8 and flush each write.

SIGINT/SIGTERM interrupt interval waits, restore the cursor/alternate screen,
export completed frames and exit 128 plus the signal number. Cleanup also runs
for ordinary exceptions. SIGKILL cannot restore a terminal or finish a bundle.
Signal ownership is supplied by the existing process-pool API; the dashboard
launches no child processes.

Seven files are exported: `archive.json`, `transcript.txt`, `snapshot.json`,
`watch.json`, `replay.json`, `report.json` and `manifest.json`. Each export is
limited to 16 MiB. The manifest gives byte counts and SHA-256 for the other six.
The archive stores settings, exact snapshot bytes as hex, readability decisions,
terminal dimensions, frames and an interruption signal. Replay recomputes every
observation and frame and rejects cached mismatches. It is consistency checking,
not authentication: alternative internally consistent metadata is permitted.

Run the actual exported `replay.json` to reproduce recorded frames, including
resizes and input failures. Its fields are exactly version, mode (`replay`),
input and output. Replay emits plain text and exits 0 for a consistent archive,
even if that archive records input errors or an interruption. `watch.json`
starts a new watch of the last valid `snapshot.json`; edits to a copy of this
request/snapshot can change the task data or layout. A fresh watch need not
reproduce a history that contained updates, errors or terminal resizes.

Publication uses single-link regular input files, fsynced staging, guarded
request/archive snapshots and a no-replace directory rename under cooperative
parents. The watched file may change after its final observation; those changes
do not invalidate the recorded history. A hard kill can leave `.tasks-*`
staging, while the final bundle is absent or complete. Test fault controls use
`TASK_DASHBOARD_FAULT`, `TASK_DASHBOARD_PAUSE` and `TASK_DASHBOARD_RELEASE` at
`staged` and `published` boundaries.

Acceptance includes 65 static layouts, a manually specified compact frame,
real PTY resize/update/error recovery, both cancellation signals and three TERM
fallbacks. Sixteen generated projects cover 1,069 tasks and edited/reordered
snapshots. It checks invalid input, inconsistent archives, all bounds, atomic
publication and filesystem restrictions. Eight Python/Rust writer/replayer/
watcher combinations consume actual exported requests, edit snapshots and
layout, and restore the original archive and transcript bytes.

## ZIP manifest validator (118)

```bash
python -m py2rust.compiler.project run examples/corpus/118_zip_validator \
  -o build/zip-demo --name zip-validator --offline
python tools/corpus.py 118
python tools/check_zip_validator.py
python tools/check_gzip_archiver.py
```

The sample audits a notes/attachments archive and writes `report` beside
`zip-job.json`. `ZIP_CONFIG` selects another request. Seven Python modules,
496 substantive lines, compile into a standalone Linux x86-64 executable.
The application contains no native adapters. It uses shared bounded DEFLATE,
CP437, CRC-32, hashing, JSON and filesystem operations. Building uses Python;
running the generated executable does not.

```json
{
  "version": 1,
  "mode": "inspect",
  "input": "sample.zip",
  "output": "report",
  "limits": {"entries": 512, "entry_bytes": 8388608, "total_bytes": 33554432}
}
```

These are the exact inspect-request fields. Paths are relative to the request's
parent. Output must be new; request/archive inputs must be unaliased regular
files. Request size is at most 64 KiB, source ZIP size 16 MiB, and a replay JSON
archive or exported file 64 MiB. Limits are strict integers: entries 0–2,048,
per-entry expansion 0–16 MiB, and aggregate expansion 0–64 MiB. Zero budgets
permit empty content. Unknown/duplicate JSON fields and boolean numeric values
are rejected.

The supported profile is single-disk ZIP32 with stored or raw-DEFLATE entries.
It checks the final end record, central-directory extent and count, local-record
bounds, local/central names, versions, flags, methods, sizes and CRC fields.
Signed and unsigned ZIP32 data descriptors are supported. A payload CRC equal
to the optional descriptor marker is disambiguated using the complete fields.
Overlapping local spans are reported and their payload is not inflated again.
Unclaimed bytes between local records and unmatched central bytes are reported.
A source may contain findings and still produce a complete forensic report.

ZIP64, encryption, unsupported methods/versions/flags and multi-disk records are
classified without decoding their payloads. This profile does not validate all
ZIP extensions. Self-extracting prefixes and additional signature records are
reported as unclaimed or unmatched structure. Timestamp fields, comments and
unknown well-framed extras are retained in the original source without semantic
interpretation. The parser requires an end record whose comment ends exactly at
EOF; ambiguous or inconsistent final-record structures are rejected. The record
format reference is the [PKWARE ZIP specification](https://pkware.cachefly.net/webdocs/casestudies/APPNOTE.TXT).

Names use UTF-8 when flagged and CP437 otherwise. Valid Info-ZIP Unicode-path
extras override a legacy spelling; their version, CRC of the original name and
UTF-8 encoding are checked. Conflicting, duplicate or malformed extras are
reported. The validator checks both central and local Unicode-path metadata.
Names are never used as filesystem paths.

Portable-path findings include absolute paths, traversal/dot/empty components,
backslashes, colons, trailing dots/spaces, Windows reserved basenames, C0/C1
controls and bidi formatting. Duplicate keys use NFC normalization and casefolding,
with a terminal directory slash removed. Thus `Name` and `name`, composed and
decomposed accent spellings, and a file/directory with the same key are reported
as collisions even when a particular filesystem could distinguish them. Unix
symlinks and special-file modes are flagged. These are inspection diagnostics;
the program performs no extraction and does not sanitize an archive for others.

Declared sizes are checked before decompression. The decoder also enforces the
actual remaining output allowance, so a false small size cannot bypass a budget.
Successful decoding charges actual bytes; failed decoding conservatively reserves
its entire allowance. This prevents repeated bad entries from repeatedly spending
the same expansion budget. Entries refused from their declared sizes consume no
expanded bytes. Stored entries are bounded too. Every decoded payload gets an
actual size, CRC-32 and SHA-256; claimed size and CRC mismatches are reported.
`verified_payloads` counts size/CRC matches, independently of path/header findings.
Overall success requires zero findings.

Eight files are exported: `source.zip`, `archive.json`, `entries.json`,
`report.json`, `report.txt`, `inspect.json`, `replay.json` and `manifest.json`.
The manifest records byte counts and SHA-256 for the other seven. The archive
preserves exact source bytes as lowercase hex, the selected budgets and complete
findings. The readable reports include entry offsets, raw names, decoded names,
flags/methods, declared/actual sizes, CRCs, content hashes and diagnostic codes.

Run exported `inspect.json` to audit the exported binary again. Edit a copy of
that request or substitute another source ZIP to change the inspection. Exported
`replay.json` uses exactly version, mode (`verify`), input and output. It
recomputes all findings and rejects cached differences, including type changes
from integer to boolean/float. Replay verifies consistency, not authenticity;
internally consistent alternate sources or settings are permitted. Inspect and
verify exit 0 without findings and 1 with findings. Invalid requests, inconsistent
replay archives and publication failures exit 2.

Publication writes and syncs a staging directory, rechecks both inputs, and uses
a no-replace directory rename under cooperative parents. A hard kill can leave
`.zip-*` staging while the final bundle is absent or complete. Test fault controls
are `ZIP_FAULT`, `ZIP_PAUSE` and `ZIP_RELEASE`, at `staged` and `published`.
Input accumulation uses a bounded bytearray so large replay files do not require
repeatedly copying the entire prefix.

Acceptance compares payloads with Python's independent `zipfile` implementation,
checks 16 generated archives with 273 entries, 41 unsafe-name/entry mutations,
115 truncated prefixes, 15 structural mutations and both ambiguous-CRC descriptor
forms. It covers legacy/Unicode names, local ZIP64 profiles, all byte/count/
expansion bounds, 54 invalid requests, 27 inconsistent archives, interruption
recovery and filesystem restrictions. A 256 MiB expansion is refused at 128 bytes
under a 128 MiB address-space limit in both runtimes. Eight writer/replayer/
inspector combinations consume actual exported requests, edit sources and
budgets, and restore original ZIP/report bytes.

## 119: Gzip log archiver

Seven readable Python modules (409 substantive lines) implement a rotated-log
archiver with a persistent index. The complete project transpiles to native Rust;
there are no application-specific Rust adapters. It streams files in 64 KiB
chunks and retains the original logs. From the repository root:

```bash
GZIP_CONFIG="$PWD/examples/corpus/119_gzip_archiver/gzip-job.json" python -m py2rust.compiler.project run examples/corpus/119_gzip_archiver --offline
```

`GZIP_CONFIG` selects a request; otherwise the program reads `gzip-job.json`.
Relative paths resolve against the request's parent. The supplied request creates
`archives/` beside the sample logs. The archive directory is exclusively managed
by this application; requests and source files must live outside it.

An archive request has exactly `version`, `mode`, `directory`, `inputs`, `level`
and `limits`. Version is integer 1; mode is `archive`; compression level is 0–9.
Each input has exactly `id` and `path`. IDs are 1–64 ASCII letters, digits,
underscores or hyphens, starting with a letter or digit. They become `<id>.gz`.
The requested IDs are unique. Existing IDs are immutable: a repeat succeeds when
the source bytes still match; different bytes require a new ID.

`verify` and `recover` requests have exactly `version`, `mode`, `directory` and
`limits`. Verification streams every indexed archive and checks its compressed
length/digest, gzip framing/CRC/ISIZE, and decoded length/digest. It reports
unfinished work without promoting or deleting it. Recovery finishes prepared
transactions or discards an unprepared stream. Both operations work after the
original source files have been rotated away; they use the captured archive and
index. An archive request first verifies and recovers its store, then processes
its inventory in order. Earlier committed logs remain complete if a later input
fails.

| Bound | Accepted range |
| --- | --- |
| Request bytes | At most 65,536 |
| Input count / total completed archive count | At most 128 each |
| Source path text | 1–4,096 Unicode characters, without NUL |
| `limits.source_bytes` | 0–1,073,741,824 per log |
| `limits.compressed_bytes` | 20–2,147,483,648 per archive |
| `limits.total_bytes` | 0–4,294,967,296 across completed logs |
| Index / pending-record input | At most 1 MiB / 64 KiB |

Integers are strict: booleans and floating-point values are rejected. Unknown
fields and duplicate JSON keys are errors. The compressed allowance also covers
the header and trailer. Expansion and aggregate allowances apply before a new
archive is accepted. Verification applies the selected limits to existing rows.
Empty logs are valid; an encoded empty gzip member is still required.

The store holds `index.json`, one gzip file per completed ID, and a persistent
`.lock` file. Index entries contain the source label, decoded size/SHA-256,
compressed size/SHA-256 and compression level. Source labels are provenance only;
verification and recovery never open a source path taken from index metadata.
A nonblocking advisory lock excludes cooperating concurrent processes.

Publication proceeds through these durable states:

1. Stream to `.stage.gz`, while hashing the source. Check the source's identity,
   size and timestamps before and after reading; mutation during the copy fails.
2. Explicitly finish and sync the gzip member, then independently decode it and
   compare the captured length and digest.
3. Sync `pending.json`, describing the fully verified stream.
4. Rename the staged file without overwriting `<id>.gz`, and sync the directory.
5. Atomically replace and sync `index.json`, then remove the pending record.

Metadata replacement uses synced temporary files. Recovery checks the stored
pending record and actual gzip bytes before publishing or indexing anything. A
kill while streaming or after close but before preparation leaves no completed
row; recovery discards that unprepared stream and an archive retry starts over.
A kill after preparation can be completed from the gzip file, without the original
log. A pending record left after the index update is checked and cleaned up.
A conflicting destination is preserved and reported as an error. Missing or
corrupt completed archives fail verification; they are not silently repaired.

Inputs and managed metadata must be single-link regular files. Final symlinks,
FIFOs, directories and hard-linked files are rejected. Unknown store files are
reported. Store parents and other processes modifying files must be cooperative;
the advisory lock is not a defense against a hostile directory owner. The index
verifies consistency, not authenticity. There is no retention deletion, append to
an existing gzip member, encryption, or reconstruction of missing original logs.

Output is one JSON summary with `completed`, `bytes`, `compressed_bytes` and
`pending`. Success exits 0; request, source, integrity, budget, lock or publication
failures exit 2 with a diagnostic on stderr. Writer implementations may produce
different valid compressed bytes; logical contents and transferred archive
integrity are checked independently.

Acceptance covers 12 generated inventories with 59 logs, 43 invalid requests,
13 inconsistent indices, 62 corrupt/truncated/trailing streams, all five caught
failure and hard-kill boundaries, four source/publication races, 128 completed
empty archives, and 11 filesystem cases. Both engines archive and independently
verify a 1 GiB log under a 128 MiB address-space limit and reject a source one byte
over the maximum. Eight writer/recoverer/inspector combinations transfer actual
archives and pending records, recover without original logs, retry unprepared
streams and verify stores containing files from different encoders.

## 120: Binary traffic-fixture replayer

Four Python modules (274 substantive lines) implement strict binary inspection
and local TCP replay. The complete project compiles to Rust with no application
adapters or compiler/runtime extensions. Inspect the shipped fixture:

```bash
TRAFFIC_CONFIG="$PWD/examples/corpus/120_traffic_replayer/traffic-job.json" python -m py2rust.compiler.project run examples/corpus/120_traffic_replayer --offline
```

The JSON request has exactly `version: 1`, `mode`, `fixture` and `limits`.
`mode` is `inspect` or `replay`. Replay also requires `peer` and `timeouts`.
`TRAFFIC_CONFIG` selects the request, defaulting to `traffic-job.json`; fixture
paths resolve against the request's directory. A replay peer has exactly `host`
(`127.0.0.1` or `::1`) and `port` (1–65,535). There is no DNS or remote-host replay.

The binary format is deliberately small and explicit:

| Field | Encoding |
| --- | --- |
| Magic/version | Eight bytes: `50 59 54 52 41 46 01 00` |
| Record count | Unsigned 32-bit big-endian integer, 1–256 |
| Each record | `offset_ms: u32`, `direction: u8`, `length: u32`, then exactly `length` payload bytes |
| Direction | 0 sends; 1 receives and compares |
| Time offsets | Nondecreasing, 0–60,000 ms; earliest start relative to successful connection |

Empty payloads are valid and retain their scheduled event, without socket I/O.
Adjacent receives may consume coalesced wire bytes; network chunk boundaries have
no meaning. Invalid magic/version, count, direction, schedule, lengths, truncated
records and extra fixture bytes fail before any connection. Diagnostics identify
the first failed record and file offset. Record indices are zero-based; `-1`
means a file-level, request or connection failure. An error after the last record
uses the record count as its index.

`limits` has exactly `fixture_bytes` (12–8,388,608), `records` (1–256),
`payload_bytes` (0–1,048,576) and `scheduled_ms` (0–60,000). Requests are at most
65,536 bytes. All integers are strict; booleans, duplicate JSON keys and unknown
fields fail. Inputs must be regular files, and final symlinks/FIFOs/directories
are rejected. Files are read in 64 KiB chunks with size and metadata checks.
The bounded fixture snapshot remains in memory, so later source replacement
cannot alter the bytes that were validated or sent. This is a bounded fixture
runner, not an unbounded packet-capture reader. Parent directories are cooperative.

`timeouts` has exactly `connect_ms` and `record_ms` (1–60,000 each), and `total_ms`
(1–120,000). The total starts immediately before connection and includes waits,
I/O and final EOF. Each record gets one absolute I/O deadline, clipped to the
remaining total; fragments never renew it. Offsets are earliest starts, not
promises of precise timing or concurrency. Records execute sequentially. Actual
start, lag, duration and total elapsed time are observations, not reproducible
fixture data. A schedule beyond the remaining total fails before waiting for it.

After all records, the client half-closes sending and requires real peer EOF
within the remaining record/total budget. Extra reply bytes, early EOF, mismatch,
connection failure and I/O timeout fail. A mismatch reports the exact payload
byte offset and expected/actual byte values. An I/O failure reports a completed
prefix; a failed send may have partially reached the peer, so that prefix is not
claimed to be an exact wire count. Socket errors use the portable `io_error`
code, with a phase and record, rather than platform-specific exception text.

Output is one JSON document on stdout: version, mode, content length/SHA-256,
record offsets, lengths, schedules, payload digests and a 32-byte hex preview.
Replay adds event timings and outcomes. Failure reports include structured
`code`, `phase`, `record`, `offset` and `offset_kind`; request/read errors use
`invalid_input`. Success exits 0; failure exits 2. Redirect stdout to retain an
inspection/transcript. The program does not modify fixtures or requests.

Checks include 12 generated fixtures with 69 records, every prefix of the compact
fixture, malformed fields, both loopback address families, scheduled sends
observed independently by the peer, immutable snapshots after source replacement,
fragmented/coalesced replies, exact byte mismatch and nonzero record indices,
early/extra/missing EOF, bounded record and total deadlines, maximum 256 records,
1 MiB payloads and an 8 MiB fixture. Four inspector/replayer engine pairs transfer
actual fixtures and reports, replay edited fixtures in the reverse direction,
and preserve their source exports.
