# Content Manager Cell - Error Codes Reference

## Overview

This document describes all error codes returned by the Content Manager Cell persist action, including detailed information about error states, cleanup procedures, and recovery instructions.

## Error Response Structure

All error responses follow this structure:

```json
{
    "success": false,
    "action": "persist",
    "error": "<User-friendly error message>",
    "error_code": "<MACHINE_READABLE_CODE>",
    "details": {
        "<context-specific-fields>": "..."
    }
}
```

---

## Error Codes

### R2_UPLOAD_FAILED

**When**: R2 storage upload fails before any database operations.

**Severity**: Medium

**Data State**: Clean - no files created, no database entries.

**Example**:
```json
{
    "success": false,
    "action": "persist",
    "error": "Failed to upload content to R2",
    "error_code": "R2_UPLOAD_FAILED",
    "details": {
        "content_type_id": "image-png",
        "filename": "test.png",
        "size_bytes": 1024000,
        "r2_error": "AccessDenied: Invalid bucket credentials",
        "status": "NO_FILES_CREATED",
        "cleanup": "NONE_NEEDED"
    }
}
```

**Recovery**: 
- Check R2 credentials and bucket permissions
- Verify network connectivity to Cloudflare R2
- Retry upload after fixing credentials

**User Impact**: ✅ Safe - no orphaned files, no data loss

---

### MONGODB_INSERT_FAILED

**When**: MongoDB insert fails after successful R2 upload, and cleanup succeeds.

**Severity**: Medium

**Data State**: Clean - R2 file was successfully deleted during cleanup.

**Example**:
```json
{
    "success": false,
    "action": "persist",
    "error": "Failed to save content metadata to MongoDB",
    "error_code": "MONGODB_INSERT_FAILED",
    "details": {
        "content_type_id": "image-png",
        "filename": "test.png",
        "r2_status": "UPLOADED_SUCCESSFULLY",
        "r2_data_ref": "r2://bucket/images/uuid-123",
        "mongodb_status": "WRITE_ERROR",
        "mongodb_error": "Connection timeout",
        "cleanup_attempted": true,
        "cleanup_status": "SUCCESS",
        "status": "ORPHANED_FILE_CLEANED_UP",
        "action_needed": "NONE - file was deleted from R2"
    }
}
```

**Recovery**:
- Check MongoDB connection and credentials
- Verify database write permissions
- Retry persist action after fixing MongoDB

**User Impact**: ✅ Safe - no orphaned files, automatic cleanup succeeded

---

### ORPHANED_FILE_CLEANUP_FAILED

**When**: MongoDB insert fails after successful R2 upload, AND cleanup also fails.

**Severity**: 🚨 CRITICAL

**Data State**: ⚠️ Inconsistent - File exists in R2 but no metadata in MongoDB.

**Example**:
```json
{
    "success": false,
    "action": "persist",
    "error": "CRITICAL: Orphaned file remains in R2",
    "error_code": "ORPHANED_FILE_CLEANUP_FAILED",
    "details": {
        "content_type_id": "image-png",
        "filename": "test.png",
        "r2_data_ref": "r2://bucket/images/uuid-123",
        "mongodb_error": "Connection timeout",
        "cleanup_error": "R2 connection lost",
        "status": "ORPHANED_FILE_IN_R2",
        "action_needed": "MANUAL - Contact admin: Delete r2://bucket/images/uuid-123 from R2 console",
        "alert_level": "CRITICAL"
    }
}
```

**Recovery**:
1. **IMMEDIATE**: Alert system administrators
2. **MANUAL**: Delete orphaned file from R2 console using the provided `r2_data_ref`
3. **VERIFY**: Check MongoDB and R2 connections
4. **CLEANUP**: Document the incident and orphaned file reference
5. **RETRY**: After fixing both MongoDB and R2, retry persist action

**User Impact**: ⚠️ Orphaned file - manual intervention required

**Prevention**: 
- Ensure stable connections to both MongoDB and R2
- Monitor connection health
- Implement automated orphaned file detection

---

### VALIDATION_ERROR

**When**: Input validation fails (missing parameters, invalid content type, file too large, invalid fragments).

**Severity**: Low

**Data State**: Clean - validation happens before any persistence.

**Examples**:

**Missing Required Field**:
```json
{
    "success": false,
    "error": "Missing 'content_type_id' parameter",
    "error_code": "VALIDATION_ERROR"
}
```

**Invalid Content Type**:
```json
{
    "success": false,
    "error": "ContentType not found: invalid-type",
    "error_code": "VALIDATION_ERROR"
}
```

**File Too Large**:
```json
{
    "success": false,
    "error": "File too large. Max size for image-png: 10485760 bytes, got: 20000000 bytes",
    "error_code": "VALIDATION_ERROR"
}
```

**Invalid Fragments**:
```json
{
    "success": false,
    "error": "Missing required fragment 'width' for ContentType 'image-png'",
    "error_code": "VALIDATION_ERROR"
}
```

**Recovery**:
- Fix the validation error based on the error message
- Verify input parameters match ContentType requirements
- Retry with corrected parameters

**User Impact**: ✅ Safe - no files created, no data loss

---

## Persistence Flow

The new atomic persistence flow prevents orphaned files:

```
1. Validate Input Parameters
   ✅ Success → Continue
   ❌ Failure → Return VALIDATION_ERROR

2. Upload to R2 (FIRST)
   ✅ Success → Continue with real data_ref
   ❌ Failure → Return R2_UPLOAD_FAILED

3. Insert to MongoDB (SECOND)
   ✅ Success → Return success
   ❌ Failure → Attempt cleanup:
       ✅ Cleanup Success → Return MONGODB_INSERT_FAILED
       ❌ Cleanup Failure → Return ORPHANED_FILE_CLEANUP_FAILED (CRITICAL)
```

## Migration: contents_runtime Collection

The persist action now uses the `contents_runtime` collection with proper schema validation and indexes:

**Indexes**:
- `id` (unique): Primary identifier
- `content_type_id`: Filter by content type
- `assignee_id`: Filter by owner
- `created_at`: Sort by creation date
- `tags`: Tag-based queries
- `data_ref` (unique): Prevent duplicate file tracking
- `status`: Filter by lifecycle state
- `origin_cell_id`: Lineage tracking

**Schema Validation**:
- Required: `id`, `content_type_id`, `assignee_id`, `data_ref`
- Status enum: `["pending", "live", "deleted"]`

## Monitoring & Alerts

**CRITICAL Alerts** (immediate response required):
- `ORPHANED_FILE_CLEANUP_FAILED`: Orphaned file in R2 requires manual cleanup

**Warning Alerts** (investigate and resolve):
- Multiple `MONGODB_INSERT_FAILED`: Check MongoDB health
- Multiple `R2_UPLOAD_FAILED`: Check R2 connectivity

**Info Alerts** (track trends):
- Frequent `VALIDATION_ERROR`: May indicate client-side issues

## Related Documentation

- [Content Manager Cell Overview](./README.md)
- [Content Types Documentation](../../../canonical/content_types/README.md)
- [Storage Backend Configuration](../backend/scripts/storage.py)
- [Test Cases](../backend/tests/test_main.py)

---

**Last Updated**: 2026-02-12  
**Version**: 1.0.0  
**Author**: Code Agent
