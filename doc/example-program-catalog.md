# Example program catalog for the Python-to-Rust transpiler

This catalog contains **120 proposed programs across 12 areas**, including 30
networking programs. Each has a **200–500 Python source-line target**, a bounded
feature set, a compiler/runtime focus, and an observable acceptance check.

These are design estimates, not measured implementations. Count substantive
Python application code across the whole project; exclude tests, comments,
docstrings, blank lines, fixtures, vendored code, generated Rust, and bulk embedded
HTML/CSS/assets. A short implementation should gain useful behavior, not padding.
If the complete scoped program exceeds 500 lines, revise its scope explicitly
before implementation; do not silently omit its stated behavior.

Implementation and verification are tracked in the [application corpus](../examples/corpus/README.md).
The machine-readable manifest retains all 120 IDs. Use `tools/corpus.py --status`
for current evidence; planned, implemented, transpiled and behaviorally verified
are distinct states, and changed source invalidates earlier results.

## How to read the list

- **B — baseline candidate:** the scoped design appears expressible with today's
  project/service APIs. This is a hypothesis to test, not a claim that it compiles.
- **E — extension target:** at least one specific language/runtime addition is
  expected. The row lists the main additions; implementation may reveal others.
- Each program should be runnable with CPython and as a standalone generated Rust
  application, usually in 2–5 small Python modules. Keep the application algorithms,
  protocol rules, validation and orchestration in Python. Native adapters should
  expose general operations, not implement the entire example.
- Baseline programs can take configuration from JSON files/environment variables
  or HTTP requests. A full argparse-based CLI is an additional shared extension;
  it is not presumed to work already.
- Use readable typed Python. Do not contort a program to evade an unsupported
  operation: record the gap and extend the transpiler when appropriate.

Fit estimates were checked against the local project on **2026-10-07**:
[service compiler](../py2rust/compiler/service.py), [Python runtime](../py2rust/stdlib.py),
[project linker](../py2rust/compiler/project.py), [service contract](service-subset.md), and
[TCP contract](service-subset.md). The general web API supports request headers,
query parameters and binary bodies; the older HTTP client still has a narrower
interface. TCP is now also available in complete service/project programs through
scoped `py2rust.stdlib` handles; the preliminary TCP frontend is retired. Richer record behavior, broader exception
handling, source-level async/await, float floor-division/modulo, and several collection and
filesystem operations remain useful extension targets.
Bounded worker callbacks are now available through `parallel_map`, as exercised by 020.
Application 021 also establishes scoped TCP resources, absolute I/O deadlines,
byte concatenation/slicing and checked unsigned integer byte codecs.
Application 022 establishes Unix socket readiness, nonblocking partial I/O,
bounded per-peer queues, slow-reader eviction, byte substring search, list removal
and dictionary/JSON-object key deletion.
Application 023 adds insertion-ordered typed-dictionary key iteration and bounded
ASCII decimal parsing, exercised by a complete SMTP capture service with an
independent client and interrupted-publication recovery.
Application 024 uses those capabilities unchanged for a complete RESP2 store,
including concurrent peers, binary values, atomic increments, expiration and
durable snapshots, verified with redis-py and an independent state model.
Application 025 establishes scoped UDP sockets with source addresses, explicit
truncation, empty datagrams and bounded waits. Its complete directory/client
project verifies announcement ordering, expiry, discovery pagination, reply
correlation and retries after a lost acknowledgement across both engines.
Application 026 adds integer bitwise operators and checked shifts. Its five-module
DNS diagnostic encodes and parses real DNS packets, validates compressed names,
selects A/AAAA answers and handles malformed replies and bounded retries.
Application 027 adds typed dataclass records, list slices and dictionary-key
snapshots, explicit numeric float conversion, canonical base64, SHA-1 bytes and
repeating XOR. Its five-module WebSocket server keeps the upgrade, frame codec,
fragmentation and room event loop in Python, with independent native-client checks.
Application 028 reuses that subset for a six-module MQTT telemetry sink. It adds
no application-specific Rust: the variable-length codec, enum/record peer state,
QoS-0 handling and durable topic history all transpile from Python. Independent
Paho and raw clients verify publishing, rejection, recovery and buffered EOF.
Application 029 adds iteration over homogeneous fixed tuples, used in readable
transfer-path validation. Its six Python modules compile to one executable with
sender and receiver modes. Independent checks cover durable chunk acknowledgements,
verified resume prefixes, lost replies, changed sources, publication recovery and
bounded-memory transfers, including all four Python/Rust endpoint combinations.

Application 030 adds scoped filesystem Unix sockets, readiness, owned-path cleanup
and bounded stale-socket recovery, plus typed conditional expressions. Its command
bus and batch client compile together from six Python modules. Independent checks
cover correlated replies, receipt-cache behavior, concurrent peers, graceful
shutdown and crash recovery in both engines and across mixed pairs.

Application 031 adds explicit metadata observations, bounded directory-name listing
and symlink-target reading. Its four-module inventory reporter verifies exclusions,
permission failures, hard links, sparse files, timestamps and traversal bounds.
A 2,000-file fixture also motivated borrowing named collections during indexed
reads and length checks while preserving owned results and evaluation order.

Application 032 adds atomic no-overwrite Linux moves, scoped Unix advisory file
locks and sets constructed from typed scalar lists. Four Python modules implement
reviewed plans, content/identity guards, two-phase staging, exact-state recovery
and a resumable reverse journal. Independent checks include swaps, directory and
symlink entries, 50 interruption boundaries, killed processes and real permission
failures; the native executable uses no Python runtime.

Application 033 uses six Python modules for bounded traversal, size/digest
bucketing, streamed byte confirmation, hard-link accounting and review-only
plans. It establishes indexed list append/extend, borrowed nested reads and
borrowed membership with Python evaluation order. Checks include deliberate
digest-prefix collisions, changed input, incomplete scans and two 160 MiB files
plus a 1,000-file group under 128 MiB per process. No application-specific Rust
or Python runtime is used by the generated executable.

Application 034 adds private exclusive directory creation, symlink creation,
permission/mtime restoration and lazy signed range steps. Six Python modules
implement content-addressed incremental backup, checksummed version manifests,
retention and atomic publication of restored trees, preserving internal hard links.
Independent checks include historical versions, corruption, killed processes,
filesystem write failures and a 160 MiB backup/restore under 128 MiB per process.

Application 035 adds JSON/None identity tests and correct eager dictionary-get
argument evaluation without copying named mappings. Six Python modules implement
a three-way synchronization planner with common baselines, subtree conflicts,
ordered copy/remove operations and an idempotent dry run. Independent execution
covers 125 type/presence combinations plus mixed edits, protected exclusions and
1,001 files (including one 160 MiB file) under 128 MiB per process.

Application 036 adds regular-file replacement, list/set/dictionary-to-list
conversion and canonical JSON with stable binary64 number formatting. Six Python
modules implement immutable blobs/manifests, named roots, retrieval and complete
graph-based collection. Checks include a shared 40-manifest DAG, interruption and
corruption recovery, capacity bounds, a 160 MiB blob under 128 MiB per process,
and all four Python/Rust writer-reader combinations over one persistent store.

