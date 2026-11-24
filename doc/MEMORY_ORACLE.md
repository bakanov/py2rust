# Memory management oracle

Status: the typed-IR oracle is implemented in `memory_oracle.py`. It proves
nonmutating application calls and argument-evaluation stability, and records
source-located blockers. Parameter ABI and liveness plans use IR in
`parameter_policy.py` and `liveness.py`. `move_safety.py` prepares transitive
resource checks for record types and owns the final move eligibility rule. The
transitional emitter still supplies current binding/view state. `view_policy.py`
prepares text/sequence slice and JSON-array view plans from IR. The independent
`efficiency_policy.py` prepares text indexing and lazy length caches. Other
optimization analyses still use AST inputs. `binding_policy.py` also prepares
loop source/item borrowing and binding writes; final loop consumption still
requires the liveness, move-safety and representation checks during emission. Alias/escape analysis and the hints below remain proposals,
not supported syntax.

This document describes the host compiler's IR policies. The portable native
compiler uses its own bounded write/retention and borrowing analyses, documented
in [self-hosting](SELF_HOSTING.md). Its existence does not implement the proposed
host ownership hints below.

## Responsibility

`argument_policy.py` owns runtime parameter passing contracts and the decision
to copy or borrow an argument from proved evaluation stability. It has no AST,
frontend or backend dependency. `library_contracts.py` uses those contracts
directly. `memory.runtime_argument_use` is a compatibility adapter: it obtains
prepared IR facts (or explicitly legacy AST facts) and calls that policy. This
keeps resource-state effects separate from the Rust parameter passing ABI.


The oracle decides whether each use copies, moves, shares a borrow, requires an
exclusive borrow, or needs shared ownership. The Rust emitter renders that plan.
Every decision should carry a source location and a reason. Unknown effects
require a conservative decision or an explicit unsupported-semantics diagnostic.
A type alone is insufficient: `list[str]` does not establish unique ownership.

Mypy's frontend supplies resolved symbols, inferred types, checked signatures,
and narrowing. It does not establish Rust lifetimes or prove absence of aliases.
Those proofs belong to our compiler-owned typed IR analyses.

## Required analyses

1. Build control flow including exceptional exits and resource cleanup. Compute
   liveness to allow moves only when no reachable later use needs the value.
2. Track places (locals, fields, indexed elements) and aliases. Distinguish Python
   object mutation from rebinding a local variable. Preserve observable sharing
   for supported operations, or diagnose unsupported sharing explicitly.
3. Summarize each function's effects: reads, mutations, retained arguments,
   returned aliases, and possible exceptions. Compute summaries to a fixed point
   across recursive calls. Runtime and native functions need explicit contracts;
   missing contracts must remain conservative.
4. Choose representations after those proofs: `&str`, `&[T]`, owned `String` and
   `Vec<T>`, or shared handles where semantics require them. `Arc` is justified by
   cross-thread sharing, not merely by uncertainty. Interior mutability needs a
   semantic reason and measured cost.
5. Verify the plan before emitting Rust. Borrow checking by rustc is an additional
   check; it cannot detect a semantically incorrect extra copy.

## Hints worth prototyping

Use ordinary `typing.Annotated` metadata so Python reference execution remains
possible. A potential interface is `Annotated[list[Message], Borrowed]` for a
parameter or `Annotated[bytes, Owned]` for a consumed buffer. Names and APIs are
not finalized.

- `Borrowed`: require a verified read-only, nonescaping access contract. Diagnose
  mutation and retained aliases. Returning a borrow requires an explicit origin
  relationship; the first version should reject it.
- `Owned`: request transfer of an existing allocation. Require dead subsequent
  uses and compatible aliases at each call site. Do not silently clone when a
  user explicitly requires transfer; report why the contract cannot be met.
- An explicit copy remains the way to request an independent snapshot. Mutable
  borrowed parameters should wait until exclusive-access analysis is reliable.

Hints must never disable checks, invent `'static`, or introduce unsafe Rust.
Keep the interface small: automatic analysis should handle ordinary code.

## First optimization targets and evidence

