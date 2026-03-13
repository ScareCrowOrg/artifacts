---
processed: true
processed_date: 2026-02-10
themes:
  - database
  - mongodb
  - indexes
  - unified-runtime
modules:
  - backend
  - database
code_verified: false
---

# MongoDB Indexes for Unified NotebookItem Schema

## Overview

This document specifies MongoDB indexes required for optimal query performance on the unified `notebook_items` collection. These indexes support the unified runtime architecture where cells and books are stored in a single collection.

**Related Documentation**:
- [Unified Runtime Schema](../../../docs/issues/discovery-planning-system-epic/unified-runtime/schema.md)
- [NotebookItem Model](../app/core/models.py)

## Collection: `notebook_items`

### Primary Index

```javascript
// Unique index on ID field
db.notebook_items.createIndex(
  { "id": 1 }, 
  { 
    unique: true,
    name: "idx_notebook_items_id"
  }
)
```

**Purpose**: Ensure unique identification of each NotebookItem
**Usage**: Primary key lookups

---

### Kind Index

```javascript
// Index for filtering by kind (cell vs book)
db.notebook_items.createIndex(
  { "kind": 1 },
  {
    name: "idx_notebook_items_kind"
  }
)
```

**Purpose**: Fast filtering by item type
**Usage**: Queries like `find({ kind: 'cell' })` or `find({ kind: 'book' })`

---

### Type Index

```javascript
// Index for filtering by notebook item type ID
db.notebook_items.createIndex(
  { "notebook_item_type_id": 1 },
  {
    name: "idx_notebook_items_type_id"
  }
)
```

**Purpose**: Fast filtering by specific cell/book types
**Usage**: Queries like `find({ notebook_item_type_id: 'png-generator-cell' })`

---

### Status Index

```javascript
// Index for filtering by execution status
db.notebook_items.createIndex(
  { "status": 1 },
  {
    name: "idx_notebook_items_status"
  }
)
```

**Purpose**: Fast filtering by execution state
**Usage**: Queries like `find({ status: 'running' })` or `find({ status: 'AWAITING_REVIEW' })`

---

### Assignee Index

```javascript
// Index for filtering by assignee
db.notebook_items.createIndex(
  { "assignee_id": 1 },
  {
    name: "idx_notebook_items_assignee"
  }
)
```

**Purpose**: Fast filtering by user/agent
**Usage**: Queries like `find({ assignee_id: 'user_123' })`

---

### Compound Index: Kind + Status + Assignee

```javascript
// Compound index for common filter combinations
db.notebook_items.createIndex(
  { 
    "kind": 1, 
    "status": 1, 
    "assignee_id": 1 
  },
  {
    name: "idx_notebook_items_kind_status_assignee"
  }
)
```

**Purpose**: Optimize multi-field queries
**Usage**: Queries like `find({ kind: 'cell', status: 'running', assignee_id: 'user_123' })`

---

### Hierarchical Tracing Index

```javascript
// Index for hierarchical queries (find parent books that executed a cell)
db.notebook_items.createIndex(
  { "fragments.executed_by": 1 },
  {
    name: "idx_notebook_items_fragments_executed_by"
  }
)
```

**Purpose**: Support hierarchical tracing queries
**Usage**: Find which Book executed a specific Cell via `fragments.executed_by`

---

### Timestamp Index

```javascript
// Index for sorting by creation time (descending = newest first)
db.notebook_items.createIndex(
  { "created_at": -1 },
  {
    name: "idx_notebook_items_created_at_desc"
  }
)
```

**Purpose**: Fast sorting by creation time
**Usage**: Queries like `find({}).sort({ created_at: -1 })`

---

## Index Creation Script

### JavaScript (MongoDB Shell)

```javascript
// Connect to database
use scareverse

// Create all indexes
print("Creating notebook_items indexes...")

db.notebook_items.createIndex({ "id": 1 }, { unique: true, name: "idx_notebook_items_id" })
print("✓ Created: idx_notebook_items_id")

db.notebook_items.createIndex({ "kind": 1 }, { name: "idx_notebook_items_kind" })
print("✓ Created: idx_notebook_items_kind")

db.notebook_items.createIndex({ "notebook_item_type_id": 1 }, { name: "idx_notebook_items_type_id" })
print("✓ Created: idx_notebook_items_type_id")

db.notebook_items.createIndex({ "status": 1 }, { name: "idx_notebook_items_status" })
print("✓ Created: idx_notebook_items_status")

db.notebook_items.createIndex({ "assignee_id": 1 }, { name: "idx_notebook_items_assignee" })
print("✓ Created: idx_notebook_items_assignee")

db.notebook_items.createIndex(
  { "kind": 1, "status": 1, "assignee_id": 1 }, 
  { name: "idx_notebook_items_kind_status_assignee" }
)
print("✓ Created: idx_notebook_items_kind_status_assignee")

db.notebook_items.createIndex({ "fragments.executed_by": 1 }, { name: "idx_notebook_items_fragments_executed_by" })
print("✓ Created: idx_notebook_items_fragments_executed_by")

db.notebook_items.createIndex({ "created_at": -1 }, { name: "idx_notebook_items_created_at_desc" })
print("✓ Created: idx_notebook_items_created_at_desc")

print("\nAll indexes created successfully!")

// Verify indexes
print("\nVerifying indexes:")
db.notebook_items.getIndexes().forEach(function(index) {
  print("  - " + index.name)
})
```

