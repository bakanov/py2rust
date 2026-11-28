# Plan: transpile OpenCiv3's complete graphical game to Rust

## Purpose and current baseline

This plan extends the working native console work to the complete Godot game. It is
an implementation plan, not a claim that the graphical game already runs.

Verified baseline:

- The reduced engine and the real `ConsoleSession.execute()` command interpreter
  compile and run as native Rust.
- The native console founds Rome, grows it to population 2, discovers Pottery, and
  completes ten turns in about five seconds.
- The current console dependency closure has 113 modules with no lowering
  blockers. The smaller campaign has 104.
- `PythonGame.py` currently fails project discovery at its first `py4godot`
  import. No graphical gameplay milestone has been reached.
- The new `py2rust.godot` generator now emits the ten consolidated native files,
  a compilable GDExtension shell, native mappings, and initial bounded helpers.
  Its Rust tests pass, but Godot scenes are not yet connected to these nodes.
- Python and native gameplay are not yet identical. Autonomous expansion and
  some production/economic behavior still differ.

The exact action for every additional file is in
[OPENCIV3_GODOT_FILE_PLAN.md](OPENCIV3_GODOT_FILE_PLAN.md). For failure
classification and concrete recovery steps, use the
[troubleshooting runbook](OPENCIV3_GODOT_TROUBLESHOOTING.md).

## Definition of done

The graphical migration is complete when all of the following work without a
Python process or embedded Python interpreter:

1. Start Godot, open the main menu, configure a new game, and enter gameplay.
2. Load the packaged standalone rules and a real Conquests BIQ scenario.
3. Display the main map, minimap, units, cities, advisors, reports, and dialogs.
4. Select and move units, fight, found and manage cities, choose research, adjust
   spending, negotiate, process AI turns, and reach a victory screen.
5. Save and reload the same game in either the Python or Rust frontend.
6. Match Python reference state for a fixed seed and command script, including
   autonomous expansion, population, technology, contact, and combat outcomes.
7. Pass existing Python-reference tests and new native Godot integration tests.
8. Produce repeatable CPU, wall-time, and peak-RSS measurements for comparable
   Python and Rust campaigns.

Godot remains the rendering engine. GDScript, scenes, themes, and media assets do
not need to be transpiled.

## Recommended architecture

Use a Rust GDExtension library loaded by the existing Godot project. Replace
py4godot node scripts with native Rust node classes or very thin GDScript
adapters. Do not attempt to emulate py4godot in the transpiler.

```text
Godot scenes / GDScript glue / editor resources
                  |
        handwritten Rust GDExtension nodes
                  |
       typed command, event, and snapshot DTOs
                  |
   +--------------+----------------+----------------+
   |              |                |                |
 transpiled    transpiled       handwritten       handwritten
 game rules    presentation     native codecs     Godot adapters
 and AI        models           and persistence   and media nodes
   |              |                |                |
   +--------------+----------------+----------------+
                  |
       shared Rust runtime and locked crate graph
```

### Boundaries

- **Transpile:** deterministic game rules, AI, reports, scoring, map-camera
  calculations, draw-command construction, and typed setup drafts.
- **Handwrite in Rust next to Python:** Godot API hosts, image/texture handling,
  bounded binary/media codecs, INI/filesystem adapters, and native save codecs.
- **Leave as Godot resources:** scenes, GDScript glue, themes, shaders, fonts,
  audio files, and art assets.
- **Keep Python only as a reference implementation and test oracle.** Production
  Rust must not import Python or start Python subprocesses.

### API design

Do not expose the generated mutable `GameState` graph directly to Godot nodes.
Use a native session object with stable IDs and explicit commands. Return small
DTOs or typed snapshots:

- `UnitSnapshot`, `CitySnapshot`, `ResearchSnapshot`, `MapSnapshot`, and
  `TurnEvents`;
- unit, city, civilization, tile, and technology IDs rather than object identity;
- simple scalars, strings, bytes, and typed records at the GDExtension boundary;
- JSON only for low-frequency setup/save/report interchange, not per-frame map
  rendering or per-tick unit updates.

The existing direct-Rust import interface supports only limited types. Before
using complex native modules, extend it to checked project-owned record DTOs and
fallible calls. Do not pass generated private type names through an unstable
string-based interface.

## File replacement convention

Generate and verify the consolidated crate with:

```bash
PYTHONPATH=. python -m py2rust.godot /path/to/OpenCiv3/C7
PYTHONPATH=. python -m py2rust.godot --check /path/to/OpenCiv3/C7
cargo test --locked --manifest-path /path/to/OpenCiv3/C7/native/Cargo.toml
```