| Target | Required proof | Expected generated form |
| --- | --- | --- |
| Forwarding network buffers through helpers | Callees read but do not retain or mutate buffers | `fn inspect(data: &[u8])` |
| Sending a final response body | No subsequent use or observable alias | Move `Vec<u8>` into response |
| Parsing fields from a packet | Stable backing allocation and bounded lifetime | Borrowed slices instead of copied slices |
| Searching saved messages | No mutation during iteration | Borrow records and strings |
| Serialization | Serializer reads compatible representation | Serialize a reference without an intermediate JSON tree |

Existing analyses already cover portions of borrowing, last-use moves, slices,
and serialization. The next improvement should use interprocedural effects to
remove conservative copies around known read-only calls, rather than making
name-based guesses that a call is harmless.

For every optimization, compare Python and generated Rust behavior, including
aliases, mutation during argument evaluation, exceptions, and cleanup. Include
negative hint tests and optimized/unoptimized comparison. Measure allocations,
peak memory, throughput, and latency on buffers of several sizes. Compare with
handwritten Rust; prioritize slowdowns materially above the user's 2x threshold.
An emitted-code check establishes structure, not a measured speedup.

## Observed candidate: read-only fallback calls

A typed-pipeline probe generated this code for a function whose fallback simply
returns JSON null:

```rust
fn py__main__select(document: &rt::Json) -> rt::Result<rt::Json> {
    rt::json_get(&((*document).clone()), "selected", &(py__main__fallback()?))
}
```

The input is already borrowed, but the argument-evaluation barrier treats the
later fallback call as unknown and copies the entire document before looking up
one field. Probe sources and output are at `/tmp/memory-oracle-baseline.py` and
`/tmp/memory-oracle-baseline.rs`. That initial probe covered emitted code; the later allocation experiment below
measures the implemented improvement.

The desired automatic rule is to retain the input borrow when all later argument
expressions are proved unable to mutate or invalidate its place. The fallback
must still execute in its original order and propagate errors normally. Unknown
or native calls keep the conservative behavior. This requires effect information
suitable for borrow proofs; existing diagnostic cost summaries explicitly do not
authorize borrowing. No source hint should be necessary for this example.

The implementation and measurements below address this case. Broader borrowing
rules still require validation of aliasing and mutation of the earlier argument's
place; this initial proof conservatively rejects such mutation.

## Implemented proof and isolated measurements

The implementation, developed at `/tmp/py2rust-oracle-g1sknttn` and now integrated,
computes a least fixed point of
nonmutating application functions directly from the typed IR. It permits only
structural value types and a small explicit operation set. Unknown calls,
recursive cycles without a proof, native calls, resources, callbacks, record
operations, and stores remain conservative. Failure and allocation are permitted;
argument evaluation order is unchanged. The adapter carries the proof to the
existing runtime-argument borrowing decision, which still examines nested call
arguments independently.

The memory plan records each function's source location and whether the
proof succeeded. Rejections retain the first blocking expression or statement,
its location, and a reason such as `unproven_callee`, `unsupported_statement`, or
`unsupported_parameter_type`. These are conservative proof failures, not claims
that every rejected function actually mutates. Nested argument blockers retain
the nested call's identity. This information is available through the internal
plan and through each function's `memory_oracle` field in
`py2rust explain` output (typed is now the default). Adding provenance left the measured
example's generated Rust byte-for-byte unchanged.

The generated fallback example becomes:

```rust
rt::json_get(document, "selected", &(py__main__fallback()?))
```

Prototype checks cover transitive calls, mutating callees, mutation inside call
arguments, and a failing fallback. Twenty IR boundary cases check the proof's
conservative exclusions. These checks are not a completed soundness audit. A separate release-build
allocation harness compared baseline emission, optimized emission, and a direct
Rust lookup at three sizes, as recorded below.

A further observed limitation must remain explicit: mutable JSON parameters are
currently passed owned copies. A helper assigning `document["selected"]` therefore
changes its private copy, rather than preserving CPython's shared-object mutation.
This optimization does not change that policy. Mutable borrowing and ownership hints
must wait for a defined aliasing contract, checked at callers; copying is not a
general solution for preserving Python alias semantics.

### Allocation result (isolated prototype)

The release harness completed successfully with offline locked Cargo dependencies.
Each call returned the expected selected string. Failing fallbacks propagated the
expected error and left the input document intact. Allocations during input
construction and output printing were excluded; the table counts requested heap
bytes during lookup, not resident memory or allocator overhead.

