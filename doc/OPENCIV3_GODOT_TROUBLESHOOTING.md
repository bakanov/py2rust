# OpenCiv3 graphical migration: troubleshooting runbook

Use this guide with the [architecture plan](OPENCIV3_GODOT_MIGRATION.md) and
[file inventory](OPENCIV3_GODOT_FILE_PLAN.md). It explains how to diagnose
failures without turning the migration into a sequence of application-specific
compiler hacks.

## 1. Triage protocol

For every failure, record this information in the module inventory before
changing code:

```text
entry point and exact command
Python file and source line
logical module and native manifest entry
failure stage and complete error text
smallest failing input or command sequence
Python-reference result
Rust result, if any
suspected ownership or API boundary
next unblocking action and verification command
```

Classify the failure before fixing it:

1. **Discovery:** project resolver cannot find a Python or native module.
2. **Frontend typing:** Mypy types are incomplete or inconsistent.
3. **Lowering:** the compiler-owned IR rejects a supported-looking construct.
4. **Emission:** generated Rust does not represent the intended operation.
5. **Cargo:** Rust types, lifetimes, ownership, or dependencies are wrong.
6. **Runtime semantics:** Rust runs but produces a different state or error.
7. **Native adapter:** a handwritten codec, filesystem, or Godot adapter fails.
8. **Godot integration:** native library loading, scenes, nodes, or rendering fails.
9. **Performance:** correct behavior is too slow or uses too much memory.

Never treat these as equivalent milestones. A file that lowers is not necessarily
valid Rust; a file that builds is not necessarily behaviorally correct.

### Standard response

1. Reproduce with the smallest complete program or command script.
2. Run the same input through the Python reference.
3. Inspect generated source only for diagnosis. Do not maintain a fix there.
4. Fix the general compiler rule, the small typed Python source, or the
   handwritten native adapter—whichever owns the behavior.
5. Add or update a focused regression test when the project already covers that
   area.
6. Regenerate, run the focused test, then run the complete scenario again.
7. Record evidence in the inventory. Do not mark a module `accepted` after only a
   successful compile.

## 2. Baseline commands

From the py2rust checkout:

```bash
# Generator and its own tests
PYTHONPATH=. python -m pytest -q tests/test_godot_generator.py
PYTHONPATH=. python -m py2rust.godot --check /path/to/OpenCiv3/C7

# Lowering inventory for the current console closure
OPENCIV3_ROOT=/path/to/OpenCiv3/C7 \
  OPENCIV3_ENTRY=civ3_console/native_session.py \
  python tools/audit_openciv3_lowering.py

# Native GDExtension crate
cargo test --locked --manifest-path /path/to/OpenCiv3/C7/native/Cargo.toml
cargo fmt --check --manifest-path /path/to/OpenCiv3/C7/native/Cargo.toml

# Changed Python code
ruff check py2rust tests
black --check py2rust tests
git diff --check
```

Do not run pytest suites concurrently or run multiple Cargo-producing test suites
against the same target directory. Use focused tests during diagnosis and the
appropriate full suite before committing shared compiler changes.

## 3. Discovery and native module resolution

### `cannot resolve local module py4godot` or another external package

**Likely cause:** the resolver encountered the Python import before consulting
`native-modules.toml`.

**Response:**

- Ensure the manifest is loaded before import resolution.
- Map the Python module to the consolidated Rust file and internal Rust module.
- Do not add a py4godot compatibility emulation layer.
- If it is a standard-library API rather than a native application module, add a
  bounded runtime contract or replace that small API in typed Python.

**Verify:** discovery prints all reachable modules and shows the native entry;
there is no external package import in the emitted dependency graph.

### `.py` and `.rs` with the same name are ambiguous

**Likely cause:** a native implementation exists without an explicit manifest
selection.

**Response:** add the mapping with `path` and internal `module`; do not weaken the
ambiguity error globally. Python keeps using `.py`; py2rust uses the selected
`.rs`.

### Changes to a native file are not used

