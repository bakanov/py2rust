# Explicit translation rules and self-hosting preparation

Status: rule restructuring and self-hosting preparation verified at the archived
`final-acceptance` revision. Native compiler development is now active; see
[Self-hosting](SELF_HOSTING.md). Later source changes require their own evidence. String operation selection and ordinary string-call
rendering now live in `py2rust/compiler/rules/strings.py`; binary numeric rules
live in `rules/numeric.py`. Runtime field and guarded dictionary lookup rules
live in `rules/records.py`; scalar conversion and condition rules live in
`rules/conversions.py` and `rules/conditions.py`. Collection and sorting decisions
live in `rules/collections.py` and `rules/ordering.py`; owned type representations
live in `rules/types.py`. Membership and ordinary comparison rendering live in
`rules/comparisons.py`; loop representations live in `rules/iteration.py`; mutation rendering lives in
`rules/assignment.py`; byte-buffer methods live in `rules/byte_methods.py`; collection overloads live in
`rules/collection_methods.py`; ordinary control-flow rendering lives in
`rules/control_flow.py`; indexing and slicing live in `rules/access.py`. Expression, statement and call handlers are separated into focused host adapters
described in [Architecture](ARCHITECTURE.md). The compiler is not yet self-hosted;
the full 1,095-test regression suite and selected application acceptance pass.

## Decisions from the design review

Adopt these recommendations from the supplied DeepSeek conversation:

- Specify a typed Python-like subset and reject unsupported constructs with their
  source locations. Do not imply arbitrary Python compatibility.
- Make each translation's matching conditions, output form, semantic restrictions
  and test cases explicit.
- Retain runtime helpers where Python semantics differ; simplify only with an
  applicable proof, not because similar-looking Rust happens to compile.
- Differentially execute positive and negative cases, including operand order,
  eager defaults, Unicode, numeric boundaries, sorting keys and cleanup.
- Infer ordinary ownership automatically. Keep explicit ownership contracts small
  and checked; their eventual implementation needs alias and escape proofs.
- Keep rules and their data independent of the Python frontend so that the
  compiler core can eventually compile to Rust.

Do not adopt blanket `Rc<RefCell<T>>`, a Python interpreter fallback, silent
overrides of ownership contracts, or borrow-checker errors as proof of source
semantics. Existing owned-value container semantics are an explicit language
choice; changing them to shared-object semantics would require a separate,
deliberate migration of the reference implementation and applications.

## Shape of a rule

Use ordinary typed functions and simple records, not a reflection-based plugin
framework or a new pattern-matching language. Each family has:

1. **Input facts:** resolved operation, receiver/operand types and required proof
   facts. AST objects and global emitter state do not belong in the rule API.
2. **Selection:** explicit `if Python condition -> decision` branches with stable
   rule identifiers. Unmatched input is rejected by the source adapter.
3. **Decision:** target operation, result type, error behavior and representation
   requirements. A rule must not silently assume missing ownership proofs.
4. **Rendering:** consume already checked operands in their specified order. Keep
   temporary binding where eliminating it could change evaluation or lifetimes.
5. **Evidence:** successful execution against the Python reference, rejection
   cases, and optimization-on/off comparisons where relevant.

The frontend adapter resolves names and supplies source locations. The ownership
oracle supplies borrowing facts. Neither Rust text inspection nor a method-name
guess establishes nonmutation. The emitter composes rule results and tracks
resource/control-flow context; it should not independently reimplement selection.

## Type representation rules

`rules/types.py::render_owned_type` takes an admitted type name and already-rendered
argument types. Scalars map to their native representations, runtime records and
handles to `rt::` names, lists and variable tuples to `Vec`, dictionaries to
`IndexMap`, sets to `BTreeSet`, and fixed tuples to Rust tuples. User record and
enum names pass through unchanged. Source type admission remains the frontend's
responsibility; this renderer does not accept arbitrary source annotations.

`backend/values.py` owns the transitional `Type` and `Expr` records. `Type.rust()`
recursively renders children and delegates representation selection to the rule.
`service.py` reexports these records for existing callers, without owning their
implementation. The frozen recursive adapter records are not claimed portable;
the production representation rule is compiled in the bootstrap suite. Borrowed
parameter representations and recursive-field indirection retain their separate
policies.

## Comparison rules

`rules/comparisons.py` selects membership by needle/container types and renders
membership, admitted null identity, empty-string equality and direct comparison.

