---
processed: true
processed_date: 2025-12-09
themes:
  - backend
  - cleanup
  - data-model
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# Canonical Cell Cleanup Strategy

## Overview

This document describes the cleanup strategy for duplicate canonical cell type files that were created before the idempotent generation feature was implemented.

## Problem

Prior to the fix, the `seed_tipos_celula()` function in `app/seed_data.py` was not idempotent. Each call would create new canonical cell type files with new UUIDs, even if a cell type with identical content already existed. This resulted in:

- 40 canonical cell files instead of 5
- 8 duplicate instances of each unique cell type
- Difficulty in tracking which cells are canonical
- Potential confusion when referencing cell types

## Solution

### 1. Idempotent Generation (Implemented)

The `seed_tipos_celula()` function now:
1. Checks if a cell type with matching parameters already exists
2. Returns the existing cell if found
3. Only creates a new cell if none exists

This is achieved through:
- New `find_by_fields()` method in `JSONDatabase` class
- Refactored `seed_tipos_celula()` to check before insert
- Comprehensive tests to validate idempotent behavior

### 2. Cleanup Script (Provided)

A cleanup script is provided at `backend/scripts/cleanup_duplicate_cells.py` to identify and remove duplicate files.

#### Usage

**Dry Run (Preview):**
```bash
cd backend
python scripts/cleanup_duplicate_cells.py --dry-run
```

This shows what would be deleted without actually deleting files.

**Actual Cleanup:**
```bash
cd backend
python scripts/cleanup_duplicate_cells.py
```

This permanently deletes duplicate files, keeping only one instance of each unique cell type.

#### How it Works

1. Scans the `Artefatos/canonicos/tipos_celula` directory
2. Normalizes each file's content (excluding the `id` field)
3. Groups files by normalized content hash
4. For each group with duplicates:
   - Keeps the first file (sorted alphabetically)
   - Deletes all other files in the group

#### Safety Features

- Dry-run mode to preview changes
- Detailed logging of all operations
- Summary report showing files kept and deleted
- Content-based grouping ensures no unique cells are lost

## Cleanup Results

When run on the original repository state:

- **Before:** 40 canonical cell files (5 unique × 8 duplicates each)
- **After:** 5 canonical cell files (5 unique)
- **Files kept:** 5
- **Files deleted:** 35

### Retained Cell Types

After cleanup, the following canonical cell types remain:

1. **Editor de Artefatos** (`2c2aa39f-fd86-4c28-bdf7-d407fba8cabe`)
2. **Memória de Conversação** (`1879e53a-09e0-4909-b958-35e247903298`)
3. **Gerador de Código** (`1cbb5e6f-1570-4462-99c6-287c37b201b6`)
4. **Validador de Artefatos** (`3a365e84-7431-4dbe-9c6c-17ab90b9d49a`)
5. **Executor de Testes** (`0cd532bb-f2b9-4951-8768-59644e40c7ab`)

## Migration Guide

If you have a running instance with duplicate canonical cells:

### Step 1: Backup (Optional but Recommended)

```bash
cp -r Artefatos/canonicos/tipos_celula Artefatos/canonicos/tipos_celula.backup
```

### Step 2: Preview Cleanup

```bash
cd backend
python scripts/cleanup_duplicate_cells.py --dry-run
```

Review the output to ensure the correct files will be kept.

### Step 3: Run Cleanup

```bash
python scripts/cleanup_duplicate_cells.py
```

### Step 4: Verify

Check that only 5 canonical cell files remain:

```bash
ls -1 Artefatos/canonicos/tipos_celula/*.json | wc -l
```

Should output: `5`

### Step 5: Test Idempotent Behavior

Run the seed function multiple times to verify it doesn't create duplicates:

```bash
python -c "from app.seed_data import seed_tipos_celula; seed_tipos_celula(); seed_tipos_celula()"
ls -1 Artefatos/canonicos/tipos_celula/*.json | wc -l
```

Should still output: `5`

## Future Considerations

### References to Deleted UUIDs

If your runtime cells or books reference deleted canonical cell UUIDs, you may need to:

1. Identify affected runtime artifacts
2. Update their `tipoCelulaId` field to reference the retained UUIDs
3. Consider adding a migration script if many references exist

### Preventing Future Duplicates

The idempotent implementation ensures:
- Multiple calls to `seed_tipos_celula()` are safe
- Existing cells are reused rather than creating new ones
- New cell types can still be added when needed

### Monitoring

To check for duplicates in the future:

```bash
cd backend
python scripts/cleanup_duplicate_cells.py --dry-run
```

If output shows "No duplicates found!", the system is clean.

## Technical Details

### Comparison Logic

Two canonical cells are considered duplicates if all of the following fields match:
- `descricao`
- `scripts` (both Python and JavaScript)
- `markup`
- `views` (array of view names)
- `workflows`
- `versao`

The `id` field is explicitly excluded from comparison since it's unique by design.

### File Selection Strategy

When duplicates are found, the cleanup script:
1. Sorts all duplicate files alphabetically by filename
2. Keeps the first file in the sorted list
3. Deletes all subsequent files

This ensures deterministic behavior across multiple runs.

## Related Files

- `backend/app/database.py` - Contains `find_by_fields()` method
- `backend/app/seed_data.py` - Contains idempotent `seed_tipos_celula()` function
- `backend/tests/test_idempotent_cell_generation.py` - Tests for idempotent behavior
- `backend/scripts/cleanup_duplicate_cells.py` - Cleanup script

## See Also

- [Issue #239129938](https://github.com/Scare-Inc/ScareVerseLab/issues/239129938) - Original bug report
- `IMPLEMENTATION_SUMMARY.md` - Overall implementation details
