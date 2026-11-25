# Additional CSV/JSON conversion comparison

Raw report filenames below refer to [local archived reports](../../REPORTS.md#local-archive),
not files shipped in this repository. Source programs and Markdown summaries remain in Git.

The unchanged Python application and compiler were compared with independently
handwritten complete Rust, using identical pinned dependencies and release
settings. Each direction has small and large workloads; execution order rotates
after warm-up over fresh identical inputs. Every invocation passes independent
CSV/typed-record checks and complete-output equality. Compilation, fixture
construction and checking are untimed.

| Direction | Size | Generated median (ms) | Handwritten median (ms) | Ratio |
|---|---|---:|---:|---:|
| CSV → JSON | Small | 10.69 | 10.48 | 1.02× |
| CSV → JSON | Large | 33.51 | 26.11 | 1.28× |
| JSON → CSV | Small | 10.92 | 10.57 | 1.03× |
| JSON → CSV | Large | 43.09 | 29.60 | 1.46× |

All four cases pass. `results.json` retains 120 timed jobs (15 per executable,
direction and size), raw observations and source/binary fingerprints. Timings
include startup, parsing, reports and durable publication. Cases contain 64/4,096
records, four declared types, quoted Unicode/CRLF strings, nested JSON, an ordered
projection and one invalid integer every seventeen rows. Independent expected
reports include every rejected input, error, row number and hash. Exit status 1
is expected because rejected rows are part of this workload.

`csv_json.rs` validates schemas once into typed column records and operates on
borrowed candidates and owned accepted values. The shared `csv_codec.rs` supports
the exact application dialect, including doubled quotes, embedded CR/LF bytes,
blank rows and strict byte/column/row limits. Canonical JSON spelling, decimal
integer parsing and regex behavior use the pinned shared low-level runtime.

`checks.json` records 162 additional complete jobs: randomized round trips across
four delimiters, dialect edge cases, null escaping, precise numeric distinctions,
rejected rows, invalid configurations and paths, and capacity runs under a 128 MiB
address-space limit. These reach 10,000 rows, 64 columns, 65,536-byte fields and
4 MiB input, with output/rejection budget checks. The checked binary hash matches
all four timed cases.

Preview/convert, input snapshot revalidation, per-file atomic writes, directory
sync and no-replace publication are retained. The native input helper rejects
hard links more strictly than the Python application; timed inputs are unaliased.
Fault-injection/pause hooks and their associated interruption/race checks are
excluded. No compiler or Python application changes were made for this comparison.