**Response:**

- Check the logical module and internal Rust `mod` path, not only the filename.
- Run `python -m py2rust.godot --check ...` to detect generator drift.
- Ensure the generated crate includes the module in `lib.rs`.
- Inspect the actual Cargo manifest used for the build; do not accidentally test a
  cached executable from another project.

### Generated crate cannot find `lib.rs` or native functions

**Response:** preserve `lib.path = "lib.rs"`, `crate-type = ["cdylib", "rlib"]`,
and the ten `pub mod` declarations. Check public native signatures against the
supported boundary types. For complex records, implement the planned checked DTO
ABI instead of exposing generated private record names.

## 4. Frontend typing and lowering failures

### Missing or narrowed types

Examples: `int | None`, mixed numeric tuples, enum properties, optional booleans,
set/list mismatch, and fixed tuples treated as variable lists.

**Response:**

- Preserve the Mypy type in the IR and adapter; do not infer a different type in
  the backend.
- Make mixed numeric intent explicit (`0.0`, `float`, or a finite constant).
- Split a nested `dict.get()` fallback if its default may be `None`.
- Replace an optional-list comparison with length/element checks or teach the
  compiler the general conversion.
- Add a focused typed-frontend test before broadening coercion.

### `IR function defaults currently require literal values`

**Response:** direct named function references are valid callback defaults only
when their signature is known. Use a typed no-op function or a direct function
reference; avoid dynamic decorators and factory-produced callbacks. Ensure the
backend passes the callback with the same owned/borrowed ABI.

### Dataclass/custom `__init__`/`field(init=False)` failures

**Response:**

- Use a plain dataclass where the record model fits.
- Use `__post_init__` for initialization that the generated constructor must call.
- Give internal optional slots defaults and expose non-optional accessors.
- Do not assign through a computed property in transpiled code; use a narrowed
  internal slot or explicit setter.
- For a true custom constructor with arbitrary parameters, implement a general
  constructor-lowering rule rather than adding another record-name exception.

### Rust keywords such as `move`

**Response:** use a consistent escaped Rust identifier while retaining the Python
source map. Renaming the Python local is acceptable when it is small and has no
public API effect.

### Block-scoped `undefined variable`

**Response:** Python and the compiler's block-local rules differ. Initialize the
variable with an explicit type before the branch. Check whether the value should
really escape the block; do not silence the diagnostic with a global.

### Dynamic unions and `type(x).__name__`

**Response:** use `isinstance` branches with an exhaustive typed helper, or add a
general tagged-union representation. Do not use dynamic reflection or unchecked
`Any` casts to suppress the error.

## 5. Cargo ownership and ABI failures

### `&mut` required or mutation disappears

**Likely cause:** a stateful receiver is owned at one call site and cloned at
another. A mutable method on a temporary has no externally visible effect.

**Response:**

- Trace the complete call chain, including helper controllers and callbacks.
- Mark the actual receiver mutable at both signature and call site.
- Evaluate immutable arguments before mutable borrows.
- Return updated state explicitly when using copy-on-write.
- Synchronize only at a real ownership boundary; avoid repeatedly cloning and
  copying controller graphs as a permanent architecture.

**Verify:** after two separate commands, the second observes the first command's
state, not merely the mutated local result.

### `cannot borrow as mutable` or immutable/mutable borrow overlap

**Response:** compute request values and scalar arguments first, then take the
mutable receiver. Do not solve it with a broader clone unless ownership semantics
permit a snapshot.

### Callback moved in a loop or expected `&T` versus `T`

**Response:** use a borrowed callable for repeated invocation and match generated
closure parameters to the source function's borrow decisions. Keep `impl Fn` ABI
consistent across defaults, direct calls, and captured callbacks.

### `&mut collection.clone()` appears in generated Rust

**Response:** this is always suspicious. Mutating record fields and nested
`setdefault` entries need real mutable places. Add a general place-emission rule
for owned fields, `get_mut`, or `entry`, and test that the resulting collection
contains the mutation.

