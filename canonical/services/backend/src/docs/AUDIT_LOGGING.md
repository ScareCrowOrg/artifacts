---
processed: true
processed_date: 2025-12-09
themes:
  - backend
  - logging
  - audit
  - monitoring
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# Audit Logging System - Documentation

## Overview

The audit logging system provides comprehensive tracking of security-sensitive operations in the ScareVerse backend, including:

- Permission denied events (403 Forbidden)
- Role assignments and removals
- Administrative actions
- Real-time alerting for critical security events

## Architecture

### Components

1. **audit_logger.py** - Core audit logging module
   - `AuditLog` class for structured log entries
   - Logging functions for specific event types
   - Persistence to JSON database
   - File-based logging to `backend/logs/audit.log`

2. **alerting.py** - Real-time alerting module
   - Slack webhook integration
   - Severity-based alert routing
   - Critical event notifications

3. **audit_router.py** - REST API for audit log access
   - `/api/audit/logs` - Query and filter audit logs
   - `/api/audit/stats` - Aggregate statistics

4. **Integration Points**
   - `permissions.py` - Logs permission denials
   - `roles_router.py` - Logs role changes

## Usage

### Logging Permission Denied

```python
from app.audit_logger import log_permission_denied

log_permission_denied(
    user_id="user-123",
    required_permission="admin.access",
    endpoint="/api/admin/config",
    ip_address="192.168.1.1"
)
```

### Logging Role Assignment

```python
from app.audit_logger import log_role_assigned

log_role_assigned(
    admin_id="admin-1",
    user_id="user-123",
    role_name="admin",
    ip_address="192.168.1.1"
)
# Automatically triggers Slack alert for admin role
```

### Logging Role Removal

```python
from app.audit_logger import log_role_removed

log_role_removed(
    admin_id="admin-1",
    user_id="user-123",
    role_name="admin",
    ip_address="192.168.1.1"
)
# Automatically triggers Slack alert for critical roles
```

### Logging Admin Actions

```python
from app.audit_logger import log_admin_action

log_admin_action(
    admin_id="admin-1",
    action="config_update",
    details={
        "config_changed": "logging_level",
        "old_value": "INFO",
        "new_value": "DEBUG"
    },
    ip_address="192.168.1.1"
)
```

## API Endpoints

### GET /api/audit/logs

Retrieve audit logs with filtering and pagination.

**Authentication:** Admin only

**Query Parameters:**
- `event_type` (optional) - Filter by event type: `permission_denied`, `role_assigned`, `role_removed`, `admin_action`
- `user_id` (optional) - Filter by user ID
- `start_date` (optional) - Start date in ISO format (e.g., `2025-01-01T00:00:00`)
- `end_date` (optional) - End date in ISO format
- `skip` (optional) - Number of records to skip (default: 0)
- `limit` (optional) - Maximum records to return (default: 100, max: 1000)

**Example Request:**
```bash
curl -H "Authorization: Bearer <admin-token>" \
  "http://localhost:5051/api/audit/logs?event_type=permission_denied&limit=50"
```

**Example Response:**
```json
{
  "total": 125,
  "skip": 0,
  "limit": 50,
  "logs": [
    {
      "id": "permission_denied_user-123_1234567890.1",
      "event_type": "permission_denied",
      "user_id": "user-123",
      "resource_type": "endpoint",
      "resource_id": "/api/admin/config",
      "action": "access_attempt",
      "details": {
        "required_permission": "admin.access",
        "reason": "insufficient_permissions"
      },
      "ip_address": "192.168.1.1",
      "timestamp": "2025-01-01T10:00:00"
    }
  ]
}
```

### GET /api/audit/stats

Retrieve audit log statistics.

**Authentication:** Admin only

**Example Request:**
```bash
curl -H "Authorization: Bearer <admin-token>" \
  "http://localhost:5051/api/audit/stats"
```

**Example Response:**
```json
{
  "permission_denied_count": 125,
  "role_changes_count": 15,
  "admin_actions_count": 42,
  "top_denied_permissions": [
    {
      "permission": "admin.access",
      "count": 45
    },
    {
      "permission": "cells.delete_any",
      "count": 32
    }
  ]
}
```

## Alerting Configuration

### Slack Webhook Setup

1. Create a Slack Incoming Webhook in your workspace
2. Set the environment variable:
   ```bash
   export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
   ```

### Alert Triggers

**Admin Role Assignment** (Warning)
- Triggered when any user is assigned the `admin` role
- Includes admin ID, target user ID, and IP address

**Critical Role Removal** (Warning)
- Triggered when `admin` or `security_admin` roles are removed
- Includes admin ID, target user ID, and IP address

