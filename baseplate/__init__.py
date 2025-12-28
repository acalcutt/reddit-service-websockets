"""Minimal `baseplate` shim for tests.

This provides a lightweight `secrets` implementation used by the test
suite so CI does not depend on an external `baseplate` package that may
not expose the same submodules.
"""

__all__ = ["secrets"]
