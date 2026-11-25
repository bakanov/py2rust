# Owned field moves: scheduler scaling

Raw report filenames below refer to [local archived reports](../../REPORTS.md#local-archive),
not files shipped in this repository. Source programs and Markdown summaries remain in Git.

Historical measurement stage; see the [final acceptance audit](../final/README.md) for the current status.

This general compiler change moves collection fields out of owned record
parameters into local variables when the original field cannot be observed before
unconditional restoration. Old-field length reads use a scalar snapshot. Other
reads, whole-record uses, resources, loops/early exits in the extraction region and
functions containing exception/resource scopes retain the copying fallback.
The current implementation is a conservative host-emitter analysis shared by the
typed and legacy frontends, not a new portable IR pass. It does not special-case
application names, record names or fields.

For example, the scheduler now emits:

```rust
let mut jobs: Vec<rt::Json> = state.jobs;
let mut counts: indexmap::IndexMap<String, i64> = state.counts;
let __field_length_trace: i64 = state.trace.len() as i64;
let mut trace: Vec<rt::Json> = state.trace;
// Update the owned locals and restore state.jobs/state.counts.
// Construct the next event using __field_length_trace + 1.
// Restore state.trace before returning the complete state.
```

Previously all three field extractions cloned their full contents. Copying the
increasing trace on every transition was a major scaling cost. Metadata snapshots
preserve the old value even if the local collection has already been modified.
Final owned values still obey the subset's independent-value semantics.

## Matched full-job measurements

The preserved previous build already includes the first field-projection and
self-replacement fixes. Python source, native source and workloads are unchanged.
Every run checks the independent oracle and complete-file equality. There are
15 timed runs per engine/size after warm-up, with rotating execution order.

| Size | Previous compiler (ms) | New compiler (ms) | Handwritten Rust (ms) | New/native |
|---|---:|---:|---:|---:|
| small | 19.53 | 17.67 | 16.83 | 1.05× |
| large | 1092.18 | 28.45 | 22.20 | 1.28× |

The large job is about 38× faster than the immediately preceding compiler in this
matched batch. The historical original 105.29× ratio came from a different batch;
do not use that ratio to calculate the speedup of this individual patch.

## Size sweep

A separate matched sweep uses nine repetitions per engine at each size, with the
same seed, three workers and 16 queue slots. Compilation, input construction and
checking are excluded; startup and durable output remain included.

| Jobs | Previous compiler (ms) | New compiler (ms) | Handwritten Rust (ms) | New/native |
|---|---:|---:|---:|---:|
| 32 | 21.27 | 19.02 | 17.74 | 1.07× |
| 64 | 31.46 | 17.75 | 16.37 | 1.08× |
| 128 | 76.71 | 19.89 | 17.12 | 1.16× |
| 256 | 261.07 | 22.65 | 19.12 | 1.18× |
| 512 | 1101.21 | 28.08 | 21.59 | 1.30× |

The old curve grows sharply as jobs and trace length increase. The new generated
code remains below 2× native at all five sizes and follows the native complete-job
curve much more closely. These bounded measurements support removal of the copying
problem, not a universal asymptotic guarantee for arbitrary programs or workloads.
The two batches retain 225 timed invocations in total (90 + 135).

## Correctness and scope

Thirty-six targeted field/record/recursive-record cases passed. The five new cases
also passed after the final type-compatibility guard was added. They exercise both
frontends and optimization settings, old lengths after local mutation, Unicode
string lengths, owned snapshots and conservative whole-record/exception fallbacks.

The generated scheduler additionally passed its full independent suite: 41 explicit
workloads, seeded and repeated replay, exact trace integrals, 90 invalid documents,
maximum-capacity cases under a 256 MiB memory limit, injected publication failures,
input aliases/changes and concurrent writers. `checks.json` records 177 calls through
the Application wrapper plus additional direct subprocesses; that wrapper count
is not presented as the total number of processes. All hashes match the measured
binary. Current compiler/application/native source fingerprints were rechecked.

Reproduce the scaling sweep from a fresh matched three-engine comparison:

```sh
PYTHONPATH="$PWD/tools:$PWD" python tools/compare_scheduler_scaling.py \
  --comparison /absolute/comparison-with-before --output /absolute/new-curve --repeats 9
```

The overall three-program goal remains active. Recursive trie traversal/update
copies and route-planner JSON/string allocation are still unresolved. Previous
results for other applications are historical evidence, not validation of this
new compiler revision.