**High Permission Denial Rate** (Error)
- Manual trigger for anomaly detection
- Can be integrated with monitoring systems

### Alert Severity Levels

- **Info** (Green) - Informational events
- **Warning** (Orange) - Security-sensitive actions
- **Error** (Red) - Critical security events or anomalies

## File Structure

```
backend/
├── app/
│   ├── audit_logger.py          # Core audit logging module
│   ├── alerting.py               # Slack alerting integration
│   ├── permissions.py            # Updated with audit logging
│   └── routers/
│       ├── audit_router.py       # Audit logs API
│       └── roles_router.py       # Updated with audit logging
├── logs/
│   └── audit.log                 # Structured audit log file
└── tests/
    ├── unit/
    │   ├── test_audit_logger.py  # Unit tests for audit logger
    │   └── test_alerting.py      # Unit tests for alerting
    └── integration/
        └── test_audit_router.py  # Integration tests for API
```

## Log Format

### File Logs (`backend/logs/audit.log`)

```
2025-01-01T10:00:00 | WARNING | PERMISSION_DENIED | user=user-123 | permission=admin.access | endpoint=/api/admin/config | ip=192.168.1.1
2025-01-01T11:00:00 | INFO | ROLE_ASSIGNED | admin=admin-1 | user=user-123 | role=admin | ip=192.168.1.2
2025-01-01T12:00:00 | WARNING | ROLE_REMOVED | admin=admin-1 | user=user-123 | role=viewer | ip=192.168.1.2
```

### Database Storage

Audit logs are stored in the `audit_logs` collection (canonical artifacts) with the following schema:

```json
{
  "id": "permission_denied_user-123_1234567890.1",
  "event_type": "permission_denied",
  "user_id": "user-123",
  "resource_type": "endpoint",
  "resource_id": "/api/admin/config",
  "action": "access_attempt",
  "details": {
    "required_permission": "admin.access",
    "reason": "insufficient_permissions"
  },
  "ip_address": "192.168.1.1",
  "timestamp": "2025-01-01T10:00:00"
}
```

## Performance Considerations

- **Latency Impact:** Audit logging adds minimal overhead (<10ms per request)
- **Async Persistence:** Database writes are non-blocking to avoid slowing down API responses
- **File Rotation:** Configure log rotation for `audit.log` to prevent disk space issues
- **Indexing:** Consider adding indexes on `timestamp`, `event_type`, and `user_id` fields for faster queries

## Security Best Practices

1. **Protect Audit Logs:** Only admins can access audit logs
2. **Immutable Logs:** Audit logs should never be deleted or modified
3. **Archive Old Logs:** Implement log archival strategy (e.g., move logs older than 90 days to cold storage)
4. **Monitor Alerts:** Ensure Slack alerts are being received and reviewed
5. **Regular Review:** Schedule periodic review of audit logs for security incidents

## Monitoring Integration (Future)

The audit logging system is designed to integrate with monitoring tools:

### Grafana Dashboard Queries

**Permission Denied Rate:**
```promql
rate(audit_log_permission_denied_total[5m])
```

**Role Changes (Last 24h):**
```promql
audit_log_role_changes_total
```

**Top Denied Permissions:**
```loki
{job="backend"} |= "PERMISSION_DENIED" | pattern "<_> | permission=<permission>" | count by permission
```

## Troubleshooting

### Logs Not Being Created

1. Check that `backend/logs/` directory exists and is writable
2. Verify `BASE_DIR` configuration in `config.py`
3. Check file handler permissions in `audit_logger.py`

### Alerts Not Being Sent

1. Verify `SLACK_WEBHOOK_URL` environment variable is set
2. Check network connectivity to Slack API
3. Review logs for alerting errors

### Database Persistence Failures

1. Check database connection status
2. Verify `audit_logs` collection exists in canonical artifacts
3. Review error logs in `audit.log`

## Testing

Run the comprehensive test suite:

```bash
# Unit tests
pytest tests/unit/test_audit_logger.py -v
pytest tests/unit/test_alerting.py -v

# Integration tests
pytest tests/integration/test_audit_router.py -v

# All audit tests
pytest tests/ -k audit -v
```

## Future Enhancements

1. **Real-time Dashboard:** Web UI for audit log visualization
2. **Advanced Analytics:** Machine learning for anomaly detection
3. **Compliance Reports:** Automated generation of compliance audit reports
4. **Multi-Channel Alerts:** Email, PagerDuty, Teams integration
5. **Log Retention Policies:** Configurable retention and archival

---

**Last Updated:** 2025-11-27  
**Module Version:** 1.0.0  
**Maintained By:** Backend Agent