Application 038 adds chained comparisons with single evaluation and short-circuit
behavior, plus correct set inclusion ordering inside and outside sequences.
Five Python modules implement nested configuration overlays, complete per-node
provenance, explicit type-change permissions and guarded atomic export. Independent
checks cover all 36 JSON-kind transitions, 60 generated overlays, changed inputs,
publication interruptions and 4,000 keys under a 128 MiB process limit.

Application 039 adds integral Unix-time conversion, portable UTC date formatting
and Unicode reverse substring search. Five Python modules implement a download
organizer with date/extension classification, deterministic collision handling,
reviewed plans and resumable directory/move journals. Independent checks cover
interruption, corruption, competing writers, actual filesystem failures and
1000 files including a 160 MiB file under a 128 MiB address-space limit, plus
all four Python/Rust planner-recovery combinations.

Application 040 uses the existing subset for a five-module fixture-tree scaffolder.
It validates complete manifests, preserves literal text/binary contents, creates
missing directories, rejects collisions and emits checksummed ownership receipts.
Checks cover cleanup of recorded partial creations, refusal to claim unrecorded
objects, interrupted cleanup, permission failures, exact entry/byte limits and
all four Python/Rust creator-cleaner combinations. All application logic is Python
transpiled to one native executable; no Python runtime is required.

Application 041 adds bare exception re-raising in lexical handlers. Five Python
modules implement CSV parsing/formatting, declared column types, projection,
invalid-row reports and atomic publication of data/report bundles. The CSV codec
itself transpiles; this implementation does not require a native CSV adapter.
Checks compare with the independent Python `csv` library, exercise 10,000 rows,
4 MiB inputs, 64 KiB fields, publication interruptions and output expansion bounds,
and verify all four Python/Rust conversion pairs.

Application 043 adds a scoped buffered binary line reader with bounded chunks,
explicit line completion and logical byte positions. Four Python modules implement
JSONL filtering/projection, verbatim streaming quarantine, durable batch checkpoints
and cancellation/recovery. Independent checks verify every committed prefix before
recovery, preserve a 160 MiB oversized line, process a valid stream over 180 MB under
128 MiB per process, and resume jobs across all four Python/Rust writer-recovery pairs.

Application 044 adds homogeneous variadic tuples and recursive immutable tuple
keys for typed dictionaries/sets. Record collection reads also borrow their field
paths. Five Python modules implement composite-key inner/left CSV joins, exact
duplicate multiplicities, ordered projection and complete unmatched-row reports.
Independent checks include malformed CSV, interrupted atomic publication, capacity
limits and all eight Python/Rust conversion/join/import pipelines with application 041.

Application 045 adds typed-list insertion with Python's index-clamping and
argument-evaluation semantics. Five Python modules implement exact-value nested
JSON differences, escaped paths, guarded functional application, inverse patches
and atomic result bundles. Independent oracles check reconstruction, old values,
stale bases, array shifts, limits and failures, with all eight Python/Rust
generator/applier/reverser combinations.

Application 046 reuses the existing subset unchanged. Four Python modules implement
bounded event-log validation, normalized ID deduplication, sequence/time high-water
marks, observed state transitions, final missing ranges and atomic diagnostics.
Independent checks include malformed records, signed integer boundaries, input and
publication failures, 256 MiB process limits and all four Python/Rust filtering/checking
pipelines with application 043. The measured implementation is 500 substantive lines;
the row below retains its original design estimate.

Application 048 adds Unicode normalization and recursive typed-sequence sorting,
despite its original baseline forecast. Four Python modules preserve raw contact
variants, normalize values, compute transitive matching groups, retain per-value
provenance and separate field/identity conflicts for review. Independent graph
checks verify repeat-import idempotence, deterministic ordering, input/publication
failures, capacity bounds and all eight Python/Rust import/update/reimport combinations.
Its measured 432 substantive lines remain within the catalog's 200–500-line bound.

Application 049 adds exact mixed integer/float JSON scalar comparison and checked
JSON-number addition. Five Python modules implement a bounded filter/select/order/group
language, escaped nested paths, source-position diagnostics, stable merge ordering,
grouped counts/sums and atomic saved results. Independent query-algebra checks include
equivalent queries, numeric limits and malformed expressions; all eight mixed-engine
CSV import/query/export pipelines consume actual output files. Its measured 500
substantive lines fit the catalog bound; callback-based sorting remains outside the
subset, so the ordering algorithm is expressed directly in Python.

Application 050 reuses the existing subset without additional runtime changes.
Three Python modules (242 substantive lines) partition JSONL by normalized UTC date
and exact topic, preserve duplicates and source order, and atomically publish shards
with an independently verified count/checksum manifest. Checks include byte-identical
repeat jobs, bounds, changing inputs, interrupted publication and all four Python/Rust
writer-reader combinations consuming actual shard files.

Application 051 adds true division for matching integer or float operands,
including once-rounded integer ratios rather than rounded-operand division.
Four Python modules (365 substantive lines) replay LRU cache traces, inspect recency,
collect cumulative hit statistics and save/restore checksummed state. An independent
logical-access-clock model verifies overwrites, zero capacity, peeks, resizing,
complete event histories and all eight Python/Rust save/resume/read combinations.

Application 052 reuses the existing subset for a four-module HTTP TTL notebook
(310 substantive lines). It stores opaque JSON values, replaces deadlines, lists
live entries, sweeps expired records and atomically saves bounded snapshots.
Every read commits its clock high-water mark before returning, preventing expired
values from reappearing after restart and clock rollback. Independent record-list
checks cover 653 transitions, concurrent clients, real wall-clock expiry, malformed
state and interrupted saves. Eight mixed-engine write/update/read combinations
consume the same saved files.

Application 053 adds five generic `heapq` operations over named typed lists.
Four Python modules (415 substantive lines) implement a persistent priority work
queue with stable sequence ties, queued/running states, cancellation, acknowledgement
and retries that join the tail of their priority. Snapshots contain logical jobs
and validated counters; restoring reconstructs the heap. An independent sorted-record
scheduler checks 38 traces and all 22 splits of a representative trace. Eight
Python/Rust save/retry/resume combinations preserve actual snapshot and event bytes.

Application 054 adds generic typed set algebra and Unicode 15.1 full default
case folding. Seven Python modules (419 substantive lines) implement an inverted
document index, replacement/deletion, nested AND/OR expressions and weighted
ranked results. An independent scalar tokenizer and brute-force document scan
verify 40 traces and all 20 splits of a representative trace. Eight Python/Rust
save/update/query combinations preserve actual snapshot and event bytes, with
deleted and replaced terms absent from restored postings.

Application 055 adds self-recursive records through typed collections and quoted
type references across project imports. Five Python modules (381 substantive lines)
implement a Unicode prefix trie with normalized replacements, usage counts, ranked
suggestions, deletion with branch pruning and dictionary export. A flat-dictionary
oracle checks 41 traces and all 23 splits of a representative trace. Eight
Python/Rust save/update/suggest combinations preserve actual snapshot, export and
event bytes. The trie reaches its 8192-node boundary in both engines.

