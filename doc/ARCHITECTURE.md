# Architecture

The default compiler uses the typed Python frontend shared by mypy and mypyc.
It does not use mypyc's CPython-oriented low-level IR or runtime. The reviewed
pure-Python mypy dependency is source-pinned; generated applications are
standalone Rust executables without a Python interpreter.

A separate portable compiler in `compiler/native/` parses source with the native
Ruff bridge, performs subset type/ownership analysis, traverses the shared IR
exchange and emits Rust through the production rules. It self-reproduces from
Python sources. It has narrower language coverage than the host path described
below; see [native compiler](SELF_HOSTING.md).

## Compilation stages

1. `compiler/project.py` discovers local Python packages and Rust modules, resolves
   the entry point, and records source mappings. `rust_imports.py` reads native
   Rust signatures using tree-sitter-rust. Local modules precede standard-library
   fallbacks.
2. `frontend/mypy.py` type-checks explicit project sources against generated
   library/native stubs without executing application code. Upstream AST nodes
   and type objects remain inside the frontend boundary.
3. `frontend/lowering.py` validates the supported subset and creates immutable
   nodes from `compiler/ir.py`: modules, functions, records, enums, statements,
   expressions, types and source locations. Unsupported constructs are diagnosed;
   they do not silently fall back to the legacy frontend.
4. `pipeline.prepare_typed()` computes memory, exception, efficiency, effect and readability plans on that IR.
   `PreparedProgram` retains the IR, plans and native declarations; emission can
   be repeated without parsing, type checking or rediscovering Rust interfaces.
5. `pipeline.emit_program()` currently uses `backend/legacy_adapter.py` to bridge
   IR and prepared decisions into `service.py` and its focused backend adapters. This temporary
   AST reconstruction is still present. Remaining ownership and optimization
   analyses use that AST; the backend is not yet fully IR-native.
6. Project packaging formats Rust, copies the runtime and native modules, writes
   the Cargo manifest/lockfile and protects managed outputs. Packaged native
   references are relative so generated projects can be relocated.

## Policy boundaries

| Responsibility | Implementation |
| --- | --- |
| Memory management | `argument_policy.py` owns runtime passing contracts and argument copy/borrow selection; `memory_oracle.py` proves nonmutating IR calls and argument-evaluation stability; `parameter_policy.py` selects parameter ABIs and callbacks; `liveness.py` plans last uses on IR; `move_safety.py` checks resource-bearing types, final move eligibility and committed ownership explanations; `view_policy.py` plans borrowed text/sequence slices and JSON arrays; `binding_policy.py` plans loop source/item borrowing; `mutation_policy.py` records collection detachment hazards; `place_policy.py` selects local borrowed representations from type and stability facts; text-index representations are selected by the efficiency policy |
| Exceptions and cleanup | `exception_policy.py` prepares termination and protected-jump decisions on IR and owns resource contracts; `backend/exception_emission.py` renders handlers, cleanup and resource scopes |
| Modules and projects | `project.py`, `project_policy.py`, `rust_imports.py` and `frontend/native.py` handle discovery, layout, record ordering, native interfaces and packaging |
| Efficient code | `efficiency_policy.py` prepares Unicode text indexes, lazy length caches and string self-appends on IR; `effect_policy.py` prepares direct effects and the call graph on IR, then combines emitted helper choices; `effects.py` owns runtime cost contracts; other `optimization.py` passes still need migration |
| Readable Rust | `readability.py` plans exhaustive tail branches, return forms and mutable bindings using `binding_policy.py`; `backend/readable_emission.py` adapts those choices to portable `rules/control_flow.py` renderers |
| Standard-library replacement | `library_contracts.py` and `libraries/` supply explicit signatures, runtime mappings and frontend stubs; `libraries/serialization.py` owns JSON eligibility and output-representation selection |
| Third-party replacement | `libraries/third_party.py` is a separate registry with executable synthetic-contract tests; no real third-party replacements are registered yet |

For typed input, exception decisions are consumed from the prepared plan.
`exceptions.py` retains the legacy AST implementation and the temporary bridge;
Rust rendering does not determine whether a protected block terminates. Unknown
loop termination stays conservative. Cross-boundary loop jumps remain unsupported
and are rejected before emission, with the original source location.

The initial memory oracle removes copies across proved nonmutating helper calls.
Alias/escape analysis and checked ownership hints remain incomplete; see
[Memory oracle](MEMORY_ORACLE.md). Extraction of policy modules is not evidence
that all backend migration or semantic work is complete.

Effect diagnostics use the prepared call graph and explicit runtime-helper
selections recorded during emission. They propagate recursion, failure, I/O,
resource/global state and unknown effects to a fixed point. Parameter writes
remain local to owned parameter values. These symbolic diagnostic facts do not
authorize borrowing or reordering; the memory oracle retains its separate proofs.

## Runtime and validation

`compiler/service_runtime/` contains the native runtime and pinned Cargo
dependencies. `py2rust/stdlib.py` and its private helpers provide Python reference
behavior for comparison tests.

