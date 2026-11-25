# Access-log analyzer: Python → Rust versus handwritten Rust

Raw report filenames below refer to [local archived reports](../REPORTS.md#local-archive),
not files shipped in this repository. Source programs and Markdown summaries remain in Git.

This selected complete application summarizes HTTP access logs. It exercises
modules, a dataclass, typed dictionaries, strings, assertions, file I/O,
environment variables and JSON. It is deliberately small enough to inspect.

- [Python entry point](../../examples/projects/access_log/main.py)
- [Python analysis](../../examples/projects/access_log/analysis.py)
- [Sample input](../../examples/projects/access_log/sample.jsonl)
- [Handwritten Rust](native.rs)
- [Benchmark driver](../../tools/compare_access_log.py)
- [Recorded raw measurements and source hashes (local archive)](../REPORTS.md#local-archive) (`benchmarks/access_log/results.json`)

## Run and inspect

For a Docker-only setup that prints timings and exports source and executables,
use the [Docker quick start](../../README.md#quick-start-with-docker-no-local-python-or-rust).

Follow the installation and one-command build in the [main README](../../README.md).
The generated `src/main.rs` contains both Python modules, with source-location
comments. The executable requires no Python runtime. Generation uses the default
typed host frontend; this is not a test of the smaller self-hosted compiler.

To reproduce the comparison from the repository root after installing py2rust:

```sh
python tools/compare_access_log.py \
  --output "$HOME/.cache/py2rust-build/access-log-benchmark-01"
```

Use a fresh output directory for each run. Add `--offline` if Cargo dependencies
are cached. Optional `--sizes 10000 100000 --samples 7` sets the default workload
explicitly. The driver retains generated Rust in `generated/src/main.rs`, the
native baseline in `generated/src/bin/access-log-native.rs`, both executables in
`target/release`, build output in `build.log`, input fixtures, and `results.json`.
It builds both binaries in the same Cargo project with the same locked dependency
graph and release profile. Compilation is not included in the timings.

## Actual code comparison

The excerpts and timings in this section are the original baseline. The latest
shared compiler changes are described in [the current performance report](../../doc/COMPILER_PERFORMANCE.md).

Project exports now use readable top-level names (see [naming rules](../../doc/projects.md#names-in-exported-rust)).
The recorded timings and source hashes below predate that presentation-only change.

Python accepts a whole string and iterates over its lines:

```python
for raw_line in text.split("\n"):
    line: str = raw_line.strip()
    if line != "":
        event: Json = json_loads(line)
        path: str = json_string(event["path"])
```

The generated function borrows the complete input as `text: &str`. Its loop is:

```rust
for raw_line__block_1 in rt::str_split(text, "\n")? {
    let line__block_2: String = rt::str_strip(&raw_line__block_1);
    if !(line__block_2.as_str()).is_empty() {
        let event__block_3: rt::Json = rt::json_loads(&line__block_2)?;
        let path__block_4: String =
            rt::json_string(rt::json_key_ref(&event__block_3, "path")?)?;
```

These are actual emitted lines, with the rest of the loop omitted.
`str_split` returns `Vec<String>` and `str_strip` returns another owned string.
The handwritten loop instead borrows slices and decodes directly into an `Event`:

```rust
for line in text
    .split('\n')
    .map(str::trim)
    .filter(|line| !line.is_empty())
{
    let event: Event<'_> = serde_json::from_str(line)?;
```

`Event.path` uses `Cow<'_, str>`: unescaped JSON paths can borrow from the input;
escaped paths still allocate when decoding requires it. Both implementations read
the complete file before processing, so neither is a streaming file reader.

For `route: str = path.split("?")[0]`, generated Rust currently emits:

```rust
let route__block_8: String = rt::at(&(rt::str_split(&path__block_4, "?")?), 0i64)?;
```

The native equivalent avoids constructing a vector and keeps a borrowed slice:

```rust
let route = event
    .path
    .split_once('?')
    .map_or(event.path.as_ref(), |(path, _)| path);
```

Other differences:

| Operation | Generated Rust | Handwritten Rust |
| --- | --- | --- |
| Counters | `i64`, `checked_add`, propagated errors | Same checked arithmetic |
| Route dictionary | `IndexMap<String, i64>`; separate `get` and `insert`, cloned keys | Same ordered map; `entry(...).or_default()` |
| JSON input | Generic JSON tree, followed by field access and conversion | Serde `Event` schema |
| Summary output | Explicit JSON object, including cloned route dictionary | Serialize borrowed `Summary` directly |
| Naming | Readable exported `Summary`/`summarize`; numbered local block suffixes remain | Ordinary `Summary`, `summarize`, `event` |
| Struct construction | `requests: requests`, etc. | Defaults and field updates |

The emitted code is recognizable Rust, with ordinary structs, borrowed input,
`Result` and checked arithmetic. Temporary names, redundant parentheses and
`.clone()` on integer fields are less idiomatic. Integer clones are cosmetic;
owned strings, container clones and JSON trees are more relevant to performance.

## Measured performance

Measured on Linux x86-64, Intel Core i3-12100, rustc 1.83.0. Each result is the
median of seven checked runs, alternating execution order after warm-up:

| Records | Input bytes | Generated Rust | Handwritten Rust | Generated/native |
| ---: | ---: | ---: | ---: | ---: |
| 10,000 | 809,587 | 11.30 ms | 2.84 ms | 3.98× |
| 100,000 | 8,096,253 | 107.04 ms | 22.63 ms | 4.73× |

At 100,000 records, generated runs ranged from 105.98–111.06 ms and native runs
from 22.49–24.39 ms. These are local measurements, not performance guarantees.
Timings include process startup, file reading from warm filesystem caches,
parsing, aggregation, and JSON output. They exclude compilation and fixture
generation. The Python reference is checked for correctness, not timed.

Every timed result is JSON-decoded and compared against independently calculated
counts. The five-record sample and both larger fixtures are also checked against
CPython. Fixtures include repeated routes, blank lines, Unicode, JSON escapes,
query strings and error responses. This compares valid records in the documented
schema, not all malformed JSON behavior: for example typed Serde and generic JSON
may handle duplicate object keys differently. This benchmark does not measure
network latency, memory consumption, or the full application corpus.

## What this identifies

This workload exceeds our approximate 2× slowdown tolerance. Candidate systematic
improvements are:

1. Lower non-escaping string split/strip loops to borrowed iterators, retaining
   Python-compatible behavior where observable.
2. Recognize `split(separator)[0]` as a borrowed prefix operation when the separator
   and index semantics permit it.
3. Fuse dictionary read/modify/write patterns into one entry operation, preserving
   evaluation order and aliasing behavior.
4. Introduce typed JSON decoding and direct struct serialization, with explicit
   schema/error contracts instead of silently changing generic JSON semantics.
5. Use liveness/ownership analysis to avoid copying the summary map at final output.

These are hypotheses supported by generated-code inspection. The total timing
does not isolate their individual costs; each optimization needs its own before/
after measurement and semantic checks. This example establishes a reproducible
baseline, not a claim that these optimizations have already been implemented.