| Python operation | Rust form | Preconditions and behavior |
| --- | --- | --- |
| Integer in bytes | `byte_value` then `contains` | Recoverable out-of-range error |
| Byte buffer in bytes | `bytes_find >= 0` | Subsequence membership, including empty needle |
| String in JSON | `json_contains_string` | Runtime JSON membership contract |
| Key in dictionary | `contains_key` | Adapter converts to the admitted key type |
| Item in list/set/variable tuple | `contains` | Adapter validates/converts element type |
| String in string | `contains` | Substring membership |
| `not in` | Negate membership result | Same operand evaluation and failures |
| Literal `None` identity | JSON `is_null`, or evaluate None expression | Adapter rejects other identity comparisons |
| String equality with empty literal | `is_empty` | Existing optimization eligibility required |
| Ordinary equality/ordering | Infix operator | Adapter checks compatible types and rejects records |

Membership always binds the needle before the container. A method call directly
on the container would reverse source evaluation order. `render_comparison_chain` binds shared operands once and nests later bindings
inside successful comparison branches. Its internal assertions reject mismatched operand/test counts.

`set_order_rule` distinguishes set inclusion, ordinary ordering, and sequences or
fixed tuples compared at their first unequal element. `render_set_order` composes
already-rendered child comparisons and asserts valid operators and sequence-child
counts. These are internal compiler invariants, not source-program diagnostics. The adapter only traverses admitted recursive types and
supplies borrowed places; control-flow rendering lives in the portable rule.
Python inclusion must never fall through to Rust `BTreeSet` lexicographic ordering.

## Iteration rules

`rules/iteration.py::select_iteration` consumes the admitted container type,
whether the source is borrowed, whether its item is a scalar, and the memory
oracle's permission to borrow items. It returns a stable rule key, a rendering
form and whether the loop binding is borrowed. It never promotes an owned source
to a borrow or independently infers lifetime safety.

| Source and ownership | Rust iterator | Item behavior |
| --- | --- | --- |
| String | `chars().map(...to_string())` | Owned one-character strings, not UTF-8 bytes |
| Borrowed bytes/bytearray | `iter().copied().map(i64::from)` | Integer values |
| Owned bytes/bytearray | `into_iter().map(i64::from)` | Integer values |
| Borrowed list/set/variable tuple | `iter()` | Borrow, copy scalars, or clone according to proof facts |
| Borrowed dictionary | `keys()` | Same item ownership choices; insertion order retained |
| Owned dictionary | `into_keys()` | Consume keys |
| Owned list/set/variable tuple | Source expression | Consume owned items |
| Homogeneous fixed tuple | Bind once, build array of fields | Consume fields without re-evaluating source |
| `range(stop)` / `range(start, stop)` | Rust range | Preserve supplied expression order |
| `range(start, stop, step)` | `rt::integer_range` | Checked stepped range |

The adapter validates homogeneous tuples, selects borrowing/consumption/snapshot
policy, manages local scope and records memory decisions. `render_iteration`,
`render_range` and `render_for` own the emitted forms. Production rule bootstrap
coverage includes supported shapes and rejected representation combinations;
execution tests check snapshots, item ownership, Unicode and control flow.

## Assignment and deletion rules

`rules/assignment.py` renders mutations after the adapter validates target shape,
value/key types and effects. The order of temporary bindings is semantic:

| Source operation | Evaluation / update rule |
| --- | --- |
| Named list index assignment | Evaluate replacement, then index, check bounds, update |
| Bytearray index assignment | Replacement, index, byte-range check, bounds check, update |
| Dictionary/JSON assignment | Replacement, key, obtain mutable object if JSON, insert |
| Nested list assignment | Replacement, then each index and its parent bounds check, update final element |
| Indexed list append/extend | Resolve receiver key/index first, then argument, mutate selected list |
| Bytearray deletion | Key, bounds check, remove |
| Dictionary deletion | Key, `shift_remove`, missing-key error; preserve remaining insertion order |
| JSON deletion | Key, require object, remove or report missing key |
| Proven string append | Literal `push_str`, or evaluate an owned suffix before changing destination |

The adapter retains parent-detachment rejection and string-builder eligibility.
The renderer must not bypass these proofs. Source type/shape errors remain
source-located adapter diagnostics; the portable indexed-mutation renderer also
asserts its internal `push`/`extend` method invariant.

## Byte-buffer method rules

