# BMP and ZIP: two further handwritten comparisons

Raw report filenames below refer to [local archived reports](../../REPORTS.md#local-archive),
not files shipped in this repository. Source programs and Markdown summaries remain in Git.

Both baselines implement complete measured jobs independently in readable Rust.
The compiler and Python applications are unchanged from the JSON-view milestone.
The existing generated release executables were reused only after their compiler,
application and binary fingerprints matched the current sources.

Each application has 15 rotated timed repetitions per size and executable,
with one warmup, identical fresh inputs, independent correctness oracles and equal
complete output file contents. Compilation and checks are untimed; process startup,
I/O, output generation and durable publication are included. The before executable
is the preceding parser-cache compiler; this extension makes no new speedup claim.

| Application | Before views, large (ms) | Current, large (ms) | Native, large (ms) | Small ratio | Large ratio |
|---|---:|---:|---:|---:|---:|
| 113 BMP thumbnails | 27.24 | 27.40 | 28.05 | 0.95× | 0.98× |
| 118 ZIP validator | 38.78 | 38.75 | 37.54 | 1.05× | 1.03× |

All four size cases meet the strict <2.00× gate. `bmp-results.json` and
`zip-results.json` retain 180 timed invocations with raw wall/CPU/RSS samples and
source/executable hashes. They are separate matched batches on the same host,
not one combined timing run. Near-1× timings have a substantial I/O/startup floor.

Together with the twelve JSON-view comparisons, coverage is now fourteen of the
original twenty applications. Thirteen pass both sizes; the resolver's large case
still fails. Missing native baselines: 077, 079, 080, 095, 109 and 115. The overall
goal and the ten later applications remain open.

## Supported jobs and independent checks

- `native/bmp.rs`: build/verify BMP projects, CORE/INFO/V4/V5 headers, top-down and
  bottom-up rows, padding, palettes/profile extents, nearest-neighbor thumbnails,
  contain/stretch layouts, exact original/thumbnail/sheet exports, escaped HTML,
  reports, manifests and rebuild/retile/replay archives. No color management is
  performed, matching the Python application.
- `native/zip.rs`: inspect/verify physical ZIP32 records, matching central/local
  headers, signed/unsigned data descriptors, bounded stored/deflate payloads,
  CRCs and SHA256, CP437/UTF8/Unicode path extras, portable-name diagnostics,
  overlap detection, budgets and exact forensic reports. Nothing is extracted
  to the filesystem. Unsupported ZIP64/encrypted entries retain diagnostics.

Both retain bounded snapshot reads, metadata revalidation, no-replace publication,
file/directory synchronization and limits. Corpus fault-injection/pause controls
are excluded, as in the earlier native references.

The BMP baseline passed **398 additional complete jobs** (`bmp-checks.json`):
header/orientation/stride variants, manual pixel goldens, profile extents, Unicode
and escaped/duplicate names, nested paths, generated layouts, actual rebuilding,
retiling and replay, malformed bitmaps, invalid requests and tampered archives.

The ZIP baseline passed **424 additional complete jobs** (`zip-checks.json`):
standard-library payload oracles, stored/deflated streams, CP437/UTF8 names and
Unicode extras, generated edit/replay/restore jobs, malformed/invalid archives,
exact forensic diagnostics, overlapping payloads and descriptors whose payload
CRC equals the optional descriptor signature. These checks cover modes beyond
the timed fixtures without adding source-specific shortcuts to either baseline.

The previous twenty-application compiler sweep remains applicable because the
compiler did not change. No full corpus run was performed.

## Reproduce

After building the current selected applications, use a fresh output directory:

```sh
PYTHONPATH="$PWD" python tools/compare_corpus_native.py \
  --generated "$HOME/.cache/py2rust-build/native-target-generated" \
  --output "$HOME/.cache/py2rust-build/bmp-zip-comparison-new" \
  --ids 113 118 --repeats 15 --check-target
PYTHONPATH="$PWD" python tools/check_corpus_native.py \
  --native "$HOME/.cache/py2rust-build/bmp-zip-comparison-new" \
  --output "$HOME/.cache/py2rust-build/bmp-zip-checks-new" --ids 113 118
```