| Unrelated payload rows | Baseline allocations | Baseline allocated bytes | Prototype allocations / bytes | Direct Rust allocations / bytes |
| ---: | ---: | ---: | ---: | ---: |
| 250 | 1,256 | 186,297 | 1 / 5 | 1 / 5 |
| 2,500 | 12,506 | 1,859,547 | 1 / 5 | 1 / 5 |
| 25,000 | 125,006 | 18,614,547 | 1 / 5 | 1 / 5 |

All three rounds at each size had identical allocation counts. Raw measurements:
`/tmp/py2rust-oracle-allocation.log`; harness and lockfile:
`/tmp/py2rust-oracle-g1sknttn/allocation-probe`. The harness uses an instrumented
system allocator solely for measurement. This is not unsafe code introduced by
the compiler. Single-operation nanosecond timings were collected but are too
short and sparsely sampled for a reliable throughput ratio; the demonstrated
result is removal of document-size-dependent copying. It does not establish a
whole-application performance improvement. The implementation has since been integrated after the unchanged-source baseline
passed all 120 applications. The integrated compiler then passed 40 frontend,
pipeline and new oracle/binding/replacement regression tests, plus four typed
web/chat/JSON application tests. All six existing optimization gates passed too.
The measurements remain scoped to the lookup example, not whole-application
performance.


## Prepared argument-evaluation proofs

`MemoryPlan.evaluations` now carries a proof for every source IR expression.
The adapter transports those facts to the existing argument-use policy instead
of requiring another Python-AST walk. Plain structural operations are checked
recursively; unknown/runtime/native calls and method mutations remain barriers.
A nested blocker retains its own source location and operation identity.
Legacy input and compiler-synthesized expressions without IR facts still use the
conservative AST implementation during backend migration.

Built-in `len` over supported structural values is now recognized as a stable
read. This is independent of arbitrary user-defined `__len__` methods, which do
not receive the proof. For example:

```python
def select(document: Json, keys: list[str]) -> Json:
    return json_get(document, "selected", len(keys))
```

Previously, the later `len` call forced a deep copy of `document`; generated
Rust now passes `document` directly to `rt::json_get`. The fallback value is still
evaluated eagerly and errors still propagate. `len(mutate(keys))` remains a
barrier because the inner call is unproved. These facts do not authorize
reordering, exclusive borrowing, alias preservation, or ownership transfer.

Focused validation passed 25 oracle, cleanup, readability and performance-gate
checks (`/tmp/py2rust-argument-memory-tests.log`). The expanded 28-test selection
also passed the eager bounds-error case, typed pipeline, chat/web/JSON applications
and default CLI checks (`/tmp/py2rust-argument-memory-app-tests.log`). The input
remains intact after the bounds error, even when its selected key exists. A test
disables the legacy AST evaluator while emitting the prepared example, ensuring
the source expressions use IR facts. This new length case establishes
copy removal in emitted code and behavioral parity; no new timing/allocation
measurement is claimed for it.

The complete example, rustfmt-formatted before/after Rust, matching implementation
files and focused logs are saved under
`$PY2RUST_BUILD_DIR/argument-evaluation-oracle/`.


## Prepared function parameter ABI

`parameter_policy.py` now computes borrow/own parameter decisions from typed IR,
and `MemoryPlan.parameters` retains them before emission. Supported read-only
value parameters can borrow; rebinding, indexed/field writes, deletion, receiver
mutation and heap operations keep owned parameters. Record and container value
semantics remain unchanged. Owned escapes are still materialized by the existing
use-site ownership policy.

Callback discovery also uses resolved IR function references. Runtime callbacks
retain their owned ABI even when the callback body only reads its argument.
Ordinary scalar and shared-resource parameter ABIs remain unchanged. A borrowed
record containing a resource is not a promise of purity or absence of shared
resource effects; representation and nonmutation proofs remain distinct.

The adapter transports prepared parameter decisions to emission. Typed input
bypasses the old AST signature analysis and callback scan; legacy input retains
them. Read-only builtin method contracts are shared by both paths. Statement
traversal still chooses conservative ownership for unsupported receiver effects.
The liveness migration is described below; move-safety guards and alias/escape analysis remain incomplete.

