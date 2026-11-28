# Lessons learned from transpiling OpenCiv3 to Rust

## Outcome

The reduced OpenCiv3 standalone console now transpiles to native Rust and runs successfully. Its dependency closure contains **104 Python modules**, all of which pass lowering with **zero blockers**.

The native release executable completes with exit code 0 and prints the same result as the Python reference:

```text
OpenCiv3 standalone Rust console
Civilizations: 32
Cities: 0
Units: 8
```

The executable is generated at:

```text
~/.cache/py2rust-build/openciv3-standalone/target/release/py2rust-service
```

The latest verified native run took about 155.5 seconds, compared with about 4.5 seconds for Python. This is a correctness milestone, not a performance target.

## What worked

- Start with a **small alternate entry point and reduced runtime surface** rather than the full interactive application.
- Keep most changes in the transpiler. Make OpenCiv3 changes small, explicit, and predictable.
- Use Mypy/MypyC as a semantic reference, not as the Rust backend.
- Fix complete generated programs, not just isolated compilation examples.
- Run the Python reference alongside the native executable throughout development.
- Treat lowering, Rust generation, Cargo compilation, and runtime parity as separate milestones.

## Important technical lessons

### Python object identity is not Rust value identity

Expressions such as `unit is settler` cannot be mapped directly to cloned Rust records. Stable IDs work better for units, cities, and networks; coordinates work better for tiles.

Mutable collections also require real places. `&mut units.clone()` modifies a temporary and silently loses appended values. Mutating collection methods must operate on the original receiver or use copy-on-write updates and assign the result back.

Copy-on-write is often simpler than propagating mutable references through a large object graph. Visibility updates were a good example: updating a copied `TileKnowledge` and assigning it back was more reliable than making every containing record mutable.

### Type information must survive lowering

Several failures came from losing type information between stages:

- optional unions after `None` narrowing;
- optional JSON values used by `isinstance`;
- JSON numbers used in ordered comparisons;
- nested callbacks with captured variables;
- fixed tuples used as variable-length sequences;
- `Counter()` versus an ordinary empty dictionary;
- `field(init=False)` and `__post_init__` initialization.

The frontend, IR, coercions, and backend must agree on these representations. A fix in only one stage usually produces a later, less understandable failure.

### Stateful methods need explicit ownership decisions

RNG rejection sampling exposed a severe semantic bug: `MapRandom.next_range()` mutated a clone and repeatedly returned the same civilization, creating an infinite loop. Mutable receiver semantics are not optional for stateful algorithms.

Argument evaluation order also matters for Rust borrowing. Evaluating immutable arguments before mutable arguments avoids many simultaneous-borrow errors, but it is not a substitute for correct object semantics.

### Native arithmetic needs an explicit overflow contract

Noise generation intentionally uses signed 64-bit wrapping arithmetic. Checked arithmetic correctly rejected it. The general solution is explicit wrapping operations with both Python-reference and native implementations, not a noise-specific compiler exception.

OpenCiv3 must keep its ordinary Python runtime independent of the compiler installation. Compiler-only helper packages cannot be imported unconditionally by the Python project.

### Error messages must include locations

Long investigations became much faster after adding caller locations to JSON conversion and indexing errors. Every generated failure should ideally identify the Python source, generated Rust site, value, and operation.

Temporary generated-code instrumentation is useful for diagnosis, but it must never become the maintained implementation. Production fixes belong in the transpiler or small Python-source changes.

## Performance lessons

The first native builds were much slower than Python for avoidable reasons:

- complex module lookup tables were rebuilt on each use;
- removing index zero from vectors made queue processing quadratic;
- unnecessary cloning amplified memory and CPU costs;
- an empty-city fast path avoided constructing hydrology that could never be used.

Collection-valued module constants now use `OnceLock`, continent traversal uses an index cursor, and empty citizen allocation returns before hydrology construction. These are general improvements, not generated-Rust patches.

Profiling later showed that caching alone was insufficient: every cached collection read still cloned the complete table. Context-sensitive `local_read()` now borrows static collection constants for lookups and iteration while owned consumers retain clones. This reduced the ten-turn native campaign from **155.8 seconds to 4.7 seconds** (about 33×), and the reduced standalone startup to **1.65 seconds**. Python's corresponding campaign takes about 7 seconds on the same machine. The profile separated 151 seconds of initialization from only 3 seconds of gameplay, preventing premature optimization of the turn engine.

This is also a concrete whole-project optimization: the compiler must consider the constant's storage lifetime and each consumer's ownership needs together. A single global `borrowed` flag is too broad—owned returns and tuple unpacking still need materialization. Cross-module immutable sharing works best as a consumer-sensitive decision.

## Validation lessons

- The reduced OpenCiv3 audit reached **104/104 modules with zero blockers**.
- Cargo successfully builds the complete reduced release executable.
- Clean native output matches the Python baseline.
- The focused 23-test regression selection passes, covering semantic rejection, conditions, parameter ownership, parser memoization, native-source rebuilding, and signed wrapping arithmetic.
- Formatting checks use Black, Ruff, and rustfmt.

A successful application run and focused regression selection do not prove the whole compiler is regression-free. The full py2rust suite is intentionally deferred while prioritizing the working application; broader commit readiness still requires that separate validation.

## Current limitations and remaining work

- Native execution remains much slower than Python.
- The reduced runtime is not the full OpenCiv3 interactive application or BIQ-compatible runtime.
- Some dynamic-union and ownership representations remain compatibility mechanisms rather than a complete Python object model.
- Full-suite validation and final commit-readiness checks are deferred.
- The native declaration fixture has a separate missing `source_types.py` issue in its temporary project and should be resolved independently of OpenCiv3.

## Full-console investigation

A second native entry now exercises city founding, production selection, trade
networks, unit removal, AI movement phases, barbarian phases, and economic rounds.
It founds Rome and completes ten autoplay rounds with one city and seven units.
Rome grows to population 2 with +2 food and +3 shields and discovers Pottery once.
Autonomous settler expansion and some production/map details still do not match
Python; this is a runnable development milestone, not full parity.

The important new lesson is that collection methods need real mutable places as
well as correct function return values. Returning `GameState` does not help when
`game.cities.append()` still mutates `game.cities.clone()`. Conversely, fixing the
receiver alone does not propagate updates through functions that return only a
report. Both sides must be designed together.

Other concrete findings:

- Assigning a container into a record before filling it relies on aliasing; build
  it first and assign the finished value when using owned-value semantics.
- Optional membership must handle `None` without unwrapping it.
- Python object-identity removal is not structural-record removal; stable IDs are
  the appropriate native representation.
- Finite ranking sentinels avoid non-finite values and unnecessary string-to-float
  conversions in a finite native numeric profile.
- Location-bearing diagnostics and native backtraces are much faster than guessing
  from a complete application's final error.

## Next milestones

1. Finish fail-fast regression diagnosis and rerun the full suite without exclusions.
2. Verify OpenCiv3 after every general compiler change, not only during the initial milestone.
3. Reduce remaining application-specific compatibility shims where a general mechanism is practical.
4. Measure native runtime before and after each optimization, while preserving output parity.
5. Commit only after documenting test results, known limitations, and generated-artifact paths.
