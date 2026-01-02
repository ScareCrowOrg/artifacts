# Pipeline Monitoring Cell - Authentication Fix

## Change Summary

**Date**: 2026-01-02  
**Type**: Bug Fix  
**Impact**: Critical functionality restored

## What Was Fixed

Fixed WebSocket authentication error that prevented the pipeline monitoring cell from connecting to real-time monitoring events.

### Root Cause

The `useMonitoringWebSocket` composable was attempting to retrieve the authentication token using an incorrect localStorage key:

```typescript
// BEFORE (incorrect)
const token = localStorage.getItem('auth_token')

// AFTER (correct)
const token = localStorage.getItem('scareverse_token')
```

### Why This Matters

The ScareVerse authentication service (`authService.js`) stores the JWT token under the key `scareverse_token`. Using the wrong key meant:
- WebSocket connection always failed
- No real-time monitoring updates
- No alert notifications
- Console errors on every cell initialization

## Files Changed

| File | Change | Lines |
|------|--------|-------|
| `frontend/composables/useMonitoringWebSocket.ts` | Token key correction | 1 |

## Testing

### Manual Testing Required

After deployment, verify:
1. ✅ Login to ScareVerse Cockpit
2. ✅ Create or open a notebook with `pipeline-monitoring-cell`
3. ✅ Check browser console - no "No auth token found" error
4. ✅ Verify WebSocket connection established
5. ✅ Verify real-time updates are received

### Automated Testing

- ✅ No existing tests broken by this change
- ℹ️ No specific tests exist for WebSocket authentication
- 📝 Future work: Add tests for WebSocket connection with auth

## Related Documentation

For complete analysis, see:
- [`/docs/issues/authentication-websocket-extension-errors/`](../../../../docs/issues/authentication-websocket-extension-errors/)
- [`ANALYSIS.md`](../../../../docs/issues/authentication-websocket-extension-errors/ANALYSIS.md) - Technical deep dive
- [`EXECUTIVE_SUMMARY.md`](../../../../docs/issues/authentication-websocket-extension-errors/EXECUTIVE_SUMMARY.md) - Stakeholder report

## Token Storage Convention

For future reference, the official token storage keys in ScareVerse are:

```javascript
// Defined in: cockpit-vue/src/services/authService.js
const TOKEN_KEY = 'scareverse_token'
const USER_KEY = 'scareverse_user'
const SESSION_KEY = 'scareverse_session'
const TOKEN_EXPIRY_KEY = 'scareverse_token_expiry'
```

**Best Practice**: Import and use `authService.getToken()` instead of accessing localStorage directly.

## Compatibility

- ✅ **Backwards Compatible**: Yes
- ✅ **Breaking Changes**: None
- ✅ **Migration Required**: None
- ✅ **Environment Impact**: None

## Rollback Plan

If issues arise, revert to previous commit. However, this is unlikely as:
- Change is minimal (1 line)
- Restores correct functionality
- No architectural changes
- No dependency changes

---

**Fixed by**: GitHub Copilot Agent  
**Reviewed by**: (pending)  
**Deployed**: (pending)