### Python (PyMongo)

```python
"""
MongoDB index creation script for unified NotebookItem schema.
Run this script after deploying the updated models.
"""

from pymongo import MongoClient, ASCENDING, DESCENDING

def create_notebook_items_indexes(db):
    """Create all required indexes for notebook_items collection."""
    collection = db.notebook_items
    
    # Primary index
    collection.create_index(
        [("id", ASCENDING)],
        unique=True,
        name="idx_notebook_items_id"
    )
    print("✓ Created: idx_notebook_items_id")
    
    # Kind index
    collection.create_index(
        [("kind", ASCENDING)],
        name="idx_notebook_items_kind"
    )
    print("✓ Created: idx_notebook_items_kind")
    
    # Type index
    collection.create_index(
        [("notebook_item_type_id", ASCENDING)],
        name="idx_notebook_items_type_id"
    )
    print("✓ Created: idx_notebook_items_type_id")
    
    # Status index
    collection.create_index(
        [("status", ASCENDING)],
        name="idx_notebook_items_status"
    )
    print("✓ Created: idx_notebook_items_status")
    
    # Assignee index
    collection.create_index(
        [("assignee_id", ASCENDING)],
        name="idx_notebook_items_assignee"
    )
    print("✓ Created: idx_notebook_items_assignee")
    
    # Compound index
    collection.create_index(
        [
            ("kind", ASCENDING),
            ("status", ASCENDING),
            ("assignee_id", ASCENDING)
        ],
        name="idx_notebook_items_kind_status_assignee"
    )
    print("✓ Created: idx_notebook_items_kind_status_assignee")
    
    # Hierarchical tracing index
    collection.create_index(
        [("fragments.executed_by", ASCENDING)],
        name="idx_notebook_items_fragments_executed_by"
    )
    print("✓ Created: idx_notebook_items_fragments_executed_by")
    
    # Timestamp index
    collection.create_index(
        [("created_at", DESCENDING)],
        name="idx_notebook_items_created_at_desc"
    )
    print("✓ Created: idx_notebook_items_created_at_desc")
    
    print("\nAll indexes created successfully!")
    
    # Verify indexes
    print("\nVerifying indexes:")
    for index in collection.list_indexes():
        print(f"  - {index['name']}")


if __name__ == "__main__":
    # Connect to MongoDB
    client = MongoClient("mongodb://localhost:27017/")
    db = client.scareverse
    
    print("Creating notebook_items indexes...")
    create_notebook_items_indexes(db)
    
    client.close()
```

---

## Usage Instructions

### Option 1: MongoDB Shell

```bash
# Connect to MongoDB
mongosh "mongodb://localhost:27017/scareverse"

# Run the JavaScript index creation commands
# (paste the commands from the "JavaScript (MongoDB Shell)" section above)
```

### Option 2: Python Script

```bash
# Save the Python script as create_indexes.py
cd /path/to/backend/scripts

# Run the script
python3 create_indexes.py
```

### Option 3: Application Startup

Add index creation to application startup in `app/database/mongodb.py`:

```python
async def create_indexes():
    """Create required indexes on application startup."""
    db = get_database()
    collection = db.notebook_items
    
    # Create indexes (see Python script above for details)
    await collection.create_index([("id", 1)], unique=True, name="idx_notebook_items_id")
    # ... (add remaining indexes)
```

---

## Index Monitoring

### Check Index Usage

```javascript
// Get index statistics
db.notebook_items.aggregate([
  { $indexStats: {} }
])
```

### Drop Unused Indexes

```javascript
// Drop a specific index (if needed)
db.notebook_items.dropIndex("idx_notebook_items_kind")
```

---

## Performance Considerations

1. **Index Size**: Monitor index size with `db.notebook_items.stats()`
2. **Write Performance**: Indexes slow down writes; ensure they're necessary
3. **Compound Index Order**: Field order matters for compound indexes
4. **Query Patterns**: Analyze actual query patterns with `explain()`

---

## Acceptance Criteria

- [ ] All 8 indexes created successfully
- [ ] Indexes verified with `getIndexes()`
- [ ] Query performance tested for common patterns
- [ ] Index usage monitored in production

---

**Last Updated**: 2026-02-10  
**Status**: Implementation Ready  
**Maintained By**: Backend Team
