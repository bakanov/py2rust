# Migration to py2rust

The distribution, imports, CLI and native runtime are now named py2rust.
Use `from py2rust.stdlib import ...` and `py2rust run PATH`. Compiler internals
live under `py2rust.compiler`. The managed output marker is
`.py2rust-project.json`; generated projects from the previous name must be rebuilt.

The standalone complete-project/service compiler and all 120 applications are
retained. The old multi-target compiler pipeline, other language backends,
legacy golden-output tests, Docker/mise configurations and preliminary networking
profile were removed. TCP support remains in the service runtime and complete
network applications. This is a source migration, not an alias for old imports.

Git history and the original MIT license preserve the upstream lineage. Local
pre-migration backup archives are not repository dependencies. Generated builds, old packages and caches were removed; chat data was
preserved. Previous results do not prove correctness after this source migration:
new checks must establish new evidence. The catalog documents coverage, not a
claim that the renamed programs have all been revalidated already.
