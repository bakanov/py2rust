# Borrowed values while constructing JSON dictionaries

Raw report filenames below refer to [local archived reports](../../REPORTS.md#local-archive),
not files shipped in this repository. Source programs and Markdown summaries remain in Git.

Historical measurement stage; see the [final acceptance audit](../final/README.md) for the current status.

Newly initialized empty `dict[str, Json]` locals may use borrowed values while a
loop only writes them from stable JSON-list iteration items. Final entries become
independent owned JSON values once after the loop. Replacing a predecessor many
times therefore no longer clones and drops its full JSON record every time.

The analysis rejects maps read or passed elsewhere during construction, nonempty
initial maps, changing backing lists/items and functions with exception handlers
or context managers. Backing iteration cannot consume its list while views remain
live. Multiple maps and sources are supported under the same proof. Owned output
materialization preserves insertion order and independent value semantics.
Empty loops and early loop exits still materialize their final contents.

The host emitter selects this from types and uses, without application-specific
names. It preserves checked key/value evaluation order and leaves function
signatures unchanged. Broader borrowed-return analysis is not implemented.

## Matched results

Runs rotate previous/current/handwritten release executables, with warm-up and
15 timed runs per engine and size. All pass the independent oracle and complete
output equality. Startup and output I/O are included; compilation/checking are not.

| Size | Previous generated (ms) | New generated (ms) | Handwritten (ms) | New/native |
|---|---:|---:|---:|---:|
| small | 10.79 | 10.76 | 10.33 | 1.04× |
| large | 105.90 | 75.61 | 18.56 | 4.07× |

The matched large improvement is approximately 29%. `results.json` retains all
90 timings and fingerprints; `builds.json` identifies the compiler/application.
The complete route oracle passes: 11 jobs and 219 answers with route/cycle witnesses
and preservation of existing reports on invalid input (`checks.json`).

Nine targeted cases passed for borrowed maps and stable map positions, including
both frontends with optimization on/off, duplicate keys, insertion order, zero
iterations, early exits, two maps, reads during construction, changing sources,
nonempty initial maps, exception-visible partial writes and independent owned
values after materialization. Formatting, lint and whitespace checks passed.

The user subsequently accepted a large-workload threshold below 6×. The final
three-program audit records acceptance separately; this summary describes the
matched evidence for this particular patch, with raw files in the local archive.