### `get_mut`/nested index errors

**Response:** a shared projection cannot be mutated. Re-resolve the parent as a
mutable place or rebuild the child and assign it back. Preserve stable IDs and
source order; do not accidentally remove an element by structural value after it
was mutated.

## 6. Runtime semantic mismatches

### State exists immediately after a command but disappears later

**Likely cause:** session, helper controller, and AI each hold a different
snapshot. It may also be an early container assignment that stored a snapshot
before construction finished.

**Response:**

- Compare state before and after each command, not only the final output.
- Propagate `GameState`, updated cities/players, and AI results through the full
  call chain.
- Build containers first and assign them once complete.
- Use a single native session owner at the Godot boundary.

### A city does not grow or research does not advance

**Response:** inspect worked tiles, ownership, food stockpile, resident count,
research target, beakers, turns researched, and known technologies separately.
A completed discovery must update the known set and clear/change the target so it
cannot be discovered repeatedly.

### Settlers never found or units never move

**Response:** inspect starting coordinates, movement, fortified state, mission
destination, escort state, path reachability, and whether the mission is retained
on the stored unit. Fix mission/movement propagation before changing AI scoring.

### `unit is ...` or resident identity differs

**Response:** Python identity is not structural record equality. Use stable unit,
city, civilization, and technology IDs. For a genuinely borrowed object identity,
use pointer equality only when both operands are the same live native place. Do
not compare cloned records by address and expect Python identity semantics.

### Duplicate keys, empty groups, or missing dictionary entries

**Response:** look for mutation of a cloned `setdefault` result or an assignment
made before a container was populated. Use `entry`/`get_mut` or finish building
before insertion.

### Integer overflow or non-finite floats

**Response:** preserve intentional signed-64 wrapping with explicit operations.
Use finite ranking sentinels for scores and valid defaults for pathfinding. Do not
replace checked arithmetic globally with wrapping arithmetic.

### Same seed, different map or civilization

**Response:** compare the isolated RNG sequence first, then terrain/noise tables,
lookup borrowing, starting locations, and city placement. A working RNG does not
prove noise or map-generation parity.

## 7. Binary codecs and persistence

### BIQ/SAV version or section errors

**Response:** verify scenario version, endianness, section names, record lengths,
and decompression boundaries. Keep commercial fixtures outside Git. Compare the
resulting typed scenario field by field with Python rather than only checking
that parsing returned data.

### Truncated input or excessive allocation

**Response:** all lengths and dimensions must use checked arithmetic and explicit
budgets before allocation or loop execution. Test zero-length records, nested
runs, trailing bytes, integer overflow, and decompression bombs.

### PCX/FLIC/AMB output is invalid

**Response:** test tiny known fixtures for each chunk independently, then palette,
pixels/audio, and media-node display. Distinguish codec failure from texture/audio
API failure.

### Save cannot be restored or behaves differently after reload

**Response:** compare canonical schema version, complete `GameState`, RNG state,
AI plans, trade sessions, human-turn token, and scenario/world identity. Validate
before replacing the active controller. Use atomic writes and preserve the last
valid save on failure.

### Save compatibility breaks after a model change

**Response:** add a schema migration and old-version fixture. Never depend on
Python `dataclasses.fields`, runtime module lookup, or dynamic imports to define
the persistent format.

## 8. GDExtension loading and Godot scenes

### Library is not found

**Response:**

- Build the correct debug/release `cdylib` for the platform.
- Check the `.gdextension` paths are `res://native/target/...` and that export
  presets include the native library.
- Verify `entry_symbol = "gdext_rust_init"` and exactly one
  `unsafe impl ExtensionLibrary` in `lib.rs`.
- Test from the Godot project root, not from the compiler repository.

### Godot class is missing or cannot be instantiated

**Response:** confirm `#[derive(GodotClass)]`, correct base class, `Base<T>` field,
and `#[godot_api]` registration. Use `INode`, `INode2D`, or `IControl` with the
matching `Base` type. Import generated traits such as `Control` and `IControl`
where required. Inspect errors from the real Godot process, not only `cargo
check`.

