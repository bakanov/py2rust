# Optimization explanations and deterministic gates

`py2rust explain` type-checks and transpiles a complete project in memory, then
prints a versioned JSON report. It does not write a generated project, invoke
Cargo, execute application code, or measure performance.

```sh
py2rust explain benchmarks/rust_quality --entry kernels.py \
  --function 'kernels.py:sum_values' \
  --deny unknown-effects --deny snapshot-iteration

py2rust explain examples/telegram --function 'app/render.py:inline_format'
python tools/check_optimization_gates.py
```

`--function` accepts a `file.py:function` glob or generated-symbol glob and can be
repeated. Without it, all declared Python functions are selected. An unmatched
selector is an error, rather than a vacuously passing check. Exit status is 0 for
an accepted report, 2 for a denied property, and 1 for compilation/selection errors.
Malformed command-line options also use argparse's exit status 2.

## What the report establishes

- Parameter ABI decisions come from the compiler's actual borrowing analysis.
- Direct-name assignment/return ownership, builder, declared view and iteration
  decisions are recorded while emitting their
  selected lowerings. Each includes a function, source line, column and reason.
- Runtime calls use the selected helper where recorded: direct JSON serialization
  is distinguished from the owned intermediate-tree implementation.
- Effect summaries propagate through statically resolved calls, including recursive
  groups. They distinguish possible failure, I/O, shared-resource/global state,
  callbacks, termination uncertainty, unknown behavior and symbolic costs.
- Unknown or unreviewed calls remain unknown. A shared Rust parameter is not evidence
  of purity. These diagnostics do not authorize reordering or change optimization.

## Strict checks and limits

`unknown-effects` rejects a selected function whose direct or transitive effect
summary is unknown. Reviewed I/O or known allocation is not rejected by this check:
it checks knowledge, not absence of effects.

`snapshot-iteration` rejects an emitted copy of a named local collection before
iteration, in a selected function or a statically reachable Python callee. The
violation identifies the source function and reason. It does not reject every
owned temporary, item copy, slice allocation, argument copy or runtime allocation.
A required snapshot can legitimately fail this opt-in check without being a
compiler correctness bug.

`owned-boundary-copy` rejects reported copies and materializations at direct-name
local assignment and return boundaries, including reachable static Python callees.
The reason distinguishes live values, protected cleanup paths, retained view
backing storage, resource lifetime conservatism and conversion of borrowed values
to owned results. Last-use moves pass. This check does not cover nested expression
copies, argument preparation, method receivers, item copies or runtime allocations;
it is not a whole-function allocation-free or zero-copy guarantee.

Reports cover declared Python functions. Main-guard statements, native bodies and
indirect callback bodies are not analyzed. Unsupported method/runtime effects are
conservative unknowns. The initial reviewed metadata covers 51 runtime helpers;
it is not a complete library cost inventory. Symbolic costs are possible work,
not measured latency, execution counts, memory bounds or a whole-program speed
guarantee. Recursion and loops can multiply those costs.

## Regression gates

`benchmarks/optimization-gates.json` selects six checks from the benchmark kernels,
chat, traffic replayer and gzip archiver. The runner verifies required borrowed
parameters and builder/view/iteration decisions, plus the configured strict checks.
A missing function, missing lowering or changed parameter mode fails the command.
The test suite also verifies that disabling optimization makes a gate fail.

Run `python tools/check_optimization_gates.py` as a deterministic CI/build check,
alongside `python -m pytest tests -q`. It does not require timing thresholds or a
network service. No remote CI provider is configured in this repository. Release
speed/scaling comparisons remain separate: `python tools/assess_rust.py --output
/absolute/fresh/output` runs the existing measured kernels and Clippy assessment.
Do not compare timing measurements while other tests or builds are running.
