# Copy-on-write recursive records: autocomplete

Raw report filenames below refer to [local archived reports](../../REPORTS.md#local-archive),
not files shipped in this repository. Source programs and Markdown summaries remain in Git.

Historical measurement stage; see the [final acceptance audit](../final/README.md) for the current status.

The compiler now shares storage for resource-free recursive value records. It
selects types by recursion and resource safety, without recognizing application
names. Python applications and handwritten baselines are unchanged.

## Representation

An optimized recursive `Node` becomes a wrapper around `Arc<NodeStorage>`, where
`NodeStorage` contains the original fields. `Clone` shares storage; `Deref` exposes
read access; `DerefMut` uses `Arc::make_mut` to detach a shared node before mutation.
Children are wrappers too, so copying a node's fields does not copy every descendant.
Unique storage can mutate without detaching. Ordinary nonrecursive records,
resource-containing records and optimization-off retain their original layout.

This preserves the subset's independent owned-value semantics, saved snapshots and
old state observed after errors. It does not introduce Python object identity or
shared mutable aliases. `Arc` retains `Send`/`Sync` when the fields permit them.
Resource-containing types are excluded to avoid changing resource lifetimes.
Partial field moves are disabled for wrappers because fields cannot move out of
dereferenced shared storage. Both typed and legacy host frontends use this rule.

The tradeoff is an allocation per constructed recursive record, atomic reference
counts when cloning and indirection when reading. Broad child maps still cost time
to copy. This is not a universal claim that all recursive programs become faster.

## Matched measurements

The previous binary includes borrowed record cursors. Runs rotate previous, new
and handwritten release executables after warm-up, with 15 timed runs per engine
and size. Every run passes the independent oracle and complete-output equality.
Startup and durable I/O are included; compilation and checking are excluded.

| Size | Previous generated (ms) | New generated (ms) | Handwritten (ms) | New/native |
|---|---:|---:|---:|---:|
| small | 19.81 | 17.02 | 16.81 | 1.01× |
| large | 881.15 | 46.92 | 24.82 | 1.89× |

The large matched case takes about 95% less time than the previous binary.
`results.json` retains all 90 timed observations and fingerprints; `builds.json`
identifies the compiler/application. Ratios from different measurement sessions
must not be divided to infer this speedup.

## Size sweep

The sweep uses eight mixed operations per term after insertion, then export and
inspect. Each size has nine timed runs per engine after warm-up, rotating order,
independent oracles and complete-output equality. The smallest sweep workload has
more commands than the small two-size benchmark above.

| Terms | Previous generated (ms) | New generated (ms) | Handwritten (ms) | New/native |
|---|---:|---:|---:|---:|
| 8 | 22.59 | 17.74 | 17.15 | 1.03× |
| 16 | 36.82 | 18.41 | 17.83 | 1.03× |
| 32 | 64.55 | 21.44 | 19.72 | 1.09× |
| 64 | 181.40 | 27.75 | 23.08 | 1.20× |
| 128 | 864.55 | 46.39 | 24.24 | 1.91× |

`scaling.json` preserves 135 timed observations and input/output hashes. Reproduce
using `tools/compare_autocomplete_scaling.py --comparison <preserved-comparison>
--output <fresh-directory> --repeats 9`. The tool verifies compiler, application and
executable hashes before measuring.

The full generated application suite passes: 41 traces (32 seeded), 23 split
replays, 92 invalid inputs, 32 state checks, 16 capacity checks and 22 publication
checks. `checks.json` records the binary hash and 337 `Application.run` calls;
publication checks can also launch subprocesses directly.

Twenty-six targeted regressions passed for recursive records, traversal cursors,
owned field moves and shared storage. They include typed/legacy frontends with
optimization on/off, deep independent snapshots, checked failures, generated-name
collisions and resource-storage exclusion. Black, Ruff and whitespace checks passed.

The observed recursive-copying problem is addressed within these workloads and
the application's 128-term capacity. The largest ratio has limited margin below
2× and is not a universal guarantee. Route planning remains active work.