`rules/byte_methods.py::select_byte_method` makes supported receiver types,
overload arity, encoding names and result/argument types explicit. The adapter
validates literal encoding arguments and normalizes their spelling before rule
selection. UTF-8 and ASCII decoding remain fallible; Latin-1 and CP437 use their
reviewed runtime decoders. `hex`, `find`, `startswith` and `endswith` retain their
existing admitted receiver/argument combinations.

The extraction corrected `bytes.join`: emitting `parts.join(separator.as_slice())`
reversed Python evaluation order. The rule now binds the separator before
evaluating parts into an explicitly typed `Vec<Vec<u8>>` binding. This also fixes
Rust element-type ambiguity for `separator.join([])`. Both bindings move their
values without introducing a clone. A failing separator skips the parts expression, and a
failing parts expression occurs after separator effects. The temporary is needed
for semantics even though the direct Rust method call is shorter.

## Collection method rules

`rules/collection_methods.py::select_collection_method` consumes receiver type, method, positional arity and
whether the receiver is a named place. Each decision explicitly records its stable
key, rendering form, argument-type labels and result-type label. `item` means the
collection's checked element type, `receiver` means the same collection type, and
`byteslike` admits bytes or bytearray. The adapter resolves these labels; they are
not dynamically inferred from emitted Rust.

| Operation | Admission | Rendering behavior |
| --- | --- | --- |
| `copy()` | List, dictionary, set, bytearray; computed receivers allowed | Reuse the already-owned collection read |
| `clear()` | Named list/dictionary/set/bytearray | Clear the original place |
| `insert(index, item)` | Named list | Evaluate index then item, clamp index using i128 |
| `pop([index])` | Named list/bytearray | Default -1, checked index, remove; byte result becomes i64 |
| `sort()` | Named list, ordered non-float elements | Stable in-place sort |
| `reverse()` | Named list/bytearray | Reverse original place |
| `extend(items)` | Named list or bytearray | Evaluate argument before mutation; byte-buffer helper validates limits |
| `append(item)` | Named list or bytearray | Push typed item or checked byte |
| `add(item)` | Named set | Insert item, discard Rust's boolean result |

Mutations on computed receivers remain rejected. Indexed list append/extend has
its own checked-place adapter and assignment rule; it is not admitted by claiming
that an indexed receiver is a named place. Dictionary `get` retains its separate
eager-default and borrowing policy. Set algebra retains its separate value rule.

## Control-flow and exception rendering

`rules/control_flow.py` renders function bodies, boolean branches/while loops,
assertions, bare re-raises, references and prepared return forms. Returns use
`Ok(value)`, an already-fallible call, or `Ok(TryFlow::Return(value))` according to
the prepared readability/cleanup plan. Pending cleanup forbids implicit returns
and direct Result forwarding; the portable renderer asserts this invariant.
The host readability adapter retains its existing invalid-input diagnostics.

`backend/exception_emission.py` remains the sole renderer for handler regions,
finally regions and resource guards. Its public functions accept ordinary typed
parameters (keyword calls remain valid on the host). The production module is
compiled by the native bootstrap test, including combinations of nested returns
and terminating bodies/cleanup. Large templates use a single join of text parts
to avoid repeated growing-string copies in their native implementation. Runtime tests still prove cleanup order and error
behavior: comparing emitted strings alone is not semantic acceptance.

Ordinary control-flow composition no longer constructs `RustNode` wrappers and
immediately discards their parsed trees. This removes a fragment-parser dependency
from this rendering path. Native Rust interface analysis still uses parsing; this
is not a claim that all compiler dependencies have been eliminated.

## Indexing and slicing rules

`rules/access.py` selects checked access by container/key types. JSON keys and
indices, dictionary values, Unicode characters, prepared text indexes, sequence
items and byte values have distinct rule identifiers. Byte indexing widens to
`i64`; dictionary reads retain missing-key errors and the owned-value copy;
sequence and text helpers retain checked negative-index behavior.

The source adapter validates tuple constant positions and converts keys before
rendering. It also supplies either a proved reference, a mapping expression or a
prepared text-index expression as required by the selected rule. Rule selection
does not invent borrowing or text-index eligibility.

Slices use the checked source reference and explicit start/end expressions.
Variable tuples use list slicing; bytearray uses byte slicing. Text slicing
selects a borrowed view or owned result, with an optional prepared Unicode index.
Slice steps remain explicitly rejected. This centralizes operation mapping while
leaving evaluation-stability and lifetime proofs with the memory oracle.

## String rules

