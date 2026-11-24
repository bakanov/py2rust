# Typed frontend migration

The target is a compiler using the typed Python frontend shared by mypy and
mypyc, with independent policies for memory, exceptions, modules, efficiency,
readable Rust, standard libraries and third-party libraries. Generated programs
must remain standalone Rust without a Python interpreter.

The shared mypy/mypyc typed frontend is the default host CLI path. Independent
policy modules prepare ownership, exceptions, effects, efficiency and readability
plans on compiler-owned IR. The host backend still adapts this IR to the existing
AST emitter. The separate [native compiler](SELF_HOSTING.md) self-hosts a narrower
subset; it does not compile or embed mypy.

## Implementation

1. `pipeline.compile_project` discovers Python modules, namespace packages and
   native Rust imports through the existing project resolver. `frontend/native.py`
   derives signatures from parsed Rust exports. `compile_typed` also accepts
   explicit module sources.
2. `frontend/scopes.py` normalizes subset block bindings before semantic analysis.
   `frontend/coercions.py` makes supported JSON conversions explicit through
   isolated mypy hooks. `libraries/stubs.py` supplies runtime signatures from the
   replacement contracts.
3. The supplied mypy frontend resolves names and produces analyzed nodes and
   expression types. `frontend/lowering.py` translates them into compiler-owned
   `ir.py` nodes with types and source locations.
4. The IR represents structured expressions, blocks, functions, records, enums,
   runtime/native calls, JSON coercions and resource scopes. Unsupported operations
   and unresolved types are rejected; there is no fallback to untyped source.
5. `project_policy.ordered_records` orders declarations by dependencies in field
   types, including nested containers. It preserves direct self-reference and
   reports unsupported mutual record cycles with a source location.
6. `backend/legacy_adapter.py` temporarily reconstructs input for `service.py` from
   the IR, without reparsing application source. This retains the mature runtime
   and ownership implementation while the backend and analyses migrate.
7. `create_project(..., frontend="typed")` uses the typed pipeline with the shared
   managed-output packager, Rust formatting, source maps and native-source copying.
   Generated native module references are relative to packaged wrappers. A compiled
   relocation test moves the source and output directories before building and
   running a project with nested Rust modules. Direct `compile_typed` emission can
   still reference original native paths; use project packaging for relocation.

## Subset semantics and type handling

Block-local declarations and loop targets receive collision-free names. This
includes inferred locals in the typed pipeline. Loop targets shadow outer
bindings; the outer value remains unchanged afterward. This existing subset rule
intentionally differs from CPython and has a compiled regression check separate
from Python parity tests. See [subset scope rules](service-subset.md).

JSON conversions apply at supported annotations, assignments, returns, record
constructors, runtime/project calls, list appends and indexed stores. Literal
containers recurse according to declared types. Literal function arguments retain
normal type checking; nonliteral containers are not weakened to `list[object]`.
Resources remain nonserializable, including inside JSON containers.

Conditional JSON values convert the selected branch explicitly. Empty container
branches therefore have JSON meaning without guessing an element type. Known JSON
null comparisons are normalized because nominal `Json` can contain null. The
attribute hook activates only for fields resolved as `Json`, handles either
operand order, and leaves ordinary optional-field narrowing unchanged. Inserted
conversion nodes are compiler-tracked and bound to the runtime conversion symbol;
user casts do not acquire this behavior.

Mypy omits some unreachable-tail expression types. Lowering retains intrinsic
scalar/tuple types, explicitly declared variable types, and return-signature
context for empty containers. It still rejects arbitrary untyped expressions.
Literal unions normalize only when all variants erase to the same supported type.

Library contracts describe fixed runtime signatures, callable parameters,
severity arguments and trailing integer defaults. CRC32 supports its default seed
and bytes/bytearray input through runtime, zlib and binascii spellings. Generic
heap operations remain typed intrinsics. Sorting preserves key/reverse keywords
and module-qualified callbacks. Generic user-function keyword arguments remain
outside current call lowering.

## Functional boundaries

| Responsibility | Current implementation | Remaining work |
| --- | --- | --- |
| Memory oracle | `memory_oracle.py`, `parameter_policy.py`, `liveness.py`, `move_safety.py`, `view_policy.py`, `binding_policy.py`: IR proofs, parameter ABIs, last uses, move guards, views and loop borrowing | Migrate remaining AST decisions; add alias/escape analysis and verified hints |
| Exceptions | `exception_policy.py`: prepared IR termination and protected-jump proofs, resource contracts; `backend/exception_emission.py`: Rust rendering | Remove transitional AST bridge and complete final acceptance |
| Projects | `project.py`, `project_policy.py`, `rust_imports.py`, `frontend/native.py`, `pipeline.py` | Broader packaging/source-map validation and default entry points |
| Efficiency | `efficiency_policy.py`: prepared Unicode indexes, lazy lengths and string builders; `effect_policy.py`: IR effects and call graph; `effects.py`: runtime cost contracts; `optimization.py`, `diagnostics.py`: other passes/reporting | Migrate remaining AST passes and preserve optimization gates/measurements |
| Readable Rust | `readability.py`: prepared tail-branch, return-form and mutable-binding decisions; `backend/readable_emission.py`, `rust_ast.py`: rendering | Migrate remaining style decisions and remove temporary AST reconstruction |
| Standard libraries | `library_contracts.py`, `libraries/`, generated stubs | Migrate remaining special-case dispatch and complete contract coverage |
| Third-party libraries | Separate `libraries/third_party.py` registry | Reviewed replacements and tests; the registry is currently empty |

The [memory oracle design](MEMORY_ORACLE.md) proposes checked ownership hints.
They are not implemented syntax. Hints must not override lifetime, aliasing,
mutation, or exception-cleanup checks. Extracting helpers alone does not complete
this part of the goal or establish a speedup.

## Dependency and installation

The reviewed pure-Python frontend version, source inventory checksum and immutable
upstream commit are recorded in `compiler/frontend/mypy-source.json` under the
`py2rust/` package. `tools/build_frontend_wheel.py --fetch --output DIRECTORY`
downloads that commit, validates the source before running build hooks and builds
the wheel. A matching local checkout can be supplied instead of `--fetch`.
See [development setup](DEVELOPMENT.md) for installation commands. Compiled mypy
visitors are not interchangeable with this dependency.

## Verification and remaining work

Selected regression entry points are `tests/test_mypy_frontend.py`,
`test_typed_pipeline.py`, `test_typed_parameters.py`, `test_typed_effects.py`,
`test_project.py` and `test_interop_frontend.py`. They cover frontend lowering,
prepared plans, project/native linking and routing of interoperability evidence.
The application runner defaults to the typed frontend; select catalog IDs for
focused acceptance. A generation-only comparison is not a native behavior test.

Earlier migration runs recorded 1,024 regression checks, 120 complete applications
and 86 interoperability scripts at their respective fingerprints. These are
historical checkpoints, not current acceptance of arbitrary later revisions.
Use current test output and fingerprinted reports when reviewing a change.

Remaining host work includes removing the AST emission bridge, general alias and
escape analysis, checked ownership hints and reviewed real third-party library
replacements. The registry boundary exists, but its presence alone is not package
support. See [architecture](ARCHITECTURE.md), [memory oracle](MEMORY_ORACLE.md),
[subset semantics](service-subset.md) and [verification](VERIFICATION.md).
