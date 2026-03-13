"""
Collection type definitions for HybridDatabase routing.

Defines which collections are canonical (file-based) vs runtime (MongoDB).
"""

# Collections that should always use canonical (file-based) storage
CANONICAL_COLLECTIONS = {
    "notebook_item_types",
    "agent_types",
    "workflows",
    "ai_models",
    "templates",
    "permissions",
    "roles",
    "job_types",
}

# Collections that should always use runtime (MongoDB) storage when available
# Note: notebook_items is the unified collection for cells and books (discriminated by 'kind' field)
# contents stores dynamically generated content (images, assets, etc) from cells
# (MongoDB operations automatically append _runtime suffix, so use base name here)
RUNTIME_COLLECTIONS = {
    "notebook_items",
    "sessions",
    "users",
    "memory",
    "traces",
    "audit_logs",
    "contents",
}