Do not create one physical Rust file per Python file. Consolidate handwritten
code into **10 Rust files under `C7/native/`, plus the crate's `lib.rs`**. The
logical modules in the file plan map to these files as follows:

| Physical file | Responsibilities |
| --- | --- |
| `godot_runtime.rs` | `GlobalSingleton`, `LogManager`, runtime services, and `AudioManager` |
| `game_node.rs` | `PythonGame` host and turn/event dispatch |
| `map_nodes.rs` | `PythonMapView`, `PythonMiniMap`, and `SpriteAtlas` |
| `advisor_nodes.rs` | All advisor, report, palace, and victory nodes |
| `menu_nodes.rs` | Main menu, shared widgets, credits, and preferences |
| `setup_nodes.rs` | All new-game player/scenario/world setup nodes |
| `media_native.rs` | Media catalogs, Godot media, sprites, PCX, FLIC, and AMB |
| `config_native.rs` | Settings and case-insensitive path handling |
| `binary.rs` | Binary records, BIQ import, and SAV decoding |
| `savegame.rs` | Native save schema, codec, migrations, and controller restoration |

Each file may expose several logical Rust modules and register several Godot
classes. Small related classes should remain together rather than being split by
Python filename. `lib.rs` owns GDExtension registration and exports; it is crate
glue, not another application module.

Current resolution rejects a `.py` and `.rs` with the same import name as
ambiguous. Add an explicit project manifest rather than silently changing that
rule. Manifest entries identify both the consolidated file and the logical Rust
module within it:

```toml
# native-modules.toml
[modules]
"openciv3.godot_media" = { path = "native/media_native.rs", module = "godot_media" }
"openciv3.binary" = { path = "native/binary.rs", module = "binary" }
"openciv3.save_codec" = { path = "native/savegame.rs", module = "save_codec" }
"PythonGame" = { path = "native/game_node.rs", module = "game_node" }
```

Rules:

- Python execution continues to use the `.py` implementation.
- py2rust uses the manifest-selected `.rs` implementation.
- A mapped `.py`/`.rs` pair is intentional, not ambiguous.
- Every native module has a documented signature, bounded inputs, error behavior,
  Rust tests, and Python/Rust parity fixtures.
- Application-specific behavior belongs in these native files, not in special
  cases in the transpiler.
- Generated Rust is never manually maintained.

## Transpiler work required

### P0: project discovery and native modules

- Load the native manifest before resolving external imports, so `py4godot` does
  not stop discovery before native replacements are known.
- Include handwritten sources and their Cargo dependencies in the generated
  crate. Keep module source maps for both Python and Rust.
- Support `cdylib` GDExtension output in addition to the current standalone
  binary. Add release/debug packaging for Linux first, then Windows/macOS.
- Generate or validate the `.gdextension` manifest and native-class registration.
- Keep all Cargo dependencies locked and test from a clean checkout.

### P0: whole-project correctness

The console exposed repeated copies and lost updates. Replace the current narrow
receiver-name shims with project-wide analysis:

- Build a call graph with direct writes, collection mutations, callback effects,
  and transitive parameter effects.
- Choose owned, shared-borrow, mutable-borrow, copy-on-write return, or shared
  interior mutability from actual use rather than module names.
- Preserve mutations through nested records, lists, dictionaries, and callbacks.
- Handle `setdefault`, nested indices, optional unions, enum fields, named
  callback defaults, and closure captures consistently.
- Keep Python `is` identity separate from dataclass structural equality. Use
  stable IDs or native handles where identity is semantically required.
- Retain explicit `_state` APIs temporarily as a compatibility mechanism. Do not
  rewrite them all until the general mechanism has parity tests.

Add a project diagnostics report listing every mutable parameter, borrowed
argument, cloned record, native boundary, and remaining dynamic union. This will
make whole-project optimization auditable.

### P1: language and runtime coverage

- Typed native DTO signatures and record layout agreement.
- Library support needed by the engine: streams, `struct`, compressed files,
  `shlex`, filesystem paths, encodings, and deterministic iteration.
- Readable diagnostics containing Python file/line, generated Rust location, and
  failing operation.
- Compile only reachable entry points, but allow alternate entries for console,
  GDExtension, tests, and media tools without recompiling unrelated UI nodes.

### P1: performance

- Preserve context-sensitive borrowing of cached constants, which reduced the
  campaign from roughly 155 seconds to 5 seconds.