The initial 37-test regression selection passed
(`/tmp/py2rust-ir-parameter-tests.log`). New callback checks also uncovered a
literal-conversion gap: registered library calls now receive the same checked
nested JSON-literal conversions as project functions. Incompatible named lists
and callback signatures remain errors. A field-method fixture was outside the
current emitter subset; executable coverage uses supported field assignment,
while an IR-only case still verifies conservative ownership for reachable
receiver mutation. The corrected final selection passed 27 checks, including
compiled record/container behavior, callback ordering and failure joins, the typed
pipeline and all optimization gates (`/tmp/py2rust-ir-parameter-final-tests.log`).
The preceding broader run passed 37 checks; its two remaining failures were the
unsupported field-method fixture corrected in the final selection. These are
overlapping selections, not a count of distinct full-suite tests. Corpus
parameter-policy generation equivalence passed all **120 applications**, covering
2,441 functions, 25 callback functions, 2,996 borrowed parameters and 800 parameters
retaining owned/value ABIs. Generated Rust was byte-for-byte identical when using
the IR and legacy parameter policies on the same prepared programs. The compiler
fingerprint remained unchanged throughout the sweep.

The added dual-use callback case also passed: the same nonmutating helper is used
as a runtime callback and directly in a later argument, while an earlier argument
borrows the document. Its owned ABI still causes the required copy at that use.
The updated equivalence, execution and negative-contract selection passed four
tests (`/tmp/py2rust-ir-parameter-callback-tests.log`).

Evidence, verifier and matching compiler sources are archived at
`$PY2RUST_BUILD_DIR/parameter-policy-migration/` with compiler SHA-256
`a8e212cff8cd7af1eacc1f0e19389bd35e7ebd5bdb4511c2b575d10650fda67a`.
Generation equivalence does not establish final full-corpus native acceptance or
completion of the remaining ownership/backend migration.


## Prepared use-site liveness

`liveness.py` builds a control-flow graph from compiler IR and computes live-in
and live-out sets to a fixed point. It handles conditional branches, loop
backedges, break/continue edges and one-time evaluation of for-loop iterables.
Declaration discovery respects loop, resource and handler binding scopes.
`MemoryPlan.liveness` records source-located move/copy eligibility and reasons.

Repeated reads in one evaluation remain copies. Try/with regions conservatively
include all protected, handler and cleanup reads in an atomic barrier: this pass
does not introduce moves inside those regions. Eligibility is not permission to
move every value. Existing guards still exclude borrowed parameters, active views
and resource-containing types whose lifetimes must not be shortened.

The temporary adapter maps resolved IR read sites onto emitter nodes; it does not
recompute liveness. If a source place is duplicated and any use requires a copy,
the conservative decision wins. Legacy AST input retains its original pass.

The initial 35-test selection passed oracle, parameter, exception, readability and
performance-gate checks (`/tmp/py2rust-ir-liveness-tests.log`). The subsequent
26-test selection passed liveness execution with moves enabled/disabled, loop
snapshots, typed pipeline and chat/web/JSON applications, plus ownership diagnostic
gates (`/tmp/py2rust-ir-liveness-app-tests.log`). Tests disable the old AST liveness
analyzer and compare selected generated programs against its decisions. These are
overlapping selections. The generation-equivalence sweep passed all **120
applications** and 2,441 functions, producing byte-for-byte identical Rust under
the IR and legacy liveness policies on the same prepared programs.

The IR plans recorded 10,405 move-eligible reads and 34,042 conservative-copy
reads, including 6,273 reads in protected regions. These are liveness decisions,
not counts of generated Rust moves or allocations: final type/view/borrow guards
can still prohibit a move. The compiler fingerprint remained unchanged and was
rechecked before archiving the report, verifier, matching compiler sources and
focused logs at `$PY2RUST_BUILD_DIR/liveness-policy-migration/`.
Compiler SHA-256:
`d973454d1f7719755a349334e40f613393da34ec7c18dc7cda574b2c0f185bca`.

This establishes generation equivalence for this policy migration, not a final
full-corpus native acceptance run. Alias/escape analysis, cleanup-aware moves,
remaining move guards/views and the IR-native backend remain unfinished.

## Prepared move-safety policy