`examples/corpus/` holds 120 multi-module applications. `tools/corpus.py` compiles
and compares them using independent acceptance checks in `tools/corpus_checks/`.
`tools/check_*.py` exercises cross-engine interoperability. Tests cover the subset,
runtime, project linking, native boundaries, chat and policy plans. Historical
corpus results are valid only for their recorded compiler fingerprints; see
[Frontend migration](FRONTEND_MIGRATION.md) for evidence and outstanding work.

Paper Plane's application policy is Python compiled to Rust. Its JavaScript
handles browser events and the Electron desktop lifecycle.


## Explicit rule migration

`rules/` contains portable string, byte-method, numeric, conversion, condition, record,
collection, collection-method, ordering, comparison, iteration, assignment, control-flow, access and owned-type representation rules. Selection and rendering are explicit functions on
ordinary typed values; production modules are compiled and executed in
`tests/test_rule_bootstrap.py`. The string selector also supplies the operation-level
contract used by the memory oracle; operand evaluation still needs its own proof.
The emitter adapts AST/type facts rather than duplicating these mappings. Its
transitional `Type` and `Expr` records live in `backend/values.py`; recursive
owned-type rendering delegates to `rules/types.py`.

See [Translation rules](TRANSLATION_RULES.md) for the agreed design, remaining
families and the staged self-hosting boundary. The Python/mypy frontend and AST
adapter are host-compiler dependencies. Rule bootstrap checks establish individual
module portability; the native compiler has separate source self-rebuild checks.

## Host adapter and packaging boundaries

`service.py` remains the transitional AST expression/statement adapter. Its
`compile_tree` delegates to `backend/module_emission.py`, which coordinates
function state, memory plans, source comments and module output.
`backend/declarations.py` separately validates imports, module constants, enum and
function declarations, and the main guard. These modules consume the same typed
plans as before; they are host-side adapters, not portable rule modules.

`project_output.py` prepares the runtime, Cargo manifest/lock and emitted main
source without importing the compiler or either frontend. Both the service writer
and whole-project builder use it. Whole-project ownership markers, native Rust
sources, destination validation and protection of hand edits remain in
`project.py`. `service_cli.py` handles the compatibility service command, with a
small forwarding entry point retained in `service.py`.

This separation permits a future native emitter to hand Rust text to packaging
without loading mypy. It does not make Python AST traversal or filesystem
packaging self-hosted; those remain explicit porting boundaries.

## Expression adapter layout

`backend/expression_emission.py` dispatches source AST shapes without a dynamic
plugin registry. Its specialized adapters keep related validation together:

- `value_emission.py`: literals, local ownership-aware reads, and typed collection
  construction, including JSON coercion and homogeneous-type checks.
- `access_emission.py`: attributes, enum members, indexing and slicing; it supplies
  validated facts to the access/record rules.
- `operator_emission.py`: unary/binary operators, conditionals and comparison
  chains; it supplies operand types and memory proofs to semantic rules.

Each adapter receives the explicit compiler context, preserves original AST nodes
for diagnostics/proof lookup, and returns `backend/values.py::Expr`. The normal
`ServiceCompiler.expr` entry point still applies conversions and owned-boundary
accounting; recursive adapters call that entry point rather than bypassing it.
`rust_text.py` owns host string-literal escaping and is shared with project linking.
These adapters still depend on Python ASTs; the portable native frontend/emitter uses a separate syntax boundary and
shares the production rule modules.

## Statement adapter layout

`ServiceCompiler.statement` retains explicit source-shape dispatch. Larger handlers
are grouped by the state they manage:

- `backend/binding_emission.py`: typed local declarations, assignments and deletion;
  preserves borrowed-view validation and owned-boundary accounting.
- `backend/protected_emission.py`: resource scopes and exception handlers; preserves
  local scope restoration, active-error tracking and pending-return handling.
- `backend/loop_emission.py`: range and collection loops; consumes iteration plans
  and restores the enclosing local/borrowed-parameter state.

These host adapters validate source constructs before calling portable renderers.
They do not infer a second ownership policy or replace the typed memory plans.
Recursive blocks still enter `ServiceCompiler.block` and `statement`, preserving
source-node identity and tail-return decisions. Call overload selection is described below.

## Call adapter layout

`backend/call_emission.py::emit_call` is an explicit ordered dispatch table written
as ordinary Python branches. Record constructors and sorted calls retain their
keyword handling before the general keyword rejection. Imported library names,
callback APIs, declared functions and method fallback retain their previous
precedence. `ServiceCompiler.call` forwards through this single entry point.

- `scalar_call_emission.py` handles extrema, ord/len, scalar conversion, abs and
  print; conversion, length and unary decisions use the portable rule families.
- `constructor_emission.py` validates byte/sequence/set constructors and empty
  annotated collections before selecting their representations.
- `callback_emission.py` validates network/parallel callback signatures and ordinary
  function arguments, preserving the memory oracle's argument borrowing decisions.
- `module_call_emission.py` handles CRC and heap operations, including argument
  evaluation before borrowing mutable heap storage.

The handlers accept only the dispatch facts they use, rather than a universal
argument bag. They continue to use compiler expression entry points, so source
locations, conversions, runtime-effect selection and ownership accounting remain
attached to the original source nodes. These are host adapters, not additional
claims of portable rule coverage.