Application 056 adds typed bytearrays, natural logarithms and checked downward
rounding. Four Python modules (395 substantive lines) implement a sized Bloom
filter, exact ingestion audit, observed false-positive measurements and raw bit
export. An independent arbitrary-precision bitset model checks 36 traces, 12
restart splits, 49 invalid snapshots and all eight Python/Rust save/resume/check
combinations. Saturated filters, audit capacity and interrupted publication are
verified without silently discarding new keys on a false positive.

For protocol examples, implement only the explicitly named subset and test its
rejections; do not claim complete standards compliance. Input/output and report
handling are part of every scope, so these are applications rather than isolated
algorithm functions.

## 1. HTTP servers and application services

| ID | Program and bounded scope | Python LOC | Coverage focus | Fit / principal extension | Acceptance check |
| --- | --- | --- | --- | --- | --- |
| 001 | **File-drop service:** upload files, list metadata, download by ID, enforce sizes, persist an index, and expire temporary entries. | 300–420 | Binary HTTP, paths, JSON, dates, persistence | B | Download arbitrary bytes unchanged; expired and unknown IDs return the documented statuses. |
| 002 | **Webhook inbox:** validate event envelopes, deduplicate event IDs, retain receipts, filter history, and export selected events. | 250–350 | HTTP validation, sets, JSON arrays, logging | B | Repeated delivery creates one stored event; malformed envelopes leave state unchanged. |
| 003 | **Bookmark redirector:** create named links, validate destinations, issue redirects, count visits, and import/export bookmarks. | 220–320 | Response headers, status codes, strings, atomic files | B | Redirect Location is correct; restart preserves links and visit counts. |
| 004 | **Expiring paste service:** create text pastes with deadlines, distinguish public/private IDs, enforce size limits, and sweep expired entries. | 250–350 | UTF-8, timestamps, tokens, permission checks | B | A Unicode paste survives restart and becomes inaccessible at its configured deadline. |
| 005 | **Versioned settings API:** update schema-listed fields, compare revision numbers, retain history, and roll back a selected revision. | 300–420 | JSON types, enums, copy/value semantics, history | B | Stale updates fail; rollback reconstructs the exact earlier settings. |
| 006 | **Scenario-based mock API:** load route definitions, match method/path, validate request fields, advance scenario states, and record a transcript. | 320–450 | Routing, state machines, JSON, binary/text responses | B | A scripted request sequence yields exactly the configured statuses and state transitions. |
| 007 | **Leased work queue:** enqueue JSON jobs, claim with a deadline, acknowledge, requeue expired leases, and inspect queue state. | 350–480 | State transitions, time, persistent collections | B | A crashed worker's job is reclaimable; an expired acknowledgement cannot remove a new lease. |
| 008 | **Resource reservation service:** create resources, book UTC intervals, reject overlaps, cancel bookings, and show an agenda. | 300–420 | Date comparisons, interval rules, validation | B | Overlapping bookings fail; adjacent half-open intervals and cancellations behave consistently. |
| 009 | **Per-key rate-limit service:** maintain sliding request windows, return allow/deny decisions, expose quota state, and restore it after restart. | 250–350 | Float timestamps, list filtering, HTTP statuses | B | Boundary-time requests obey the chosen window rule; different keys remain independent. |
| 010 | **Server-sent-event notification board:** publish small events, stream subscriptions, retain replay IDs, and handle reconnects and slow readers. | 350–480 | Long-lived HTTP, buffering, cancellation | E: streaming responses, backpressure and disconnect handling | Reconnect resumes after the last acknowledged event; a slow subscriber does not block others. |

## 2. HTTP clients, integration and resilience

| ID | Program and bounded scope | Python LOC | Coverage focus | Fit / principal extension | Acceptance check |
| --- | --- | --- | --- | --- | --- |
| 011 | **Service health monitor:** poll configured endpoints, record latency and outages, apply failure thresholds, and write a status report. | 280–400 | HTTP errors, clocks, logging, time series | E: recoverable network errors | One unreachable endpoint is reported without stopping checks of the remaining endpoints. |
| 012 | **Paginated JSON harvester:** follow a documented next-page URL, reject repeated cursors, deduplicate records, checkpoint, and resume a bounded import. | 280–400 | HTTP client, sets, JSON, checkpoint files | B | Restart resumes at the saved page; overlapping pages produce no duplicate record IDs. |
| 013 | **Resumable file downloader:** fetch in ranges, save progress, detect changed validators, verify a digest, and atomically publish the final file. | 350–500 | Binary client I/O, HTTP headers, hashing | E: request/response headers, binary streaming, file handles and digest API | Interrupted download resumes correctly; a changed ETag prevents mixing file versions. |
| 014 | **HTTP contract test runner:** load fixture requests, check statuses and selected JSON fields, compare snapshots, and generate a failure report. | 300–420 | JSON schemas, client/server behavior, diagnostics | B | A known faulty test server produces the expected named mismatches and summary counts. |
| 015 | **Webhook delivery outbox:** persist deliveries, send idempotency keys, classify failures, back off, and move exhausted items to a dead-letter list. | 350–480 | Retry state, headers, persistence, failure recovery | E: custom client headers and recoverable I/O errors | A scripted sequence of disconnects and HTTP errors preserves pending deliveries across restart. |
| 016 | **Local website link auditor:** crawl a bounded local site, resolve relative links, deduplicate URLs, report broken links, and stop at a depth budget. | 300–450 | URL resolution, HTML parsing, graph traversal | E: HTML parser, URL resolution and recoverable client errors | Cycles terminate; relative links resolve correctly; external hosts are excluded by policy. |
| 017 | **JSON endpoint change watcher:** poll snapshots, compare nested fields, suppress configured paths, retain changes, and render a readable difference report. | 300–420 | Recursive JSON, object traversal, timestamps | E: general object-key iteration and error recovery | Ignored fields produce no event; nested additions/removals are reported once per change. |
| 018 | **Quota-aware API batcher:** read pending requests, honor rate-limit headers, checkpoint completed IDs, and resume without repeating successful work. | 320–450 | Response headers, retry timing, queues | E: client response headers and recoverable errors | A fixture server's retry deadlines are respected; already completed IDs are skipped after restart. |
| 019 | **Circuit-breaker gateway:** forward a fixed family of requests, count upstream failures, open the circuit, probe recovery, and expose state. | 350–480 | Nested HTTP calls, enums, deadlines | E: recoverable client errors and forwarding headers/bodies | Closed/open/half-open transitions match a deterministic failure-and-recovery trace. |
| 020 | **Bounded HTTP load probe:** run a configured request schedule, limit concurrency, record latency buckets, and export reproducible summaries. | 320–450 | Concurrency, cancellation, numeric aggregation | E: tasks/async or worker threads, arithmetic and histogram support | Concurrency never exceeds the limit; cancellation leaves no active workers or missing results. |

## 3. TCP, UDP and application protocols

