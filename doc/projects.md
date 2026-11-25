# Whole projects and direct Rust imports

`py2rust-project` resolves a local Python project's imports, transpiles its reachable
modules, incorporates handwritten Rust sources, and builds or runs one native
application. It uses the [typed service subset](service-subset.md), including
HTTP/HTTPS, JSON, typed dataclass records and the existing library API. It does not broaden that subset to
arbitrary Python, third-party Python packages or general Python classes.

## One command

From the downloaded py2rust checkout:

```bash
py2rust-project run examples/projects/json_app --offline
```

This resolves `main.py`, the `app` package and `native.rs`, then prints:

```json
{
  "bytes": 6,
  "message": "Hello, 世界",
  "path": "/hello",
  "status": "ok",
  "version": 1
}
```

There is no separate binding-generation or Cargo command to run. Rust compiles
automatically when needed. On a fresh machine, omit `--offline` so Cargo can
download the locked dependencies. Python, Rust/Cargo and rustfmt must be installed.
Refresh the CLI with `python -m pip install -e .`.

```bash
py2rust-project run /path/to/project
py2rust-project build /path/to/project --release
py2rust-project transpile /path/to/project -o /path/to/generated-rust
py2rust-project run /path/to/project --entry app/__main__.py
```

Without `--entry`, the entry is `main.py`, or `__main__.py` if `main.py` is absent.
Other layouts use `--entry`, relative to the source root. For a `src/` layout,
pass `src/` as the source root and select the package entry file. Only Python
modules reachable from the selected entry are compiled; tests, tools and other
entry points are not implicitly executed or linked.

Output defaults to `<project>/.py2rust/rust/`. The binary is
`target/debug/py2rust-service` there, or `target/release/py2rust-service` with
`--release` (`.exe` on Windows). `run` uses the project root as its working
directory. This implementation is verified on Linux with Python 3.13.5 and
Rust 1.83.0.

Use `--name file-drop` to select another executable name (letters, digits,
underscores and hyphens, starting with a letter). Names are recorded in the
project metadata. When sharing `CARGO_TARGET_DIR` across different generated
projects, give each project a distinct name so cached builds cannot select
another project's executable. The application corpus verifies this case.

