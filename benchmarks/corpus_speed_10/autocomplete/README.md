# Additional autocomplete comparison

Raw report filenames below refer to [local archived reports](../../REPORTS.md#local-archive),
not files shipped in this repository. Source programs and Markdown summaries remain in Git.

The unchanged Python application and compiler were compared with handwritten
complete Rust using the same release settings and pinned dependencies. Execution
order rotates after warm-up over fresh identical inputs. Independent dictionary
oracles and complete-output equality check every invocation. Compilation, fixture
construction and checking are untimed.

| Size | Generated median (ms) | Handwritten median (ms) | Ratio |
|---|---:|---:|---:|
| Small | 28.41 | 21.14 | 1.34× |
| Large | 2,210.39 | 30.70 | **72.00×** |

The large workload fails the strict threshold; it has no accepted exception.
`results.json` retains 60 timed complete jobs, 15 per executable and size, with
raw wall/CPU/RSS observations and source/binary fingerprints. Times include startup,
serialization and durable publication, not just trie operations.

Workloads begin with 8/128 Unicode terms and execute 42/1,154 commands. They mix
PUT, case-normalized HIT, GET, DELETE, paginated prefix suggestions, EXPORT and
INSPECT. Native traversal borrows nodes, updates mutate the owned trie, and ranking
sorts borrowed matching nodes by descending usage and ascending normalized key.
Cached node and terminal counts update along the changed path; deletion prunes
empty branches. Normalization retains NFKC followed by casefold using the shared
pinned Unicode helpers.

`checks.json` records 312 additional complete jobs against the independent
normalized-dictionary oracle: randomized traces, normalization collisions and
Unicode forms, ranking ties, pagination, subtree pruning, split-and-resume replay,
malformed snapshots, usage/lifetime limits, 8,192-node capacity, text/byte bounds,
output budgets and unwritable destinations. The checked native executable hash
matches both measured sizes.

## General optimization opportunities

Source inspection finds three recurring copy patterns:

```rust
let result: (Index, rt::Json) = apply(index.clone(), command)?;
let count = (index.root.clone()).nodes.clone();
```

Lookup also clones the complete root and then each selected subtree:

```rust
fn find(root: &Node, key: &str) -> rt::Result<Node> {
    let mut current: Node = (*root).clone();
    // For each character:
    current = current.children.get(&letter).ok_or("missing dict key")?.clone();
    // ...
}
```

Recursive updates additionally clone child maps. These are potential contributors
to the large gap, based on source inspection rather than allocation profiling.
A general compiler solution needs borrowed recursive traversal and return-view
provenance, direct scalar-field access, and ownership transfer into self-replacing
updates. It must preserve independent values when aliases escape, the owned empty
lookup fallback, exception behavior and historical event snapshots. Replacing all
clones indiscriminately would not establish those properties. No compiler changes
or application-specific rewrites were introduced for this comparison.

The baseline preserves preview/write modes, saved-state validation and rebuilding,
canonical checksums, exact event bytes, per-file atomic writes, synchronization,
input revalidation and no-replace bundle publication. The shared input helper
rejects hard links more strictly than the Python application; timed inputs are
unaliased. Fault-injection/pause hooks and their associated checks are excluded.
All thirty current generated compiler/application/binary fingerprints were checked;
previous compiler measurements remain applicable.
