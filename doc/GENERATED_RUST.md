# Generated Rust readability

This comparison isolates the readability pass after the performance optimizations.
Both versions already include borrowed parameters, slice views and direct JSON
serialization. These are actual generated excerpts from complete applications,
formatted with rustfmt; they are not manually rewritten example implementations.

The compiler now infers binding mutability, borrows string literal arguments,
uses tail expressions, forwards compatible `Result` calls without `Ok(call()?)`,
compares borrowed string slices where safe, uses `is_empty` and `String::new`,
and constructs JSON scalars directly. Unknown effects still prevent borrowing,
and returns inside cleanup machinery retain their control-flow representation.

## Chat: literal arguments

Allocating owned strings just to borrow them obscured a straightforward environment
lookup. The generated function keeps the current fallible function ABI even though
this particular body cannot fail; infallibility inference is a separate change.

Before:

```rust
fn py__app__store__data_directory() -> rt::Result<String> {
    return Ok(rt::env_get(
        &("PAPER_PLANE_DATA".to_string()),
        &("data".to_string()),
    ));
}
```

After:

```rust
fn py__app__store__data_directory() -> rt::Result<String> {
    Ok(rt::env_get("PAPER_PLANE_DATA", "data"))
}
```

## Gzip: immutable bindings and Result forwarding

The local is immutable, and the final runtime Result can be returned directly.

Before:

```rust
fn py__documents__absolute(path: &str, base: &str) -> rt::Result<String> {
    let mut joined: String = rt::path_join(base, path)?;
    return Ok(rt::path_join(
        &(rt::path_resolve(&(rt::path_parent(&(joined))?))?),
        &(rt::path_name(&(joined))?),
    )?);
}
```

After:

```rust
fn py__documents__absolute(path: &str, base: &str) -> rt::Result<String> {
    let joined: String = rt::path_join(base, path)?;
    rt::path_join(
        &(rt::path_resolve(&(rt::path_parent(&(joined))?))?),
        &(rt::path_name(&(joined))?),
    )
}
```

## Traffic: borrowed byte chunk and literal

The slice view was already present before this pass. The new output removes the
unnecessary mutable binding and allocation of the byte-order argument.

Before:

```rust
    let mut count: i64 =
        rt::int_from_bytes(rt::slice_view(data, 8i64, 12i64), &("big".to_string()))?;
```

After:

```rust
    let count: i64 = rt::int_from_bytes(rt::slice_view(data, 8i64, 12i64), "big")?;
```

## Measured readability signals

Clippy was run on the complete generated application binaries, with the same
`clippy::all`, `clippy::pedantic`, `unused_mut` and `unused_parens` force-warn flags
for both versions. The table counts diagnostics whose primary span is generated
generated application modules under `src/`, excluding `src/native/`, runtime-library
diagnostics and dependencies. Current exports preserve this module layout; the
archived measurements below were collected from the former flat `src/main.rs`.

| Application | All warnings before | After | Unnecessary mut before | After |
| --- | ---: | ---: | ---: | ---: |
| chat | 613 | 203 | 68 | 1 |
| traffic | 240 | 117 | 56 | 0 |
| gzip | 294 | 164 | 59 | 0 |

These are readability signals, not speed measurements or proof that all remaining
warnings are bugs. Redundant parentheses, formatting temporaries, explicit checked
arithmetic, some required owned copies and conservative Result-returning ABIs
remain. Several checked operations are deliberately more verbose than unchecked
handwritten Rust. Some warnings become visible only after other warnings disappear.

Validation includes native/reference comparisons, mutation and heap operations,
string reference representations, error returns, resource lifetimes and finally
handling. All 120 catalog projects transpile. Complete gzip and traffic Python/native
acceptance passed. The fresh full regression run passed 817 tests after the trimming correction and
diagnostics integration. The final measured compiler subsequently passed 825 tests and all 120 complete
application checks. The refreshed assessment reproduces the Clippy totals above;
see [final timing and memory results](OPTIMIZATION_RESULTS.md).

Generated sources, full diffs, Clippy diagnostics and the measurement script are in
`$HOME/.cache/py2rust-idiomatic/`. Optimizer regression tests live in
`tests/test_optimization.py`; performance evidence is tracked separately in
[OPTIMIZATION_STATUS.md](OPTIMIZATION_STATUS.md).

## Typed string references and parameter contracts

The typed parameter policy now consults the same reviewed string-method contract
as the memory oracle. A helper that only calls `casefold()` borrows its string
input; rebinding that parameter still requires ownership. For a retained caller
binding, the relevant emitted forms change as follows:

```rust
// Before
fn py__main__folded(mut text: String) -> rt::Result<String> {
    Ok(rt::casefold(&(text)))
}
// Caller: py__main__folded(original.clone())?

// After
fn py__main__folded(text: &str) -> rt::Result<String> {
    Ok(rt::casefold(text))
}
// Caller: py__main__folded(&original)?
```

The result remains an owned string. The removed input clone is an allocation
improvement established by the emitted code; no timing claim is made here.

String helpers also reuse existing references and the common reference renderer:

| Before | After |
| --- | --- |
| `rt::str_strip(&(text))` for borrowed `text` | `rt::str_strip(text)` |
| `rt::casefold(&(text))` for now-borrowed `text` | `rt::casefold(text)` |
| `rt::str_strip(&(text))` for owned `text` | `rt::str_strip(&text)` |

Compound owned expressions retain grouping. This rendering cleanup alone is not
a runtime speedup. The example above is indented for presentation; complete raw
before/after output and source are archived at
`$PY2RUST_BUILD_DIR/reference-readability/`.

Validation: 43 tests passed in the combined reference/string/serialization/
readability/pipeline/parameter/gate selection. The remaining test expected the
wrong parentheses around `original.clone()`; after correcting only that assertion,
it passed separately. Native tests exercised both optimization modes, retained
input, temporary lifetimes, evaluation order and failing arguments. This is
44 passing selected tests across those runs, not a fresh full-suite result.