### Existing Python and native classes conflict

**Response:** disable the py4godot node before enabling the native replacement.
Use thin GDScript wrappers for autoloads and scene scripts that must remain Godot
resources. Preserve scene node names and signal wiring. Do not register both
implementations simultaneously.

### `project.godot` autoload still starts Python

**Response:** replace each Python autoload with a GDScript adapter that constructs
the registered native class and forwards its public methods. Verify there is no
Python process and no `res://GlobalSingleton.py`/`LogManager.py` left in the
active autoload list.

### Scene method or signal is unavailable

**Response:** expose methods with `#[func]`, use Godot-compatible argument/return
types, and keep snake_case naming consistent with GDScript calls. Connect signals
in the native node or wrapper; do not assume a Rust method automatically becomes
a Godot signal.

### Runtime crashes during process, callbacks, or shutdown

**Response:** keep Godot object access on the main thread unless the selected
Godot crate contract explicitly allows otherwise. Move CPU-only generation to
workers if needed and apply results on the main thread. Clear textures/audio and
release controllers in `exit_tree`; test repeated scene entry/exit for leaks and
use-after-free.

### Headless build works but rendering is wrong

**Response:** separate draw-command errors from GPU/resource errors. Compare the
pure draw batches first, then texture descriptors, viewport coordinates, wrapping,
and font/color resources. Use a real-window smoke for issues headless mode cannot
prove.

### Godot version or Rust compiler incompatibility

**Response:** the initial crate pins Godot `0.2.4` for Rust 1.83 and declares a
Godot 4.2 minimum. Verify it against the actual Godot 4.7 executable. If a newer
binding is required, update Rust and the lockfile as a separate reviewed change;
do not silently float the Godot crate or toolchain.

## 9. Performance and memory regressions

### Native code is dramatically slower than Python

**Response:** profile initialization and gameplay separately. Check repeated
clones of cached constants, lookup tables, worlds, and draw buffers before changing
algorithms. The previous major regression came from cloning cached noise tables;
context-sensitive borrowing fixed it.

### RSS or minor page faults increase after DTO work

**Response:** measure allocation count and snapshot size. Replace full-state JSON
or record snapshots with stable-ID deltas, reused buffers, and shared immutable
rule/world views. Do not serialize each frame.

### Benchmark appears faster but performs less work

**Response:** compare turn, cities/population by owner, technology, units, known
map, contact, and AI plan counts. A speed result is valid only for equivalent
work. Report mean user/system/wall CPU and maximum peak RSS over at least five
alternating runs, plus the exact commit and command script.

### Build artifacts fill the disk

**Response:** keep `target/` outside submitted source where possible, remove only
known generated caches, and preserve generated source and lockfiles. Do not delete
application saves, fixtures, or commercial media during cleanup.

## 10. Verification gates and inventory status

Use these gates for every logical module:

| Status | Required evidence |
| --- | --- |
| `not_started` | Action and dependencies are identified. |
| `in_progress` | Reproduction and current failure are recorded. |
| `blocked` | Exact blocker, attempted fixes, and next unblocking dependency are recorded. |
| `parity` | Focused Python/Rust behavior and complete scenario match. |
| `accepted` | Parity plus required Godot smoke, lifecycle, and performance checks pass. |

For `blocked`, always record an actionable dependency such as "needs native DTO
ABI" rather than "compiler does not work." A blocker is not a reason to patch
unrelated game rules.

Before committing a milestone:

1. `py2rust.godot --check` is clean.
2. Focused compiler and engine tests pass.
3. Native crate tests and `cargo fmt --check` pass.
4. The generated console or graphical scenario runs end to end.
5. The inventory and generated snapshot are updated.
6. `git status` contains no build logs, target directories, or temporary probes.
7. Documentation distinguishes proven behavior from planned and broken behavior.
