"""Explicit translation rules on portable values, independent of frontend ASTs.

Keep rule selection deterministic. Adapters supply types and proof facts;
renderers consume decisions without inventing additional semantic rules.
"""
