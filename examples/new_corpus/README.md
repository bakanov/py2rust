# OpenCiv3-inspired application corpus

These nine small, deterministic applications complement the general-purpose catalog in
`examples/corpus`. They exercise the failure modes and program shapes documented in
`LESSONS_LEARNED.md`, without requiring an OpenCiv3 checkout, game assets, a GUI, or input files.
Each application has a normal Python entry point, several focused modules where useful, and an
`expected.txt` golden output. They are correctness fixtures, not performance benchmarks or a second
implementation of OpenCiv3.

| ID | Application | Main coverage |
| --- | --- | --- |
| [001](001_scenario_rules/main.py) | Scenario rules | Shared collection constants, fixed-tuple iteration, `Counter`, optional JSON narrowing and numeric comparisons, `field(init=False)`, `__post_init__` |
| [002](002_unit_lifecycle/main.py) | Unit lifecycle | Stable unit/city IDs, coordinate identity, removal without object identity, mutation of real collection receivers, returning updated records |
| [003](003_fog_of_war/main.py) | Fog of war | Copy-on-write `TileKnowledge`, persistent explored state, current visibility, coordinate keys, optional tiles and membership |
| [004](004_turn_phases/main.py) | Turn phases and AI | Cursor-based queues, work appended during traversal, nested sorting callbacks with captures, optional destinations, finite ranking sentinels |
| [005](005_seeded_map/main.py) | Seeded map selection | Stateful RNG receivers, initialization hooks, rejection sampling that consumes rejected draws, reproducible independent streams |
| [006](006_noise_permutation/main.py) | Noise permutation | Explicit signed-64-bit wrapping arithmetic, deterministic terrain generation, module constants, fixed tuples |
| [007](007_trade_network/main.py) | Trade network | Stable network IDs, indexed breadth-first traversal, road/airport components, `Counter` resource stocks, optional city lookup |
| [008](008_city_economy/main.py) | City economy | Optional worked tiles and production, build-then-assign citizen updates, growth/production/research rounds, empty-city fast path |
| [009](009_mini_campaign/main.py) | Integrated mini-campaign | A reduced alternate entry point combining founding, unit removal and movement, visibility, city rounds, research, and multiple owners |

The fixtures deliberately use application-level invariants in their printed output. For example,
the RNG case includes a rejected duplicate, the city case grows and completes exactly one building
and technology, and the campaign checks the state after each complete turn. This makes semantic
regressions visible even when Rust compilation succeeds.

## Run the checks

From the repository root, with the development environment from `doc/DEVELOPMENT.md` installed:

```bash
# Fast reference-only check.
python examples/new_corpus/check.py --python-only

# Transpile, compile, run, and compare every application (offline Cargo build).
python examples/new_corpus/check.py

# Selected examples, or optimized native builds.
python examples/new_corpus/check.py 002 005 009
python examples/new_corpus/check.py --release
```

Generated Cargo projects and executables go to
`$PY2RUST_BUILD_DIR/new-corpus`, or `~/.cache/py2rust-build/new-corpus` when that variable is unset.
Use `--online` only when Cargo dependencies are not already cached. The checker runs applications
sequentially because native verification uses shared build resources. Builds have a 240-second
limit, and each resulting executable has a separate 20-second limit so a bad loop fails the check
instead of running indefinitely.
