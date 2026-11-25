# Bounded deterministic parser caching

Raw report filenames below refer to [local archived reports](../../REPORTS.md#local-archive),
not files shipped in this repository. Source programs and Markdown summaries remain in Git.

This is a follow-up to the shared optimizations in `native_round_two`.
Application Python and handwritten resolver sources are unchanged.

The compiler accepts only closed functions with one immutable string argument,
a Copy scalar/tuple result and audited deterministic operations. Unknown calls,
global reads, observable I/O, parameter mutation and mutable returned objects
keep ordinary execution. Only successful results are cached. Each function retains
at most 64 keys of at most 256 UTF-8 bytes; longer keys bypass caching. Calculations
run outside the mutex, including recursive or concurrent calls to the runtime helper.

The cache is selected structurally, never by application or function name.
Disabling compiler optimization disables this lowering. This is a host-backend
optimization; it does not extend the separate self-hosted compiler.

## Initial resolver comparison

`resolver-results.json` contains 15 rotated samples per executable and size,
with fresh identical fixtures, independent oracles and equal complete file contents.
The before executable is the previous optimized compiler, not the original compiler.

| Size | Before (ms) | Cached (ms) | Handwritten (ms) | Cached/native |
|---|---:|---:|---:|---:|
| Small | 13.61 | 13.32 | 12.70 | 1.05× |
| Large | 62.98 | 55.73 | 22.34 | 2.49× |

The large job improves by about 11.5% within this matched comparison, but still
fails the strict <2.00× goal. This is not evidence that all twenty cases pass.

A fresh, separately oracle-checked Callgrind run of the pre-cache resolver records
703,478,480 generated instructions. Inclusive constraint construction accounts for
342,850,901 (48.74%) and version parsing for 139,413,079 (19.82%). Inclusive costs
overlap; these are not wall-time percentages. Raw profiles are retained under
`~/.cache/py2rust-build/resolver-current-profile`.

The remaining large cost is owned JSON constraint construction across function
boundaries. The native baseline uses typed records and borrowed parsed requirements.
Reducing that cost requires representation and lifetime proofs across callees,
not an assumption that returned JSON can always borrow its inputs.

## Refreshed eleven-application comparison

`native-results.json` contains 15 timed samples for each of eleven applications,
two sizes and three executables (990 timed invocations). Every run passed its
independent oracle and complete-file equality check. Source/compiler/executable
hashes and individual wall-time/CPU/RSS measurements are included.

| Application | Previous optimized, large (ms) | Now, large (ms) | Native, large (ms) | Small ratio | Large ratio |
|---|---:|---:|---:|---:|---:|
| 068 Huffman compressor | 31.44 | 32.25 | 18.40 | 0.99× | 1.75× |
| 071 Common-access-log analyzer | 84.83 | 85.48 | 45.73 | 0.99× | 1.87× |
| 078 Regex rewrite (preview) | 2.85 | 2.96 | 2.75 | 0.97× | 1.08× |
| 096 Package resolver | 64.23 | 54.82 | 22.61 | 1.13× | 2.42× |
| 100 Text diff | 36.02 | 36.04 | 25.03 | 1.01× | 1.44× |
| 104 Circuit calculator | 38.08 | 38.17 | 26.08 | 1.02× | 1.46× |
| 105 Telemetry analyzer | 79.34 | 78.79 | 61.64 | 1.05× | 1.28× |
| 110 Population simulator | 40.35 | 40.50 | 35.81 | 1.10× | 1.13× |
| 111 PNG inspector | 36.14 | 35.98 | 31.48 | 1.07× | 1.14× |
| 112 WAV analyzer | 38.43 | 40.17 | 28.19 | 1.03× | 1.43× |
| 117 Terminal dashboard | 17.49 | 18.38 | 18.05 | 1.00× | 1.02× |

Ten applications pass both sizes; the resolver still fails at large size.
Nine original native baselines are still missing, so the global target is open.

`corpus-results.json` records all twenty rebuilt applications and forty checked
size cases, five repetitions per Python/generated engine (400 timed invocations).
These Python comparisons establish selected-workload correctness, not the native gate.
Three runtime cache tests, four typed/legacy optimization-on/off executable parity
cases and nine effect/cost regressions passed. Formatter and linter checks passed
for the new compiler pass and parity test.
