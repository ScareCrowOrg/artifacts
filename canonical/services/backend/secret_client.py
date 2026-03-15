"""
Compatibility shim – SecretClient has been moved to ``artifacts/shared``.

Import from the new canonical location::

    from artifacts.shared.secret_client import SecretClient

This module re-exports ``SecretClient`` for backward-compatibility with any
code that still imports from the old location.
"""

from artifacts.shared.secret_client import SecretClient  # noqa: F401

__all__ = ["SecretClient"]