`move_safety.analyze()` checks all record fields to a fixed point before Rust
emission. Resource-free recursive records may move. An unknown or resource type
anywhere in a reachable record graph prevents the move, including resources
nested inside containers. This preserves the conservative lifetime behavior of
the previous emitter check; it does not imply that Rust itself cannot move a
resource handle.

A last-use decision is only a candidate. `can_transfer()` also requires a local,
owned value of a permitted type that is neither a borrowed view nor the backing
allocation of a live view. The emitter currently supplies that view state, using prepared slice/array
plans and the prepared text-index analysis; this is not yet full IR alias or
escape analysis. The adapter translates qualified
record/enum names and passes the prepared type plan to the backend.

`tests/test_typed_move_safety.py` verifies recursive resource reachability and
legacy code-generation equivalence, then disables the old emitter type check
while executing complete programs. All 12 focused tests passed: Python/Rust
comparisons cover text and JSON views, sequence snapshots, file cleanup and
recursive records with optimization both enabled and disabled. This phase is a
policy migration, not a measured runtime speed improvement. A further 29
parameter, liveness, exception and optimization-gate regression tests passed.
The complete 120-program native corpus was not rerun for this change.


## Prepared slice and array views

`view_policy.py` now plans borrowed text slices, sequence slices and JSON-array
locals directly from typed IR. Each selected view records its source location,
kind and original backing parameter. Chained slices retain that same backing
allocation. Both annotated and inferred local declarations participate.

The policy reuses the parameter mutation analysis and argument-evaluation
proofs. Rebinding, receiver mutation and exception-handler bindings disqualify
unstable values; a view cannot be selected if later writes require an independent
snapshot. Sequence slice bounds and JSON-array arguments must pass the existing
effect checks. Owned results are still materialized where they escape. These
rules preserve the existing subset's value semantics, not general CPython alias
semantics.

The backend consumes this prepared plan through the temporary adapter. Legacy
AST view scanners remain for explicit legacy compilation and comparison tests.
Text-index and cached-length decisions are prepared separately by
`efficiency_policy.py`.

The focused suite passed 11 tests, and the final expanded suite passed 40 tests
covering views, parameters, move safety, liveness and optimization gates. Native
view cases disable all three legacy view scanners and run both optimization
modes, comparing Python and Rust behavior for Unicode slices, JSON views,
sequence snapshots, bounds and owned escapes. This is a migration of existing
optimization decisions, not a measured new speedup.

The final generation sweep compared all 120 applications and 2,441 functions
against the legacy view scanners and emitted identical Rust. The prepared plans
selected 9 text views, 18 sequence views and 99 JSON-array views across that
catalog. These are static decisions, not measured allocation counts. Compiler
fingerprint: `ce4a07dca1941209c27ddd4a91dedff2386d3d080a18abc56142aebcbb4968d5`.
Matching sources, verifier, report and logs are archived at
`$PY2RUST_BUILD_DIR/view-policy-migration/`. The fingerprint remained
unchanged during the sweep. This generation-only comparison does not establish
current native acceptance for all 120 applications.


## Collection detachment facts

`mutation_policy.py` identifies known receiver mutations and heap intrinsics
that can detach or reorder a selected collection element. Argument-evaluation
facts retain these source-located hazards for each expression and its operands.
The adapter maps their resolved binding names; indexed append/extend and nested
assignment checks consume the facts instead of scanning reconstructed ASTs.

This preserves the owned-value subset's rejection of operations that would need
Python object alias identity after an element is removed. It is not a complete
alias or exclusive-access analysis. Absence of a recorded local mutation does
not prove a call pure; unknown argument effects remain conservative under the
separate evaluation policy.

The 29-test selection passed, covering rejection and original source locations,
native nested writes in both optimization modes with the old scanner disabled,
bounds/depth/large-grid checks, evaluation/failure order, argument memory, views
and optimization gates. Matching evidence is archived under
`$PY2RUST_BUILD_DIR/mutation-policy-migration/`; verification metadata
records compiler fingerprint and scope. No full suite or corpus sweep was run
for this revision.


## Immutable string transformations remove JSON snapshots

