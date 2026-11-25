# General compiler performance improvements — 2026-11-25

This work changes shared compiler lowering and runtime helpers, not the access-log
application. It addresses two recurring causes of excessive work: materializing
short-lived collections and allocating dictionary keys for updates that do not
need ownership of a new key. The access-log Python source and handwritten Rust
baseline were not modified.

## Selection from source inspection

We inspected the corpus before selecting tests. A static syntax scan found:

| Candidate pattern | Expression sites | Programs containing candidates |
| --- | ---: | ---: |
| Direct iteration over `split(...)` | 28 | 19 |
| Immediate split indexing | 35 | 13 |
| `len(split(...))` | 11 | 9 |
| Dictionary `.get(...) + ...` updates | 10 | 7 |

These are syntactic candidates, not claims that all sites qualify. Programs may
appear in multiple rows, and one source line can contain several expressions.
Type, argument shape, ownership and side effects determine actual eligibility.

Representative existing applications are circuit gateway **019** (header tokens),
batch worker **090** (word-frequency counters), code metrics **095** (line counts
and module prefixes), and ZIP validator **118** (filename stems). These four
complete applications were selected for functional checks. No full-corpus run was
performed. The performance fixtures isolate the same patterns without network
latency hiding the compiler's costs; their timings are not timings of those four
servers/applications.

## Problem 1: constructing a list that its consumer never needs

Previously `text.split(separator)` always produced `Vec<String>`. That required
scanning the whole input, allocating its vector and allocating each part, even
when the next operation only requested `[0]`. This changes the amount of necessary
work, not merely the spelling of Rust. Long query strings and large documents can
make the difference extreme.

The shared expression and loop emitters now recognize three immediate consumers:

| Python expression | New lowering | Work avoided |
| --- | --- | --- |
| `text.split(sep)[constant]` | Forward iterator plus checked selected-item extraction | Vector and unselected strings; nonnegative indexes stop when found |
| `len(text.split(sep))` | Allocation-free count with a single-character fast path | Vector and every part's owned string |
| `for part in text.split(sep)` | Iterate borrowed parts of one source snapshot | Vector and per-part allocations when the loop binding is read-only |

Whitespace splitting without an explicit separator is supported too. A stored
split list retains its existing owned representation. Indexing a stored list,
dynamic indexes, unsupported split overloads and escaping list results are not
silently rewritten.

Counting uses a character-pattern fast path for a separator containing exactly
one Unicode scalar; multi-character separators keep forward string-pattern
semantics. Measurements exposed this distinction: merely removing the vector
still left a gap between generic string search and the native character path.

The iteration transformation owns one source snapshot. It therefore preserves
the original split result if the body reassigns the source or separator. A
read-only loop binding borrows each part; a reassigned binding gets an owned
string. Owned-use boundaries such as appending a part to an escaping list still
materialize a string. This eliminates unnecessary ownership without allowing
references to outlive the snapshot. Borrowing the original source when stronger
stability proofs permit it is a remaining opportunity.

Correctness details matter:

- Empty explicit separators fail before iteration, including an empty input.
- Whitespace uses the runtime's Python-compatible predicate, including U+001C–U+001F.
- Negative indexes count the **forward** split. Using `rsplit` would be incorrect
  for overlapping separators: `"aaa".split("aa")[-1]` is `"a"`.
- Receiver/argument evaluation order and side effects are preserved. Only constant
  indexing is fused, avoiding reordered evaluation of an effectful index.
- The selected substring remains owned when returned. Literal separators borrow
  static text instead of allocating a string on every call.

Implementation: [split lowering](../py2rust/compiler/backend/split_emission.py),
[loop lowering](../py2rust/compiler/backend/loop_emission.py), and
[runtime iterators](../py2rust/compiler/service_runtime/src/split_views.rs).

## Problem 2: repeated string-key counters allocate on every hit

The ordinary lowering of `counts[key] = counts.get(key, default) + increment`
cloned keys and performed separate lookup and insertion even when the key was
already present. Repeated words, request routes and status aggregates make this
an especially frequent path.

For named `dict[str, int]` locals, the same named string key, and literal integer
default/increment operands, the compiler now borrows the key and uses `get_mut`.
On a hit, it updates the counter with checked arithmetic without allocating a
key. On a miss, it checks the arithmetic first, then allocates and inserts the new
key. Dictionary insertion order remains unchanged.

This deliberately does not use `entry(key.to_owned()).or_insert(default)`:
that would still allocate on every hit and would insert an absent key before an
overflow error. Exceptions make that difference observable. Both existing values
and missing keys must remain unchanged if arithmetic fails.

Effectful defaults/increments, mismatched lookup/assignment keys, other value
arithmetic, complex target expressions and other key types retain ordinary
lowering. This is a conservative shared compiler optimization, not a special
case for a route table or a named function.

Implementation: [counter recognition](../py2rust/compiler/backend/counter_emission.py)
and [assignment rendering](../py2rust/compiler/rules/assignment.py).

## Measurements

The results below use preserved before/after release executables, interleaved
with handwritten Rust: nine measured runs per executable after warm-up, rotating
execution order. They include process startup, warm file reads, computation and
stdout; compilation is excluded. Machine: Linux x86-64, Intel i3-12100, rustc
1.83.0. Raw samples and executable/generated-source hashes are retained in
[the evidence directory](../benchmarks/performance_2026_11/).

