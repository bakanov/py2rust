# Additional LRU cache comparison

Raw report filenames below refer to [local archived reports](../../REPORTS.md#local-archive),
not files shipped in this repository. Source programs and Markdown summaries remain in Git.

The unchanged Python application and compiler were compared with a handwritten
complete Rust implementation using identical pinned dependencies and release
settings. Execution order rotates after warm-up, with fresh identical inputs.
Independent ordered-cache oracles and complete-output equality check every timed
invocation. Compilation, fixture construction and checking are untimed.

| Size | Generated median (ms) | Handwritten median (ms) | Ratio |
|---|---:|---:|---:|
| Small | 18.01 | 17.77 | 1.01× |
| Large | 173.67 | 27.58 | **6.30×** |

The large workload fails the strict threshold; it has no accepted exception.
`results.json` retains 60 timed complete jobs (15 per executable and size), raw
wall/CPU/RSS observations and source/binary fingerprints. Times include process
startup, JSON serialization and durable file publication.

Workloads contain 66/1,602 mixed commands and 8/128 cache slots. They exercise
nested Unicode JSON values, PUT/GET/PEEK/DELETE, final resizing with evictions and
inspection. The native implementation uses a hash map for owned values and a
sorted map of sequence numbers for recency, with logarithmic recency updates.
GET moves a hit to the most-recent position; PEEK leaves order unchanged.
Serialized entries retain oldest-to-newest order independently of hash order.

`checks.json` records 288 additional complete jobs against the existing independent
oracle. These include 32 randomized traces, preview/write parity, unchanged state
restoration, splitting and resuming the sample trace at every boundary, exact
JSON numeric values, large-counter hit rates, counter overflow, malformed states,
invalid commands and maximum key/value/depth/command/input sizes. They also check
rejection of event output above 16 MiB. Fault-injection/pause publication checks
are explicitly excluded because native baselines do not implement those controls.
The checked executable hash matches both measured sizes.

## General optimization opportunity

The generated `apply` takes a borrowed cache but copies both mutable fields on
every command:

```rust
fn apply(cache: &Cache, command: &rt::Json) -> rt::Result<(Cache, rt::Json)> {
    // ... validation ...
    let mut values: indexmap::IndexMap<String, rt::Json> = cache.values.clone();
    let mut stats: indexmap::IndexMap<String, i64> = cache.stats.clone();
    // ... update and return a new Cache ...
}
```

The handwritten implementation updates the owned cache in place. Repeated copying
of all cached JSON values is a plausible contributor to the workload-size gap;
this observation comes from source inspection, not an allocation profile. A general
compiler improvement could transfer ownership into self-replacing calls and move
record fields after proving their old values are no longer observable. It must
preserve exception behavior, aliases, returned tuple lifetimes and event snapshots.
No such optimization or application-specific rewrite was added in this comparison.

The baseline preserves checked counter increments, Python-compatible integer
true division, canonical checksums, state accounting validation, per-file atomic
writes, synchronization, snapshot revalidation and no-replace bundle publication.
The shared input helper rejects hard links more strictly than the Python app;
timed fixtures use unaliased files. The compiler was unchanged, and all thirty
current generated compiler/application/binary fingerprints were rechecked.
