# Handwritten sprite-atlas comparison

Raw report filenames below refer to [local archived reports](../../REPORTS.md#local-archive),
not files shipped in this repository. Source programs and Markdown summaries remain in Git.

The independent Rust implementation in `../native/atlas.rs` preserves first-fit
shelf order, padding, stable height/width/name sorting, exact samples, sampled SVG,
source archives and durable publication. Extracted sprite files are read from the
finished atlas pixels, not substituted with copies of the original files. Both
pack and verify modes are implemented; fault-injection/pause controls are excluded.
The P6 decoder follows the handwritten PPM reference with the tighter sprite bounds.

No compiler or Python application changes were needed. Compiler/application/binary
fingerprints were checked before reusing current release builds. The comparison
rotates generated, handwritten and preserved preceding generated executables over
fresh identical jobs. Every run passes an independent oracle and complete-file
hash equality; compilation and checks are untimed.

| Size | Generated median (ms) | Handwritten median (ms) | Ratio |
|---|---:|---:|---:|
| Small | 277.56 | 287.65 | 0.96× |
| Large | 159.40 | 150.30 | 1.06× |

Both sizes meet <2.00×. `results.json` retains all 90 timed invocations (15 samples
per size and executable), fingerprints and wall/CPU/RSS observations. These are
complete durable-publication jobs, not isolated packing kernels. The small-job
wall times exceeded the large-job times in this batch; I/O variation prevents
interpreting this as a size-scaling curve or a compute-speedup claim. Coarse process
CPU measurements are mostly zero and do not establish kernel equivalence.

The native program additionally passed **341 varied complete jobs** (`checks.json`):
manual shelf layouts, 8/16-bit samples, padding and ordering combinations, Unicode
sort ties and escaping, raster-boundary bytes, generated projects, extraction/repack
and archive replay, malformed PPM images, invalid settings and tampered archives.

Coverage is now fifteen original applications: fourteen below 2.00× at both sizes,
plus the resolver accepted by the user at its observed 2.39×. Missing native
baselines are 077, 079, 080, 095 and 109; the later ten examples also remain open.
Historical raw measurements retain their strict `target_met` flags. The revised
comparison gate supports the explicit `--exempt-from-target 096` option without
hiding the resolver measurement or relabeling it as below 2.00×.