| ID | Program and bounded scope | Python LOC | Coverage focus | Fit / principal extension | Acceptance check |
| --- | --- | --- | --- | --- | --- |
| 021 | **Framed TCP task broker:** accept length-prefixed JSON jobs, acknowledge IDs, enforce frame limits, and maintain a persistent pending list. | 350–480 | Framing, bytes, JSON, sockets | E: unified TCP/project profile, byte-buffer operations and binary integers | Split and coalesced writes yield the same jobs; oversized/truncated frames are rejected. |
| 022 | **Line-based room chat:** maintain several TCP peers, nicknames and rooms; broadcast messages, bound queues, and clean up disconnected peers. | 350–480 | Socket ownership, per-peer state, Unicode | E: multiplexed sockets, buffer operations and cancellation | A slow or disconnected peer does not prevent messages reaching other room members. |
| 023 | **SMTP capture server:** support HELO/EHLO, MAIL, RCPT, DATA, RSET and QUIT; handle dot stuffing and save received messages locally. | 350–480 | Protocol enums, CRLF parsing, file persistence | E: TCP/string integration and recoverable per-connection errors | An independent SMTP client delivers a message; dot-stuffed lines and invalid command order are handled correctly. |
| 024 | **RESP key-value server:** implement a bounded PING/GET/SET/DEL/INCR command set, expirations, a snapshot, and command errors. | 400–500 | Nested frame parsing, maps, integers, time | E: unified TCP, numeric parsing, byte slicing and map deletion | An independent RESP client agrees on null replies, binary values and integer overflow errors. |
| 025 | **UDP service directory:** announce services, reply to discovery requests, age out peers, deduplicate announcements, and print a registry. | 250–380 | Datagram semantics, time, peer records | E: UDP and socket address types | Duplicate/out-of-order announcements do not corrupt the registry; stale peers expire. |
| 026 | **DNS lookup diagnostic:** issue A/AAAA queries, match response IDs, decode bounded compression pointers, retry, and print answers/errors. | 350–480 | Binary parsing, bit operations, UDP | E: UDP, struct-like byte codecs, bitwise operations and timeout recovery | Local DNS fixtures cover valid compression, pointer cycles, truncation and mismatched IDs. |
| 027 | **Small WebSocket room server:** upgrade HTTP, accept bounded text frames, handle ping/pong/close, broadcast, and reject unsupported frames. | 400–500 | HTTP upgrade, framing, connection state | E: upgraded connections, byte/bit operations, digest/base64 and multiplexing | An independent client exchanges Unicode text and ping/pong; invalid masking and over-limit frames fail predictably. |
| 028 | **MQTT telemetry sink:** implement CONNECT, QoS-0 PUBLISH, PING and DISCONNECT; validate packet lengths and persist a per-topic history. | 350–500 | Variable-length framing, enums, JSON export | E: TCP integration, binary codecs and recoverable peer errors | A local client publishes multiple topics; unsupported QoS and malformed lengths are rejected. |
| 029 | **Chunked TCP file transfer:** pair a sender and receiver with chunk acknowledgements, resume offsets, checksums and safe final-file publication. | 400–500 | Bidirectional sockets, streaming files, integrity | E: unified TCP, file handles, seek, hashing and I/O recovery | Interrupted transfer resumes and reproduces exact bytes; a corrupted chunk is detected. |
| 030 | **Unix-domain command bus:** serve local request IDs, dispatch a few commands, return structured errors, and clean up socket files on shutdown. | 280–400 | Local IPC, resource lifetime, filesystem cleanup | E: Unix sockets, context-managed resources and graceful shutdown | Multiple local clients receive correctly correlated replies; restart handles a stale socket path. |

## 4. Files, directories and durable artifacts

| ID | Program and bounded scope | Python LOC | Coverage focus | Fit / principal extension | Acceptance check |
| --- | --- | --- | --- | --- | --- |
| 031 | **Directory inventory reporter:** traverse a tree, apply exclusions, record sizes/types/times, aggregate by extension, and export a manifest. | 250–380 | Paths, traversal, metadata, aggregation | E: stat/scandir or walk, sorting and per-file error recovery | Fixture manifests match; symlinks, inaccessible paths and empty directories follow the documented policy. |
| 032 | **Batch rename planner:** apply naming rules, preview collisions, execute an approved plan in a fixture tree, and emit a reversible journal. | 300–420 | Regex, paths, transactions, rollback records | E: rename, canonical paths, metadata and recoverable file errors | Collisions cause no partial renames; applying the reverse journal restores original names. |
| 033 | **Duplicate-file finder:** group by size then digest, verify candidate bytes, report duplicates, and export an optional deduplication plan. | 300–420 | Hashing, binary files, grouping | E: metadata, incremental digests and streaming reads | Equal-sized different files remain distinct; hash matches are confirmed by byte comparison. |
| 034 | **Incremental snapshot backup:** copy changed files, store version manifests, restore a selected version, and enforce a simple retention policy. | 400–500 | Metadata, hashes, file copying, recovery | E: traversal, streaming copies, metadata and controlled deletion | A restored fixture tree matches its snapshot; an interrupted snapshot is never advertised as complete. |
| 035 | **Two-tree synchronization planner:** compare source and destination, identify conflicts, produce ordered copy/remove operations, and validate a dry run. | 300–420 | Tree comparison, deterministic ordering, conflicts | E: metadata, traversal, hashing and richer collections | The plan is idempotent and preserves conflicts instead of silently overwriting them. |
| 036 | **Content-addressed artifact store:** import files by digest, attach named manifests, retrieve artifacts, and collect only unreferenced blobs. | 350–480 | Hash maps, graph reachability, files | E: digests, metadata, streaming copies and deletion | Shared blobs are stored once; collection preserves every blob reachable from a live manifest. |
| 037 | **Batch text normalizer:** process an explicit file manifest, normalize line endings and trailing spaces, preview changes, save backups, and report results. | 220–320 | Unicode, string slices, text I/O, atomic replacement | B | Reapplying normalization changes nothing; backups reproduce original UTF-8 bytes and line endings. |
| 038 | **Layered configuration merger:** merge nested base/site/user files, track value provenance, flag type conflicts, and export the resolved document. | 300–420 | Recursive dictionaries, JSON, diagnostics | E: general mapping iteration and recursive record traversal | Override precedence and provenance are correct; incompatible value types produce precise paths. |
| 039 | **Download-folder organizer:** classify by extension and date, preview target folders, resolve filename collisions, move files, and journal changes. | 300–420 | Paths, metadata, date formatting, file mutation | E: stat, rename and general date formatting | A fixture run matches its preview; name collisions do not overwrite unrelated files. |
| 040 | **Fixture-tree scaffolder:** consume a JSON manifest, validate relative names, create directories and text/binary fixtures, and emit a cleanup receipt. | 250–350 | JSON validation, paths, bytes, directories | B | The generated tree matches the manifest; absolute/traversal names and existing-file collisions are rejected. |

## 5. Data ingestion and structured transformations

