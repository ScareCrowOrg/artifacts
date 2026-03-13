"""
Adapter Classes for Notebook Items - Backward Compatibility Facade

This file maintains backward compatibility with the original monolithic module.
All functionality has been modularized into the adapters/ package.

For new code, import from the package:
    from app.models.adapters import CellAdapter, BookAdapter

This facade will be maintained for legacy code compatibility.
"""

# Re-export all public APIs from the modularized package
from .adapters import BookAdapter, CellAdapter, NotebookItemAdapter

__all__ = ["NotebookItemAdapter", "CellAdapter", "BookAdapter"]
