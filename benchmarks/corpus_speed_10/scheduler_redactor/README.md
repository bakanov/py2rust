# Additional scheduler and log-redactor comparisons

Raw report filenames below refer to [local archived reports](../../REPORTS.md#local-archive),
not files shipped in this repository. Source programs and Markdown summaries remain in Git.

Both applications use unchanged Python sources and the same compiler fingerprint
as the original twenty and the other follow-up comparisons. Handwritten complete
jobs run with the same release settings and pinned dependencies. Each batch rotates
generated/native execution after warm-up over fresh identical inputs. Independent
oracles and complete-file equality check every invocation; fixture creation,
compilation and checking are untimed.

| Application | Size | Generated median (ms) | Handwritten median (ms) | Ratio |
|---|---|---:|---:|---:|
| Scheduler simulator | Small | 29.72 | 22.11 | 1.34× |
| Scheduler simulator | Large | 2,666.85 | 25.33 | **105.29×** |
| Log redactor | Small | 11.10 | 11.03 | 1.01× |
| Log redactor | Large | 27.29 | 14.37 | 1.90× |

The scheduler's large case fails the threshold; it has no accepted exception.
Both redactor sizes pass. The two `*-results.json` files retain 120 timed complete
jobs (15 per executable and size), source/binary fingerprints and raw wall/CPU/RSS
observations. These times include startup, serialization and durable publication.

## Scheduler (088)

`../../corpus_speed_20/native/scheduler.rs` implements typed job records, a binary
event heap and a FIFO deque. The phase ordering is identical: completion, expiry,
dispatch, then arrival; worker selection and arrival ties retain their ordering.
The seeded workload uses the same Park–Miller generator and rejection sampling.
All job outcomes, trace rows, time integrals, exact-ratio statistics, original and
resolved replay jobs, text reports and manifest bytes match.

The workload contains 32/512 seeded jobs, three workers and 16 queue slots.
`scheduler-checks.json` records 162 additional jobs: 41 explicit workloads, seeded
runs and exact replay, known generator states and rejection sampling, 90 invalid
jobs, full 512-job capacity, 32 workers, a 511-job queue and memory-limited export.
The independent reference scans events rather than using the implementation's heap.

### Source-level explanation and general improvement candidates

Generated Rust copies the complete state at transition call sites:

```rust
state = transition(state.clone(), index, "running", worker)?;
```

The transition then copies its large fields again:

```rust
let mut jobs: Vec<rt::Json> = state.jobs.clone();
let mut counts = state.counts.clone();
let mut trace: Vec<rt::Json> = state.trace.clone();
```

Repeated full job-list copies and copies of an ever-growing trace create work
that grows roughly quadratically with workload size. The handwritten version
updates the owned state directly and appends one event. This is source inspection,
not a measured allocation profile or a claim that all runtime belongs to cloning.
The complete-output checks establish that phase ordering and reports were retained.

A general ownership improvement should prove when `state = transition(state, ...)`
can transfer ownership, and when owned record fields can move into locals and back.
It must account for exception handlers, other live aliases, whole-record reads and
field reads before reassignment. In particular, this application reads the old
trace length while constructing the next event: blindly replacing every field
clone with `mem::take` would change that value. Proven metadata snapshots or more
precise field liveness are needed. No application-name special case or semantic
shortcut was used, and this issue remains unresolved.

## Log redactor (089)

`../../corpus_speed_20/native/log_redactor.rs` validates disjoint nested paths,
then mutates each selected owned JSON value in place. Ordered literal/regex rules,
UTF-8 expansion bounds and per-rule/per-target counters match. It produces only
sanitized records, numeric audit information and output hashes. Error boundaries
emit fixed phase messages, never source text, patterns, replacements or paths.
The regex engine is shared to retain Python-compatible matching behavior.

The workload contains 32/1,024 JSONL records, three nested targets and two rules,
including absent fields and multiple matches. `redactor-checks.json` records 130
additional complete jobs covering independent literal/regex results, nested fields,
exact counters, sensitive-diagnostic checks, invalid/duplicate JSON, expansion
limits and a 4 MiB input/output under a 256 MiB address-space limit.

Although this workload passes, generated output accumulation still emits
`output = [output.clone(), encoded].concat()`. A general dead-prefix append lowering
could avoid repeated copies while preserving the value observed by aliases and
error paths. This is an identified opportunity, not an implemented optimization.

Both baselines retain input snapshot revalidation and durable no-replace bundle
publication. Native fault-injection/pause hooks are excluded, so their associated
interruption/race suites were not run.

Five additional comparisons are complete; 041, 044, 045, 051 and 055 remain.
The original twenty-case evidence remains separate and unchanged.