`select_string_rule(receiver, method, arity)` returns a `StringRule` containing a
stable key, rendering form, Rust target, result type, argument type and fallibility.
An empty key explicitly denotes an unsupported overload. Exact string receiver
typing is checked before the memory oracle uses the same selector as its
operation-level nonmutation contract. Operand effects are still checked separately.

| Python operation | Rust operation | Required behavior |
| --- | --- | --- |
| `text.casefold()` | `rt::casefold(text)` | Preserve Unicode case folding |
| `text.strip()` | `rt::str_strip(text)` | Preserve Python whitespace rules |
| `strip/lstrip/rstrip(chars)` | `rt::str_strip_edges(...)` | Character set, not prefix removal; optional `None` |
| `text.lower()/upper()` | `to_lowercase()/to_uppercase()` | Owned result; supported Unicode mapping |
| `text.encode()` | `as_bytes().to_vec()` | UTF-8 overload only |
| `text.split()` | `rt::str_split_whitespace(text)` | Python whitespace behavior |
| `text.split(separator)` | `rt::str_split(text, separator)` | Empty separator is a recoverable error |
| `startswith/endswith(pattern)` | `starts_with/ends_with(pattern)` | Exact supported one-argument overload |
| `find/rfind(pattern)` | `rt::str_find/str_rfind(...)` | Character offsets, not byte offsets |
| `text.replace(old, new)` | `replace(old, new)` | Receiver then arguments, each evaluated once |
| `separator.join(parts)` | Bind separator, then `parts.join(separator)` | Preserve Python receiver-first evaluation |

String operands use the existing argument-stability proof before borrowing local
places. Literal arguments do not need owned allocations. Fallible calls carry
their `Result` expression so tail returns can forward it instead of `Ok(call()?)`.
Trimming's optional-value setup remains in an adapter for now.

## Collection rules

`rules/collections.py` distinguishes Unicode character length, byte/item length,
fixed tuple arity, prepared text indexes and prepared length caches. The adapter
supplies existing proof facts; the rule does not invent indexing/cache eligibility.
For a nonlocal fixed-tuple expression, rendering evaluates the expression before
returning the constant arity. This preserves effects and failures.

Sequence constructors explicitly select byte-to-integer conversion, dictionary
key snapshots or collection-item snapshots. Fixed homogeneous tuples are adapted
to the existing sequence representation before rule selection. Snapshot semantics
remain explicit; borrowing the input is not permission to alias the output.

## Ordering rules

`rules/ordering.py` selects permitted total-order shapes from recursively supplied
child facts. Floats and arbitrary records remain unsupported; enums retain their
reviewed ordering, and fixed tuples retain the runtime's arity bound.

Sorting rules distinguish stable ascending sort, stable reversed comparison and
one-key-evaluation-per-item sorting. The key case calls the reviewed decorating
runtime helper. Reversing the final sorted list would reverse equal-key order;
calling Rust's `sort_by_key` could repeat key effects. Neither is an allowed
replacement for these rules.

## Condition rules

`condition_problem(type_name)` accepts only bools; `boolean_operator` maps the
supported bool-only `and`/`or` operations to short-circuit Rust operators. The typed
frontend checks `if`, `while`, assertions, conditional expressions, `not` and both
operands of `and`/`or` before handing IR to the emitter. Invalid truthiness reports
`condition.bool` at the original source line and requests an explicit comparison.
This is a deliberate subset rejection, not incomplete emulation of Python's
value-returning boolean idioms.

## Numeric rules

`select_numeric_rule(operator, left_type, right_type)` separates numeric policy
from AST dispatch. Its key identifies the operation; its form selects a runtime
helper, checked Rust method, finite float operation or infix bitwise operation.

| Python operation | Rust decision |
| --- | --- |
| Integer `+`, `-`, `*` | `checked_add/sub/mul`, overflow becomes `Result` error |
| Integer `//`, `%` | `rt::int_floor_div/int_modulo`, preserve signed floor/remainder rules |
| Integer or float `/` | Explicit true-division helper returning float |
| Integer `<<`, `>>` | Checked runtime shift helpers |
| Integer `&`, `|`, `^` | Native infix operation |
| Float `+`, `-`, `*` | Native operation checked by `rt::finite` |
| Bool arithmetic, mismatched operand types, unsupported operators | No matching rule; source adapter diagnoses |

Unary negation, bitwise inversion, boolean negation and `abs` now use explicit
`select_unary_rule` / `render_unary` decisions. The signed-i64 minimum literal
remains a source-adapter special case because its positive magnitude is outside
the supported integer range. Nonnumeric concatenation remains in the explicit operator adapter. The selector
expects any supported mixed-number conversion to have occurred before selection;
it does not silently cast operands.