| ID | Program and bounded scope | Python LOC | Coverage focus | Fit / principal extension | Acceptance check |
| --- | --- | --- | --- | --- | --- |
| 041 | **CSV/JSON converter:** handle quoted cells and embedded newlines, apply declared column types, select columns, and report invalid rows. | 250–380 | Text codecs, type conversion, tabular data | E: CSV adapter, numeric conversions and row-level error recovery | Round trips preserve commas, quotes, empty cells and embedded newlines. |
| 042 | **Schema-driven record cleaner:** validate fixed fields, normalize strings and UTC timestamps, apply defaults, and write accepted/rejected JSON records. | 300–420 | JSON extraction, regex, dates, diagnostics | B | Every input record is either preserved in accepted output or reported with field-level rejection reasons. |
| 043 | **Streaming JSONL transformer:** read line by line, filter/project fields, maintain bounded batches, quarantine bad rows, and checkpoint offsets. | 300–420 | Iteration, streaming, cancellation, error boundaries | E: file handles/seek, iterators and recoverable decode errors | Memory remains bounded with increasing input; restart neither loses nor repeats committed batches. |
| 044 | **CSV join utility:** perform inner/left joins on declared keys, handle duplicate keys, select output fields, and report unmatched rows. | 320–450 | Hash joins, composite keys, collections | E: CSV, tuple-key dictionaries, mapping iteration and sorting | Duplicate-key multiplicities and unmatched rows agree with a small independent reference implementation. |
| 045 | **Nested JSON diff and patch:** compare objects and arrays, produce path-based changes, validate old values, and apply or reject a patch. | 350–480 | Recursive data, indexing, copy semantics | E: mapping iteration, list mutation and recursive value types | Applying a generated patch reconstructs the target; a stale base document fails without partial mutation. |
| 046 | **Event-log consistency checker:** validate event IDs, sequence progression, UTC ordering and allowed state transitions; export a diagnostic report. | 250–350 | Enums, sets, temporal invariants, pretty output | B | Fixtures identify exact duplicate IDs, missing sequence numbers and invalid transitions. |
| 047 | **Versioned configuration migrator:** chain explicit schema migrations, validate each version, back up inputs, and recover from an incomplete upgrade. | 280–400 | Multi-module transforms, JSON, atomic state | B | Every supported old version reaches the same current schema; invalid inputs preserve the original file. |
| 048 | **Contact import deduplicator:** normalize names/addresses, merge by declared keys, retain provenance, and separate ambiguous conflicts for review. | 300–420 | Unicode, dictionaries, stable ordering, business rules | B | Re-import is idempotent; conflicting values remain visible instead of being silently discarded. |
| 049 | **JSON query console:** support a small filter/project/order/group grammar, validate field paths, and pretty-print results from saved datasets. | 350–480 | Parsing, higher-order sorting, grouped collections | E: richer collection traversal, sort keys and arithmetic | Equivalent queries produce matching results; malformed expressions report their source positions. |
| 050 | **JSONL partition writer:** load a bounded input file, group records by date/topic, write named shards, and persist row-count manifests. | 250–350 | Nested collections, strings, paths, atomic writes | B | The shards contain every input record exactly once and their counts match the manifest. |

## 6. Data structures used in storage and search

| ID | Program and bounded scope | Python LOC | Coverage focus | Fit / principal extension | Acceptance check |
| --- | --- | --- | --- | --- | --- |
| 051 | **LRU cache workbench:** replay GET/PUT/DELETE traces, enforce capacity, inspect recency, collect hit statistics, and save/restore state. | 250–350 | Ordered maps, deletion, identity/value behavior | E: map deletion/reordering or deque operations, numeric division | Eviction order matches a reference trace, including overwrite and zero-capacity cases. |
| 052 | **TTL key-value notebook:** store JSON values with deadlines, inspect live entries, sweep expired entries, and persist bounded snapshots. | 250–350 | Time, JSON, map/list updates, state recovery | B | Expiration and replacement deadlines survive restart; expired entries never appear in reads. |
| 053 | **Persistent priority work queue:** enqueue with priorities, preserve tie order, cancel or retry jobs, and reconstruct the heap from a snapshot. | 300–420 | Heaps, ordered tuples, queue state | E: heapq, richer tuple ordering and collection operations | Pop order is stable for ties and unchanged after restoring a saved queue. |
| 054 | **Small document search engine:** tokenize text, build an inverted index, update/remove documents, evaluate AND/OR queries, and rank results. | 350–480 | Sets, postings lists, tokenization, ranking | E: set algebra, map iteration/deletion and sorting | Results agree with a brute-force scan; removed documents disappear from all postings. |
| 055 | **Prefix autocomplete index:** insert/update terms, delete terms, count usage, retrieve ranked prefix suggestions, and export the dictionary. | 300–420 | Trie nodes, recursive types, traversal | E: typed recursive records, mutable nested maps and sorting | Suggestions match a reference scan for Unicode prefixes, updates and deletions. |
| 056 | **Bloom-filter ingestion gate:** size a filter, ingest keys, persist its bit array, report likely duplicates, and compare against an exact audit set. | 300–420 | Bitsets, hashing, numerical sizing | E: bytearray/bit operations, digest API and math | No inserted key becomes a false negative; measured false positives and storage size are reported. |
| 057 | **External record sorter:** generate bounded sorted runs, merge them, verify ordering, and clean up interrupted temporary runs. | 350–480 | Iterators, heaps, file resources, stable sort | E: streaming files, heapq, keyed sorting and resource cleanup | Output equals an in-memory reference while peak working data remains within the configured bound. |
| 058 | **Time-series ring-buffer recorder:** ingest samples, retain a rolling window, query summaries, export selected intervals, and restore saved state. | 280–400 | Deques, time windows, numeric aggregation | E: deque operations, division and numerical helpers | Retention boundaries and summaries match a reference list across wraparound and restart. |
| 059 | **Interval-indexed log browser:** import start/end spans, index overlaps, query a time range, update records, and show matching events. | 350–480 | Interval trees, bisect, recursive records | E: typed records, ordered insertion and collection mutation | Indexed results equal brute-force interval checks for touching, nested and empty intervals. |
| 060 | **Append-only miniature database:** implement GET/SET/DELETE, journal records, replay on startup, detect an incomplete tail, and compact to a snapshot. | 400–500 | Durable logs, binary/text boundaries, recovery | E: append/seek/fsync, checksums, truncation and error recovery | Restart after each injected write interruption yields the last complete committed state. |

## 7. Algorithms inside useful applications