- Add cross-module clone proofs and shared immutable rule/world views.
- Avoid whole-map clones per frame and whole-state clones per command.
- Reuse map draw buffers, texture atlases, and DTO snapshots.
- Measure before changing algorithms. Use the same command script and game state
  for Python and Rust comparisons; report mean CPU and maximum peak RSS over at
  least five runs.

## Delivery milestones

### Milestone 0: lock the reference and native baselines

- Freeze fixed-seed command scripts and expected snapshots in both frontends.
- Record Python console and Godot smoke results before further changes.
- Fix native autonomous settler expansion and remaining turn/economy parity.
- Add a machine-readable module inventory with owner, action, dependencies, and
  status for every file in the file plan.

Exit: the same ten-turn command script has equivalent Python/Rust state.

### Milestone 1: native scenario and persistence support

- Implement bounded BIQ/SAV/PCX/FLIC/AMB codecs as native modules with fixtures.
- Define a versioned save schema independent of Python dataclass introspection.
- Implement typed save-state conversion and compatibility tests in both
  directions.
- Implement INI/settings and path adapters with `res://`/`user://` mapping.

Exit: identical scenario state and a save/load round trip for console and native
library callers.

### Milestone 2: GDExtension shell

- Add `cdylib` packaging and native-class registration.
- Replace `GlobalSingleton`, `LogManager`, and the `PythonGame` host with
  handwritten Rust nodes.
- Initialize settings, media, session state, and error reporting.
- Open the main menu and enter an empty gameplay scene with no Python process.

Exit: Godot starts, native logging works, and a headless smoke confirms native
node initialization and shutdown.

### Milestone 3: map and core gameplay

- Implement `PythonMapView` and `PythonMiniMap` as native nodes.
- Transpile camera and draw-command models; batch GPU texture work in Rust.
- Implement unit selection, movement, founding, city production, research,
  economy, and turn advancement through the native session.
- Render map updates from typed deltas rather than cloning the full game state.

Exit: a native Godot campaign reaches population 2, discovers Pottery, meets
another civilization, and matches the console reference.

### Milestone 4: dialogs and advisors

- Implement production, research, economy, diplomacy, government, combat, and
  victory dialogs.
- Transpile report models and draw-command generation.
- Add domestic, science, foreign, palace, and victory native views.

Exit: every console-accessible gameplay action also works through the graphical
UI, including keyboard/mouse input and dialog validation.

### Milestone 5: new-game setup, saves, and media completion

- Complete setup drafts, opponent/world selection, BIQ loading, and save loading.
- Complete textures, unit animation, palace media, and audio lifecycle.
- Verify media-disabled standalone mode and classic media mode.

Exit: a fresh Godot process can configure, play, save, reload, and continue a
real scenario without Python.

### Milestone 6: parity, optimization, and release

- Run all focused engine tests and complete graphical smoke campaigns.
- Compare identical Python/Rust states and resolve remaining differences.
- Profile initialization, map rendering, AI turns, save encoding, and memory.
- Package generated source, locked dependencies, native library manifests, and
  reproducible build/run instructions.

Exit: documented acceptance campaign and resource benchmark pass from a clean
checkout.

## Verification strategy

Use four layers:

1. **Compiler tests:** frontend, lowering, ownership, native signatures, crate
   output, and error locations. Keep routine checks focused; run the full suite
   before committing shared compiler changes.
2. **Engine parity tests:** fixed-seed snapshots after every command and turn.
   Include autonomous expansion, contact, combat, research, growth, and saves.
3. **Native codec tests:** malformed-input budgets, truncation, integer bounds,
   decompression limits, and byte-for-byte fixtures.
4. **Godot integration tests:** headless startup/shutdown, native scene entry,
   input dispatch, map updates, advisor dialogs, save/reload, and media/audio
   cleanup. Add real-window smoke checks for rendering that headless tests cannot
   validate.

Do not use successful compilation alone as a milestone. Do not edit generated
Rust to make a smoke test pass.

## Main risks and chosen responses

- **Mutable object graph:** address with whole-project effect analysis and
  explicit native session ownership, not additional receiver-name exceptions.
- **GDExtension ABI complexity:** keep a small typed boundary and isolate it in
  handwritten Rust nodes.
- **Parser/media scope:** use bounded native codecs and existing fixtures instead
  of expanding Python parser support unnecessarily.
- **Save compatibility:** define an explicit schema; do not reproduce dynamic
  Python introspection.
- **Performance regressions from DTOs:** send deltas and reuse buffers; never
  serialize the full state every frame.
- **Large generated source:** split emitted modules into a small number of Rust
  crates/modules after source maps and linking are stable, while retaining one
  locked workspace.
