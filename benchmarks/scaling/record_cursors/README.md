# Borrowed recursive traversal: autocomplete

Raw report filenames below refer to [local archived reports](../../REPORTS.md#local-archive),
not files shipped in this repository. Source programs and Markdown summaries remain in Git.

Historical measurement stage; see the [final acceptance audit](../final/README.md) for the current status.

This is intermediate progress on the active scaling goal. Python applications and
handwritten baselines remain unchanged. The rule applies to record types and
checked projections generally; it does not recognize trie or application names.

## Lowering and ownership

A record local initialized from an already-borrowed record parameter may become a
reference cursor when all subsequent assignments descend through its fields or
indexed collections. The analysis rejects mutation through the cursor, method
calls on it, other rebindings and resource-containing records. Checked lookup
errors remain in place. Returning or storing the cursor materializes an independent
owned value using the existing ownership boundary.

Illustrative generated traversal before:

```rust
let mut current: Node = root.clone();
// Within the traversal loop:
current = current.children.get(&letter).ok_or("missing dict key")?.clone();
// At the owned return boundary:
Ok(current)
```

After:

```rust
let mut current: &Node = root;
// Within the traversal loop:
current = current.children.get(&letter).ok_or("missing dict key")?;
// At the owned return boundary:
Ok((*current).clone())
```

The cursor no longer copies every ancestor subtree. This does not yet provide
borrowed function results or optimize recursive functional updates. The proof
currently lives in the host emitter and applies to typed and legacy frontends.

## Matched measurements

The previous executable is the preserved first scaling patch (owned boundaries).
The new executable includes the intervening general lowering changes as well as
record cursors; this is not an isolated single-rule ablation. The harness rotates
old, new and handwritten release executables with one warm-up and 15 timed runs
per engine and size. Every job passes an independent oracle and complete-output
equality. Compilation/checking are excluded; startup and durable I/O are included.

| Size | Previous generated (ms) | New generated (ms) | Handwritten (ms) | New/native |
|---|---:|---:|---:|---:|
| small | 21.51 | 19.96 | 16.68 | 1.20× |
| large | 1435.33 | 858.78 | 24.93 | 34.45× |

The large matched run is approximately 40% faster but remains far above 2×.
`results.json` retains all 90 timed observations and fingerprints; `builds.json`
identifies the generated application and compiler. These are historical results
for that fingerprint, not a claim about later compiler versions.

The full generated autocomplete oracle passed: 41 traces (32 seeded), 23 split
replays, 92 invalid-input checks, 32 state checks, 16 capacity checks and 22
publication checks. `checks.json` records the binary hash and 337 calls through
`Application.run`; publication checks can also launch subprocesses directly, so
that count is not a total process count.

The final targeted regression run passed 21 cases across cursor traversal, record
field projections and recursive records. Coverage includes typed/legacy frontends,
optimization on/off, missing descents, exception-visible cursor state, owned
snapshots and mutation fallback. Black, Ruff and the whitespace diff check passed.

## Remaining work

The generated lookup still clones the returned subtree. Recursive updates copy
child maps and selected children; retained scalar reads also prevent some owned
nodes from moving. The command loop preserves old state across checked failures.
Removing these costs requires borrowed-result provenance, safe ownership transfer
or persistent representations, with tests for independent snapshots and errors.
Autocomplete's scaling problem is not solved by this patch.
