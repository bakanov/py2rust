# Python subset semantic audit

This is the checklist adopted from the supplied DeepSeek conversation. It separates
the behavior of our language from CPython compatibility and from Rust memory safety.
A successful Rust build does not prove either source behavior or copy efficiency.

The evidence column names implementation/test sources inspected for this audit.
It does not mean every listed test was rerun on the current revision. Current run
scope is recorded in [Translation rules](TRANSLATION_RULES.md).

| Source pattern | Current contract | Rule / evidence | Remaining work |
| --- | --- | --- | --- |
| `if x`, `while x`, `assert x`, conditional expressions | Require bool; reject implicit truthiness before emission | `rules/conditions.py`, `test_condition_rules.py` | Collection/optional rejection coverage is in `test_semantic_rejections.py` |
| `a and b`, `a or b`, `not a` | Bool operands only; short-circuit evaluation | Conditions/unary rules; native short-circuit test | No value-returning boolean idioms promised |
| Integer arithmetic | Signed i64; checked overflow; bool is not int | `rules/numeric.py`, arithmetic/bitwise/abs tests | Wider integer support is outside this subset |
| Signed `//`, `%`, `/` | Python-style floor/modulo; true division; recoverable zero-divisor errors | Numeric rules and runtime helpers | Preserve boundary/error cases as rules evolve |
| `int(text)` | Bounded ASCII decimal grammar and i64 range | `int_from_decimal`, scalar conversion rule | Python Unicode digits and underscore spellings are not promised; keep restrictions explicit |
| `float(text)` | Bounded decimal grammar, underscores, correctly rounded finite binary64 | `test_service_float_parse.py` | NaN/infinity rejected; no arbitrary numeric protocol |
| `str(float)`, default float `print` | Shortest decimal text with Python notation and negative zero | `float_text.rs`, `test_float_text.py` | Arbitrary format specifications and `repr` remain unsupported |
| `round`, general formatting | No translation rule | Unsupported-call path | Emission rejection and original source location are tested; do not emit Rust rounding by analogy |
| String length/indexing/slicing | Unicode scalar count/index behavior within the subset; negative indexes checked | `rules/access.py`, collection/text rules; Unicode/view/index tests | No surrogate code points; retain source restrictions |
| `strip`, `split`, `find`, `casefold` | Reviewed Python-style helpers; exact supported overloads | `rules/strings.py`, string/strip/casefold tests | No blanket mapping of unknown string methods |
| `separator.join(items)` | Evaluate separator first, then items for both strings and bytes | String/byte method rules and effect/failure tests; empty byte-list join fixed | Preserve temporary lifetimes and type context when simplifying output |
| Collection assignment and mutation | Owned-value semantics, not CPython shared mutable object identity | Subset reference; arithmetic/record/mutation tests | General alias/escape analysis remains absent; avoid claiming copies preserve Python aliases |
| Dictionary iteration | Insertion order | `IndexMap`, collection ordering tests | JSON canonical serialization deliberately has its own ordering contract |
| `mapping.get(key, default)` | Eager default even when key exists; only effect-free literal defaults may be simplified | Record/lookup rule; native web test | Indexing, assignment/deletion and collection mutations now have explicit rule modules |
| `len(tuple_expression)` | Known length does not erase evaluation, exceptions or bounds checks | `rules/collections.py`, `test_collection_rules.py` | Keep evaluation separate from constant result selection |
| `list/tuple(collection)` | Independent item/key snapshot; bytes become integer values | Collection constructor rules and native tests | Unsupported constructors need explicit diagnostics |
| `sorted(..., key=...)` | One key call per item, stable order, eager direction before callbacks | Ordering rules, `sorting.rs`, sort-key tests | Keep callback signature and ownership contracts visible |
| Function defaults | Currently reject all defaults, including mutable defaults | `frontend/lowering.py:function` | Mutable and immutable defaults have source-boundary rejection tests; stricter than Python |
| Resources and exceptions | Shared resource handles; explicit cleanup; Result-based subset handlers | Exception policy, native production renderer bootstrap, resource/runtime/finally tests | Rust panic is not a Python exception; no arbitrary exception hierarchy |
| Generics and protocols | Concrete supported types; no general TypeVar/Protocol compiler | Frontend type lowering and subset reference | TypeVar rejection/location tested; diagnostic wording can still be clearer |
| Async, generators, late-bound closures | General source constructs unsupported | Frontend rejection paths | Native networking primitives do not imply asyncio translation |
| Regex patterns | Explicit bounded syntax and result contract, not arbitrary `re` compatibility | Regex capture/Unicode/anchor tests; subset reference | Preserve rejection of lookaround/backreferences and document shorthand differences |
| Date/time | Explicit UTC, precision and timezone helper contracts | Datetime/microsecond/timezone tests | Do not infer equivalence for arbitrary naive/aware Python datetime operations |
| Randomness | Explicit token helpers, no general seeded Python random-sequence compatibility | Token tests and replacement registry | No promise that a Rust RNG reproduces Python seeded output |
| Unknown standard/third-party imports | Require explicit replacement contract or local implementation | Library registries and replacement tests | Never silently embed a Python runtime |

## Decisions that are not optimization hints

Owned-value semantics, mutable sharing, weak references and exception behavior are
language contracts. A future `Owned`/`Borrowed` annotation must be checked against
those contracts and against call-site alias/escape facts. It cannot silently change
object identity or introduce a hidden copy when the user requires transfer.

The review does not justify blanket `Rc<RefCell<T>>`, RustPython fallback or a
compile-and-repair loop as the primary semantic analysis. Rust borrow checking is
an additional verifier. The current typed IR and independent policy modules remain
the foundation for explicit rules and future native compiler components.
