---
processed: true
processed_date: 2025-12-09
themes:
  - operations
  - logging
  - security
  - audit
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# Backend Logs Directory

This directory contains application logs for the ScareVerse backend.

## Log Files

### audit.log
**Purpose:** Security audit trail for RBAC operations  
**Format:** Structured text logs with timestamp, level, and event details  
**Retention:** Configure log rotation (recommended: 90 days)

**Example entries:**
```
2025-01-01T10:00:00 | WARNING | PERMISSION_DENIED | user=user-123 | permission=admin.access | endpoint=/api/admin/config | ip=192.168.1.1
2025-01-01T11:00:00 | INFO | ROLE_ASSIGNED | admin=admin-1 | user=user-123 | role=admin | ip=192.168.1.2
```

## Log Rotation

Configure log rotation to prevent disk space issues:

### Using logrotate (Linux)

Create `/etc/logrotate.d/scareverse-backend`:

```
/path/to/ScareVerseLab/backend/logs/*.log {
    daily
    rotate 90
    compress
    delaycompress
    notifempty
    create 0644 runner runner
    sharedscripts
    postrotate
        # Optional: restart backend service
        # systemctl reload scareverse-backend
    endscript
}
```

### Manual Rotation

```bash
# Archive old logs
mv audit.log audit.log.$(date +%Y%m%d)
gzip audit.log.$(date +%Y%m%d)

# Restart logging (backend will create new file)
```

## Log Levels

- **INFO:** Normal audit events (role assignments, admin actions)
- **WARNING:** Security-sensitive events (permission denials, role removals)
- **ERROR:** System errors during audit logging

## Monitoring

Monitor log files for security incidents:

```bash
# Watch for permission denials
tail -f audit.log | grep PERMISSION_DENIED

# Count recent permission denials
grep PERMISSION_DENIED audit.log | tail -100 | wc -l

# Find admin role assignments
grep "ROLE_ASSIGNED.*role=admin" audit.log
```

## Security

- **Access Control:** Restrict read access to administrators only
- **Immutability:** Never delete or modify audit logs
- **Backup:** Include logs in backup strategy
- **Archival:** Move old logs to secure long-term storage

---

**Note:** This directory is excluded from Git via `.gitignore` to prevent committing sensitive log data.
