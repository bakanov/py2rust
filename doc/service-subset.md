# HTTP, JSON and standard-library service subset

`py2rust-service` compiles an explicitly typed, Python-like subset into a standalone
Cargo project. It adds a tested first implementation of HTTP, JSON and all eight
requested library areas. Generated executables need no Python runtime. The complete-project compiler shares
this service backend and runtime.

Use [the project command](projects.md) for multiple Python modules and direct
imports of handwritten Rust files. The production commands below still use the existing compiler; see
[frontend migration](FRONTEND_MIGRATION.md) for the separate mypy-based pipeline.

## Block scope differs from CPython

Loop targets are local to the loop. A loop target shadows an outer binding with
the same name, and the outer value remains unchanged after the loop. New local
bindings inside a block also stay within that block. The mypy-based pipeline
renames these bindings before checking types, including inferred locals, to
preserve the subset's existing behavior. Code that relies on CPython leaking a
loop variable into the surrounding scope is outside this contract.

## Try it

From this checkout, with the workspace virtual environment installed:

```bash
py2rust-service examples/services/json_server.py -o build/json_server
py2rust-service examples/services/json_client.py -o build/json_client
cargo build --locked --manifest-path build/json_server/Cargo.toml
cargo build --locked --manifest-path build/json_client/Cargo.toml
```

Start `./build/json_server/target/debug/py2rust-service` in one terminal, then
`./build/json_client/target/debug/py2rust-service` in another. They exchange a JSON
greeting containing `世界` over loopback port 8080 and exit after one request.
The server logs the method/path and the client prints the JSON response.

The same sources can run under Python, including a Python client with a Rust
server or the reverse:

```bash
python -u examples/services/json_server.py
# In another terminal:
python examples/services/json_client.py
```

The library demo combines strings, dates, time, logging, files/directories,
pretty-printing, regexes, enums and collections. It writes
`build/service-demo-output/report.json` relative to the working directory:

```bash
python examples/services/stdlib_demo.py
py2rust-service examples/services/stdlib_demo.py -o build/stdlib_demo
cargo run --locked --manifest-path build/stdlib_demo/Cargo.toml
```

Use Python 3.10+ and Rust 1.83+ with rustfmt. To install or refresh the CLI:
`python -m pip install -e '.[test]' ruff`.
The optional `service-reference` extra installs `html5lib` for Python reference
runs of HTML applications; the test extra includes it too. Native executables
use Rust's pinned `scraper`/`html5ever` dependencies and need no Python packages.
An equivalent module entry point is `python -m py2rust.compiler.service`.
The first Cargo build downloads dependencies; subsequent builds can add
`--offline`. Each generated project includes its runtime source and a pinned
`Cargo.lock`. Treat the output directory as generated: regeneration replaces
`Cargo.toml`, `Cargo.lock`, `src/main.rs` and the copied runtime modules in `src/`.

## HTTPS example

`examples/services/https_server.py` and `https_client.py` use a local CA and a
localhost certificate. The server accepts one connection on port 8443, with a
30-second accept deadline and a 5-second connection deadline. Create development
certificates with OpenSSL, from the checkout root:

```bash
mkdir -p build/tls
openssl req -x509 -newkey rsa:2048 -nodes -days 2 -subj /CN=Local-Service-CA \
  -addext basicConstraints=critical,CA:TRUE -addext keyUsage=critical,keyCertSign,cRLSign \
  -keyout build/tls/ca.key -out build/tls/ca.crt
openssl req -newkey rsa:2048 -nodes -subj /CN=localhost \
  -keyout build/tls/server.key -out build/tls/server.csr
cat > build/tls/extensions.cnf <<'EOF'
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=DNS:localhost
EOF
openssl x509 -req -in build/tls/server.csr -CA build/tls/ca.crt -CAkey build/tls/ca.key \
  -CAcreateserial -days 2 -extfile build/tls/extensions.cnf -out build/tls/server.crt
py2rust-service examples/services/https_server.py -o build/https_server
py2rust-service examples/services/https_client.py -o build/https_client
cargo build --locked --manifest-path build/https_server/Cargo.toml
cargo build --locked --manifest-path build/https_client/Cargo.toml
```

Run `./build/https_server/target/debug/py2rust-service`, then
`./build/https_client/target/debug/py2rust-service` in another terminal. Both
programs use paths relative to the checkout root. The Python equivalents are
`python -u examples/services/https_server.py` and
`python examples/services/https_client.py`.

The client trusts `build/tls/ca.crt` explicitly and still verifies the hostname.
Use `localhost` in its URL: the example certificate deliberately has no IP SAN.
Certificates/keys are generated locally; no private key is embedded in the source.
These short-lived certificates are only for local development.

## Coverage and boundaries

| Area | Implemented | Current boundary |
| --- | --- | --- |
| HTTP/HTTPS | GET/POST/PUT/DELETE clients, JSON and binary web handlers, custom headers, verified TLS, explicit private CA support, bounded bodies and streaming web responses | Synchronous application callbacks; HTTP/1 only, no mTLS; older JSON server is serial, streaming is available in the general web server |
| JSON | Objects/arrays/null/bools/numbers/strings, parse/serialize, typed extraction, object updates, pretty output | String keys, signed 64-bit integers, finite floats, nesting at most 64; no custom encoders |
| Strings | Unicode code-point length/index/slice/find/rfind, negative indices, strip/lstrip/rstrip, split/join, replace, prefix/suffix checks, case conversion, full case folding, UTF-8 encode/decode, literal Latin-1/ASCII byte decoding and NFC/NFD/NFKC/NFKD normalization | No slice steps, search start/end arguments, formatting mini-language or other codecs; case folding is pinned to Unicode 15.1, other case tables follow the installed runtimes |
| Time/datetime | Unix time, monotonic elapsed time, bounded sleep, UTC now, RFC3339 parse/format, integer Unix-time conversion, portable date-format directives, adding seconds, comparisons | UTC output, years 1–9999, explicit input offset, at most 6 fractional digits; explicit TZif timezone helpers; no implicit database lookup, locale-dependent formatting or general strptime |
| Logging | Level filtering and DEBUG/INFO/WARNING/ERROR/CRITICAL messages to stderr | Configure with `log_configure`; format `LEVEL:message`; no named loggers, handlers, interpolation arguments or file rotation |
| Files/directories | UTF-8 text, scoped binary files, seek/truncate/sync, hard links, identity/metadata, recursive/exclusive mkdir, bounded sorted directory names, symlink creation/targets and permission/mtime restoration | UTF-8 paths; metadata/identity tested on Linux; traversal stays in Python; no globbing or recursive deletion |
| Pretty printing | `pretty(value)` produces readable, sorted, two-space-indented JSON | JSON-compatible values; no arbitrary Python object repr |
| Regular expressions | Unicode pattern/input, search/fullmatch, whole-match findall, literal replacement | ASCII shorthand classes and common Python/Rust regex syntax; no lookaround, backreferences or `(?...)` extensions; findall/replace reject zero-width matches |
| Enums | `class Name(Enum)` with explicit homogeneous nonnegative integer or string literals, equality, `.name`, `.value` | Integers through i64 max; unique names/values; no aliases, auto, flags, methods or construction from a value |
| Typed records | Plain `@dataclass`, typed fields, scalar defaults, positional/keyword construction, field reads and named-local field assignment | Owned values; no methods, inheritance, factories, comparison, automatic JSON conversion or shared mutable aliases |
| Data structures | Typed lists, insertion-ordered dictionaries, sets, fixed and variadic tuples; list slices, dictionary-key snapshots, membership/length, list append, set add, dict get/update, sequence indexing and min-heaps | Value semantics, homogeneous list/set elements and dict key/value types; no shared mutable aliases, comprehensions or collection inheritance; heaps require totally ordered non-float values |
| HTML/URLs | HTML5 static-link extraction, HTTP(S) relative resolution, normalized origins | UTF-8 input, explicit bounds, static attributes only; no JavaScript, CSS URLs or general DOM API |
| Foreground processes | Concurrent direct-argv pipelines, binary stdin/stdout/stderr, complete environments, deadlines and signal cleanup | Linux main thread, default SIGCHLD, 1–8 stages; no shell parser in the runtime, job control or process-tree sandbox |
| Worker threads | `parallel_map` with ordered JSON results and scoped worker lifetimes | Named callbacks, independent value copies, 1–64 workers per call; no shared mutable state, task handles or forced cancellation |
| TCP and binary framing | Scoped listeners/streams, bounded accept, absolute I/O deadlines, Unix readiness polling, nonblocking reads/partial writes, half-close, byte concatenation/slices, integer byte codecs | Numeric IPv4/IPv6, explicit framing; readiness tested on Linux; no raw-TCP DNS/TLS |
| UDP | Scoped sockets, one-datagram send/receive, numeric source addresses, explicit truncation and bounded waits | Numeric IPv4/IPv6, at most 65507 bytes; tested on Linux; no DNS, IPv6 zones, multicast membership or delivery guarantees |
| Unix sockets | Scoped filesystem listeners/streams, bounded I/O, readiness, partial writes and owned-path cleanup | Tested on Linux; existing parent directory, at most 107 UTF-8 path bytes; no abstract sockets, descriptor passing or peer credentials |

TCP, UDP, Unix sockets, HTTP, JSON and persistence can coexist in one service/project program.
Import the socket handles and operations from `py2rust.stdlib`. The preliminary network profile is retired. Source-level async/await remains
unsupported. HTTP transport uses Tokio internally. TCP uses Rust standard-library
sockets, Mio for Unix readiness polling and socket2 for send-buffer configuration.
Both blocking and nonblocking TCP operations are available. UDP uses Rust
standard-library datagram sockets and does not add a Cargo dependency.

## Library API

Import the following from `py2rust.stdlib`. This module is the executable Python
reference for the library contract.

| API | Behavior |
| --- | --- |
| `unicode_normalize(form, text)` | Unicode NFC/NFD/NFKC/NFKD normalization; invalid forms raise a recoverable error for nonempty text |
| `Json`, `json_loads(text)`, `json_dumps(value)` | JSON values; dumps uses sorted keys, compact separators and literal Unicode |
| `json_loads_unique(text)` | Parse JSON with the same value bounds, rejecting duplicate decoded object keys at every depth |
| `json_scalar_compare(left, right)` | Return -1, 0 or 1 for compatible JSON scalars; mixed integer/float ordering preserves integer precision |
| `json_number_add(left, right)` | Checked integer-only addition or finite binary64 addition if either operand is float; booleans and nonnumbers are rejected |
| `json_canonical(value)` | Deterministic JSON for content IDs: sorted keys, compact Unicode, signed-64-bit integers and normalized 17-digit binary64 scientific notation |
| `json_string(value)`, `json_int(value)`, `json_bool(value)` | Require the exact JSON scalar type; bool is not an int |
| `json_float(value)`, `json_is_null(value)` | Extract a number as float; test null |
| `pretty(value)` | Format JSON-compatible primitives, lists, tuples or dictionaries with string keys |
| `ceil(value)`, `floor(value)` | Round a finite float upward/downward to a signed 64-bit integer; integer arguments remain exact; out-of-range results are recoverable errors |
| `math_log(value)` | Natural logarithm of one positive finite number; domain errors are recoverable |
| `math_sqrt(value)` / `math.sqrt(value)` | Square root of one nonnegative finite number, preserving signed zero; negative inputs raise recoverable errors |
| `parallel_map(callback, items, workers)` | Run a named `(Json) -> Json` callback over at most 10,000 JSON values, using 1–64 workers; return results in input order after all workers finish |
| `unix_time()`, `monotonic()`, `sleep(seconds)` | Float seconds; sleep must be finite and between 0 and 86400 |
| `DateTime`, `utc_now()` | UTC timestamp |
| `datetime_parse(text)`, `datetime_iso(value)` | Parse strict RFC3339; format UTC with six fractional digits and `+00:00` |
| `datetime_add_seconds(value, seconds)` | Checked date arithmetic with integer seconds |
| `datetime_from_unix(seconds)` | Integral Unix seconds to UTC, from `-62135596800` through `253402300799` inclusive |
| `datetime_unix_microseconds(value)` | Exact signed integer microseconds since the Unix epoch, including negative fractional timestamps; no float timestamp conversion |
| `datetime_format(value, pattern)` | Locale-independent UTC formatting with explicit supported directives and a 1024-byte pattern limit |
| `http_retry_after(value, now)` | Parse a Retry-After header into a Unix deadline no earlier than `now` |
| `log_configure(level)`, `log(level, message)` | Levels 10, 20, 30, 40, 50; messages are strings |
| `read_text(path)`, `write_text(path, text)` | Strict UTF-8, preserve CRLF/LF; write replaces the file |
| `read_bytes(path)`, `write_bytes(path, data)` | Binary buffers, including NUL and non-UTF8 bytes |
| `FileHandle`, `file_open(path, mode)` | Open a regular binary file; modes `rb`, `r+b`, `x+b` (exclusive create), `w+b` (create/truncate) |
| `file_lock(path) -> FileHandle` | Nonblocking exclusive Unix advisory lock, released when the shared handle closes |
| `rename_no_replace(source, destination)` | Atomic Linux move that refuses every existing destination; no overwrite fallback |
| `file_read(handle, count)`, `file_write(handle, data)` | Read up to `count` bytes; write all bytes; at most 32 MiB per call |
| `line_open(path, offset) -> LineReader` | Buffered read-only regular file, starting at an absolute byte offset between zero and file size |
| `line_read(reader, limit) -> tuple[bytes, bool]` | At most 1–1,048,576 raw bytes; the boolean marks LF or physical EOF, allowing oversized lines to be streamed in chunks |
| `line_position(reader)`, `line_close(reader)` | Logical consumed-byte position, excluding read-ahead, and shared-handle closure |
| `file_seek(handle, offset, whence)`, `file_size(handle)` | Seek from start/current/end (`0`/`1`/`2`), returning the position; size and positions fit signed 64 bits |
| `file_truncate(handle, length)`, `file_sync(handle)`, `file_close(handle)` | Resize, sync data/metadata, close; closing twice is allowed |
| `link_file(source, destination)`, `sync_directory(path)` | Publish a hard link without replacing an existing name; sync a directory |
| `path_parent(path)`, `path_name(path)`, `path_is_symlink(path)`, `path_same(left, right)` | Lexical parent/basename, symlink check (including broken links), existing-file identity |
| `Sha256`, `sha256_new()`, `sha256_update(state, data)`, `sha256_digest(state)` | Incremental SHA-256; update returns a new state, digest returns 64 lowercase hex characters |
| `mkdir_all(path)`, `list_dir(path)` | Create parent directories; list sorted basenames |
| `path_join(parent, child)`, `path_exists(path)` | OS path joining and existence |
| `html_links(document, max_links)` | Return JSON with first base href (or null) and ordered `{tag, attribute, value}` links |
| `url_resolve(base, reference)`, `url_origin(url)` | Resolve a bounded HTTP(S) reference and drop its fragment; return a normalized origin |
| `remove_file(path)`, `remove_dir(path)` | Remove a file or an empty directory |
| `regex_search(pattern, text)`, `regex_fullmatch(pattern, text)` | Boolean result |
| `regex_capture(pattern, text, full_match)` | Null or numbered group strings and character spans; full-line matching or first search result |
| `regex_findall(pattern, text)` | List of whole matched strings, even when pattern contains groups |
| `regex_replace(pattern, replacement, text)` | Replace all matches; replacement is literal, with no group interpolation |
| `constant_time_equal(left, right)` | Compare byte contents through Python `hmac.compare_digest` / Rust `subtle`; buffer lengths are not concealed |
| `HttpResponse`, `http_request(method, url, body, timeout_ms, max_body)` | Response has integer `.status` and string `.body` |
| `https_request_ca(method, url, body, timeout_ms, max_body, ca_file)` | HTTPS only; trust the explicit PEM CA bundle, with hostname checking |
| `web_request(method, url, body, headers, timeout_ms, max_body)` | Binary body and custom headers; returns `WebResponse` with readable `.status`, `.body`, `.headers` |
| `web_request_ca(method, url, body, headers, timeout_ms, max_body, ca_file)` | Binary/header client using an explicit PEM CA bundle; HTTPS only |
| `HttpReader`, `web_open(url, headers, timeout_ms, max_body)` | GET response headers/status immediately, with a streaming body handle |
| `web_open_ca(url, headers, timeout_ms, max_body, ca_file)` | Streaming GET using an explicit PEM CA bundle; HTTPS only |
| `web_read(reader, count)`, `web_close(reader)` | Read up to `count` bytes (1–32 MiB); empty bytes at EOF; idempotent close |
| `HttpServer`, `http_listen(host, port)`, `http_port(server)` | Numeric IPv4 listener; port 0 chooses an available port |
| `https_listen(host, port, cert_file, key_file)` | HTTPS listener with PEM certificate chain and matching unencrypted private key |
| `http_serve_json(server, handler, count, max_body)` | Serve up to `count` connections using `(method: str, path: str, body: Json) -> Json`; default deadlines 30000/10000 ms |
| `http_serve_json_timeout(server, handler, count, max_body, accept_timeout_ms, connection_timeout_ms)` | Set explicit accept and total connection I/O deadlines |
| `TcpListener`, `tcp_listen(host, port)`, `tcp_port(listener)` | Listen on numeric IPv4/IPv6; port 0 chooses an ephemeral port |
| `TcpStream`, `tcp_connect(host, port, timeout_ms)` | Connect with a deadline, then initialize a separate stream I/O deadline |
| `tcp_accept_timeout(listener, accept_ms, io_ms)` | Bound the accept wait and initialize the accepted stream's I/O deadline |
| `tcp_set_deadline(stream, timeout_ms)` | Set the absolute deadline for subsequent stream reads/writes to now plus this interval |
| `tcp_recv(stream, count)`, `tcp_sendall(stream, data)` | Receive up to 1 MiB; send an entire buffer of at most 1 MiB; empty received bytes mean EOF |
| `tcp_accept_ready(listener, limit, io_ms)` | Accept up to 1–64 pending connections without waiting; return an empty list when none are ready |
| `tcp_select(listener, readers, writers, timeout_ms)` | Unix readiness snapshot as JSON: `accept` bool and sorted `read`/`write` index arrays; up to 1,024 handles per list and 0–60,000 ms wait |
| `tcp_recv_ready(stream, count)` | Nonblocking read of 1–1,048,576 bytes; return `(data, eof)`, distinguishing would-block `(b"", False)` from EOF `(b"", True)` |
| `tcp_send_ready(stream, data)` | Attempt one nonblocking write of at most 1 MiB; return the accepted byte count, possibly partial or zero |
| `tcp_send_buffer(stream, size)` | Set the OS send-buffer hint to 1,024–1,048,576 bytes; the OS can clamp or double this value |
| `tcp_shutdown_write(stream)` | Half-close sending while retaining the ability to receive |
| `tcp_close(stream)`, `tcp_close_listener(listener)` | Close the shared handle; repeated close is allowed |
| `UdpSocket`, `udp_bind(host, port)`, `udp_port(socket)` | Bind numeric IPv4/IPv6; port 0 selects an ephemeral port; return the local port |
| `udp_sendto(socket, data, host, port, timeout_ms)` | Send one 0–65507-byte datagram to a numeric IP of the same family and port 1–65535 |
| `udp_recvfrom(socket, limit, timeout_ms)` | Receive one datagram as `(bytes, source_host, source_port, truncated)`; limit 1–65507 bytes |
| `udp_close(socket)` | Close the shared socket; repeated close is allowed |
| `int_from_bytes(data, byteorder)`, `int_to_bytes(value, length, byteorder)` | Unsigned encoding/decoding of 0–8 bytes with explicit `big` or `little` order; values must fit nonnegative signed i64 |
| `int_from_decimal(text)` | Parse up to 4,096 ASCII bytes as signed decimal digits with an optional sign and surrounding ASCII whitespace; require a signed 64-bit result |
| `int_lshift(value, count)`, `int_rshift(value, count)` | Signed-64-bit shifts with recoverable negative-count and left-shift-overflow errors; source `<<`/`>>` lower to these helpers |