`libraries/method_effects.py` supplies reviewed contracts for supported string
method/arity combinations. The receiver must resolve to `builtins.str`, and the
oracle must independently prove every operand's evaluation stable. This covers
both direct method calls and application helpers composed from proved operations.
Unknown calls and mutating operands still block borrowing. Methods can allocate
or fail; their execution stays eager and in the original order.

For example, `json_get(document, "selected", text.strip())` previously cloned the
whole document before computing the fallback. The new proof permits borrowing
`document`. An empty-separator `split()` still raises even if the selected key
exists; `parts.pop().strip()` and a logging helper followed by `.strip()` retain
the conservative snapshot.

A controlled allocator probe compared the same compiler with the new string
contract disabled, enabled, and equivalent handwritten Rust. Each lookup returns
`"small"` from an existing key and eagerly trims `" fallback "`. Payload rows are
unrelated to the result and are constructed outside the measured region.

| Payload rows | Before: allocations / bytes | After: allocations / bytes | Handwritten: allocations / bytes |
| --- | --- | --- | --- |
| 250 | 1,257 / 186,305 | 2 / 13 | 2 / 13 |
| 2,500 | 12,507 / 1,859,555 | 2 / 13 | 2 / 13 |
| 25,000 | 125,007 / 18,614,555 | 2 / 13 | 2 / 13 |

All three repetitions matched at each size. These are allocation calls and
requested allocation bytes in a debug build, not elapsed-time, peak-memory or
whole-application throughput measurements. The fallback allocation and owned
result remain; the unrelated input-tree copy is eliminated.

All 21 selected tests passed, including before/after emitted-code checks,
interprocedural propagation, nested-effect blockers, native value/failure-order
comparisons in both optimization modes, collection safety, argument memory and
gates. Source, generated Rust, handwritten harness, Cargo lockfile, CSV, logs and
compiler snapshot are at
`$PY2RUST_BUILD_DIR/string-method-oracle-2h2nh52c/`, fingerprint
`037f48947c4c378aaf1fad2460e75982583cb14ce9df77ac40224d3191ddf51e`.
No full suite or corpus sweep was run for this revision.

## Implementing checked hints incrementally

Keep automatic inference as the default. A hint should constrain the oracle's
plan, not force a Rust token such as `&` or `.clone()` into the output.

A first implementation should preserve `typing.Annotated` metadata at the source
boundary before mypy erases it, resolve the metadata symbol rather than matching
its spelling, and attach a compiler-owned contract to the corresponding IR
parameter. Python reference execution needs inert, importable marker definitions.
Unsupported metadata must produce a source-located diagnostic rather than being
silently ignored when it is a py2rust ownership contract.

Validate contracts after parameter effects and liveness, and before rendering:

1. `Borrowed` requires read-only, nonescaping use on every path. Returning or
   storing a reference requires an origin/escape analysis we do not yet have;
   reject these cases in the first implementation. Allocating an independent
   result from the borrowed input remains allowed.
2. `Owned` requires an existing compatible owned representation, no live aliases,
   and no reachable subsequent use (including exception handlers). A required
   transfer that would need a clone is a compilation error with the blocking use.
3. Native Rust imports must supply reviewed retention/mutation contracts before
   they can participate in either proof. Unknown native calls remain barriers.
4. Run a verifier over the selected plan, retaining the proof reason and source
   location for diagnostics. A successful Rust borrow check does not establish
   that the compiler preserved source semantics.

Do not introduce mutable borrowing or lifetime syntax in the first hint API.
The immediate prerequisite is explicit escape and alias summaries; the existing
nonmutating summary alone is insufficient. Tests must include retained arguments,
returned aliases, callbacks, recursive calls, exception-path uses, and rejected
transfers, in addition to native/reference parity for accepted programs.


## Committed ownership explanations

`move_safety.owned_boundary` owns the diagnostic decision for a committed owned
use. Emission and diagnostics share `MoveContext` and the transfer predicate.
The emitter supplies current binding/view facts, including whether a string owns
backing storage for a Unicode index. The policy distinguishes materializing a
borrowed value from copying owned backing storage and preserves resource and
exception-path explanations. It does not extend the alias/escape proof.

The extraction passed 32 selected tests. Captured Rust and diagnostics for the
move/copy/materialization/cleanup example are unchanged. This is organizational
work, with no claimed allocation or throughput improvement.
