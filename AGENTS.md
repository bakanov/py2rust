# py2rust development

This repository compiles complete typed Python-subset applications to Rust only.
Read README.md and doc/DEVELOPMENT.md for commands and storage requirements.

Use explicit returns, public type hints and 120-character Python lines. Preserve
native and Python-reference behavior together. Keep source maps and readable
module/function names. Test complete generated programs, not merely compilation.
Do not delete application data or source fixtures during build cleanup. Keep the
MIT license and upstream attribution. Do not run pytest concurrently.