Compatibility spellings also compile: `json.loads`, `json.dumps`, `time.time`,
`time.monotonic`, `time.sleep`, `logging.info` and the other four level methods,
`pprint.pformat`, `math.ceil`, `math.floor`, `math.log`, `unicodedata.normalize(form, text)`, and
`hmac.compare_digest` with two byte arguments.
These lower to the profile API. Running those spellings in
Python invokes the real standard library, whose options, bounds and formatting
may differ. Use `py2rust.stdlib` functions when comparing the reference contract.
In particular, `pprint.pformat` in generated Rust means pretty JSON, not Python repr.
Python's `math.ceil` and `math.floor` can produce arbitrarily large integers; the generated code
rejects results outside the subset's signed 64-bit range. Use `ceil` or `floor` from
`py2rust.stdlib` for the same checked behavior in reference runs.

## Mutable byte buffers and logarithms

`bytes()` and `bytearray()` construct empty buffers. A single argument can be an
integer zero-filled length, another bytes/bytearray value, or a typed `list[int]`.
List literals receive the integer element type, including `bytes([])`. Each byte
must be 0–255. Both constructors copy input buffers and reject negative lengths.
New constructors and bytearray growth have a 64 MiB result limit in native code;
Python's builtins do not have this profile-specific bound. This is a buffer-size
bound, not a total process-memory guarantee. Existing immutable-byte operations
retain their own documented limits.

A named bytearray supports integer indexed assignment and deletion, `append(int)`,
`extend(bytes_or_bytearray)`, `pop()`/`pop(index)`, `clear()` and `reverse()`.
Negative indices are checked. Failed byte conversion, indexing or growth leaves
the target unchanged apart from argument side effects. Assignment evaluates its value before its index; method
arguments evaluate before mutation. Explicit `copy()`, contiguous slices,
`bytearray.fromhex(text)`, `hex()` and strict `decode()` are supported. Decoding
defaults to UTF-8; a single literal encoding may select UTF-8 (`utf-8`, `utf8`),
Latin-1 (`latin-1`, `latin1`, `iso-8859-1`, `iso8859-1`) or ASCII (`ascii`). Encoding
names are case-insensitive and underscores are treated as hyphens. Every Latin-1
byte maps to the same-valued Unicode character. Invalid UTF-8 or non-ASCII bytes
raise recoverable errors. The receiver evaluates once. Dynamic encoding names,
error-handler arguments, keywords and other codecs remain unsupported. Slices and
copies keep the bytearray type. Slice assignment, strides, dynamic encodings,
error-handler arguments, `insert`/`remove`, implicit coercion to bytes, and mutation through
record fields or nested containers are outside this contract. Load a field into
a local, modify it and write it back. Pass `bytes(buffer)` to APIs requiring bytes.

Both byte types support lexicographic comparisons, integer or byte-subsequence
membership, integer iteration, and `list(buffer)`/`tuple(buffer)` conversions.
An out-of-range integer membership needle raises a recoverable error. Native
bytearrays follow the existing owned-value contract: assignment and function
arguments copy values; iteration takes a snapshot. Avoid shared mutable aliases
and mutation during iteration when comparing with CPython.

`math.floor(value)` rounds down to signed i64, preserving integer inputs exactly,
including values beyond binary64's exact integer range. `math.log(value)` accepts
one positive finite number and returns its natural logarithm. Zero, negative,
NaN/infinite arguments, and nonfinite results are rejected; no second base
argument is supported. `floor` and `math_log` in `py2rust.stdlib` provide the checked
reference contract. Native transcendental results can differ by small floating
point rounding errors across platforms; validation compares numerical tolerances.

## Portable UTC dates and reverse string search

`datetime_from_unix(seconds)` converts an integer number of Unix seconds to UTC.
It accepts the inclusive range `-62135596800..253402300799`, corresponding to
`0001-01-01T00:00:00Z` through `9999-12-31T23:59:59Z`. It neither uses the local
timezone nor rounds floating-point timestamps. For filesystem nanoseconds,
use integer floor division by `1000000000`, which also handles pre-epoch values.
Out-of-range seconds are recoverable errors.