Plain `@dataclass` records and their field annotations can be imported across
project modules, including decorator and record aliases. The
[record contract](service-subset.md#typed-dataclass-records) defines the supported
constructor defaults, updates and owned-value semantics.

Named sort-key functions can also cross module boundaries. For example,
`from model import rank` followed by `sorted(rows, key=rank)` emits an ordinary
Rust function reference with the checked signature. The
[external record sorter](../examples/corpus/057_external_sort/main.py) uses this
across four Python modules, including typed file resources and heap-based merges.

## Import Rust as a local module

Place these files in one directory:

`main.py`:

```python
from fast import byte_count, normalize_path


def main() -> None:
    path: str = normalize_path("/hello?lang=zh")
    size: int = byte_count("世界".encode())
    print(path, size)


if __name__ == "__main__":
    main()
```

`fast.rs`:

```rust
pub fn normalize_path(path: &str) -> String {
    path.split('?').next().unwrap_or("/").to_owned()
}

pub fn byte_count(data: &[u8]) -> usize {
    data.len()
}
```

Run `py2rust-project run .`. The compiler reads public Rust function signatures,
checks the Python arguments and generates ordinary Rust calls. No `.pyi` file,
decorator, registration table, PyO3 wrapper or manual build is needed.
`import fast`, `import fast as native` and `from fast import byte_count as size`
also work. These imports belong to the transpiled language; ordinary CPython
does not gain an `.rs` import hook.

## Python module support

- Local absolute and relative imports, aliases and package re-exports.
- Packages with `__init__.py`, plus namespace directories without that file.
- Typed functions, enums and annotated scalar constants shared between modules.
- Independent namespaces: two modules can define functions with the same name.
- Cross-module calls and HTTP handler callbacks.
- Entry code under a main guard, or simple top-level entry statements.
- Main guards in imported modules are omitted from the application entry.

Imports resolve statically without executing Python source. Imported modules may
contain imports, declarations and docstrings; arbitrary import-time effects are
rejected. Module constants need explicit scalar types and literal values, e.g.
`PORT: int = 8080` or `PREFIX: str = "/api"`. They cannot be reassigned. Mutable
globals, circular imports/re-exports, star imports, dynamic/nested imports,
`sys.path` mutation and package installation are unsupported.

Existing stdlib spellings such as `import json` can use aliases in project mode;
`from py2rust.stdlib import json_loads as decode` works too. Supported fallback
modules are `json`, `time`, `logging`, `pprint`, `hmac`, `math`, `unicodedata`, `heapq` and `sys` (integer
`exit` only). A local module takes precedence over these fallback imports, except
for built-in `sys` and `time`. For example, `import math` can refer directly to a
project's `math.py` or `math.rs`; otherwise `math.ceil` uses the service profile.
`enum` and `py2rust.stdlib` retain their special profile meanings. Other external
Python imports produce a source error. Local `.py` and `.rs` files with the same
import name are ambiguous and rejected.

The linker lowers Python declarations into one generated Rust source with distinct,
readable names. `.py2rust-project.json` maps those names back to source files and
lines. Python validation errors retain their original file/line; Rust compiler
diagnostics point to the generated source or copied Rust file.

## Rust function interfaces

The Rust body can use normal Rust. Its exported interface must fit this table:

| Rust interface | Python-like type | Conversion |
| --- | --- | --- |
| `i64` | `int` | Direct |
| Other signed/unsigned integers, `usize`, `isize` | `int` | Checked both ways; out-of-range values return an error |
| `f64` | `float` | Results must be finite, including inside supported containers |
| `bool` | `bool` | Direct |
| `String`, `&str`, `&'static str` | `str` | Owned or borrowed argument; borrowed results are copied |
| `Vec<u8>`, `&[u8]` | `bytes` | Owned or borrowed buffer; borrowed results are copied |
| `Vec<T>` | `list[T]` | Owned elements with matching representation, e.g. `i64`, `String`, `f64`, nested vectors |
| Tuples of supported owned types | `tuple[...]` | Fixed shape; integer elements use `i64` |
| `serde_json::Value`, `py2rust_service_runtime::Json` | `Json` | Results are checked against the service JSON contract |
| No return type / `()` | `None` | Unit |
| `Result<T, E>` / `std::result::Result<T, E>` return | `T` | Errors propagate through the generated function's `Result` |

For `Result`, the error must convert into `Box<dyn Error + Send + Sync>`; `String`
and compatible Rust error types work. Rust panics are not converted to Python
exceptions. Exports must be top-level `pub fn`, synchronous, safe and nongeneric.
Interfaces using `Option`, structs, traits, callbacks, mutable references, type
aliases or conditional `#[cfg]` exports are currently rejected. Keep every
top-level public function in an imported file within this interface; private
helpers may use richer Rust types.

Rust submodules using `mod helper;` work with the normal layout, e.g. `fast.rs`
and `fast/helper.rs`. Generated wrapper modules preserve that resolution. Relative
`.rs` paths are copied under `src/native/`; generated/hidden/build directories are
excluded from the supporting-file scan. Prefer `self::` and `super::` internally:
`crate::` refers to the generated application. The runtime's locked crates are
available, including `serde_json`, `regex`, `chrono`, Hyper/Tokio and rustls.
Inference of extra Cargo dependencies, macros generating exports, `build.rs`
integration and non-Rust `include_*` assets are not implemented yet.

## Rebuilds and output ownership

Rerunning the command checks sources and invokes Cargo incrementally. Unchanged
generated files keep their timestamps. Python/Rust edits are reflected automatically;
removed managed Rust files are removed from the generated tree. Builds enforce
the lockfile.

The output must be empty or already managed for the same source root. The command
refuses to overwrite hand-edited generated files, unrelated files at generated
destinations, or paths escaping the output directory. Put handwritten Rust changes
in the original `.rs` files, then rerun. Cargo's target cache and unrelated files
are retained. There is no background watcher yet.

## Network example and verification

The example also has an HTTP entry calling the shared Python handler and Rust:

```bash
py2rust-project run examples/projects/json_app --entry server.py --offline
```

It accepts one request on loopback port 8080. A JSON POST body such as
`{"name":"世界","path":"/hello?x=1"}` gets the response shown above. The existing
HTTPS and timeout APIs are also available in project modules.

Complete projects can also use the service library's `TcpListener`/`TcpStream`
handles, framing primitives and deadlines. The
[task broker and batch client](../examples/corpus/021_tcp_broker/main.py) compile
together from six Python modules into one executable; `BROKER_MODE` selects
serving or sending a batch. See the [service TCP contract](service-subset.md#tcp-and-binary-framing).

`UdpSocket` also works across project modules with scoped cleanup. The six-module
[UDP directory and retrying client](../examples/corpus/025_udp_directory/main.py)
compile into one executable selected with `DIR_MODE=serve` or `client`, using the
[datagram contract](service-subset.md#udp-datagrams) for source addresses,
truncation and timeouts.

`ProcessPool` handles may likewise appear in imported function annotations and
cross ordinary Python module boundaries. The five-module
[process supervisor](../examples/corpus/093_process_supervisor/main.py) uses this
to keep service lifecycle policy separate from configuration and status storage.
Its resulting executable runs concurrent native children without Python; see the
[process-pool contract](service-subset.md#nonblocking-process-pools).

```bash
python -m pytest tests/test_project.py -q
```

Tests compile and execute generated Rust, send a real HTTP request across module
boundaries, compare pure Python package output with Rust, check native type/error
conversions and rebuild after Python/Rust edits. They also check missing imports,
unsupported interfaces, source diagnostics and output ownership.

Earlier validation on 2026-10-05: all 157 project/service/TLS/TCP tests passed, including
29 project tests. The installed `transpile`, `build` and `run` commands worked on
the mixed example; a second run reused the build cache. Ruff and whitespace checks
passed. The wheel contains the linker, signature parser, command entry point and
runtime, and generated a mixed project successfully when imported from the wheel.

The complete [Rust-import workbench](../examples/corpus/094_rust_imports/main.py)
exercises local error recovery across six Python modules and three adjacent Rust
adapters. Ordinary imports cover checked integer arguments/results, `Result`,
Unicode and byte buffers, recursive finite-float validation, and owned JSON. Its
[run instructions and schema](../examples/corpus/README.md#rust-import-validation-workbench-094)
include inspection reports and repeatable expectations. Every Python application
module compiles, while the generated executable calls the `.rs` files directly
and has no Python runtime. Separate test shims are used only for CPython comparison.

## Names in exported Rust

Project commands (`transpile`, `build`, and `run`) assign readable Rust names at
export, after linking and compiler analysis. For the access-log example:

| Internal symbol | Exported Rust |
| --- | --- |
| `py__analysis__Summary` | `Summary` |
| `py__analysis__summarize` | `summarize` |
| `py__main__main` | `run_main` |

Rust's `main` remains the executable entry point and calls `run_main`. When
multiple modules export the same name, the compiler qualifies it with a readable
module prefix, such as `left_value` and `right_value`, or `LeftSummary` and
`RightSummary`. It also avoids Rust keywords and names already used by locals;
a numeric suffix resolves remaining collisions deterministically.

This is a syntax-aware identifier rewrite, not a text substitution. String
values, comments, source paths and handwritten Rust files remain intact. The
project manifest maps the exported names back to the original Python/Rust source
locations. Internal IR and optimization reports retain stable linker IDs;
exported function report rows additionally record `rust_symbol`. Low-level IR
emission APIs still expose internal names. Block-local temporary naming is a
separate concern and is unchanged by this pass.

Rebuild your Docker image with `docker build -t py2rust-demo .` and run it again
to get these names in a new export directory. Previously exported files are not
modified.
