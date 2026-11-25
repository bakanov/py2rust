# Borrowed JSON projection helpers: route planner

Raw report filenames below refer to [local archived reports](../../REPORTS.md#local-archive),
not files shipped in this repository. Source programs and Markdown summaries remain in Git.

Historical measurement stage; see the [final acceptance audit](../final/README.md) for the current status.

This is intermediate progress on the active three-program scaling goal. It changes
only general compiler lowering; Python applications and handwritten baselines are
unchanged. There is no application/function/field-name specialization.

## General rules

A helper consisting solely of `return json_string(value[key])`, with typed JSON
and string parameters, can expose a borrowed projection to a read-only consumer.
Actual arguments must be a named JSON backing and a named/literal key; effectful
or temporary arguments retain the owned call. Checked key lookup and string-type
validation remain in their original evaluation position.

Stable string membership in string-keyed maps/sets borrows its needle. An immutable
local receiving a projection from an already-borrowed JSON parameter or iteration
item can hold `&str`; owned returns, insertions and other escaping values still
materialize through the existing ownership boundary. Effectful helper bodies and
mutable/nonborrowed backing remain conservative. This is currently a host-emitter
rule, not general interprocedural return-view analysis in the portable IR.

Adding a borrowed string to a set checks whether it is already present before
materializing an owned key. This avoids repeated allocation in reachability loops;
new keys still allocate, and validation/effects in the argument are retained.

## Matched measurements

The previous executable is the preserved first scaling patch. Runs rotate old,
new and handwritten release executables, with 15 timed invocations per engine and
size after warm-up. Every run passes the independent oracle and complete-output
equality. Startup and durable output are included; compilation and checking are not.

| Size | Previous generated (ms) | New generated (ms) | Handwritten (ms) | New/native |
|---|---:|---:|---:|---:|
| small | 9.26 | 9.08 | 8.51 | 1.07× |
| large | 340.80 | 256.25 | 14.62 | 17.52× |

The large case remains far above 2×; the route-planner problem is not solved.
`results.json` preserves all 90 timed observations and source/binary fingerprints.

Thirteen targeted cases passed across typed/legacy frontends, optimization on/off,
JSON consumers and string views. New cases check helper effects, argument effects,
container effects and evaluation order, missing keys/wrong types, immutable local
views, escaping owned values, backing mutation, duplicate set insertion and Unicode.
The generated route planner also passed its complete graph oracle: eleven jobs,
219 answers (77 finite, 9 closed, 63 unreachable and 70 negative-cycle), validated
route/cycle witnesses and preservation of existing reports on invalid input.

## Remaining measured costs

An independent, oracle-checked Callgrind run on the new release binary recorded
3,872,627,167 instructions. Its output hash matches the historical profile fixture.
`profile-summary.json` records binary/raw-profile hashes; annotated profiles are
in the local archive, and the raw profile remains in `scaling-projections-profile` in the build
cache. This profiling run is not included in the timing samples.

The inclusive profile attributes 37.97% to `can_reach`, 25.06% to `json_key_ref`
and 21.72% to `IndexMap::get_index_of`. These categories overlap and must not be
summed. Exclusive instructions include string comparison (21.77%), JSON key lookup
(16.27%), indexed-map lookup (13.01%) and SipHash writes (7.94%). Deallocation is
3.38%, much smaller than the repeated lookup/comparison work. Percentages are
instruction shares, not measured wall-time shares.

The generated loop still repeatedly decodes immutable edge fields and performs
string-keyed membership/lookups. The native model resolves names once and uses
integer-indexed arrays. A general next step is stable per-element projection reuse
across repeated scans, retaining lazy validation and immutable-backing proofs.
Predecessor JSON copies and redundant map probes also remain. These are proposals,
not implemented optimizations or reasons to claim completion.