## Scalar conversion rules

`rules/conversions.py` selects scalar conversion by target and source type. Each
rule records fallibility so compatible tail calls can forward `Result` directly.

| Python operation | Rust decision |
| --- | --- |
| `int(decimal_text)` | Bounded ASCII decimal parser returning `Result<i64>` |
| `float(decimal_text)` | Bounded decimal parser with underscore and finite-value checks |
| `float(integer)` | Explicit i64-to-f64 conversion |
| `float(float_value)` | Identity |
| `str(integer/string/exception)` | Supported display conversion |
| `str(float_value)` and default float `print` | `rt::float_to_string`, shortest digits with Python notation rules |
| Other scalar conversions | Source-located rejection; no bool-as-int assumption |

The float text audit found that Rust Display omits `.0`, and even Debug can select
another equally short decimal at halfway cases. The helper uses the existing
pinned serde_json/Ryu shortest digits, preserving negative zero and applying
Python's fixed/scientific thresholds and signed, padded exponent. It accepts only
finite binary64, consistent with the numeric subset. This is not support for
arbitrary Python format specifications or `repr`.

## Runtime record and lookup rules

`runtime_field_type(record, field)` is the single field-type mapping consumed by
frontend web stubs and the emitter. `borrowed_runtime_field` separately selects
reviewed owned WebRequest/WebResponse value fields. Scalar status conversion and
resource-bearing HttpReader fields do not gain borrowing from a type declaration
alone. Local reads such as `len(request.body)` can now borrow the buffer instead
of cloning it.

`dictionary_get_style` requires a stable receiver/argument evaluation and a local
place before selecting a borrowed lookup. With a literal string key and literal
empty-string default, the result uses `get(...).cloned().unwrap_or_default()`.
Other defaults remain eager. Unknown effects preserve the original lowering;
this rule does not reorder arbitrary defaults or infer mutation freedom from
method names.

## Semantic audit and acceptance boundaries

The detailed contract/evidence table is maintained in
[Semantic audit](SEMANTIC_AUDIT.md), rather than duplicated as a migration todo
list here. Its entries distinguish our Python-like subset from full CPython
semantics. Tests named there establish particular contracts, not universal Python
compatibility. Current execution evidence is recorded below.

The source review confirms explicit rules for conditions, numeric operations,
conversions, strings, collections, sorting and cleanup. Source rejection checks
cover defaults, general TypeVars, collection/optional truthiness and unsupported
rounding. Mutation diagnostics preserve original locations, and native mutation
checks cover both optimization modes. Sorting checks include stability, key-call
count, failures, argument order and imported callbacks.

Some rendering remains intentionally in host adapters: optional string-trim
argument setup, nonnumeric concatenation, record construction and callback APIs.
These are visible, bounded branches with type validation, not portable production
rules. Moving them into the future native core requires preserving operand effects
and source diagnostics. The current preparation milestone does not claim that all
emission is independent of Python ASTs or that the compiler can already compile
itself.

Final acceptance requires the complete regression suite, selected representative
applications and interoperability checks, and optimization gates on the final
source. The user explicitly requested selected programs instead of the full
120-application catalog.
A successful extraction equivalence check does not replace execution of the earlier
semantic fixes. Failures must be investigated before recording final acceptance.

## Host and native compiler boundaries

The first checkpoint compiles the **production rule sources** with drivers,
then compares its decisions and rendered snippets against Python. The native
executable runs with `PATH`, `PYTHONHOME` and `PYTHONPATH` set to nonexistent
locations. This tests a real compiler component; it is not a self-hosted compiler.

Keep new portable rules within the subset: explicit annotations and returns,
plain dataclasses, ordinary containers and control flow. Avoid Python AST classes,
reflection, monkey-patching, nested closures, dynamic dispatch registries and
unrestricted heterogeneous objects. Do not duplicate a simplified rule module
solely to make the bootstrap test pass.

Further checkpoints are:

1. Expand production rule coverage and compile each portable family in its tests.
2. Define a versioned, validated exchange format for typed IR, source locations
   and policy decisions. Test Python/native round trips and malformed input.
3. Compile the rule and emission core into a native executable consuming that IR.
   A Python/mypy producer at this checkpoint is a transitional build dependency,
   not a fully standalone compiler.