| ID | Program and bounded scope | Python LOC | Coverage focus | Fit / principal extension | Acceptance check |
| --- | --- | --- | --- | --- | --- |
| 061 | **Route planner:** load a named weighted graph, apply closures, use Bellman–Ford, reconstruct routes, and explain unreachable paths or negative cycles. | 320–450 | Graphs, dictionaries, integer arithmetic, JSON | B | Small graphs agree with an exhaustive oracle; closures and negative cycles produce correct diagnostics. |
| 062 | **Dependency build planner:** load targets and edges, select requested targets, find prerequisites, produce build layers, and explain cycles. | 300–420 | Graph traversal, sets, maps, deterministic reports | B | Every prerequisite precedes its target; cycle fixtures return a valid cycle witness. |
| 063 | **Small shift scheduler:** read availability and staffing requirements, use bounded backtracking, score candidates, and explain unsatisfied constraints. | 350–480 | Backtracking, records, mutable search state | E: dataclasses, nested list mutation and richer ordering | Every proposed schedule satisfies hard constraints; tiny cases match exhaustive best scores. |
| 064 | **Parcel packing planner:** group items under capacity rules, use a documented packing heuristic, retain package manifests, and report unplaceable items. | 280–400 | Greedy algorithms, sorting, record updates | E: keyed sorting and typed records | Every item is assigned once or rejected explicitly; no package exceeds its capacity. |
| 065 | **Terrain route visualizer:** load a text grid, assign terrain costs, find a path with A*, render it in ASCII, and export search statistics. | 320–450 | Priority queues, grids, path reconstruction | E: heapq, nested sequence updates and numeric helpers | Path cost agrees with a reference shortest-path solver; unreachable destinations are handled. |
| 066 | **Dependency impact auditor:** load a module graph, compute reverse dependencies and strongly connected groups, then explain the impact of changed modules. | 320–450 | Graph algorithms, recursive state, collections | E: richer sets/maps and convenient recursive records | Reported affected modules match reachability; strongly connected groups satisfy mutual reachability. |
| 067 | **Repeated-phrase document auditor:** tokenize documents, index n-grams, merge overlapping matches, and produce a cross-document report. | 320–450 | Sequence windows, tuple keys, grouping | E: list slicing, tuple-key maps and sorting | Known repeated passages are found with stable positions and without counting overlapping windows repeatedly. |
| 068 | **Huffman file compressor:** construct a codebook, encode a bounded file, write a checked container, decode it, and report compression statistics. | 350–480 | Trees, heaps, bitstreams, byte containers | E: heapq, binary codecs, mutable bytes and division | Empty, single-symbol and binary fixtures round-trip; malformed codebooks are rejected. |
| 069 | **Timetable journey planner:** load scheduled connections, account for transfer time, compute earliest arrival, and print the selected journey. | 350–480 | Temporal graphs, heaps, date arithmetic | E: heapq, duration operations and typed records | Results match exhaustive tiny timetables, including overnight journeys and missed transfers. |
| 070 | **Sudoku batch-solving tool:** read boards, validate givens, solve with a search budget, detect multiple solutions, and export diagnostics and statistics. | 300–420 | Backtracking, nested data, cancellation budgets | E: nested list mutation, integer division/modulo and richer record types | Invalid, unsatisfiable, unique and multiple-solution boards are distinguished correctly. |

## 8. Text processing, parsers and small languages

| ID | Program and bounded scope | Python LOC | Coverage focus | Fit / principal extension | Acceptance check |
| --- | --- | --- | --- | --- | --- |
| 071 | **Access-log analyzer:** parse a documented log format, extract request fields, aggregate status/path counts, select time windows, and report malformed lines. | 280–400 | Regex captures, time, maps, ranking | E: regex match groups, numeric parsing and sorting | Parsed fields and aggregate counts match hand-labeled fixture logs. |
| 072 | **Small static-site builder:** process a defined Markdown subset, generate heading anchors/navigation, escape HTML, and write a linked site from a manifest. | 350–480 | Unicode parsing, recursion, files, HTML generation | B | Golden pages match; duplicate headings remain linkable and source HTML is safely escaped. |
| 073 | **Template rendering engine:** support escaped substitutions, a bounded loop/condition syntax and includes; detect missing values and include cycles. | 350–480 | Recursive parsing, scopes, JSON, source errors | B | Nested templates match golden output; include cycles and malformed blocks report useful locations. |
| 074 | **Expression calculator with variables:** parse numbers and operators, support parentheses and assignment, retain a session, and report expression errors. | 300–420 | Tokenization, precedence, numeric types | E: numeric conversion, division/modulo and recoverable arithmetic errors | Precedence matches an independent evaluator; division by zero does not destroy the session. |
| 075 | **INI-style configuration editor:** parse sections and quoted string values, preserve a documented comment policy, expand named variables, and rewrite files. | 250–380 | String scanning, dictionaries, round-trip formats | B | Parse/write/parse preserves values; duplicate keys and variable cycles are diagnosed. |
| 076 | **Minimal command shell:** parse quoting, run external commands and bounded pipelines, manage environment overrides, and report exit statuses. | 350–500 | Processes, streams, parsing, resource cleanup | E: subprocess, pipes, process groups and signal handling | Arguments retain their quoting semantics; a failed pipeline leaves no live child processes. |
| 077 | **Python source-outline browser:** read a project manifest, parse modules, list definitions/imports/docstrings, and emit a cross-linked HTML outline. | 300–420 | AST traversal, recursive nodes, project structure | E: AST adapter or typed parser nodes | Outlines agree with CPython AST fixtures, including decorators and nested definitions. |
| 078 | **Regex batch rewrite tool:** prevalidate ASCII rules, preview literal replacements, back up explicitly listed files, and produce a per-rule audit. | 250–350 | Regex, text I/O, logging, dry-run behavior | B | Invalid rules cause no writes; literal replacement semantics match in Python and Rust. |
| 079 | **Tiny automation-language interpreter:** implement a documented let/if/repeat grammar, build an AST, execute within a step budget, and trace variables. | 350–480 | Tagged AST nodes, scopes, recursion, diagnostics | E: dataclasses/tagged unions, numeric conversion and recoverable errors | The step limit terminates loops; nested scopes and source-position errors match fixtures. |
| 080 | **Stateful syntax-highlighting exporter:** lex a small configuration language, handle multiline strings/comments, escape input, and emit themed HTML. | 250–380 | Enums, state machines, Unicode slices, HTML | B | Token boundaries match fixtures; unfinished strings and hostile markup cannot corrupt output HTML. |

## 9. Time, scheduling, automation and logging

| ID | Program and bounded scope | Python LOC | Coverage focus | Fit / principal extension | Acceptance check |
| --- | --- | --- | --- | --- | --- |
| 081 | **Recurring reminder daemon:** load fixed-interval UTC reminders, advance deadlines, apply a missed-run policy, persist progress, and log due reminders. | 250–350 | Time, enums, persistence, long-running loops | B | A supplied clock trace yields the expected reminders before and after restart. |
| 082 | **Cron schedule explorer:** parse a documented five-field subset, calculate the next runs, explain rejected expressions, and export a schedule. | 320–450 | Calendar arithmetic, sets, formatting | E: datetime field access, weekday/calendar operations and numeric parsing | Month boundaries, leap days and weekday combinations match known UTC fixtures. |
| 083 | **Activity timer journal:** start/pause/resume/stop named sessions over HTTP, retain completed intervals, and export totals in seconds. | 250–350 | Monotonic/wall time, state machines, JSON | B | Paused time is excluded; illegal transitions fail; completed intervals survive restart. |
| 084 | **Rotating log router:** read several live logs, parse levels, apply filters, route to files, rotate by size, and preserve read positions. | 350–480 | File handles, logging handlers, offsets | E: seek/tail, metadata, configurable handlers and I/O recovery | Rotation and restart neither skip nor duplicate complete input lines. |
| 085 | **Job deadline inspector:** read expected jobs and completion events, classify late/missing/on-time results, apply grace periods, and emit a report. | 220–320 | RFC3339, comparisons, enums, diagnostics | B | Exact deadline/grace boundaries are classified correctly, including explicit input time offsets. |
| 086 | **Cross-timezone appointment converter:** import appointments, resolve timezones, detect ambiguous/nonexistent times, and print equivalent schedules. | 280–400 | Timezone semantics, typed errors, formatting | E: zoneinfo, local datetime construction and fold handling | DST transitions are handled according to an explicit user-selectable ambiguity policy. |
| 087 | **Debounced directory watcher:** poll or subscribe to a tree, classify changes, collapse bursts, retain an event journal, and resume watching. | 280–400 | Filesystem events, timers, maps | E: metadata/watch API and cancellable waits | Rapid rewrites collapse into the configured event sequence; renames and deletions remain visible. |
| 088 | **Discrete-event scheduler simulator:** simulate arrivals, queues, workers and deadlines with a fixed seed, then export event traces and summary statistics. | 350–480 | Heaps, reproducible randomness, numerical aggregation | E: heapq, seeded random API and arithmetic | A seed reproduces the trace; conservation of jobs and queue-capacity invariants always hold. |
| 089 | **Structured-log redactor:** read bounded JSONL logs, validate selected fields, apply ordered literal/ASCII-regex masking rules, and produce audit counts. | 250–350 | JSON, regex, strings, logging, pretty output | B | Fixture secrets are absent from both output records and audit reports; unrelated fields are preserved. |
| 090 | **Checkpointed batch worker:** process deterministic record jobs in batches, save results and progress together, resume after interruption, and report completion. | 280–400 | Atomic snapshots, explicit state, restart semantics | B | Interrupting at each checkpoint boundary yields the same final results as an uninterrupted run. |

