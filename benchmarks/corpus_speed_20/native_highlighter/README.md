# Handwritten syntax-highlighter comparison

Raw report filenames below refer to [local archived reports](../../REPORTS.md#local-archive),
not files shipped in this repository. Source programs and Markdown summaries remain in Git.

The independent Rust implementation in `../native/highlighter.rs` covers bounded
Unicode-aware tokenization, nested comments, escaped and multiline strings,
malformed-token diagnostics, source coordinates, HTML escaping, both themes,
source downloads and byte-identical replay bundles. The static stylesheet is
shared with the application, as is the runtime number-validation regex engine;
lexing, project handling and rendering are handwritten.

No compiler or Python application changes were needed. Current generated,
preceding generated and handwritten release executables rotate over identical
fresh jobs; every run passes an independent oracle and exact complete-file checks.

| Size | Generated median (ms) | Handwritten median (ms) | Ratio |
|---|---:|---:|---:|
| Small | 16.61 | 16.02 | 1.04× |
| Large | 50.59 | 50.70 | 1.00× |

Both sizes pass <2.00×. `results.json` retains all 90 timed invocations, compiler,
application and native fingerprints, and raw wall/CPU/RSS observations. These
include startup and durable file publication, not just tokenization time.

The native implementation passed 46 additional complete jobs (`checks.json`):
independent token fixtures with 240 generated fragments, HTML reconstruction,
source/diagnostic coordinates, both themes, replay and 41 invalid-input cases.
The oracle now removes a hard-link alias before its malformed-source tests, so
those tests reach the intended content and budget checks. The generated program
also passed this strengthened suite (`generated-checks.json`).

Shared snapshots reject hard-linked inputs more strictly than the Python
application. Measured inputs are unaliased regular files. Native fault-injection
and pause controls are outside the measured scope.

Coverage is seventeen original applications: sixteen below 2.00× at both sizes,
plus the resolver accepted at 2.39×. References for 077, 095 and 109 and the ten
additional examples remain outstanding.
