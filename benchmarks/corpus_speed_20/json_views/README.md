# Nested JSON views and a twelfth handwritten baseline

Raw report filenames below refer to [local archived reports](../../REPORTS.md#local-archive),
not files shipped in this repository. Source programs and Markdown summaries remain in Git.

Application Python is unchanged. The typed memory oracle now propagates stable
JSON backing through read-only `json_array` loops, within the owning loop body.
It may borrow read-only array locals from nested items and string locals extracted
from JSON parameters or those items. Rebinding, source mutation or local mutation
prevents these views. Escaping values still materialize at owned boundaries.

The backend records string views in move safety, so an owned callback argument
cannot move while a borrowed string depends on it. The runtime string-view helper
retains the same type validation. Legacy and optimization-disabled builds retain
the owned fallback. The separate self-hosted compiler is unchanged.

For example, omitting generated scope suffixes, the resolver changes from:

```rust
let numbers: Vec<rt::Json> = rt::json_array(rt::json_key_ref(atom, "value")?)?;
let operator: String = rt::json_string(rt::json_key_ref(atom, "op")?)?;
```

to:

```rust
let numbers: &[rt::Json] = rt::json_array_ref(rt::json_key_ref(atom, "value")?)?;
let operator: &str = rt::json_string_ref(rt::json_key_ref(atom, "op")?)?;
```

## Performance evidence

`native-results.json` records 15 rotated release samples per size and executable,
with fresh identical inputs, independent oracles and complete-file equality checks.
The before build includes parser caching. All 1,080 timed invocations passed their
output checks. The compiler, application and executable fingerprints are recorded.

| Application | Before views, large (ms) | Now, large (ms) | Native, large (ms) | Small ratio | Large ratio |
|---|---:|---:|---:|---:|---:|
| 068 Huffman compressor | 32.05 | 32.94 | 18.81 | 1.02× | 1.75× |
| 071 Common-access-log analyzer | 85.67 | 85.57 | 45.87 | 0.94× | 1.87× |
| 078 Regex rewrite (preview) | 2.80 | 2.77 | 2.60 | 1.01× | 1.07× |
| 096 Package resolver | 55.01 | 54.26 | 22.68 | 1.01× | 2.39× |
| 100 Text diff | 36.72 | 35.95 | 25.58 | 1.01× | 1.41× |
| 104 Circuit calculator | 37.30 | 37.09 | 25.74 | 1.01× | 1.44× |
| 105 Telemetry analyzer | 85.19 | 86.68 | 66.05 | 1.01× | 1.31× |
| 110 Population simulator | 41.93 | 41.12 | 35.97 | 0.98× | 1.14× |
| 111 PNG inspector | 41.20 | 41.33 | 34.64 | 1.02× | 1.19× |
| 112 WAV analyzer | 44.08 | 45.16 | 29.78 | 1.09× | 1.52× |
| 114 PPM filters | 50.65 | 51.37 | 28.58 | 1.07× | 1.80× |
| 117 Terminal dashboard | 19.00 | 18.45 | 17.86 | 0.97× | 1.03× |

Eleven of twelve applications pass both sizes; 23 of 24 size cases pass. The eight
missing original baselines are 077, 079, 080, 095, 109, 113, 115 and 118. The target
is not achieved. Resolver constraint records still own their copied JSON fields.

The resolver's 55.01 → 54.26 ms change is small and should not be presented as a
large or statistically established speedup. The preceding array-only comparison
is preserved in `arrays-only-resolver.json`; it likewise did not establish a large
wall-time improvement. This pass removes allocations and improves ownership
representation, but the larger cross-function record-copying problem remains.

The independently handwritten PPM baseline passes both timed sizes at 1.07× and
1.80×. Its generated source is unchanged from the preceding compiler; this addition
expands coverage rather than demonstrating a PPM compiler speedup. Complete jobs
include crop/invert/threshold processing, reports, histograms, sampled SVG, binary
exports, replay archives and durable publication. The native implementation also
implements archive verification. Fault-injection and pause controls are excluded.

## Compiler verification

`corpus-results.json` records all twenty rebuilt applications and forty checked
workloads: five repetitions per Python/generated engine, 400 timed invocations.
These comparisons establish selected-workload correctness, not the native gate.

Forty focused view/effect/move-safety cases passed across the targeted runs. They
include typed/legacy and optimization-enabled/disabled execution, nested JSON
arrays, Unicode strings, mutations requiring snapshots, returned owned values,
invalid projections and a callback whose JSON argument must stay alive while a
string view is used. The callback cases were rerun after the ownership fix.

The new PPM baseline additionally passed **322 varied complete jobs** against the
independent PPM oracle (`ppm-checks.json`): depth/header/boundary cases, every u16
sample value, manual pixel goldens, generated filter-composition properties,
archive/process replay, all proper prefixes of a small image, malformed raster
data and invalid/tampered requests and archives. These checks do not exercise
the excluded fault-injection/pause controls.