| Workload | Before (ms) | After (ms) | Native (ms) | Speedup | After/native |
| --- | ---: | ---: | ---: | ---: | ---: |
| Prefix of large text | 109.81 | 1.13 | 0.97 | 96.98× | 1.16× |
| Count split parts | 128.55 | 22.99 | 22.82 | 5.59× | 1.01× |
| Traverse split parts | 14.66 | 5.86 | 3.91 | 2.50× | 1.50× |
| Repeated string-key counter | 16.42 | 7.35 | 5.55 | 2.23× | 1.32× |
| Access log, 10,000 records | 11.26 | 9.63 | 2.84 | 1.17× | 3.39× |
| Access log, 100,000 records | 106.18 | 90.41 | 22.55 | 1.17× | 4.01× |

The counter baseline already includes split-loop fusion. Its measured gain covers
the additional counter optimization and literal-separator cleanup; it is not the
gain from the entire optimization group. The other baselines precede both changes.
These are observed local ratios, not general guarantees. Very short prefix timings
include a substantial process-startup floor. No allocator or RSS measurement was
performed; allocation claims above describe emitted operations, not measured heap
statistics.

The text fixtures use 20,000 Unicode-containing lines. Prefix extraction and
counting repeat 100 times; traversal and counters repeat 10 times. They are
complete generated executables with file input and checked output. Each fixture
is checked against CPython and independently calculated expected results. The
access-log benchmark similarly checks both input sizes against an independent
input oracle and CPython. The final interleaved measurement verifies every
before/after output against the native output using identical input bytes.

## Validation and limits

- 15 targeted split/string/iteration tests passed, including optimized and
  unoptimized typed and legacy paths; the final literal-separator and character-count refinements
  each additionally passed all five split-consumer tests.
- Four counter tests passed: typed/legacy parity, effectful fallback, and
  optimized/unoptimized overflow behavior on both missing and existing keys.
- Selected corpus programs **019, 090, 095, 118** passed their application checks.
  ZIP validation included malformed archives, bounds, memory, publication and
  filesystem checks. These checks preceded the final literal-separator and character-count
  refinements; the final split-specific tests cover those changes.
- Final release benchmarks compiled and checked the generated programs and native
  baselines. No Python runtime is used by the measured Rust executables.

The shared host backend is used by the typed frontend and legacy comparison
frontend. The separately self-hosted native compiler has its own lowering and was
not extended or claimed faster here. Optimization reports record the selected
`split_consumer` and `dictionary_counter` decisions. No Python source hints or
application rewrites are needed.

## Problems still visible in generated code

The access-log application remains above the approximate 2× target. These changes
do not eliminate all of its costs. Remaining candidates include:

1. **Generic JSON trees instead of typed decoding.** Every record becomes a
   generic `Json` object, is validated, and is then accessed field by field. The
   handwritten baseline deserializes into a schema. A general solution requires
   explicit schemas or IR proofs about all uses, with specified missing/extra/
   duplicate-field and numeric-error behavior; replacing parsing based on one
   example's field accesses would be unsafe.
2. **Owned derived strings.** `strip`, `json_string`, and selected split parts
   still produce owned strings. Borrowed views need backing-lifetime, mutation
   and escape proofs across local declarations and branches. Strings retained
   in a map need ownership; strings only inspected often do not.
3. **Final serialization copies.** The example explicitly constructs generic JSON
   and copies the summary map. Direct struct serialization needs a supported
   general serialization contract, or last-use analysis must safely consume the
   fields. This is outside the hot per-record loop, so its priority should be
   guided by measurements on larger outputs.
4. **Repeated materialized collections beyond immediate consumers.** A local list
   that is only counted or iterated later needs IR use/escape analysis before the
   compiler can avoid constructing it. The current transformations intentionally
   do not guess from nearby statements.

These are evidence-based optimization candidates, not individually profiled cost
shares. The measurements establish end-to-end improvements, not a decomposition
of the remaining time. The recommended next substantial step is extending the
IR memory oracle to prove borrowed derived-string lifetimes, then adding a clear
typed-JSON boundary with semantic parity tests.

## Reproduce

After the normal development setup, generate fresh measurements with:

```sh
python tools/compare_text_consumers.py --output "$HOME/.cache/py2rust-build/text-new"
python tools/compare_text_consumers.py --workload map_counter \
  --output "$HOME/.cache/py2rust-build/counter-new"
python tools/compare_access_log.py --offline \
  --output "$HOME/.cache/py2rust-build/access-log-new"
```

These scripts require cached Cargo dependencies (`cargo fetch --locked
--manifest-path py2rust/compiler/service_runtime/Cargo.toml` populates them). Use
fresh output directories. Each preserves generated source, executable, input,
build log and results. To compare two preserved builds under rotating execution
order:

```sh
python tools/measure_codegen_changes.py --workload text \
  --before /absolute/path/to/text-before --after /absolute/path/to/text-new \
  --output /absolute/path/to/new-comparison.json
```

Use `--workload counter` or `access-log` for those fixtures. The comparison script
requires equal input bytes and a new output file. Reproducing historical timing
requires the preserved historical executables or rebuilding the corresponding
compiler version; running the current compiler twice is not a before/after test.
For the Docker access-log demo, rebuild the image before running it again.