## 10. Operating-system and developer tools

| ID | Program and bounded scope | Python LOC | Coverage focus | Fit / principal extension | Acceptance check |
| --- | --- | --- | --- | --- | --- |
| 091 | **Process-based test runner:** load test commands, set temporary environments, capture output, enforce deadlines, and write a structured result report. | 320–450 | Subprocesses, deadlines, streams, cleanup | E: subprocess and process-group cancellation | Hanging and failing fixtures are reported correctly; timeout cleanup removes all child processes. |
| 092 | **Incremental build executor:** load a small dependency manifest, check file freshness, execute serial build steps, cache results, and explain rebuilds. | 350–480 | Filesystem metadata, graphs, child processes | E: stat, subprocess and recoverable command errors | Editing one input rebuilds exactly the affected targets; failed steps do not produce valid cache entries. |
| 093 | **Local process supervisor:** start configured services, capture logs, restart failures with backoff, expose status, and shut down the whole group. | 350–480 | Resource ownership, signals, asynchronous events | E: processes, signals and cancellable concurrent I/O | Flapping services obey restart limits; shutdown leaves no managed process running. |
| 094 | **Rust-import validation workbench:** dispatch JSON commands to a few small native adapters, validate results, compare Python references, and save an inspection report. | 250–380 | Multi-module imports, bytes/tuples/JSON, native boundaries | E: local recovery of fallible native calls; existing direct Rust imports cover normal cases | Checked integer conversion, Unicode, binary buffers, non-finite floats and Result errors behave as specified. |
| 095 | **Project code-metrics browser:** enumerate Python modules, count structural constructs, build import links, flag oversized functions, and export HTML/JSON reports. | 300–420 | ASTs, traversal, aggregation, source locations | E: AST adapter, directory traversal and sorting | Reported symbols and locations match a hand-labeled multi-package fixture. |
| 096 | **Small package constraint resolver:** read a local version index, parse a bounded semantic-version grammar, backtrack dependencies, and explain conflicts. | 350–480 | Parsing, search, immutable candidate state | E: typed records, ordering, richer collections and optional results | Tiny repositories agree with exhaustive solutions; unsatisfiable constraints have a reproducible explanation. |
| 097 | **Source-header compliance checker:** inspect a supplied file manifest, validate permitted headers and year strings, group violations, and emit suggested text edits. | 220–320 | Text slices, regex, dates as strings, reporting | B | Each fixture violation has an exact file/line; suggested edits preserve unrelated source text. |
| 098 | **Transfer benchmark harness:** launch local sender/receiver programs, vary payload sizes/chunking, measure completion, verify digests, and compare runs. | 300–420 | Cross-process networking, clocks, measurements | E: subprocess, hashing and richer numerical summaries | Python/Python, Python/Rust, Rust/Python and Rust/Rust pairs transfer identical fixture bytes. |
| 099 | **Environment configuration validator:** load a field schema, parse JSON-encoded scalar settings, apply defaults/dependencies, and print a redacted effective configuration. | 250–350 | Environment, JSON scalar types, enums, pretty output | B | Missing/invalid combinations are diagnosed; secret settings never appear unmasked in the report. |
| 100 | **Text diff and patch utility:** compare bounded text files with an LCS-based diff, create context hunks, check the base, and apply or reject a patch. | 350–480 | Dynamic programming, sequence mutation, text I/O | E: indexed list updates, richer iteration and sequence slicing | Diff/apply round trips preserve Unicode and final-newline state; stale hunks are rejected. |

## 11. Practical domain and numerical applications

| ID | Program and bounded scope | Python LOC | Coverage focus | Fit / principal extension | Acceptance check |
| --- | --- | --- | --- | --- | --- |
| 101 | **Shared-expense allocator:** import integer-cent expenses, split by declared shares, distribute remainder cents, retain settlements, and report balances. | 300–420 | Exact integer arithmetic, maps, deterministic rules | E: integer division/modulo and sorting | Allocated cents exactly equal the input total; settlement balances sum to zero. |
| 102 | **Inventory reservation ledger:** record receipts, reserve stock for orders, release/cancel reservations, reconcile counts, and persist an audit trail. | 300–420 | Enums, integer invariants, JSON, atomic persistence | B | No accepted transaction makes available stock negative; replay reproduces the same balances. |
| 103 | **Dimensional unit converter:** parse quantities, track dimension exponents, combine conversion factors, reject incompatible units, and retain a conversion notebook. | 300–420 | Typed records, tuples, numeric conversion | E: division, numeric parsing and compound dictionary keys | Round trips stay within tolerance; incompatible dimensions are rejected before producing values. |
| 104 | **Series/parallel circuit calculator:** load a bounded resistor tree, validate components, evaluate equivalent resistance, and explain each reduction step. | 280–400 | Recursive records, floats, arithmetic errors | E: division, typed recursive structures and recoverable numeric errors | Known circuits match analytic results; zero/invalid inputs follow documented rules without panics. |
| 105 | **Telemetry trend analyzer:** read timestamped samples, detect gaps, compute rolling statistics and outliers, and export a compact report. | 320–450 | Sliding windows, floating point, numerical stability | E: math/statistics helpers, division and deque operations | Summaries agree within declared tolerances; empty and constant series remain well-defined. |
| 106 | **Electricity-tariff simulator:** import interval consumption, apply time bands and tiers, compare fictional tariff definitions, and explain each charge. | 350–480 | Decimal arithmetic, time bands, aggregation | E: decimal/fixed-point helpers and calendar operations | Hand-calculated fixtures agree exactly; changing interval partitioning does not change the total charge. |
| 107 | **Recipe and shopping-list scaler:** parse rational quantities, resize portions, convert compatible units, combine ingredients, and save weekly plans. | 280–400 | Fractions, normalization, nested collections | E: rational numbers, division and richer ordered grouping | Scaling up then down recovers exact rational quantities; incompatible units remain separate. |
| 108 | **Tournament standings manager:** register teams, validate results, calculate rankings with documented tie breakers, and export fixtures and tables. | 280–400 | Records, sorting, stable ties, persistence | E: keyed multi-field sorting and richer record types | Standings match hand-worked seasons; editing a result recomputes all affected ties. |
| 109 | **Warehouse movement simulator:** load a grid, replay robot/box commands, detect blocked moves, support undo, and print/export the resulting layout. | 320–450 | Mutable grids, enums, undo records | E: nested list updates and typed records | Undo restores the exact initial grid; blocked moves preserve all invariants. |
| 110 | **Population simulation runner:** validate a small growth model, integrate fixed timesteps, compare parameter sets, and export series plus an SVG plot. | 350–480 | Numerical loops, floats, data export, rendering | E: division, numerical helpers and number formatting | Simple analytic cases stay within a declared error bound; invalid timestep settings are rejected. |