`unicode_normalize(form, text)` supports the four forms defined in
[Unicode Standard Annex #15](https://www.unicode.org/reports/tr15/), including
canonical composition/decomposition, compatibility decomposition, combining-mark
ordering and algorithmic Hangul composition. It does not case-fold text. Rust uses
`unicode-normalization` 0.1.23 with Unicode 15.1 tables, matching the tested Python
3.13 reference. Python uses its installed `unicodedata` tables; newer Unicode versions
can assign new characters, so update and test both runtimes together. Invalid form
names are recoverable errors for nonempty text. Like CPython, empty text returns
unchanged before the form name is checked. Ordinary `import unicodedata` lowers its two-argument
`normalize` call; other `unicodedata` APIs and keyword arguments remain unsupported.

`datetime_format(value, pattern)` normalizes an aware value to UTC and uses a
portable directive subset. Literal Unicode, whitespace and an empty pattern
are preserved. The pattern is at most 1024 UTF-8 bytes. English weekday/month
names and zero-padding are independent of process locale; `%Y` has four digits
even for years below 1000. The supported directives are:

| Directives | Output |
| --- | --- |
| `%Y`, `%m`, `%d` | Four-digit year and two-digit month/day |
| `%H`, `%M`, `%S`, `%f` | Two-digit hour/minute/second and six microsecond digits |
| `%z`, `%Z` | `+0000` and `UTC` |
| `%j` | Three-digit ordinal day of year |
| `%a`, `%A` | Abbreviated and full English weekday |
| `%b`, `%B` | Abbreviated and full English month |
| `%w`, `%u` | Sunday-based 0–6 and Monday-based 1–7 weekday numbers |
| `%%` | Literal percent sign |

Unknown directives, an unmatched final `%`, locale modifiers, flags and widths
are rejected. This is a named portable helper, not unrestricted platform
`strftime` compatibility. Parsing remains the existing strict RFC3339 operation;
there is no general `strptime`. The explicit TZif helpers below provide named-zone conversion.

The ordinary one-argument `text.rfind(needle)` method returns the last matching
Unicode code-point index, or `-1` if absent. An empty needle returns `len(text)`.
The receiver and needle each evaluate once in source order. Optional start/end
arguments remain unsupported, as for the existing forward `find` method.

## Filesystem observations

Three general operations support traversal written in Python:

- `path_stat(path: str, follow_links: bool) -> Json` returns `kind`, `size`,
  `mode`, `device`, `inode`, `links`, `mtime_ns`, `atime_ns` and `ctime_ns`.
  Kind is one of `file`, `directory`, `symlink`, `fifo`, `socket`, `block`,
  `char` or `other`. Mode contains the low 12 permission/special bits. Times are
  signed integer nanoseconds since the Unix epoch; `ctime_ns` means inode-change
  time. False observes the final symlink itself; true follows it. Missing targets
  are errors only when followed. Every numeric field must fit signed 64-bit.
- `directory_names(path: str, limit: int) -> list[str]` returns sorted immediate
  names. The limit is 1–100000. The final component must be a directory rather
  than a symlink. Too many entries, listing errors or non-UTF-8 names raise an
  error; callers never receive an arbitrary truncated subset. Empty directories
  return an empty list.
- `read_link(path: str) -> str` returns the stored target text without resolving
  or requiring the target to exist. Ordinary files and non-UTF-8 targets raise
  errors.

Paths must be nonempty and NUL-free. Redundant separators, trailing separators
and `.` components are normalized consistently with Python's `Path`; `..` and
ancestor symlinks retain filesystem resolution semantics. Metadata currently
requires Unix and is verified on Linux x86-64. These are separate observations,
so concurrent changes can race between calls. A no-follow traversal requires
stable ancestor directory entries. Metadata sizes are apparent byte sizes,
including holes in sparse files, rather than allocated disk usage.

The implementation uses [Rust's Unix metadata fields](https://doc.rust-lang.org/stable/std/os/unix/fs/trait.MetadataExt.html)
and checked integer conversion. Nanoseconds never pass through floating point.
Application 031 implements its queue, exclusions, limits, errors, hard-link
aggregation and report publication in Python using these operations.

## No-overwrite moves and scoped file locks

`rename_no_replace(source, destination)` moves a file, directory or symlink entry
using Linux `renameat2(RENAME_NOREPLACE)`. Any existing destination, including a
dangling symlink or a hard link to the source, causes an error. Source equal to
destination also fails. Missing sources, permissions, cross-device moves and
unsupported kernels/filesystems return recoverable errors; the runtime never
falls back to an operation that could overwrite a destination. Paths are nonempty,
NUL-free and normalized like the filesystem-observation paths above. The operation
moves the final symlink itself and does not synchronize directories automatically.
See the [Linux rename contract](https://man7.org/linux/man-pages/man2/rename.2.html).

`file_lock(path)` returns a shared `FileHandle` holding `flock(LOCK_EX | LOCK_NB)`.
It creates a regular lock file with mode 0600 when needed, without truncating an
existing file. Final symlinks and special files are rejected; another holder
causes an immediate error. Use `with file_lock(path) as lock:` for scoped release,
or `file_close(lock)` explicitly. Closing one alias closes every alias. A killed
process also releases its lock. The persistent lock file remains: unlinking or
replacing it would let another process lock a different inode. This is an advisory
lock requiring cooperating writers and stable ancestor directories, not a
mandatory protection against arbitrary file changes. Python uses `fcntl.flock`;
Rust calls the same OS operation through `libc`.

The four-module [rename planner](../examples/corpus/032_rename_planner/main.py)
keeps collision checks, approval digests, staging, checkpoints, state validation
and reversal in Python. Atomic no-overwrite moves prevent clobbering; the batch
as a whole is resumable rather than atomic. Its acceptance checks cover both
engines without a Python runtime in the native execution environment.

`replace_file(source, destination)` atomically moves a regular source file over
an absent or distinct regular destination. Final symlinks, directories, special
files and same-inode aliases are rejected before the rename. An already-open
reader of the old destination retains the old inode. File contents/metadata belong
to the incoming inode; existing hard links to either inode are not overwritten.
The runtime does not synchronize either directory automatically. Validation and
rename are separate observations, so callers must protect entries and ancestor
directories from races. Unix is required; Linux x64 is verified. This supports the
artifact store's explicitly named staging files and atomic reference replacement.

## Restore filesystem operations

`mkdir_new(path)` creates one directory with mode 0700 subject to the process
umask. The parent must exist; every existing destination, including a dangling
symlink, causes an error. `create_symlink(target, path)` creates a new symlink
without replacing existing entries. Its nonempty UTF-8 target is stored literally,
including `..`, absolute paths and missing targets; it is never resolved.

`path_set_metadata(path, mode, mtime_ns)` sets ordinary permission bits (0–0777)
and a signed-64-bit modification timestamp in nanoseconds. A final symlink is
updated without following it and requires mode 0777; its permissions are unchanged.
Regular files and directories are opened with no-follow/nonblocking flags, checked
again through the descriptor, updated and synchronized. Other entry kinds fail.
Existing access time is preserved; ownership and other metadata are not restored.
Underlying filesystem timestamp precision/range can restrict the stored value.
Permission and timestamp updates are separate operations and can partly succeed
before an OS error. Ancestor symlinks retain normal filesystem semantics; these
operations assume stable parents. All three operations are verified on Linux x64.
Callers must sync parent directories when durability of new entries is required.

The [snapshot backup](../examples/corpus/034_snapshot_backup/main.py) composes
these operations in Python with hashes, manifests, retention and no-overwrite
publication. It synchronizes its object/manifests directories and restore parent,
and restores child metadata before applying read-only directory permissions.

## TCP and binary framing

`TcpListener` and `TcpStream` support `with` scopes, including across project
modules. Normal exits, returns, exceptions, `break` and `continue` close the scoped
resource. Handles are shared references: closing one alias invalidates the others.
Socket handles are not JSON values and cannot be passed through `parallel_map`.

TCP is a byte stream. A receive returns up to the requested size and may return
less; applications must accumulate data and implement their own message framing.
The [complete task broker](../examples/corpus/021_tcp_broker/protocol.py) uses
four-byte big-endian lengths followed by UTF-8 JSON. Its Python source handles
split/coalesced TCP writes, frame limits, clean EOF and truncated messages.

Blocking I/O timeout arguments accept 1–86,400,000 milliseconds. `tcp_connect` applies the
timeout to connecting, then starts a fresh I/O deadline after connection succeeds.
Accept has separate waiting and initial I/O limits. Reads and writes share the
stream's absolute deadline until `tcp_set_deadline` resets it; partial reads do
not extend it. `tcp_sendall` tracks that same deadline across partial writes.
Calls can fail after transferring part of a buffer, so callers must treat the
connection or their protocol transaction accordingly. OS scheduling can add a
small delay to timeout observation. `tcp_accept_timeout` polls nonblocking accept
at intervals of up to two milliseconds. Raw TCP has no hostname resolution or TLS;
the HTTP/HTTPS APIs keep their existing TLS support.

For several peers, `tcp_select` waits for a readiness snapshot. Its `read` and
`write` arrays contain indices into the supplied lists, not socket descriptors.
Duplicate handles report each corresponding index. Readiness is a hint: a ready
read/write can still return would-block, EOF or an error. A zero timeout polls
without waiting; larger timeouts are bounded at 60 seconds. Each call creates
fresh polling registrations over temporary owned descriptor duplicates, so
subsequent snapshots can report unread data again. Unix is required; Linux is
the verified target. Non-Unix builds return a recoverable unsupported error.

Use `tcp_accept_ready`, `tcp_recv_ready` and `tcp_send_ready` after polling. These
calls do not wait for the stored blocking I/O deadline; application code owns
idle, incomplete-frame and drain deadlines. The accept call initializes the
accepted streams' blocking deadlines using `io_ms`. A ready read returns bytes
and a separate EOF flag, and a ready write returns a byte count; retain unsent
suffixes for later writes. Blocking read/write calls restore blocking mode when
used after ready calls. Send-buffer configuration is an OS hint, distinct from
an application queue limit. The [room chat](../examples/corpus/022_room_chat/main.py)
demonstrates bounded queues, per-peer work budgets and slow-reader eviction.

Byte concatenation with `+` and slices with optional/negative start and end indices
follow Python's clamping rules; slice steps remain unsupported. `data.find(needle)`
accepts one bytes argument and returns the first byte offset, -1 if absent, or 0
for an empty needle. The spellings
`int.from_bytes(data, byteorder)` and `value.to_bytes(length, byteorder)` compile
to the checked codecs above. Both arguments are explicit; there is no signed mode
or arbitrary-precision result. Length zero encodes only zero, and an empty input
decodes as zero. Plain CPython permits larger integers/byte lengths, so use
`int_from_bytes` and `int_to_bytes` for identical checked reference behavior.

## UDP datagrams

`UdpSocket` supports the same `with` cleanup rules as TCP handles. Normal exits,
returns and exception unwinding close the resource and invalidate all aliases;
explicit close is idempotent. Sockets are not JSON values and cannot pass through
`parallel_map`. Concurrent I/O through aliases is outside this contract.

Each send produces one datagram; each receive consumes one datagram. An empty
payload is a valid message, not EOF. When a datagram exceeds `limit`, the returned
bytes contain its prefix and `truncated` is true; the rest is discarded, not left
for the next receive. An exact-size message has `truncated` false. The runtime
receives one extra byte to distinguish these cases. Linux x86-64 is the verified
target for this behavior. Source addresses are numeric IP strings and integer
ports; IPv6 addresses with scope IDs are rejected. Hostnames and zone suffixes
are not accepted as bind or destination addresses.

Timeouts accept 1–86,400,000 milliseconds and apply to a single send or receive.
Rust retains the absolute deadline across interrupted system calls. A timeout is
a recoverable error and leaves the socket usable; OS scheduling can delay its
observation slightly. A successful send means the OS accepted the whole datagram,
not that the peer received it. Loss, duplicates and reordering belong in the
application protocol. The [complete directory/client](../examples/corpus/025_udp_directory/main.py)
implements sequence checks, finite retries, source/request correlation and
size-bounded replies entirely in Python before transpilation.

## Filesystem Unix sockets

`UnixListener` and `UnixStream` are scoped resources with the same shared-handle
aliasing rules as TCP. These operations are tested on Linux x86-64:

| API | Contract |
| --- | --- |
| `unix_listen(path, recover_stale)` | Bind a filesystem stream socket; parent must exist; path must be nonempty, NUL-free and at most 107 UTF-8 bytes after canonicalizing its parent |
| `unix_connect(path, timeout_ms)` | Connect within a bounded wait; create a stream with an absolute I/O deadline |
| `unix_accept_timeout(listener, accept_ms, io_ms)` | Bounded accept; accepted stream receives its own I/O deadline |
| `unix_accept_ready(listener, limit, io_ms)` | Accept 0–`limit` ready peers, with `limit` between 1 and 64 |
| `unix_set_deadline(stream, timeout_ms)` | Reset the absolute blocking-I/O deadline |
| `unix_recv(stream, count)` | Read up to 1–1048576 bytes; empty bytes indicate EOF |
| `unix_sendall(stream, data)` | Send at most 1048576 bytes under the stream's absolute deadline |
| `unix_recv_ready(stream, count)` | Return `(bytes, eof)` immediately; `(b"", False)` means would block |
| `unix_send_ready(stream, data)` | Return bytes written immediately; retain unsent bytes; zero means would block or empty input |
| `unix_send_buffer(stream, size)` | Request a 1024–1048576-byte send buffer; the kernel may adjust it |
| `unix_select(listener, readers, writers, timeout_ms)` | Return `{accept, read, write}` readiness with original list indices; 0–60000 ms and at most 1024 entries per list |
| `unix_shutdown_write(stream)` | Half-close sending, leaving reads available |
| `unix_close(stream)`, `unix_close_listener(listener)` | Idempotent close through all aliases; listener close also removes its owned socket path |

Connect/accept/I/O timeout arguments are 1–86400000 milliseconds. Readiness and
nonblocking operations do not consume the blocking-I/O deadline; application code
controls its own session/partial-frame timers. Readiness is a snapshot and does
not guarantee a subsequent operation will still be ready. Repeated stream aliases
in readiness lists retain their separate indices.

With `recover_stale=False`, any existing path is rejected. With `True`, only a
filesystem socket whose bounded 100-ms probe returns connection refused is
reclaimed. A successful probe opens then closes a connection to the existing
listener and causes the new bind to fail. Timeouts, permission failures, ordinary
files, directories and symlinks do not authorize removal. Cleanup compares the
path's device/inode with the created socket and preserves replacement files.
The canonical parent anchors cleanup even for relative input paths. Normal scoped
exit, propagated errors and explicit close clean up; forced process termination
can leave a stale path. Automatic final-drop cleanup is best effort.

These operations assume an appropriately protected parent directory; the identity
checks are not atomic protection against hostile directory-entry replacement.
Abstract sockets, datagrams, descriptor passing and peer-credential inspection
are not implemented. The adapter uses Rust's
[Unix socket types](https://doc.rust-lang.org/std/os/unix/net/index.html), the
already pinned socket2 crate for bounded connect, and Mio for readiness. It adds
no dependency. Application 030 keeps its framing, command dispatch, receipt cache
and fair event loop entirely in transpiled Python.

## Bounded callback workers

`parallel_map` accepts a named, typed callback, including one imported from another
Python module in the same project:

```python
from py2rust.stdlib import Json, json_int, parallel_map

def square(item: Json) -> Json:
    number: int = json_int(item)
    return {"input": number, "square": number * number}

def run() -> None:
    results: list[Json] = parallel_map(square, [3, 1, 2], 2)
    print(results)
    return
```

Each invocation receives its own deep copy of the input value. Mutating it does
not change the input list or another invocation's data. Inputs and results must
satisfy the JSON contract. Results retain input order, regardless of completion
order. All callbacks finish before the function returns, including when a
callback raises a recoverable exception. In that case, the first error in input
order is raised after the workers join; other callbacks are not cancelled.
An empty input returns an empty list, but still validates the worker limit.

Rust uses scoped native threads; the Python reference uses `ThreadPoolExecutor`.
There are at most `min(workers, len(items))` active callbacks per call. This is a
per-call limit, so nested calls can create additional threads. Lambdas, closures,
shared mutable Python objects, asynchronous tasks and forced cancellation are
outside this interface. A callback must finish its own work; one that never
returns prevents the map from returning. Applications can use deadlines and an
external cancellation signal, as demonstrated by the
[complete HTTP load probe](../examples/corpus/020_load_probe/main.py).

## HTML and URL contract

`html_links` accepts at most 1 MiB of UTF-8 text and 1–10000 links. It parses
HTML with scripting enabled for `noscript` interpretation but never executes
scripts or loads resources. The implementation uses `scraper`/`html5ever` in
Rust and [html5lib](https://html5lib.readthedocs.io/en/latest/) in Python. The
first base element having an `href` supplies `base`; an empty value is preserved.
Links are returned in DOM order, with entities decoded and the first duplicate
attribute retained. HTML templates and foreign-namespace elements are excluded.
Normal HTML descendants of foreign integration points are still HTML elements.

Extracted attributes are `a/area/link[href]`,
`img/script/iframe/audio/source/input[src]`, `video[src,poster]`, and `object[data]`.
Parsing errors are recovered by the HTML5 libraries. Bounds errors are recoverable
runtime errors and never return a partial list. The API does not expose a full
DOM, execute scripts, inspect CSS or handle `srcset`. These library versions are
tested for the documented fixtures; this is not a complete browser conformance claim.

`url_resolve` requires an absolute HTTP(S) base and permits relative references.
Its 8192-byte input/output bounds include UTF-8 encoding. Authority hosts must be
ASCII DNS names or canonical dotted IPv4, with optional 1–5 digit ports in
1–65535. Credentials, IPv6 literals, controls, backslashes, invalid percent escapes,
non-HTTP schemes, and surrounding ASCII spaces are rejected. Applications may
trim HTML attribute whitespace before calling it. Unicode paths and queries are
UTF-8 percent-encoded, fragments are removed, and percent hex digits are uppercase.
Literal and encoded dot segments resolve, default ports disappear, and scheme/host
case is normalized. Empty query strings and repeated path slashes are retained.
`url_origin` returns scheme, host and any non-default port. Matching an origin does
not imply matching every host or subdomain; callers enforce their own crawl policy.

## HTTP contract

The client sends `Content-Type: application/json` and `Connection: close`.
Supply a string body, usually `json_dumps(payload)`. The URL must use `http://` or `https://`
without credentials or a fragment. Percent-encode non-ASCII URL paths yourself.
It returns non-2xx statuses and bodies normally, does not follow redirects, and
decodes chunked responses. Invalid UTF-8 and oversized responses are errors.
`max_body` is 1–1,048,576 bytes and `timeout_ms` is 1–86,400,000 ms. This is a
blocking client; Python socket timeouts and Rust client deadlines need not expire
at exactly the same instant, and DNS timing is not guaranteed.

`web_request` accepts `bytes` and `dict[str, str]` request headers. Its response
body remains bytes, including NUL and invalid UTF-8; `max_body` is 1–33,554,432
bytes. All clients cap outgoing bodies at 33,554,432 bytes. The binary client
defaults to `application/octet-stream`; a supplied `Content-Type` replaces that
default. Header names are case-insensitive tokens; values must contain only
printable ASCII or tab. Case-insensitive duplicate request names are rejected.
`Host`, `Content-Length`, `Transfer-Encoding`, and `Connection` are managed by the
transport and cannot be supplied. Response header names are lowercase, and only
the first value of a repeated name is exposed. Non-ASCII response header values
are errors, including for the text client. Both clients connect directly without
environment proxy discovery. Redirects are never followed automatically.

`web_open` exposes `.status` and `.headers` before consuming the body. The
`max_body` limit applies cumulatively across reads, including chunked responses;
truncation, overflow and I/O errors close the reader. `timeout_ms` is a whole
response deadline, including time spent by the application between reads.
Reads after that deadline fail even if bytes are already buffered. DNS and
connection setup still depend on platform/client timeout behavior. A `with`
scope releases the reader on success, error, or an early return. Upload bodies
remain buffers; streaming uploads are not implemented.

`http_retry_after(value, now)` interprets decimal delay seconds and the three
HTTP date forms in [RFC 9110 sections 5.6.7 and 10.2.3](https://www.rfc-editor.org/rfc/rfc9110.html#section-10.2.3).
It returns an absolute Unix deadline, preserving fractional seconds for relative
delays and returning `now` for past dates. Obsolete two-digit years resolve in a
rolling 100-year window ending fifty years after the supplied reference time,
including month/day/time at that boundary. Weekdays must match the calendar;
date spelling and GMT are case-sensitive. A leap-second value of 60 maps to
the following Unix second. Leading/trailing space or tab is allowed; other
extra whitespace and nonstandard timezones are rejected. Inputs are bounded at
64 UTF-8 bytes, and `now` and resulting deadlines must lie from Unix epoch to
9999-12-31T23:59:59Z. Invalid input is recoverable. This adapter does not sleep
or apply application backoff; callers persist and enforce the returned deadline.

HTTPS always checks the certificate chain and hostname. `http_request` uses the
default trust roots: Python's platform/OpenSSL store and Rust's bundled Mozilla
roots via ureq. Those stores may differ. For deterministic private-service trust,
`https_request_ca` uses only the CA bundle you supply; it rejects plain HTTP URLs.
There is no verification-disable option. TLS 1.2 and 1.3 are supported; client
certificates, encrypted private keys, certificate hot reload and HTTP/2 are not.

The server passes the method, raw path/query and parsed body to the handler.
An empty request body becomes JSON null. It replies with JSON and status 200;
malformed JSON gets 400, an oversized declared body gets 413, and a handler error
gets 500. Requests using transfer encoding are outside this server subset.
Use Content-Length for request bodies. `count` is 1–100000; `max_body` uses the
same range as the client. Exact protocol headers and unsupported-method handling
can differ between the reference and Rust libraries.

The server handles one connection at a time and closes it after one response.
`http_serve_json` now defaults to a 30000 ms accept timeout and a 10000 ms
connection timeout; the explicit variant accepts 1–86400000 ms for each.
The connection deadline starts after TCP accept and covers the TLS handshake,
headers, body reads and response writes. It is an absolute budget: receiving
occasional bytes does not reset it. A stalled or malformed peer is closed and
consumes one of the `count` slots, then the server accepts the next connection.
An idle accept timeout propagates as an error. A timeout may close the transport
without an HTTP response, so clients must handle EOF/reset as well as status codes.

These are I/O deadlines, not a CPU sandbox: a synchronous handler cannot be
preempted and must finish by itself. There are no detached Rust request tasks;
the Python reference joins its connection watchdog on cleanup. The kernel can
queue connections, but only one is processed at a time. This older JSON server
has no streaming API; use the general web server below for streaming responses.
Graceful external shutdown and concurrent application handlers remain future work.

## Language and semantic contract

Functions, parameters, return values and new local variables need annotations.
Use `int`, `float`, `bool`, `str`, `bytes`, `bytearray`, the library types (including
`WebRequest`, `WebResponse`, `StreamChunk`, `FileHandle`, `HttpReader` and `Sha256`), enums,
typed dataclass records, `list[T]`, `dict[K, V]`, `set[T]`, fixed `tuple[T1, T2]` and homogeneous variadic `tuple[T, ...]`.
Keys/set elements are strings, integers, bools, enums or immutable tuples composed
recursively of those types. Fixed tuples used as keys have at most 12 fields. Conditions are bools; no implicit
truthiness. Use one `if __name__ == "__main__":` entry point.

Conditional expressions `a if condition else b` require a bool condition and
compatible branch types. The condition evaluates once and only the selected
branch runs. Expected annotations guide empty-collection inference, JSON
conversion and integer-to-float conversion. Generated Rust uses an `if` expression;
errors from the unselected branch are not evaluated.

Supported control flow includes if/else, while, for over lists/sets, dictionary
keys, bytes/bytearrays, homogeneous fixed/variadic tuples or one/two/three-argument range, break/continue, return
and assertions with optional string messages. Loop
variables and block-local declarations have block scope. Functions can call each
other, and fallible calls propagate errors through Rust `Result` and `?`.
String iteration yields one-character strings in Unicode scalar order, including
combining marks as separate characters. The iterable expression is evaluated once;
reassigning its source variable inside the loop does not change that iteration.
The existing block scope for loop bindings still applies.
Missing returns and some invalid Rust type combinations are still diagnosed by
the Rust compiler. Async, comprehensions and general classes/decorators are not supported.
The record subset below permits `@dataclass` and constructor keyword arguments.
The single-file service frontend rejects import aliases; the project linker resolves
its documented local and standard-library import aliases before compilation.

`with expression as name:` supports one `FileHandle`, `LineReader`, `HttpReader`, `TcpListener`,
`TcpStream`, `UdpSocket`, `UnixListener`, `UnixStream` or `ProcessPool` binding per
statement; scopes can nest. The binding must not shadow an existing local.
Generated Rust uses a resource guard whose destructor closes the handle on
normal completion, return, propagated error, break or continue. This is an
explicit resource subset, not arbitrary Python context-manager support. Closing
does not imply a durability guarantee: call `file_sync` before committing progress,
and `sync_directory` after publishing or removing directory entries.

`try` with exactly one `except Exception` handler is supported, optionally with
`as error` and an `else` block. `str(error)` exposes the message; I/O/parser error
wording can differ between runtimes. Generated Rust catches propagated `Result`
errors, including failed assertions, and preserves returns through nested try
blocks. Rust panics are not caught. `else` runs after a successful protected block;
its errors escape that block's handler. Bare `raise` inside a lexical
`except Exception` handler propagates its active error message. Nested handlers
temporarily replace the active error and restore the outer error afterward;
a nested try can catch a re-raised error without consuming the outer handler's
ability to raise it again. Resource guards still close on propagation. Exception
identity, traceback objects and chaining are not exposed. Bare `raise` outside
a lexical handler or `finally`, explicit `raise SomeError(...)`, specific exception classes,
multiple handlers, and break/continue across a protected boundary remain unsupported. Exception variables cannot shadow an existing local. Normal
block scope still applies; declare a variable before the try if both paths update it.

`finally` runs after protected success, a pending function return, or a propagated
error. It can accompany the supported handler/else form or appear alone after
`try`. A return or error from cleanup replaces the pending outcome. Nested cleanup
runs from inside outward. Bare `raise` inside cleanup propagates its pending
error (or an enclosing handler's error); without either, it raises the message
`No active exception to reraise`. Owned-value and lexical-local rules continue to
apply. Loop-local break/continue are supported inside either block; jumping to a
loop outside a protected closure is diagnosed. Cleanup handles recoverable
runtime errors, not process exit, SIGKILL, or Rust panics.

`LineReader` is a scoped resource with the same shared-alias lifetime rule as
`FileHandle`. `line_read` preserves LF, CRLF, bare CR, NUL and invalid UTF-8 bytes;
only LF ends a logical line before EOF. A returned chunk includes its LF when
present. If its byte limit is reached before the line ends, the flag is false;
at exact EOF it is true even when the final chunk has exactly the requested size.
Subsequent EOF reads return `(b"", True)`. The reader uses a 64 KiB internal buffer,
accepts offsets inside a line or a UTF-8 sequence, and exposes byte positions
independent of internal read-ahead. It performs no decoding or newline conversion.
As with file handles, `with` closes aliases on errors and early returns; explicit
close is idempotent and reads/position queries after close are errors.

Service integers are signed 64-bit values, unlike the initial TCP profile's i32.
Addition, subtraction, multiplication and unary minus check overflow. Floating
arithmetic rejects non-finite results. Integer `//` and `%` follow Python's floor
and divisor-sign rules, including negative operands. Division/modulo by zero and
an unrepresentable quotient return recoverable errors. `i64::MIN % -1` is zero;
`i64::MIN // -1` exceeds the subset's integer range.
`abs(value)` accepts an `int` or `float`, preserves that numeric type and evaluates
its argument once. Integer `abs(i64::MIN)` raises a recoverable overflow error.
Floating absolute value clears the sign, including negative zero, and requires
a finite result. Bool, complex and collection operands are unsupported.
True division (`/`) accepts two `int` operands or two `float` operands and always
returns `float`. Integer ratios round once to nearest binary64 with ties to even;
operands are not first rounded to floats. This preserves Python's result above
2^53, including `9007199254740993 / 3`, and permits `i64::MIN / -1` as a float.
Float division preserves signed zero and finite subnormal results. Zero divisors,
including negative floating zero, raise recoverable errors. Native float division
rejects a nonfinite result, consistent with the profile's other checked float
arithmetic; ordinary CPython may produce infinity outside this finite-result
contract. Mixed `int`/`float` operands still require an explicit conversion, as do
other arithmetic operators. Float floor-division/modulo remain unsupported. Python
itself keeps its usual unbounded integer semantics, so programs must stay within
the profile's range. Float display and JSON numeric spelling can differ between
Python and Rust; compare parsed numeric values, not exact float text.

Integer `&`, `|`, `^` and `~` use signed bit patterns, matching Python for values
within the subset range. Both operands must be integers; bool/float operands and
set bitwise operations are unsupported. Left/right shifts evaluate operands once
in source order. Negative counts are recoverable errors. Left shift rejects an
out-of-range result instead of wrapping; `-1 << 63` is valid, while `1 << 63` is
not. Zero shifted left by any nonnegative signed-64-bit count remains zero.
Right shifts preserve the sign; counts of 64 or more yield zero or minus one.
The `int_lshift`/`int_rshift` reference functions enforce the same bounds in Python;
ordinary Python operators retain Python's arbitrary-precision semantics.

For loops support `range(stop)`, `range(start, stop)` and `range(start, stop, step)`.
Arguments evaluate once in source order. Three-argument ranges iterate lazily,
including negative steps, without allocating a list. A zero step is a recoverable
error even for an empty range. Signed-64-bit boundaries terminate correctly when
the next mathematical value would overflow; `break` and `continue` retain their
normal behavior. Range objects outside a for-loop remain unsupported.

`value is None`, `value is not None` and their reversed spellings are supported
when the other operand is JSON or a None-valued expression. The nonliteral operand
evaluates exactly once; only JSON null matches, never false, zero, empty text or
empty containers. General object identity comparisons remain unsupported.

Chained comparisons such as `1 <= limit <= 20000` evaluate operands left to right,
evaluate each middle operand once and stop before later operands after a false
comparison. Generated Rust saves operands in named locals and uses nested `if`
expressions; it does not duplicate an expression or eagerly evaluate the whole
chain. Equality, ordering, membership and the supported literal-None identity
operators can be combined, subject to each adjacent pair's type rules. Numeric
comparison pairs still require equal types; convert mixed int/float values
explicitly. Container operands retain the subset's owned-value semantics, not
CPython shared mutable alias behavior.

Set `<`/`<=`/`>`/`>=` use proper/non-strict subset and superset relations. Disjoint
or incomparable sets are not ordered by their smallest elements. Lists and
tuples containing sets compare their first unequal elements using those same
inclusion rules, then lengths when applicable; native BTreeSet's lexicographic
order must not leak into these expressions. This does not make sets valid
arguments to the subset's `sorted` operation.

Ordinary `import heapq` supports `heapify(heap)`, `heappush(heap, item)`,
`heappop(heap)`, `heapreplace(heap, item)` and `heappushpop(heap, item)` through
qualified calls such as `heapq.heappop(heap)`. The first argument must be a named
typed list of integers, booleans or strings, or recursively ordered list/tuple
combinations of those types. Floats, JSON, enums, records, sets and custom
comparisons are excluded. Direct `from heapq import …`, keyword arguments and
other heapq functions are not currently supported; project module aliases work
through the usual linker rules.

These are in-place min-heap operations following the
[Python heapq contract](https://docs.python.org/3.13/library/heapq.html).
Heapify takes linear time; push/pop/replace take logarithmic comparisons.
The caller maintains the heap invariant between operations. Pop and replace on
an empty heap raise a recoverable error without changing it; push-pop on an empty
heap returns the supplied item and leaves the heap empty. Push-pop retains the
larger of the supplied item and previous root, while replacement always removes
the previous root. Item arguments evaluate once before mutably borrowing the
heap, including expressions that pop from that same list. The subset's owned
container semantics still apply across assignments and function calls. A sequence
counter in a tuple can supply stable tie order; heaps do not supply FIFO ties
automatically. See the [complete priority queue](../examples/corpus/053_priority_queue/main.py).

`list(value)` accepts a typed list, set or dictionary. Dictionaries produce keys
in insertion order; list order and duplicates are preserved; set order is unspecified
between engines, so sort it when order matters. The receiver evaluates once. Named
and nested local containers are borrowed, copying only the returned elements/keys;
dictionary values are not cloned just to take a key snapshot. The result follows
the subset's owned-value semantics. Other iterables and heterogeneous values are
outside this constructor's current contract.

A named typed dictionary's `get(key, default)` borrows the dictionary and returns
an owned copy of the selected value. Both arguments evaluate in source order
before looking up the key, even when the key is present. If default evaluation
clears the dictionary, lookup sees the cleared dictionary, as in Python. A computed
receiver evaluates once before both arguments and retains the subset's owned-value
semantics. This avoids copying an entire named mapping for every lookup.

Strings, bytes, bytearrays, collections and JSON have owned-value semantics. Assignments and
function arguments still copy their values. Indexed reads and slices of named
local containers borrow the container and copy only the returned value. Typed
list/dictionary subscript paths rooted in a local, such as `groups[key][index]`,
also borrow intermediate containers. Length checks and membership borrow these
paths without copying them; the membership needle evaluates before its container. Computed receivers evaluate once before their
indices, and tuple-length expressions preserve receiver side effects. Updating a collection argument therefore does not
update its caller's collection; return a new value explicitly. Do not depend on
Python identity or shared mutable aliases. Set iteration order is unspecified
across the two runtimes. List iteration uses a snapshot: do not mutate a container
while traversing it. Tuple indexing requires a nonnegative constant; strings,
lists, bytes and JSON arrays allow checked negative indices. Dict/JSON-object
item assignment is supported. Named lists also support integer item assignment,
including negative indices, with recoverable bounds errors. A chain of typed
lists rooted in a named local also supports writes such as `grid[row][column] = value`
at any depth. The value evaluates first; indices then evaluate once from outer
to inner, checking each parent before evaluating its child's index. Invalid
indices raise recoverable errors without the assignment. The value and outer
index may mutate the root before lookup. Inner indices must not structurally
mutate/reorder that root or its nested lists, including through `heapq` operations:
preserving a detached object's identity is outside this owned-value subset.
The write updates the selected element in place without copying the containing
grid. Nested dictionary/JSON/tuple/string paths, record-field roots and slice
assignment remain unsupported. A list directly inside a named typed list or
dictionary supports `container[index].append(value)` and
`container[index].extend(values)`. The lookup evaluates once and validates the
index/key before evaluating the argument; missing keys do not get inserted.
Read-only arguments can refer to that same collection, including self-extension.
Arguments that call a mutating method or `heapq` operation on the parent collection are rejected:
preserving a removed target through Python's mutable aliases is outside the
owned-value contract. Deeper append/extend targets and JSON-container mutation methods
remain unsupported. Named lists support `pop()` and `pop(index)`
with checked negative indices; empty/out-of-range removal is a recoverable error.
The index expression is evaluated before checking the resulting list length,
including when it mutates the same list. `del mapping[key]` removes a key from
a named typed dictionary or JSON object and errors when it is missing. Typed
dictionary deletion preserves remaining insertion order. `for key in mapping`
iterates a typed dictionary's keys in insertion order, evaluating the dictionary
expression once. As with lists, Rust traverses a snapshot; do not add or delete
keys while iterating. Replacing existing values is supported. Deletion from lists
or nested receivers, and multiple deletion targets, are not supported.

`int(text)` with one string argument lowers to `int_from_decimal`. The accepted
grammar is an optional `+`/`-`, then one or more ASCII decimal digits, surrounded
by any of space, tab, CR, LF, vertical tab or form feed. Leading zeros are allowed.
Empty input, underscores, Unicode digits/whitespace, radix prefixes, alternate
bases and non-string conversion are outside this spelling's current subset.
Input is bounded at 4,096 bytes; overflow is a recoverable error. Use the explicit
`int_from_decimal` adapter in reference code when the same rejection behavior is
needed: ordinary Python `int` permits additional forms and larger integers.

File, HTTP and TCP handles intentionally share their external resource across copies:
file aliases share the cursor, and closing one alias closes all of them. This
lets resource scopes work through function calls. Digest states use value
semantics instead: `next_state = sha256_update(state, data)` leaves `state`
unchanged, and `sha256_digest` does not consume either state. Rust delegates
SHA-256 to `ring`; Python uses `hashlib`.

Regex patterns and input may contain Unicode. Literal characters, dot and negated
classes match Unicode code points. Shorthands `\w`, `\d`, `\s` and their complements
retain Python `re.ASCII` behavior; `\b` and `\B` use ASCII word boundaries.
`\B` follows Python 3.13 behavior and does not match an empty input. The Rust
adapter expands these classes without disabling UTF-8 matching. `$` matches
the end of input or immediately before one final LF; `\Z` matches only the end.
CRLF is not normalized: `$` may match between its CR and final LF. Full matches
still have to consume the entire input, including any final newline.

`regex_capture(pattern, text, full_match)` returns null when there is no match;
otherwise it returns `{"groups": [...], "spans": [...]}`. Index zero is the whole
match, followed by numbered parenthesized groups. Nonparticipating groups are null
in both arrays. A participating empty group has an empty string and an equal-start/end
span. Spans are half-open Unicode code-point indices, not UTF-8 byte positions.
Repeated groups retain the last captured value according to the supported regex
syntax. With `full_match=True`, the match must cover the entire input; with false,
it is the first search match. Zero-width results are allowed because this API returns
only one match. Replacement and `findall` reject every zero-width match, including
an empty match immediately after a nonempty match. Replacement strings are literal;
`$1`, `\1` and `\g<name>` do not expand capture groups.

Capture input is bounded at 65,536 UTF-8 bytes, the pattern at 4,096 bytes, and the
number of capturing groups at 64 (excluding group zero). Invalid patterns and bounds
are recoverable errors, including when the input would not match. The Rust runtime
retains at most one compiled capture pattern, keyed by pattern and matching mode;
results remain independent values. The cache is safe for concurrent workers.

Regexes intentionally cover only common syntax. Avoid engine-specific character
class operations and escapes. User-supplied extension groups, lookarounds and
backreferences remain unsupported. Ordinary patterns use Rust's `regex` engine;
patterns containing an unescaped `$` or `\B` assertion use `fancy-regex` 0.14.0
with a 1,000,000 backtracking-step limit. Exceeding that native execution limit
is a recoverable error; the CPython reference has no equivalent step counter.
These are bounded subset semantics, not a promise of full Python `re` compatibility.

## Implementation and validation

- `py2rust/stdlib.py`: runnable Python library reference.
- `py2rust/compiler/service.py`: explicit type checking, source-line errors and lowering;
  reuses py2rust's Rust control-flow/function AST nodes. This is a separate typed
  frontend, not an extension of every upstream inference/rewrite pass.
- `py2rust/compiler/service_runtime/`: Rust runtime, pinned manifest and lockfile. HTTP uses
  `ureq` for clients and Hyper/Tokio for servers, with rustls for TLS. JSON uses
  `serde_json`, dates use `chrono`, regexes use `regex`/`fancy-regex`, digests use `ring`, base64 uses `base64`,
  HTML uses `scraper`/`html5ever`, URLs use `url`,
  dictionaries use `indexmap`, and TCP/Unix-socket readiness uses `mio`. No HTTP parser
  is implemented here.
- `tests/test_services.py`: compiles generated programs and compares behavior
  with Python, plus actual loopback HTTP exchanges and invalid-input cases.
- `tests/test_service_tls.py`: generates short-lived certificates with OpenSSL;
  verifies trusted/untrusted/expired/wrong-host TLS and server I/O deadlines.

Fetch the locked dependencies once, then test offline:

```bash
cargo fetch --locked --manifest-path py2rust/compiler/service_runtime/Cargo.toml
python -m pytest tests/test_corpus_evidence.py tests/test_service_regex_capture.py tests/test_service_arithmetic.py tests/test_service_division.py tests/test_service_heaps.py tests/test_service_set_algebra.py tests/test_service_casefold.py tests/test_service_bitwise.py tests/test_service_bytearray.py tests/test_service_log_floor.py tests/test_service_errors.py \
  tests/test_service_records.py tests/test_service_recursive_records.py tests/test_service_codecs.py tests/test_service_canonical_json.py \
  tests/test_service_comparisons.py tests/test_service_datetime.py tests/test_service_timezones.py tests/test_service_strings.py tests/test_service_string_iteration.py tests/test_service_normalization.py tests/test_service_sorting.py tests/test_service_json_numbers.py \
  tests/test_service_http_client.py tests/test_service_http_reader.py tests/test_service_resources.py tests/test_service_lines.py tests/test_service_tuples.py tests/test_service_insert.py tests/test_service_filesystem.py \
  tests/test_service_rename.py tests/test_service_restore.py \
  tests/test_service_markup.py tests/test_service_http_dates.py tests/test_service_request_target.py \
  tests/test_service_parallel.py tests/test_service_tcp.py tests/test_service_select.py tests/test_service_udp.py \
  tests/test_service_unix.py tests/test_service_tokens.py tests/test_service_unicode_regex.py \
  tests/test_service_collections_math.py \
  tests/test_service_streams.py \
  tests/test_project.py tests/test_services.py tests/test_service_tls.py tests/test_network.py tests/test_telegram.py -q
cargo clippy --locked --offline --manifest-path py2rust/compiler/service_runtime/Cargo.toml -- -D warnings
```

Tests require localhost socket permissions, and TLS tests also need OpenSSL.
They cover all four Python/Rust
client/server combinations, malformed JSON, body limits, chunked responses,
non-2xx statuses, redirects, timeouts, UTF-8, scalar type errors, overflow,
dates, logging output, file round trips, regexes, enums and collections.
The full upstream multi-language suite is outside this local validation.

Local validation on 2026-10-10 (Python 3.13.5, Rust 1.83.0): all 483 selected tests
passed in one complete run (403 seconds). Coverage includes project linkage, local Python/Rust module precedence,
chat behavior, Unicode regex cases, secret byte comparison, membership conversions,
collection clearing, checked ceiling/floor arithmetic, logarithm vectors and domains,
bytearray mutation and growth limits, streaming backpressure,
disconnect cleanup, real 60-second empty-stream deadlines, scoped resource
cleanup, known SHA-256 vectors, incremental client reads and response deadlines,
HTML5 link extraction, a 258-case URL-resolution matrix, binary chunk joining,
independently calculated Retry-After calendar/deadline vectors, original incoming
request targets, application cache policy without duplicate default headers,
ordered worker results, input isolation, worker limits and joins after errors,
IPv4/IPv6 TCP scopes, half-close, deadlines and binary integer/slice vectors,
Unix readiness snapshots, actual nonblocking backpressure, partial writes,
EOF/would-block distinction, collection removal and binary substring search.
Typed dictionary traversal and bounded decimal parsing additionally cover
insertion order, expression evaluation, signed limits and ASCII whitespace.
UDP parity covers IPv4/IPv6 source addresses, empty and exact-fit datagrams,
truncation without spillover, maximum-sized payloads, timeouts, invalid bounds
and scoped cleanup through aliases.
Bitwise checks cover signed boundary patterns, evaluation order, large shifts,
negative counts, checked overflow and rejection of noninteger operands.
Record checks cover defaults, constructor evaluation order, nested field updates,
owned copies, shared resource handles, collection snapshots, imported types and
invalid declarations/construction. Codec checks cover known base64/SHA-1/masking
vectors, canonical padding, exact byte limits and recoverable errors; list slices
and explicit float conversion have boundary and evaluation-order parity checks.
Tuple-loop checks cover single evaluation, break/continue, singleton tuples,
owned collection/record values, shared resource handles and unsupported mixed types.
Conditional expressions cover lazy branches, single condition evaluation, records,
empty collections, contextual conversions and invalid operand types. Unix socket
checks cover filesystem ownership, stale/active sockets, aliases, cleanup through
errors/returns, readiness, half-close, partial writes, backpressure and deadlines.
Chained-comparison checks cover side-effect order, a shared file cursor, skipped
errors, nested chains, signed boundaries, floats, strings, bytes, sequences,
membership and literal-None tests. Independent set oracles cover 512 triples and
64 nested sequence combinations, including incomparable sets; invalid mixed
types and general identity chains are rejected.
UTC-format checks compare 1009 timestamp vectors with an independent datetime
oracle, including year boundaries, negative epochs, leap dates, the 2038 boundary,
all supported directives, offset normalization, microseconds, literal Unicode,
exact pattern-byte limits and recoverable invalid formats. Reverse search checks
cover 506 Unicode/empty/overlapping substring pairs and operand evaluation order.
Filesystem checks compare metadata to independent OS calls, including exact
negative/nanosecond times, symlink choices, hard links, special files, permissions,
UTF-8 failures and overflow. Symlink access times are bracketed by independent
observations because following/reading a link may update them; other fields and
regular-file timestamps are compared exactly. Collection-read checks verify owned copies,
evaluation order and large list/dictionary lookups under 128 MiB address-space limits.
No-overwrite move checks cover existing files, directories, dangling symlinks,
hard links, Unicode names and competing writers with exactly one winner. Lock
checks cover independent OS contention, scope unwinding, shared-handle close,
content preservation and process termination. Scalar-list set construction is
checked for single evaluation, duplicate removal, owned results and rejected types.
Canonical JSON tests use an independent decimal-rounding oracle for 3,000 finite
binary64 vectors per engine, including subnormals, extreme exponents, negative
zero, numeric spellings, integer boundaries, escapes and exact bitwise round trips.
Replacement tests verify regular-file publication, existing open readers, hard-link
identity, non-overwrite failures for other entry types and alias rejection. Typed
list conversions cover one evaluation, container copies, nested sets and an
80,000-key snapshot under 128 MiB without cloning dictionary values.
Dictionary-get tests cover receiver/key/default order, clearing during default
evaluation, native owned results and an 80,000-entry mapping under a 128 MiB
address-space limit. Null-identity checks distinguish null from other JSON values
and preserve expression side effects. Evidence tests verify selective manifest
invalidation, transitive imports, package initializers, import cycles and rejection
of dynamic checker dependencies.
Restore-operation checks compare exact permissions and positive/negative nanosecond
mtime against independent OS calls, prove final symlinks never update their target,
and reject existing destinations, special files and invalid modes/paths. Signed
range-step checks cover argument order, empty/zero-step ranges, integer extremes,
negative steps and early termination of a range spanning the full integer domain.
Indexed appends/extensions and nested reads cover negative indices, missing keys,
lookup-before-argument behavior, self-extension, owned copies and rejected aliasing.
Membership checks verify needle-before-container order, including a needle that
mutates its container. Separate 128 MiB regressions verify that nested reads,
length, membership and indexed updates do not clone large list/dictionary members.
Ruff, runtime Clippy with
warnings denied, Rust formatting and whitespace checks also passed. The
[application corpus](../examples/corpus/README.md) separately verifies complete
native programs under an environment without Python on PATH. Its WebSocket
deadline fixtures permit TCP reset only after validating the expected close
frame, only for unacknowledged closes while the client continues sending.
Ordinary graceful-close checks still require EOF; this accounts for the
unread-input behavior described in [RFC 6455 section 1.4](https://www.rfc-editor.org/rfc/rfc6455.html#section-1.4).

The [fixture-tree application](../examples/corpus/040_fixture_tree/main.py) composes
the existing document, byte, path, lock and exclusive-file APIs without shared
compiler/runtime changes. Its whole-project checks compare exact contents and
ownership receipts, preserve unrelated files, reject changed/unrecorded entries,
exercise interrupted creation/cleanup and real permission failures, and run at
the 4 MiB payload and 1,000-entry bounds under 128 MiB per process. Separate
Python/Rust creator-cleaner pairs verify that receipts work across both engines.

The [CSV/JSON converter](../examples/corpus/041_csv_json/main.py) additionally
exercises bare re-raising during failed publication cleanup. Its CSV state machine,
formatting, typed row validation, projection and rejection reporting are all
transpiled Python. Independent checks use the Python `csv` module, preserve
embedded newlines/quotes/Unicode, test atomic data/report publication and bounds,
and round-trip typed records across all four Python/Rust writer-reader pairs.
Exception regressions specifically check nested active-error restoration,
repeated re-raising, propagation from `else`, resource closure and unsupported
raise forms.

Buffered-line checks use an independent byte-stream oracle for offsets, limits,
LF/CRLF/bare CR, invalid UTF-8, exact EOF and repeated EOF. They exercise aliases,
closed handles, invalid bounds, non-regular files and resource cleanup, plus a
64 MiB logical line under a 128 MiB address-space limit. The complete
[JSONL transformer](../examples/corpus/043_jsonl_transform/main.py) composes the
reader with atomic checkpoints and streaming quarantine. Its acceptance checks
verify interrupted/cancelled recovery without lost or duplicated committed rows,
corruption rejection, a valid stream over 180 MB and a 160 MiB oversized record
under 128 MiB per process, including mixed Python/Rust recovery.

Tuple regressions check variadic construction, source reuse, dynamic/negative
indexing, slicing, nested keys, enum keys, duplicate-key updates, iteration,
ordering and rejected mutable/float key types. The complete
[CSV join utility](../examples/corpus/044_csv_join/main.py) exercises tuple-key
hash indexes against an independent nested-loop oracle. Both engines verify
69 join cases, 83 invalid cases, 21 publication cases, path/permission failures,
10,000 input rows, 100,000 output rows, 64-component keys and exact byte bounds.
Eight mixed-engine pipelines combine it with the complete CSV/JSON converter.

The [JSON diff/patch project](../examples/corpus/045_json_patch/main.py) adds
Python list insertion for ordered array edits. Five Python modules implement
exact canonical-value differences, guarded functional application, inverse
patches and atomic publication. Independent iterative-diff and mutable-tree
oracles check scalar/container transitions, numeric representation, escaped paths,
array shifts, stale/late failures, capacity limits and interruption behavior.
Eight mixed-engine diff/apply/undo combinations preserve exact canonical values.
Insertion regressions cover every boundary, expression order, self-mutating
arguments, failed values, records, JSON, shared resources and unsupported calls.

The [event-log consistency checker](../examples/corpus/046_event_log/main.py)
uses the existing enum, record, tuple-key, UTC, JSON and buffered-line APIs without
shared compiler/runtime changes. Four Python modules preserve exact record locations,
classify duplicate IDs/sequences, retain temporal high-water marks, track observed
state chains and publish complete JSON/text diagnostics. Independent checks cover
late arrivals, final missing ranges, integer limits, malformed records, changed
inputs and publication interruptions. Bounds run under 256 MiB per process; four
mixed-engine pipelines consume the JSONL transformer's actual filtered output.

Unicode normalization checks compare 70,148 form results per engine against
Python's Unicode 15.1 tables, covering every decomposition-bearing scalar, every
Hangul syllable and combining-mark permutations. They check idempotence, argument
order, invalid forms/types and local Python/Rust module precedence. Nested sorting
checks cover recursive lexicographic order, prefixes, empty sequences, tuple/list
combinations, one evaluation, independent top-level results and rejected unordered
element types.

The [contact import deduplicator](../examples/corpus/048_contact_import/main.py)
uses those extensions in four Python modules. It preserves original source variants,
normalizes matching values, groups transitive matches, retains per-value provenance
and separates conflicts for review. Independent graph checks verify idempotent
re-imports, deterministic ordering, changed/corrupt inputs, publication failures
and capacity bounds under 256 MiB per process. Eight mixed-engine import/update/reimport
combinations consume actual persisted books without losing earlier variants.

JSON numeric regressions compare thousands of mixed integer/float pairs against an
independent rational-number order oracle and Python arithmetic. They include i64
limits, the 2^53 boundary, adjacent floats, subnormals, signed zeros, overflow,
scalar kinds, single argument evaluation and invalid arities.
The [JSON query console](../examples/corpus/049_json_query/main.py) uses these shared
operations in five fully transpiled modules. Independent query algebra and stable
sorting verify filters, projections, grouped counts/sums, nested paths, equivalent
expressions, precise malformed-query locations and saved-file publication. Its
2,000-row cases and eight mixed CSV import/query/export combinations use native
binaries with Python removed from their execution environment.

The [JSONL partition writer](../examples/corpus/050_jsonl_partition/main.py) uses
existing JSON, UTC datetime, hashing, tuple-key and atomic-publication APIs without
new compiler/runtime changes. Three fully transpiled modules preserve every input
record occurrence in deterministic date/topic shards. Independent checks verify
manifests and checksums, exact repeats, UTC boundaries, capacity limits, changed
inputs and killed writers; all four mixed-engine pairs reproduce actual saved
shards byte-for-byte.

True-division regressions check 35,942 signed-integer ratios against Python,
with an independent rational-number oracle for nonzero results and explicit
signed-zero checks. These include cases that fail if both operands are rounded
to float before division. Thousands of finite binary64
pairs are compared bit-for-bit, covering subnormals, signed zeros and underflow.
Additional checks cover evaluation order, zero divisors, native nonfinite-result
errors, result annotations and unsupported operand types.
The [LRU cache workbench](../examples/corpus/051_lru_cache/main.py) uses integer
true division for its cumulative hit rate. Four Python modules replay commands,
preserve recency, enforce capacity and publish checksummed state with complete
event history. An independent access-clock oracle checks eviction and accounting;
every split of a representative trace reproduces uninterrupted execution. Eight
mixed-engine save/resume/read combinations consume actual snapshot files.

The [TTL notebook](../examples/corpus/052_ttl_notebook/main.py) composes existing
HTTP, JSON, time and filesystem APIs without a compiler extension. Its four
modules save JSON values and deadlines with a durable clock high-water mark.
Checks compare 653 HTTP transitions against a record-list oracle, including exact
expiry and replacement deadlines, then exercise concurrent clients, the actual
wall clock, corruption and interrupted atomic saves. All eight mixed-engine
write/update/read combinations preserve expiration through restart and clock rollback.

Heap regressions compare 2,000 mixed heap operations, including each resulting
list, against CPython's heapq implementation. Independent sorted outputs check
86 input collections, including 3,001 elements. Additional checks cover nested
sequences, tuple ties, Unicode, booleans, signed integer limits, empty-heap errors,
item evaluation and rejected types/calls. The
[persistent priority queue](../examples/corpus/053_priority_queue/main.py) uses
these generic operations in four Python modules, with an independent sorted-record
oracle, cancellation and ID reuse, retries, capacity, save/restore, corruption,
interrupted publication and eight mixed-engine save/retry/resume combinations.

Set-algebra checks cover 1,324 input pairs, independent membership oracles,
algebraic laws, unchanged inputs, independent results, nested calls, error/evaluation
order, tuples and rejected types/calls. Case-folding checks compare all 1,112,064
Unicode scalar values against CPython 3.13 / Unicode 15.1, plus expansion sequences,
idempotence and evaluation order. The generated table reproduces exactly after
formatting. The [document search engine](../examples/corpus/054_document_search/main.py)
uses these operations in seven Python modules; an independent brute-force scan
verifies search, ranking, replacement and deletion. All eight mixed-engine
save/update/query combinations consume the actual snapshot files.

The case-fold extension's wheel contains the generated Rust table. Its extracted
compiler builds a complete two-module project using case folding and set algebra;
the resulting executable passes with Python paths disabled.

Recursive-record checks cover dictionary, list, variadic-tuple and nested fixed-tuple
fields, 97-level trees, independent native copies, imported quoted aliases and
literal string preservation. Invalid inline recursion, record keys, unknown types
and malformed annotations fail before native compilation. The
[autocomplete index](../examples/corpus/055_autocomplete/main.py) uses the extension
in five Python modules. An independent flat dictionary checks suggestions, normalized
updates, pruning, usage counts, export and reconstruction through every trace split;
eight mixed-engine combinations preserve actual saved files. A wheel extraction
check builds a complete two-module recursive-record project and runs its binary
with Python paths disabled.

The heap extension's packaging check built a wheel, extracted its compiler and
runtime, compiled a project using a heapq module alias, and ran the resulting
binary with Python absent from its environment. Earlier packaging checks also
confirmed the remaining runtime modules and lockfile. The local certificate recipe passed OpenSSL
chain/hostname verification. Earlier targeted upstream unit checks passed 34
tests with 4 optional skips; the full multi-language suite was not run.

Further extensions include graceful HTTP server shutdown, source-level async/await,
record serialization for request/response schemas, richer collection operations,
and a common binding description shared by the TCP and service profiles. Replacing
the remaining conservative cloning with borrowing should follow behavioral tests
and measurements, as with the inventory and duplicate-finder applications'
indexed-read and grouping improvements.

## General web applications

The [Paper Plane application](../examples/telegram/README.md) exercises an additional
HTTP interface. `web_serve(host: str, port: int, handler)` runs until terminated;
`handler` has signature `(WebRequest) -> WebResponse`. Requests expose `method`,
`path`, `target` (original HTTP request target), `headers: dict[str,str]` (lowercase
names), `query: dict[str,str]` (URL-decoded), and `body: bytes`. Use `target` when
repeated query parameters, their order, blank values or original percent escapes
matter; the convenience query map cannot retain all of those distinctions.
Construct responses with `web_response(status, body, headers)`.
The server bounds bodies to 32 MiB and connections to 60 seconds; the Rust adapter
supports 64 concurrent network connections and serializes application callbacks on
one event loop. Handler errors become HTTP 500 and do not stop the server. This
interface currently serves HTTP; use an HTTPS reverse proxy for public hosting.
Responses default to `Cache-Control: no-store` only when the application has not
supplied that header. The check is case-insensitive and does not append a second
default to an explicit cache policy. `X-Content-Type-Options: nosniff` is added
by the server.

`web_serve_stream(host, port, handler, poll)` adds streaming responses to that
server. The handler still returns `WebResponse`; use
`web_stream(headers: dict[str,str], state: Json, interval_ms: int) -> WebResponse`
to begin a status-200 stream. The `poll(state: Json) -> StreamChunk` callback uses
`stream_chunk(body: bytes, state: Json, done: bool)` to provide the next bytes,
replacement cursor/state and completion flag. Empty nonfinal chunks wait for the
next poll; a final chunk may contain data. This is a general byte-stream adapter;
the [notification board](../examples/corpus/010_notification_board/main.py) encodes
SSE and manages event replay in application Python.

Each chunk and serialized state is bounded at 64 KiB; intervals are 1–60,000 ms.
HTTP framing headers (`Content-Length`, `Transfer-Encoding`, `Connection`,
`Trailer`) are managed by the runtime and rejected in streaming headers.
Callbacks run serially and must finish quickly. Network writes happen outside
the application callback: Rust's HTTP body is polled on writer demand, while the
Python reference finishes each bounded socket write before requesting another
chunk. Neither starts a background producer queue. A callback error aborts the
response; it cannot change an already sent HTTP status.

The server permits 64 connections, with at most 32 live streams to leave capacity
for regular requests. Further stream attempts get 503. A 60-second total
connection deadline also bounds stalled or idle streams; applications should
support reconnects. Disconnect/error/timeout drops transport-owned stream state
and cancels further polls. Python can detect a quiet disconnect on the next write
or at the deadline; use periodic heartbeat bytes when prompt cleanup matters.
These adapters do not yet provide source-level async tasks or a graceful external
shutdown API. Streaming clients use `HttpReader`; streaming uploads remain future work.

`json_array(value)` extracts a `list[Json]`; `json_get(value, key, default)` reads an
object; `json_kind(value)` reports `null/bool/number/string/array/object`;
`json_parse(text, default)` returns the default on invalid input. `json_loads`
raises on invalid input and retains the last value of a repeated object key.
`json_loads_unique(text)` rejects repeated decoded keys, including escaped spellings
of the same key, at every object depth. Reusing a key in separate sibling objects
is valid. Both functions retain the 64-level nesting, signed 64-bit integer,
finite binary64 and UTF-8 requirements. Parser metadata names such as
`$serde_json::private::Number` are ordinary object keys. The Rust parser uses
borrowed raw JSON fragments to validate containers without interpreting those
keys as internal number wrappers; no Python parser or runtime is involved.
`env_get(name, default)`, `random_token()` (32 random bytes encoded as
hex, Linux `/dev/urandom`), `write_text_atomic(path, text)` (same-directory replacement
and fsync), and `url_quote(text)` (UTF-8 percent encoding) are available in both
runtimes. These functions are general adapters; application logic stays in Python.

`ord(value)` accepts exactly one positional `str`, `bytes` or `bytearray` value.
A string must contain exactly one Unicode scalar; bytes and bytearrays must
contain exactly one byte. The result is an integer code point or byte value.
Empty/multiple-character values raise a catchable runtime error; the argument
evaluates once. Surrogate code points remain outside the UTF-8 string profile.
The regression checks every Unicode scalar and all 256 byte values against
CPython, including invalid lengths and combining sequences.

Strings support `[start:end]` with Unicode code-point and negative-index semantics,
without steps. `strip()`, `lstrip()` and `rstrip()` accept no argument, a
single string character set, or `None`. Omitted/`None` arguments remove Python
Unicode whitespace, including U+001C–U+001F. An explicit string identifies
individual characters to remove; an empty string preserves the input. This
follows the [Python trimming contract](https://docs.python.org/3/library/stdtypes.html#str.strip).
The receiver is evaluated once before its argument, and operand failures propagate
through the normal local exception path. Character-set operations use Unicode
scalar values without normalization. Keyword arguments and other argument types
are rejected by the typed compiler. Bytes support `startswith`, `endswith` and `find` with one bytes argument.
Loop variables may be reassigned or mutated. JSON/dict/list assignments evaluate the
right-hand value before borrowing the destination for mutation. Shared mutable
alias semantics across function boundaries are still outside this subset.

## Canonical JSON for shared content IDs

`json_canonical(value)` accepts the same serializable subset values as `json_dumps`.
It uses sorted string keys, compact separators and literal UTF-8; there is no Unicode
normalization. Signed-64-bit integers are decimal tokens. Finite binary64 numbers
are rounded to 17 significant decimal digits in scientific notation, then trailing
fractional zeros and the decimal point are stripped. Exponents have no redundant
plus sign or leading zeros. Float zero is `0e0`, negative float zero is `-0e0`;
integer zero remains `0`. Integer `1` and float `1e0` intentionally have distinct
encodings. Equivalent float token spellings normalize to the same binary64 encoding.
The depth, integer, finite-number and Unicode checks match the existing JSON APIs.

For example, `0.1` becomes `1.0000000000000001e-1`; `1.0` becomes `1e0`. The encoding
preserves round trips of binary64 values and is stable between the Python reference
and Rust runtime. It is this subset's explicit encoding, not an RFC 8785/JCS claim.
`json_dumps` and `pretty` keep their existing display behavior. Applications that
hash ordinary display JSON containing floats should explicitly choose canonical
encoding when IDs must be shared across engines. Artifact-store manifests do so.

## Complete-application extensions

The [application corpus](../examples/corpus/README.md) checks complete programs
with independent behavioral oracles in both Python and generated native Rust.
No Python runtime is embedded in those executables.

- Typed sets of matching element types support `&`, `|`, `-` and `^`, and the
  methods `intersection(other)`, `union(other)`, `difference(other)` and
  `symmetric_difference(other)`. Each operand evaluates once, left to right;
  the result owns its elements and changing it leaves the inputs unchanged.
  Elements use the existing string, integer, bool, enum and immutable tuple
  contract. Methods take exactly one matching typed set; general iterables,
  multiple operands, keyword arguments and in-place algebra are outside this
  extension. Native code uses standard Rust `BTreeSet` operations.
- `text.casefold()` implements full default Unicode 15.1 case folding, including
  expansions such as `Straße` to `strasse`, final sigma to sigma and dotted capital
  I to `i` plus combining dot. It has no arguments, locale selection or Turkic
  overrides, and does not normalize text. For normalized search, explicitly use
  `unicode_normalize("NFKC", text).casefold()`. The native table is generated by
  `tools/generate_casefold.py` from the pinned CPython 3.13 / Unicode 15.1
  reference and shipped as Rust source; native execution never consults Python.
  Run the generator with that reference and then `rustfmt` to reproduce the table.
  A different Unicode version in the Python reference may have different mappings.

- Empty `list()`, `dict()` and `set()` require a matching
  expected type, usually a local annotation. Lists support `extend(other_list)`,
  `copy()`, `reverse()` and stable `sort()`.
  A named typed list supports `insert(index, value)`: negative indices count from
  the current end and all out-of-range indices clamp to the front/end, including
  signed-64-bit extremes. The index expression runs before the value expression,
  then the insertion position uses the list's length after both arguments. The
  operation returns `None`. Value errors propagate before insertion; argument
  side effects retain Python evaluation order. Indexed/nested receiver forms,
  keyword arguments and non-integer indices remain unsupported.
  Matching typed lists support `left + right`, evaluating each operand once from
  left to right. The result owns its ordinary values; resource elements retain
  shared handles. Empty literals use the other operand's type or an enclosing
  list annotation. Two empty operands require an annotation.
  `sorted(list, key=named_function, reverse=boolean)` returns a stable sorted copy.
  A typed dictionary is also accepted: `sorted(mapping)` sorts its keys and
  preserves the mapping. The optional key callback receives each dictionary key
  in insertion order, with stable ties in either direction. The iterable and
  direction expressions each evaluate once. Dictionary literals still need
  inferable key/value types; annotate an empty dictionary before sorting it.
  The optional key is `None` or a named annotated function taking exactly one
  matching element and returning an ordered non-float value. Keys are evaluated
  once per item in input order, after evaluating the list and direction. Errors
  stop evaluation. Equal keys retain input order in both directions. A callback
  receives an owned ordinary value, so changes to that value do not alter the
  sorted items; resource aliases remain shared. Imported project functions work
  as keys. Lambdas, callable values, extra positional arguments and expanded
  keyword arguments are outside this spelling. The in-place `list.sort()` still
  accepts no arguments.
  Sorting supports integers, bools, strings and recursively nested lists/tuples of
  these values. Generated enum ordering uses declaration order; ordinary CPython
  `Enum` values are not orderable, so sort their names/values for reference parity;
  direct float/JSON sorting remains unsupported. A key permits records and JSON
  payloads to be sorted through an explicitly typed projection. Fixed tuples used
  as ordered values have at most twelve fields, recursively, matching Rust's
  standard ordering implementations.
  Lists support `[start:end]`, including omitted, negative and clamped bounds;
  slice steps and slice assignment remain unsupported. `list(typed_dictionary)`
  returns an insertion-ordered key snapshot that permits deletion during traversal.
  `list(value)` also copies a typed list, set or homogeneous fixed/variadic tuple.
  `set(typed_list)` supports `int`, `str` and `bool` elements, removing duplicates
  from one evaluation of the list without changing it. Set iteration order is
  unspecified across engines; float and mutable element types are rejected.
  Lists directly stored in named typed lists/dictionaries additionally support
  indexed `append` and `extend`, with lookup-before-argument evaluation and the
  structural self-mutation restriction described above.
  Dicts and sets also support `copy()`, under the existing value-semantics contract.
  Named lists, dictionaries and sets support zero-argument `clear()`; previously
  copied collections retain their contents.
  Nonempty fixed tuples support `for item in values` when every element has
  exactly the same type. The tuple expression evaluates once, then its elements
  are traversed in order. Rust uses a local tuple and a fixed array of its owned
  fields; collections/records retain value semantics and resources retain shared
  handles. Empty and heterogeneous tuple iteration is rejected, including mixed
  `int`/`float` tuples. Tuples themselves may still have heterogeneous fields when
  accessed by constant index.
  Homogeneous variadic `tuple[T, ...]` supports empty and nonempty literals,
  `tuple()` under an expected annotation, and `tuple(value)` from a typed list,
  dictionary (its keys), set, or homogeneous fixed/variadic tuple. These immutable
  sequences use owned Rust `Vec<T>` storage; mutation methods and indexed writes
  remain rejected. Length, iteration, membership, negative/dynamic indexing,
  clamped step-free slices, JSON serialization and compatible tuple comparisons
  are supported. Fixed/variadic tuple conversion evaluates its input once and
  preserves the source. Tuple fields retain the established value semantics for
  collections and shared-handle semantics for resources. Recursive tuple keys
  exclude floats, JSON, records, resources and mutable collections.
  Record collection fields and constant-index fixed tuple fields rooted in locals are borrowed for indexed reads,
  length and membership, including nested paths, while returned values remain
  owned. A 40,000-element fixture verifies linear reads under a 128 MiB process
  limit without cloning the entire record field on each lookup. A 1 MiB tuple-held
  byte buffer also supports a full indexed scan without copying the buffer per byte.
  Nested paths preserve evaluation order; assigned and returned values remain owned.
  Two-argument scalar `min(a, b)`/`max(a, b)` support integers,
  finite floats, strings and bools of matching types. One-argument `min(values)`/
  `max(values)` accept typed lists and homogeneous fixed or variadic tuples of
  those scalar types. They evaluate the collection once, preserve the first
  equal item (including the sign of zero), and raise a recoverable error for an
  empty collection. Named list and variadic-tuple paths are borrowed; only the
  selected scalar is copied. Fixed tuples are adapted into an owned sequence
  before selection. Other iterables, `key` and `default` remain unsupported.
- `bytes.fromhex(text)` and `data.hex()` support binary fixtures. Decoding permits
  ASCII whitespace between complete bytes, rejects invalid/incomplete pairs,
  and encoding returns lowercase hexadecimal. `separator.join(chunks)` accepts
  a bytes separator and `list[bytes]`, preserving arbitrary binary data; an empty
  list produces empty bytes. This permits assembling bounded HTTP reads before
  UTF-8 decoding, including code points split across chunks.
- A string may be tested with `in`/`not in` against a `Json` object (keys), array
  (string elements), or string (substring); scalar containers raise an error.
- `json_equal(a, b)` compares nested JSON structurally. Booleans stay distinct
  from numbers; equivalent integer/float values compare equal without rounding
  large integers to floats. Prefer this explicit function for semantic JSON
  comparison; raw `Json == Json` and membership in `list[Json]` still use backend value equality and can differ
  for numeric spellings or bool/number pairs. `pretty()`/`json_dumps()` accept
  heterogeneous JSON-compatible collection literals directly.
- `json_scalar_compare(a, b)` returns `-1`, `0` or `1` for two compatible
  scalars: null/null, bool/bool, string/string, or number/number. Strings compare
  lexicographically by Unicode scalar values. Numeric comparisons preserve exact
  signed-i64 versus finite-binary64 order, including values above 2^53; they do
  not first round both operands to floats. Containers and incompatible kinds
  raise recoverable errors. Signed zeros compare equal.
- `json_number_add(a, b)` accepts JSON numbers only. Two integers produce a
  checked signed-i64 integer; either float promotes the operation to binary64.
  Integer overflow and nonfinite floating results are recoverable errors.
  Mixed addition has ordinary float rounding and is not exact decimal arithmetic.
  These explicit JSON operations do not change the static subset's requirement
  for explicit numeric conversions in mixed-type Python operators.
- `json_keys(object)` returns sorted string keys, giving object traversal a
  deterministic order across runtimes; non-objects raise an error.
- `path_resolve(path)` returns an absolute canonical UTF-8 path. The path must
  exist, and symlinks are resolved. It is not an atomic filesystem permission
  check; applications performing sensitive concurrent mutations need stronger
  filesystem primitives.
- `sys.exit(integer)` or `process_exit(integer)` terminates with a POSIX-style
  eight-bit status. It is not intercepted by `except Exception`. Rust flushes
  stdout/stderr first. Other `sys` APIs are outside this profile.
- `limit_address_space(maximum_bytes)` lowers the current Unix process's soft
  `RLIMIT_AS` and returns the actual bound. It accepts 32 MiB through 16 GiB,
  preserves the hard limit and never raises an inherited lower soft limit.
  Invalid values and system-call failures are recoverable errors; non-Unix
  platforms report an unsupported operation. This is a process-wide virtual
  address-space bound, not a per-container allocation budget or an RSS setting.
  An allocation failure may terminate native execution, so applications should
  also bound their working batches and retain recoverable on-disk state.
- `import hmac; hmac.compare_digest(left_bytes, right_bytes)` and
  `constant_time_equal(left_bytes, right_bytes)` share the byte-comparison adapter.
  Other HMAC operations and the standard function's string overload are not yet
  part of this profile. `random_token()` supplies 32 random bytes as 64 hex digits.


## Typed dataclass records

Use `from dataclasses import dataclass` and a plain `@dataclass` declaration:

```python
@dataclass
class Frame:
    opcode: int
    payload: bytes = b""
    finished: bool = True
```

`Frame(1, payload=b"hello")` compiles to a Rust struct literal with named fields.
The emitted struct derives `Clone` and retains readable field names. Field types
may include supported scalars, collections, resources, enums and previously
declared records. Required fields precede fields with defaults; defaults must be
scalar literals (`str`, `bytes`, `bool`, signed `int` or finite `float`). Constructor
arguments may be positional or keywords; expressions evaluate once in their
supplied order. Missing, duplicate, unknown and mistyped arguments are diagnosed.

Read fields with `frame.payload`; update a named local with
`frame.payload = frame.payload + chunk`. For nested fields or a record stored in
a collection, load a local, update it and assign it back explicitly. Rust records
follow the subset's owned-value contract: copying a record copies its ordinary
fields, and a callee returns its updated record. CPython's mutable object identity
and aliasing are not reproduced. Resource fields still clone the shared handle,
so closing one alias closes that resource for the other aliases.

Records may refer to their own type through a list, dictionary value or homogeneous
variadic tuple. For example:

```python
@dataclass
class Node:
    terminal: bool
    children: dict[str, "Node"]
```

This emits a regular Rust struct containing `IndexMap<String, Node>`. The collection
provides storage indirection, so an additional wrapper or application-specific Rust
module is unnecessary. Nested combinations such as `tuple[int, list["Node"]]`
also work. Direct self fields and fixed tuples containing an inline self field
are rejected with a diagnostic before Cargo runs. Record keys and set elements
remain unsupported.

Quoted annotations can name supported types in fields, function signatures and
local annotations. Project compilation resolves imported aliases inside these
annotations while preserving ordinary string values. Parsing never evaluates an
annotation as Python code. Self references are supported; references to other
records still require those records to have been declared. Mutually recursive
declarations and general forward type resolution are not implemented.

These are finite owned trees. Native assignment and function arguments clone
their ordinary contents; self-referential types do not add Python object identity,
shared mutable graphs or reference cycles. Load a child, return its changed value,
and write it back into the parent. The
[autocomplete trie](../examples/corpus/055_autocomplete/trie.py) demonstrates this
pattern while keeping its Python reference behavior consistent. Deep cloning and
recursive calls cost memory and stack space; applications must bound their trees.

The subset does not implement methods, inheritance, decorator arguments, mutable
defaults, `field`/`default_factory`, `__post_init__`, arbitrary forward types,
reflection, automatic JSON serialization or record equality/ordering/membership.
Compare fields explicitly; dictionary-key membership is supported when values are
records. Names must satisfy the compiler's identifier restrictions, including Rust
reserved words. Project imports support record and decorator aliases, with local
`dataclasses.py`/`.rs`/package modules taking precedence over the standard fallback.

`float(value)` accepts an `int`, `float` or decimal `str`. Integer conversion uses
the same signed-i64-to-f64 conversion as a float annotation. String inputs contain
at most 4096 ASCII bytes, including optional surrounding ASCII whitespace. Decimal
spellings accept a leading sign, a decimal point, an `e`/`E` exponent and single
underscores between digits, matching Python within this bounded grammar. Results
round to binary64; underflow may produce a signed zero. Invalid spellings,
non-ASCII text, NaN/infinity names and overflow to a nonfinite result are recoverable
runtime errors. Bool/bytes conversion, hexadecimal float strings and Unicode
digits are outside this spelling. Mixed numeric arithmetic still requires explicit
conversion. The Python reference uses the built-in `float`; callers must stay
within these finite/size/ASCII bounds when comparing engines.

## Bounded binary codecs

The following `py2rust.stdlib` functions are available in both runtimes:

| Function | Contract |
| --- | --- |
| `base64_encode(data: bytes) -> str` | Standard padded ASCII base64; at most 1 MiB of input |
| `base64_decode(text: str) -> bytes` | Canonical padded base64 only, including canonical padding bits; no whitespace; at most 1,398,104 encoded bytes and 1 MiB decoded bytes |
| `crc32(data, value=0) -> int` | IEEE CRC-32 over bytes or bytearray; optional previous checksum for incremental input; unsigned 32-bit result |
| `sha1_digest(data: bytes) -> bytes` | Twenty raw SHA-1 bytes for legacy protocol handshakes; input at most 1 MiB |
| `bytes_xor(data: bytes, key: bytes) -> bytes` | Repeat a 1–4096-byte key across at most 1 MiB of data; empty data is valid |

Bounds and invalid encodings raise recoverable errors. The WebSocket room server
uses these general primitives; HTTP upgrades, frame parsing, fragmentation,
room state and flow control remain in transpiled application Python.

`crc32` also accepts ordinary `zlib.crc32(data[, value])` and
`binascii.crc32(data[, value])` calls. Use one or two positional arguments, with
bytes or bytearray data and an optional signed-i64 seed. The seed defaults to zero
and is masked to its low 32 bits, matching Python's incremental checksum behavior.
The result is an integer from 0 through 4,294,967,295. Both arguments evaluate once
in source order; buffers retain the subset's owned-value semantics. This primitive
has no additional codec-size limit or external Rust dependency. Other operations
from these modules, general buffer objects and keyword arguments are unsupported.
Local project modules named `zlib` or `binascii` still take precedence over the
standard-library fallback. Regression checks cover standard vectors, signed seed
boundaries, 512 independent seeded slices, all splits of a message, a 16 MiB
incremental checksum, and complete project imports.

## Foreground native process pipelines

```python
from py2rust.stdlib import process_pipeline

result: tuple[list[int], bytes, list[bytes]] = process_pipeline(
    [["/usr/bin/printf", "%s\\n", "hello"], ["/usr/bin/tr", "a-z", "A-Z"]],
    [{"LANG": "C"}, {"LANG": "C"}], "/tmp", b"", 3000, 1048576
)
```

`result[0]` contains each stage's exit code (negative signal number for a signal
exit); `result[1]` is final stdout and `result[2]` contains separate stderr bytes
for every stage. Stages run concurrently over native kernel pipes, with no shell
interpretation. Executables must be absolute; `cwd` must be an existing absolute
directory. Each environment is a complete replacement. Parsing, command lookup,
environment merging and pipeline status policy belong in Python application code.

The contract permits 1–8 stages, 1–128 arguments per stage and 64 KiB of UTF-8
argument bytes including terminators per stage. Environments permit up to 256
ASCII identifier keys of 1–128 characters, no NUL in values, and 64 KiB total
`name=value` bytes including terminators per stage. Cwd is at most 4096 UTF-8
bytes. Input is at most 16 MiB. The combined final stdout and all stderr limit is
0–16 MiB; timeout is 1–60000 ms and covers spawning, transfer and waiting.
Nonzero stage exits are results, and all stages are awaited until completion or
the deadline. Validation, spawn, I/O, timeout and output-limit failures raise
recoverable exceptions. Partial captures are discarded on errors.

This Linux foreground API requires the main thread and default SIGCHLD handling.
It temporarily captures SIGINT and SIGTERM, cancels with a recoverable error,
kills owned process groups and reaps direct children before restoring handlers.
Each stage starts in its own process group. `waitid(WNOWAIT)` retains unreaped
leaders until group cleanup, avoiding PID reuse during cleanup. Leftover group
members are killed when all leaders exit, including descendants holding pipes
open. This also happens on failure; direct children are reaped.

It is not a sandbox or a job-control shell: programs can deliberately escape
groups, and privileged children or an uncatchable signal to the parent are outside
this cleanup guarantee. Signals and process-wide handler changes by unrelated
threads must not race this call. Kernel scheduling/uninterruptible I/O can delay
cleanup beyond the nominal deadline. Python reference execution of this API
requires Python 3.11+ (`Popen(process_group=0)`); native execution needs no Python.
The implementation uses [Python process groups](https://docs.python.org/3.13/library/subprocess.html),
[Rust CommandExt](https://doc.rust-lang.org/std/os/unix/process/trait.CommandExt.html),
and Linux [waitid/WNOWAIT](https://man7.org/linux/man-pages/man2/waitpid.2.html).

[Application 076](../examples/corpus/076_command_shell/main.py) supplies the
readable Python lexer, planning, command lookup, error/status policy and binary
capture publication over this shared primitive. Regression tests include native
child fixtures, transfers beyond pipe capacity, exact/over bounds, early-reader
SIGPIPE, interrupts, main-thread/SIGCHLD rejection, repeated calls without leaked
file descriptors or unreaped direct children, and signal-handler restoration.

## Native Python statement parsing

`python_statement_tree(source: str) -> Json` parses source without importing or
executing it. The native implementation uses the MIT-licensed Ruff 0.9.10 parser,
pinned to revision `0dfa810e9aad9a465596768b0211c31dd41d3e73` for Rust 1.83.
No Python interpreter is embedded or launched. The Python reference uses CPython
3.13's `ast` with the Python 3.12 grammar and Unicode 15.1 tables. This API's
reference execution specifically requires those Unicode tables.

The result is `{"version": 1, "nodes": [...]}`: statements in preorder, each with
`kind`, `parent` (an earlier array index, or -1 for the module), `block`, `line`,
`column`, `end_line`, `end_column`, `name`, `decorators`, `names`, `module`,
`level` and `string`. Lines are one-based; columns count UTF-8 bytes. Definition
locations start at `def`, `async def` or `class`, excluding decorators.
Decorator records contain the four location fields and the expression's source
`text`, excluding `@`. Names are normalized using Python's NFKC rules. Import
aliases and global/nonlocal names are `{"name": ..., "asname": ...}` records;
`asname` is empty when absent. ImportFrom supplies `module` and relative `level`.
`string` contains the decoded value only for standalone literal-string expression
statements; otherwise it is null. Application code decides which are docstrings.

Blocks are `body`, `orelse`, `finalbody`, `handlers.N` or `cases.N` (zero-based).
Handler/case wrapper nodes are omitted. `elif` becomes nested `If` statements,
matching CPython's representation. All ordinary statement kinds are projected,
including async definitions/loops/context managers, `TryStar`, `Match` and 3.12
`TypeAlias`. Expressions are parsed and checked but are not exposed as an AST.
This is a statement projection for analysis tools, not general Python reflection
or an expansion of the executable transpilation subset.

Input is at most 128 KiB of UTF-8, without NUL. One initial UTF-8 BOM is accepted;
CRLF and CR become LF before positions are assigned. Limits are 16,384 significant
tokens (excluding comments, nonlogical newlines and EOF), 128 nested brackets,
64 indent levels, 4,096 statements, 64 statement levels and 128 expression levels.
The native parser and its recursive AST destruction run on a dedicated 64 MiB
stack, joined before return. Bounds raise recoverable errors. Syntax diagnostics
include source positions; exact error wording/positions can differ by parser.

Lone-surrogate Unicode escapes in nonraw strings, including f-string literals and
embedded string expressions, are rejected rather than replaced. Raw strings and
bytes retain their corresponding literal semantics. Named Unicode escapes must
identify one character; Unicode named sequences are outside this profile.
Unicode 15.1 names and identifier tables are pinned so dependency updates cannot
silently admit newer names or identifiers. Duplicate parameters and explicit call
keywords are rejected. As with an AST parser, successful parsing does not prove
that the source would execute or pass all Python compiler context checks.

[Application 077](../examples/corpus/077_source_outline/main.py) implements scopes,
docstring cleanup, import linking, source rendering and atomic publication in five
transpiled Python modules. The shared runtime only supplies the bounded parser
projection. Tests compare independently against CPython ASTs and include source
that would write files or raise if executed.

## Named timezones from explicit TZif data

`timezone_project(data: bytes, instant: DateTime) -> Json` and
`timezone_local(data: bytes, local: str) -> Json` use caller-supplied TZif bytes.
The Python reference uses `zoneinfo.ZoneInfo.from_file`; native Rust uses the
locked `tz-rs` 0.6.14 library, compatible with the Rust 1.83 baseline. Neither
operation searches a timezone directory, uses the process `TZ` setting, starts
another program, nor embeds a Python interpreter. Callers load and retain the
rules they want, so both engines can use identical data.

Projection returns `utc`, `local`, `offset_seconds`, `abbreviation` and `is_dst`.
`utc` has six fractional digits and a `+00:00` suffix; `local` has six fractional
digits without a suffix. Integral second offsets preserve historical rules such
as Amsterdam's former offset of 1,172 seconds. UTC and projected local dates must
both lie in Gregorian years 0001–9999. There is no leap-second representation.

Local input has the exact shape `YYYY-MM-DDTHH:MM:SS[.ffffff]`, with zero to six
fractional digits, uppercase `T`, and no offset. Resolution returns:

| Field | Meaning |
| --- | --- |
| `kind` | `unique`, `fold` (repeated time), or `gap` (skipped time) |
| `local` | The requested local timestamp, normalized to six fractional digits |
| `candidates` | One or two exact projections, ordered by increasing UTC; empty for a gap |
| `projections` | For a gap, two projections obtained using the offsets on its two sides, ordered by UTC; otherwise empty |

If either fold interpretation overflows the supported UTC years, resolution fails;
it does not discard that interpretation and relabel a repeated time as unique.

A gap's projections preserve the requested position within the skipped interval:
New York's skipped `02:30` projects to `01:30` or `03:30`, and Lord Howe's skipped
`02:15` projects to `01:45` or `02:45`. Selection/rejection policies belong to the
Python application. More than two exact candidates and gaps without exactly two
projections are rejected. POSIX footer rules extend future transitions; without
a footer, the final recorded type continues. Before the first transition, the
first standard type applies (or type zero if none exists), matching ZoneInfo.

The bounded data profile accepts TZif versions 1–3, 44 bytes–1 MiB, at most
20,000 strictly increasing transitions, 1–256 local types and 1–4,096 designation
table bytes. Offsets must have magnitude below 86,400 seconds. Designations are
3–7 ASCII letters, digits, `+` or `-`, matching the native library's profile.
Transition indices, DST/standard/UTC indicators and block boundaries are checked;
UTC indicators require corresponding standard indicators. Leap-second tables
(including `right/` data), TZif v4, and larger designation profiles are unsupported.
Underlying parser errors are recoverable; exact diagnostic wording can differ.
Ordinary `zoneinfo` imports and general `datetime` timezone constructors are still
outside the transpilation subset.

The timezone tests compare both engines against independent ZoneInfo round trips,
including all 497 installed named zones from the tested 2026c database, precise
DST boundaries, half-hour and two-hour transitions, date-line changes, historical
second offsets, future footer rules, synthetic files and malformed inputs.
[Application 086](../examples/corpus/086_timezone_converter/main.py) exercises
these primitives in a complete six-module appointment converter, including exact
TZif export and replay without a system timezone database.

### Structured single-command outcomes

`process_run(arguments: list[str], environment: dict[str, str], cwd: str,
input: bytes, timeout_ms: int, max_output: int) -> tuple[Json, bytes, bytes]`
runs one direct-argv command using the same foreground process-group engine and
bounds as `process_pipeline`. Environment values replace the inherited environment.
The result contains metadata, stdout bytes and stderr bytes.

Metadata has exactly `kind`, `returncode` and `interrupt_signal`. `kind` is
`exited`, `timeout`, `output_limit`, `spawn_error` or `interrupted`. Only `exited`
has a non-null return code, including negative signal exits. `interrupt_signal`
is zero except when SIGINT/SIGTERM cancels the parent call. Validation, platform,
thread/disposition and unexpected I/O errors still raise. The pipeline API retains
its existing exception behavior.

Timeout, output-limit and interrupt outcomes preserve the byte prefixes already
read before cancellation. Total capture never exceeds `max_output`; an output
limit is reported only after observing at least one excess byte, retaining the
full allowed prefix. For simultaneous stdout/stderr, their division of the shared
budget depends on readiness order. No ordering between the two streams is implied.
Unread bytes pending at a deadline are not promised. A spawn failure returns empty
captures. Owned process groups are terminated and direct children reaped before
returning any execution outcome; the preceding foreground ownership limitations
apply. Callers can report a failed command's partial output and continue with the
next command without launching a shell or a Python interpreter.

### Nonblocking process pools

`ProcessPool` owns independent Linux child process groups in a resource scope.
The main thread may own one pool or one foreground `process_pipeline`/`process_run`
operation at a time; overlapping ownership raises instead of replacing signal
handlers. SIGCHLD must retain its default disposition. This extends the same
argv/environment validation and process-group cleanup used by foreground commands.

| API | Behavior |
| --- | --- |
| `process_pool() -> ProcessPool` | Acquire scoped signal/process ownership |
| `process_spawn(pool, argv: list[str], environment: dict[str,str], cwd: str) -> int` | Start a direct child with a complete replacement environment and `/dev/null` stdin; return a pool-local ID |
| `process_poll(pool, id: int, limit: int) -> tuple[Json,bytes,bytes]` | Observe exit and read at most `limit` bytes from each pipe once, without waiting; return metadata, stdout and stderr |
| `process_signal(pool, id: int, number: int)` | Send SIGTERM (`15`) or SIGKILL (`9`) to the owned group |
| `process_pool_signal(pool) -> int` | Return the first SIGINT/SIGTERM received during this scope, or zero |
| `process_pool_close(pool)` | Kill all remaining owned groups, reap direct children, close pipes and restore handlers; repeated close is harmless |

A pool holds at most 32 children, including exited children whose output has not
been drained. Read limits are 1–65,536 bytes **per stream per call**. There is no
retained output buffer inside the pool, retry policy, deadline, logging policy, or
sleep. Applications choose polling frequency and retain or discard received data.
Poll both streams and every live child to avoid blocking producers or starving
other services. Binary bytes are preserved, and no cross-stream ordering is
promised. Spawn arguments use the existing 128-argument/64 KiB bound and absolute
executable/cwd paths; environment limits remain 256 entries/64 KiB.

Metadata contains exactly `pid`, `exited`, `returncode`, and `complete`.
`returncode` is null while the leader is running and is negative for a signal exit.
On observing leader exit, the pool kills remaining group members and continues
bounded pipe draining. `complete` becomes true only after leader exit and EOF on
both pipes. That call reaps/removes the child; further operations on its ID fail.
IDs increase within a pool and are never reused there. Empty reads alone do not
mean completion: the child may be running or no bytes may currently be ready.

Signals are sticky for the scope. After parent interruption, spawn is rejected,
while polling, group termination and close remain available so the application
can perform a bounded shutdown. Closing a shared alias closes the resource for
all aliases. A `with` guard closes it on return, errors, break and continue.
All public pool operations require the main thread. Deliberately escaped process
groups, external child reaping/handler replacement, and uncatchable supervisor
termination are outside this cooperative foreground ownership contract.

[Application 093](../examples/corpus/093_process_supervisor/main.py) keeps service
configuration, backoff, attempt limits, bounded logs and status publication in
Python while compiling the complete application to standalone Rust.


### Exact rational arithmetic

`Rational` is an immutable service-library value imported from `py2rust.stdlib`.
It supports function arguments, returns, dataclass fields and typed collections.
Use the following explicit operations; the profile does not promise arbitrary
`fractions.Fraction` constructors, operators or methods.

| Function | Result | Contract |
| --- | --- | --- |
| `rational_new(numerator: str, denominator: str)` | `Rational` | Signed ASCII integers; reduce and normalize denominator positive; reject zero denominator. |
| `rational_decimal(text: str)` | `Rational` | Exact signed ASCII decimal with digits on both sides of an optional point; no exponent, whitespace or underscore. |
| `rational_add/sub/mul/div(left: Rational, right: Rational)` | `Rational` | Exact reduced result; division rejects zero. |
| `rational_compare(left: Rational, right: Rational)` | `int` | Exact -1, 0 or 1. |
| `rational_numerator(value: Rational)` | `str` | Canonical signed integer numerator. |
| `rational_denominator(value: Rational)` | `str` | Canonical positive denominator; zero is represented as 0/1. |
| `rational_fixed(value: Rational, places: int)` | `str` | Round once, ties to even, exactly 0–18 decimal places; rounded zero has no minus sign. |

Each constructor input is bounded to 4,096 ASCII characters. Reduced numerators
and denominators are each bounded to 65,536 bits after every arithmetic operation;
intermediate products can be larger before reduction. Formatting supports the
whole allowed result range independently of CPython's integer-string digit limit.
The Python reference uses `Fraction`; native code uses a shared Rust `num-bigint`
implementation. There is no Python dependency at runtime. Native/Python tests
cover 602 independent operand pairs, decimal half-even ties, both component-size
boundaries, exact cancellation, invalid inputs and recovery after errors.


### Complete BMP image processing project

[Application 113](../examples/corpus/113_bmp_thumbnails/main.py) exercises bounded
binary parsing, signed header fields, bytearray pixel mutation, explicit fill
loops, typed records across six modules, strict JSON, file snapshots and atomic
publication. It reads four uncompressed 24-bit BMP header layouts and writes
thumbnails, contact sheets and portable rebuild/replay bundles. Every application
module is Python source transpiled to native Rust. Byte-string multiplication
is outside this subset; this example uses readable explicit buffer-fill loops.
The application and packaged native acceptance require no compiler/runtime changes.


### Complete P6 image-filter project

[Application 114](../examples/corpus/114_ppm_filters/main.py) transpiles seven Python
modules for P6 header/raster parsing, 8/16-bit sample codecs, typed image records,
ordered filters, full-resolution RGB histograms, CSV/SVG output and atomic replay
bundles. Exact pixel/histogram checks exercise every 16-bit sample value. It uses
explicit loops for accumulation and reads histogram arrays once before CSV
iteration, respecting owned collection semantics. All application logic remains
Python source compiled to native Rust; no shared compiler/runtime extension is needed.


### Complete sprite-atlas project

[Application 115](../examples/corpus/115_sprite_atlas/main.py) compiles seven Python
modules for PPM sprite loading, first-fit shelf packing, image composition and
actual atlas extraction. Its sort key returns an integer/integer/string tuple
from nested records. Explicit shelf replacement respects owned-value semantics.
Tests compare every sprite's extracted RGB samples with the original, including
16-bit input, maximum atlas size, padding and edited layouts. The packaged native
application uses the existing compiler/runtime without Python or custom adapters.


### Complete SVG dashboard project

[Application 116](../examples/corpus/116_svg_dashboard/main.py) transpiles seven
Python modules for strict JSON datasets, bounded binary64 scales, exact decimal
tick spelling, bar/line geometry, escaped HTML/SVG and portable replay bundles.
Typed scale records cross module boundaries; explicit loops generate decimal
zeros without string repetition. SVG element attributes use readable dictionaries.
The independent checker enumerates Decimal step candidates and checks geometry,
markup structure, edited-data replay and atomic output publication. All seven
modules compile from the packaged transpiler and run without Python. This example
uses the existing compiler/runtime; it adds no application-specific adapters.


### Terminal output and whole-project cleanup

`terminal_info() -> Json`, `terminal_write(text: str) -> None` and
`terminal_cells(text: str) -> list[tuple[str, int]]` are shared service APIs.
`terminal_info` queries stdout itself: `isatty`, `ansi`, `columns` and `rows`.
Unavailable or zero dimensions use 80×24; `COLUMNS` and `LINES` are ignored.
ANSI capability requires a TTY and a `TERM` value other than empty, `dumb` or
`unknown`. Applications choose their own escape sequences and fallback layout.
`terminal_write` encodes UTF-8, writes without an added newline, and flushes.
Its limit is 1 MiB per call. Write/flush failures are catchable, including
incomplete writes on nonblocking pipes; bytes already written cannot be undone.

`terminal_cells` accepts at most 64 KiB of UTF-8. It rejects C0/C1 controls,
surrogates and bidi formatting characters U+061C, U+200E/F, U+2028/9,
U+202A–202E and U+2066–2069. It returns intact extended grapheme clusters with
Unicode 16 cell widths; ambiguous characters are narrow. A standalone zero-width
cluster is prefixed with a dotted circle and assigned one cell. This is an
explicit layout policy, not a promise that every terminal/font uses those widths.

The Python reference uses `uniseg==0.9.1` property tables and a linear UAX29
segmenter, with `wcwidth==0.2.14` explicitly selecting Unicode 16. Native Rust uses
`unicode-segmentation==1.12.0` and embedded width tables generated by
`tools/generate_terminal_tables.py`, followed by `rustfmt` on the generated
source. These reference dependencies belong to the
`service-reference` installation extra and are unnecessary at native runtime.
The table generator preserves the upstream license. Regression fixtures include
Unicode's GraphemeBreakTest 16.0.0; segmentation, table boundaries, every accepted
Unicode scalar's width, long combining sequences, real PTYs, resize queries,
output flushes, disconnected pipes and nonblocking partial writes are checked.

[Application 117](../examples/corpus/117_terminal_dashboard/main.py) compiles seven
Python modules for task snapshot validation, cell-aware layout, live refresh,
signal cleanup and portable replay bundles. Its nested `finally` blocks restore
the cursor/alternate screen and release signal ownership after ordinary return
or recoverable errors. As with all cleanup, process termination through SIGKILL,
`process_exit` or an unrecoverable native panic cannot run a Python `finally`.


### Bounded DEFLATE and ZIP filenames

`deflate_decompress(data: bytes, maximum: int) -> bytes` decodes exactly one raw
DEFLATE stream. Input is limited to 32 MiB; the output allowance is 0–64 MiB.
The allowance is enforced while decoding, before accepting expanded output.
Invalid/truncated streams, trailing bytes, concatenated streams and exceeded
budgets raise recoverable errors. This API expects raw DEFLATE, without a zlib or
gzip wrapper. An empty payload still requires a complete encoded empty stream.
Python uses its standard `zlib`; Rust uses pinned `flate2=1.0.35` with its pure
Rust backend. Neither the native decoder nor native applications need Python.

Literal `bytes.decode("cp437")` and `bytearray.decode("cp437")` are also supported,
including the `437` and `ibm437` aliases, with case-insensitive literal names.
The native upper-half mapping is embedded and all 256 input bytes are tested
against Python's codec. As with the existing byte codecs, dynamic encoding names
and non-strict error handlers remain outside the supported subset.

[Application 118](../examples/corpus/118_zip_validator/main.py) keeps ZIP record
parsing, path classification, expansion accounting, CRC checks and report policy
in seven Python modules. Only the reusable decoder and byte codec are native
runtime additions. Stored/deflated ZIP32 entries and both descriptor forms are
covered, including a CRC equal to the optional descriptor marker. The application
never extracts entries. Tests use Python's ZIP writer/reader, crafted damaged
records, whole-project replay and a 256 MiB expansion fixture constrained to a
128-byte allowance inside a 128 MiB process.

The `test` extra now includes the pinned terminal reference dependencies, and
Tox installs `service-reference`, so collecting the expanded service tests does
not rely on those dependencies being present accidentally.


### Streaming gzip resources

The shared service library provides these typed resources and functions:

| API | Result and behavior |
| --- | --- |
| `gzip_create(path, level, compressed_limit, expanded_limit)` | `GzipWriter`; exclusively create a new regular file |
| `gzip_write(writer, data)` | Write at most 1 MiB of `bytes` per call; empty input is allowed |
| `gzip_finish(writer)` | `(compressed_size, expanded_size)` after writing the trailer, syncing and closing |
| `gzip_writer_close(writer)` | Abort and close; does not certify a complete archive |
| `gzip_open(path, compressed_limit, expanded_limit)` | `GzipReader`; open a regular file and validate its header |
| `gzip_read(reader, count)` | Up to `count` bytes, with `count` in 1–1 MiB; fill the request unless validated EOF is reached |
| `gzip_reader_close(reader)` | Close without draining or validating the rest of the stream |

Limits are nonnegative signed 64-bit integers; a writer's compressed allowance
must accommodate its 10-byte header. Both compressed and expanded budgets are
enforced during I/O, including the final compressed trailer. Streams use bounded
buffers rather than allocating the advertised or allowed total size. Files are
opened without following a final symlink; parent directories must be cooperative.

`GzipReader` and `GzipWriter` support `with`. Aliases share the underlying resource,
so closing or finishing one closes every alias. A failed streaming I/O operation
or finish also closes it. Invalid per-call chunk sizes are rejected before I/O.
Close is idempotent; read, write, finish or context entry after close raises a
recoverable error. Exiting a writer's scope only aborts it: call `gzip_finish`
explicitly inside the scope, and use its successful return before publishing the
file. This avoids treating ignored destructor errors as successful completion.

The reader accepts **one gzip member** and rejects trailing data, including zero
padding and another member. This is an explicit profile; the
[gzip format permits a series of members](https://www.rfc-editor.org/info/rfc1952/).
It checks reserved flags, optional header CRC, data CRC and ISIZE. Optional extra
fields are bounded by their 16-bit length, and names/comments are limited to
65,535 bytes each. Empty reads certify that the member and physical EOF were
validated. Bytes returned before EOF are provisional: closing early does not
certify integrity. No append, seeking, embedded-name extraction or multi-member
decoding API is provided.

Writers support levels 0–9, emit a zero timestamp, OS=255 and no optional header
fields. Python uses incremental `zlib`; native Rust uses the existing pinned
`flate2` dependency. Compressed blocks and sizes may differ between engines.
Interoperability checks compare decoded bytes, while each stored archive records
the digest of its actual compressed representation.

[Application 119](../examples/corpus/119_gzip_archiver/main.py) compiles seven
Python modules for rotated-log inventory, incremental hashing, bounded gzip
creation, index validation and crash recovery. Its application policy remains
Python; only reusable resource operations are supplied by the Rust runtime.
Tests include independent gzip decoders, all compression levels, corrupt headers
and trailers, resource aliases, killed processes at five transaction boundaries,
mixed-engine recovery, and a 1 GiB log archived under a 128 MiB address-space limit.


## Default finite-float text

`str(value)` and `print(value)` for a finite float use shortest round-trip decimal
digits with Python-style notation. Integral values retain `.0`, including `-0.0`;
scientific notation is used below decimal exponent -4 or at exponent 16 and above.
Exponents include a sign and at least two digits. This is distinct from
`json_canonical`'s fixed 17-significant-digit representation. NaN/infinity and
arbitrary formatting specifications remain outside this contract.