4. Replace or port remaining frontend, project and native-interface dependencies
   before claiming end-to-end compiler self-hosting. The supplied mypy frontend,
   Python `ast` adapter, tree-sitter bindings and Python packaging code are real
   blockers, not solved by compiling the rules.
5. Demonstrate stage-one/stage-two compiler builds and equivalent complete-program
   behavior. Native rule execution alone does not satisfy this final checkpoint.

Actual full self-hosting is the user's next project stage. The current stage must
leave explicit boundaries, portable production components and executable checks
that make that work possible without presenting mypy as already portable.


## Verification and acceptance

Production rule portability is checked by `tests/test_rule_bootstrap.py`: it
compiles each actual rule module, executes the native binary without Python on
its search paths, and compares decisions/renderings against Python. This is not
full compiler self-hosting. Domain tests execute generated programs and compare
values, effects, errors and cleanup; a compiling renderer alone is insufficient.

Durable regression cases added during this work include:

- `test_float_text.py`: finite float display, signed zero, exponent boundaries,
  halfway cases, seeded random values, and borrowed parsing inputs.
- `test_condition_rules.py` and `test_semantic_rejections.py`: boolean-only
  conditions, short-circuit behavior, unsupported defaults/generics/rounding.
- `test_collection_rules.py`: tuple-length effects/failures, Unicode lengths,
  sequence snapshots and dictionary order.
- `test_comparison_rules.py`: membership evaluation/failure order, comparison
  chains and nested-set partial ordering through both optimization modes.
- `test_assignment_rules.py`: replacement-before-key order, failed replacement,
  dictionary/JSON deletion and reinsertion order.
- `test_byte_method_rules.py`: receiver-first bytes join, empty-list joining and
  separator/parts failures through typed and legacy frontends.
- `test_collection_method_rules.py`: typed insertion/buffer effects, JSON insert
  conversion, and rejection of incorrect non-JSON items and indices.

Selected earlier acceptance snapshots are archived under
`$PY2RUST_BUILD_DIR/`. Each includes logs and source hashes; they are
revision-specific evidence, not automatically acceptance of subsequent changes.

| Snapshot directory | Evidence and scope |
| --- | --- |
| `scalar-condition-rules` | Float display experiment and scalar/condition checks |
| `collection-ordering-rules` | All 22 complete typed applications executed successfully; follow-up generation/runtime equivalence after a parameter rename |
| `iteration-rules` | All 22 emitted applications and runtime sources remained byte-identical to that accepted baseline; generation-only comparison |
| `assignment-rules` | 65 regression and 2 typed effect checks |
| `byte-method-rules` | 44 initial checks; after fixing empty joining, 16 final checks; selections overlap |
| `collection-method-rules` | 62 initial checks; 22 follow-up checks after adding the JSON insert hook |
| `emitter-boundaries` | 70 project/CLI/typed-parameter/pipeline checks; 14 follow-up checks for packaging import isolation and all 13 production rule bootstraps |
| `control-flow-rules` | 35 corrected checks including all 15 portable production components; after joining large templates, 14 focused checks and 21 byte-identical template combinations |
| `access-rules` | 63 checks covering all 16 portable components, typed views/references, Unicode indexes, tuples and bytearray behavior |
| `expression-adapters` | 63 expression/pipeline/ownership checks; 32 follow-up checks covering portable components and source rejections |
| `statement-adapters` | 56 assignment, iteration, ownership, typed pipeline, exception, finally and resource checks |

The later bytes-join and frontend JSON-insert fixes postdate the 22-application
byte-equivalence snapshot. That snapshot must not be presented as acceptance of
those fixes. The final regression run now passes all 1,095 tests in 2632.96 seconds. Its log
and 499 verified source/test/tool hashes are archived under `final-acceptance`.
The catalog run verified applications 001–047 before being stopped at the user’s
request to use selected programs. Application 048 was interrupted and is not
counted. Webhook delivery and seven HTTP client applications pass all four
Python/Rust server-client combinations. All six optimization gates pass.
The acceptance record rechecks all 499 source hashes and the current fingerprints
and six successful stages of all 47 completed catalog programs.

## Current native compiler boundary

The rule-extraction checkpoint above prepared shared components. The portable
source frontend and emitter now additionally self-reproduce from Python sources;
see [self-hosting](SELF_HOSTING.md) for current scope, commands and verification.
The host mypy frontend, AST adapters and Cargo packaging remain separate. Neither
rule portability nor source self-reproduction establishes full CPython support,
general alias inference, checked ownership hints or host/native feature parity.
