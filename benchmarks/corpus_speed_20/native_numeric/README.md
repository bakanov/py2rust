# Population and WAV native comparisons — 2026-11-25

Raw report filenames below refer to [local archived reports](../../REPORTS.md#local-archive),
not files shipped in this repository. Source programs and Markdown summaries remain in Git.

These two additional baselines extend the [active goal report](../../../doc/NATIVE_PERFORMANCE_GOAL.md)
to nine of the original twenty applications. They do not complete the global target.

- `native-results.json`: two applications, two sizes, 15 timed observations per
  original-generated/current-generated/handwritten executable (180 runs).
  Every run passed independent output checks and identical complete-file hashes.
- `varied-checks.json`: 36 additional complete jobs. Population checks include
  closed-form Decimal references, RK4 refinement, zero/equilibrium populations,
  Unicode/escaped labels and replay. WAV checks include empty and odd-chunk inputs,
  replay, and every signed16 sample under five rational gain/peak settings.

The compiler and application sources are unchanged from `../native_round_two/`.
All twenty current build fingerprints and binary hashes, and the source/binary
hashes of all nine handwritten comparisons, were rechecked. The earlier 40-case
correctness sweep remains applicable; it was not rerun solely to add native
references. Numeric comparisons and the previous seven comparisons were separate
batches; each rotates its own three executables on identical fresh inputs.

Current large-workload ratios: population 1.13×, WAV 1.39×. Both small cases also
pass. Complete source and executable artifacts:

- `/home/dima/.cache/py2rust-build/corpus-native-numeric`
- `/home/dima/.cache/py2rust-build/corpus-native-numeric-varied`

Handwritten sources are `../native/population.rs` and `../native/wav.rs`.
Both implement their processing and verification modes, with durable publication
and complete JSON/CSV/SVG artifacts. As with the other native baselines, the
fault-injection/pause hooks are not implemented or timed.