## 12. Binary formats, graphics and media tools

| ID | Program and bounded scope | Python LOC | Coverage focus | Fit / principal extension | Acceptance check |
| --- | --- | --- | --- | --- | --- |
| 111 | **PNG structure inspector:** walk chunks, decode dimensions/metadata, check CRCs and ordering, and produce an HTML/JSON report without decoding pixels. | 280–400 | Binary layouts, checksums, bounds checking | E: struct-like codecs, byte slicing and CRC API | Known chunks are described correctly; truncation, impossible lengths and bad CRCs are detected. |
| 112 | **PCM WAV analyzer:** read mono 16-bit PCM, inspect levels, normalize with clipping checks, and generate a waveform preview and output file. | 350–480 | Signed binary integers, numerical scaling, files | E: binary codecs, mutable byte buffers and arithmetic | Output headers are valid; clipping is reported and sample values agree with a reference calculation. |
| 113 | **BMP thumbnail maker:** parse uncompressed 24-bit BMP, handle row padding/orientation, resize by nearest neighbor, and write a contact sheet. | 320–450 | Binary headers, grids, coordinate arithmetic | E: bytearray, integer division and sequence mutation | Fixtures cover top-down/bottom-up images and padded rows; output pixels match golden images. |
| 114 | **PPM image filter pipeline:** parse a bounded P6 format, crop/invert/threshold images, generate histograms, and emit transformed images plus a manifest. | 350–480 | Byte/text boundaries, image buffers, numerical loops | E: binary slicing, mutable buffers and numeric conversion | Pixel results match fixtures; invalid dimensions and truncated rasters are rejected before allocation. |
| 115 | **Sprite-atlas packer:** load small PPM sprites from a manifest, pack rectangles with padding, compose an atlas, and write coordinate metadata. | 350–480 | Packing heuristics, image copying, JSON manifests | E: mutable buffers, indexed sequences and keyed sorting | Sprites never overlap; extracting every sprite from the atlas reproduces its source pixels. |
| 116 | **SVG metrics dashboard generator:** validate a JSON dataset, calculate scales/ticks, lay out bar/line charts, escape labels, and write a standalone dashboard. | 300–420 | Floating point, formatting, HTML/XML escaping | E: division, rounding and numerical formatting | Negative/constant/empty datasets render valid SVG; labels cannot inject markup. |
| 117 | **Terminal task dashboard:** read task-status snapshots, render bounded progress columns, refresh in place, and preserve readable fallback output. | 280–400 | Terminal I/O, Unicode display width, timers | E: terminal capability/size APIs, flushing and display-width handling | Narrow windows and wide Unicode text do not corrupt layout; redirected output remains readable. |
| 118 | **ZIP manifest validator:** list entries, detect duplicate/traversal names, enforce expanded-size budgets, verify CRCs, and report archive structure. | 250–380 | Archive adapters, paths, size accounting | E: zipfile-like adapter and recoverable archive errors | Crafted fixture archives are classified without extracting files or exceeding inspection budgets. |
| 119 | **Gzip log archiver:** stream rotated logs into bounded archives, keep an index, verify decompression, and recover incomplete archive attempts. | 300–420 | Compression streams, file lifetimes, recovery | E: gzip, streaming handles, metadata and error handling | Every completed archive decompresses to the original bytes; interrupted files are not marked complete. |
| 120 | **Binary traffic-fixture replayer:** parse a custom timestamped direction/length format, inspect records, replay against a local TCP peer, and compare replies. | 350–480 | Binary parsing, sockets, deadlines, deterministic replay | E: unified TCP, binary codecs, streaming/seek and recoverable errors | Fragmented replay yields the expected transcript; malformed lengths and reply mismatches identify the failing record. |

## A useful first implementation batch

Start with these twelve baseline candidates to cover existing capabilities before
adding several new library families at once:

| ID | Program | Why start here |
| --- | --- | --- |
| 001 | File-drop service | Real binary HTTP and file persistence. |
| 006 | Scenario-based mock API | Reusable fixture server for later networking examples. |
| 014 | HTTP contract test runner | Reusable behavioral checks for the generated services. |
| 037 | Batch text normalizer | Unicode, exact file bytes and idempotence. |
| 042 | Schema-driven record cleaner | Typed JSON extraction and useful rejection diagnostics. |
| 047 | Versioned configuration migrator | Multi-module transformations and restart behavior. |
| 052 | TTL key-value notebook | Time boundaries and persistence together. |
| 061 | Route planner | Nontrivial graph logic using the present collection subset. |
| 073 | Template rendering engine | Parsing, recursion, scopes and HTML escaping. |
| 081 | Recurring reminder daemon | Long-running state and deterministic clock inputs. |
| 097 | Source-header compliance checker | Files, regex and precise diagnostic locations. |
| 102 | Inventory reservation ledger | Stateful invariants across many operations. |

Then select extension examples by the next compiler feature being developed.
Examples 041/071 isolate CSV and regex-capture APIs; 051/053 exercise richer
collections; 074/101 expose arithmetic/error gaps; 031/043 cover metadata and
streaming; 063/079 motivate typed records; 021/030 exercise socket integration;
020/093 motivate concurrency and cancellation. This is a suggested order, not a
prediction that the remaining examples will become supported automatically.

## Turn the catalog into evidence

For each implemented program, record separate outcomes for: Python reference
behavior, source acceptance, generated Rust compilation, runtime parity, its
row-specific acceptance check, and generated-code readability. A successful build
alone does not establish correct behavior.

Use deterministic fixtures and isolated temporary directories. Networking tests
should use local peers and ephemeral ports; where both sides are implemented,
exercise Python/Python, Python/Rust, Rust/Python and Rust/Rust. Compare behavior
against the stated acceptance oracle as well as against Python, since both
implementations can share a bug.

Include empty input, malformed input, Unicode, binary/NUL data, boundary sizes,
integer overflow where relevant, and interruption/restart cases where the scope
requires recovery. Supply timestamps or seeds for deterministic scenarios;
use tolerant assertions for real clocks and documented floating-point bounds.

Measure actual Python SLOC after implementation. Report runtime-adapter and
handwritten Rust code separately. Keep semantic algorithms in Python even when
a generic hashing, compression, socket or parser adapter is necessary. Benchmark
copying/allocation and large-input behavior separately from functional correctness.

For Rust readability, inspect a representative generated function, preserved
names/source locations, error propagation and resource lifetimes. Track required
source workarounds explicitly so a green test does not hide an awkward language
restriction.
