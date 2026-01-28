# Frontend Integration Notes - Generation Mode Default

## Issue Identified

During code review of the backend refactoring, inconsistencies were found between backend and frontend regarding the default generation mode.

## Current State

### Backend (Correct) ✅
- **Default Mode:** `local-gpu`
- **Location:** `backend/scripts/main.py` line 57
- **Rationale:** Preserves existing behavior, maintains backward compatibility

### Frontend (Needs Update) ⚠️
The following frontend files incorrectly set `cloud-api` as the default:

1. **Schema Definition:** `artifacts/canonical/notebook_item_types/3d-mesh-prototyping-cell.json`
   - Line 15: `"default": "cloud-api"` should be `"default": "local-gpu"`
   - Line 43: `"default": "cloud-api"` should be `"default": "local-gpu"`
   - Line 45: Description states "cloud-api (default)" should be "local-gpu (default)"

2. **UI Component:** `artifacts/canonical/cell_types/3d-mesh-prototyping-cell/frontend/components/GenerationModeSwitcher.vue`
   - Line 46: Description states "Fast generation via external API (default)" - remove "(default)"
   - Line 48: Badge assignment marks `cloud-api` as "Default" - should be `local-gpu`

## Required Changes

### 1. Update Schema Default
**File:** `artifacts/canonical/notebook_item_types/3d-mesh-prototyping-cell.json`

```json
{
  "generationMode": {
    "type": "string",
    "default": "local-gpu",  // Change from "cloud-api" to "local-gpu"
    "enum": ["cloud-api", "local-gpu", "manual-upload"],
    "description": "3D generation method: local-gpu (default), cloud-api, or manual-upload"
  }
}
```

### 2. Update UI Component
**File:** `frontend/components/GenerationModeSwitcher.vue`

Update the mode descriptions:
- **local-gpu**: Add "(default)" or "Default" badge
- **cloud-api**: Remove "(default)" text

Update badge logic (around line 48):
```vue
<v-chip
  :color="mode.value === 'local-gpu' ? 'primary' : 'default'"
  :label="mode.value === 'local-gpu' ? 'Default' : ''"
>
```

## Why This Matters

1. **Backward Compatibility**: Existing integrations expect `local-gpu` as default
2. **User Expectations**: Frontend should match backend behavior
3. **Documentation Consistency**: All docs state `local-gpu` is default
4. **Testing**: Tests assume `local-gpu` when mode is unspecified

## Testing Required

After frontend updates:
1. Verify default mode is `local-gpu` when `generationMode` is not provided
2. Test all three modes work correctly
3. Verify UI shows correct default indicator
4. Check schema validation passes

## Backend Status

✅ Backend correctly implements `local-gpu` as default  
✅ Backend supports all three modes  
✅ Backend is backward compatible  
✅ Backend tests pending (unit, integration)  

## Frontend Action Items

- [ ] Update schema definition to default `local-gpu`
- [ ] Update GenerationModeSwitcher.vue to mark `local-gpu` as default
- [ ] Update GenerationModeSwitcher.vue description text
- [ ] Test default behavior without `generationMode` specified
- [ ] Update any frontend documentation if needed
- [ ] Verify UI matches backend behavior

---

**Created:** 2026-01-28  
**By:** Backend Agent  
**Assignee:** Frontend Agent  
**Priority:** High (affects backward compatibility)  
**Related PR:** Backend Refactoring - Hybrid Generation Modes
