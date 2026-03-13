---
processed: true
processed_date: 2025-12-09
themes:
  - authentication
  - token-expiration
  - error-handling
  - ux
modules:
  - frontend
code_verified: true
dead_docs_found: false
---
# Token Expiration Implementation Summary

## Overview
This document describes the implementation of automatic token expiration detection and redirect to login functionality for the ScareVerse Cockpit Vue.js application.

## Problem Statement
When a user's authentication token expires, the application would receive 401 errors from API calls but there was no clear indication to the user that they needed to log in again. This led to a poor user experience and confusion.

## Solution
Implemented a centralized API service that intercepts all HTTP requests and automatically handles 401 (Unauthorized) errors by:
1. Detecting token expiration via 401 responses
2. Clearing authentication data
3. Redirecting the user to the login screen
4. Displaying a clear message: "Sessão expirada. Por favor, faça login novamente."

## Implementation Details

### 1. New API Service (`src/services/apiService.js`)
Created a centralized service that wraps the native `fetch` API:
- **Automatic Auth Headers**: Adds authentication headers from `authService` automatically
- **401 Detection**: Intercepts 401 responses and triggers session expiration flow
- **Event System**: Provides a callback mechanism (`onSessionExpired`) to notify the application
- **Error Propagation**: Throws a special `SESSION_EXPIRED` error that components can handle

### 2. App.vue Updates
- Added `sessionExpiredMessage` state to hold the expiration message
- Registered a session expiration handler that sets the message and resets auth state
- Passes the message to the `LoginPanel` component for display
- Automatically redirects to login when auth state becomes invalid

### 3. LoginPanel.vue Updates
- Added prop `sessionExpiredMessage` to receive expiration message
- Displays the message in a prominent orange banner above the login button
- Message styling uses warning colors (orange background, white text) to draw attention

### 4. Component Updates
Updated all components that make API calls to use the new `apiService`:
- `ChatIA.vue` - Chat with AI functionality
- `ServiceManagement.vue` - Service management operations
- `AppHeader.vue` - AutoHotkey status checks
- `FileBrowser.vue` - File listing and loading
- `NotebookCell.vue` - Content saving
- `UnifiedSettingsPanel.vue` - Settings and service operations

Each component now:
- Imports and uses `apiService.fetch()` instead of native `fetch()`
- Handles `SESSION_EXPIRED` errors gracefully without showing redundant error messages
- Removes manual auth header management (handled by apiService)

## User Experience Flow

### Scenario 1: Token Expires During Usage
1. User is logged in and using the application
2. Token expires (e.g., after 7 days)
3. User performs an action that makes an API call
4. API returns 401 Unauthorized
5. apiService detects 401 and triggers session expiration
6. Auth data is cleared from localStorage
7. User is automatically redirected to login screen
8. Orange banner displays: "Sessão expirada. Por favor, faça login novamente."
9. User can click "Entrar com Google" to log in again

### Scenario 2: First Visit (No Token)
1. User visits the application
2. If auth is required, login panel is shown
3. No session expiration message is displayed
4. User can proceed with login normally

## Testing

### E2E Test Coverage
Created comprehensive E2E tests in `e2e/token-expiration-flow.spec.js`:

1. **Test: Redirect on 401 from Chat API**
   - Simulates authenticated user
   - Mocks 401 response from chat API
   - Verifies redirect to login
   - Verifies session expiration message is displayed
   - Verifies localStorage is cleared

2. **Test: Redirect on 401 from Service Status API**
   - Simulates authenticated user
   - Mocks 401 response from services endpoint
   - Verifies session expiration handling

3. **Test: No Message on First Login**
   - Verifies session expiration message is NOT shown on first visit
   - Ensures clean UX for new users

4. **Test: Message Clearing After Login**
   - Verifies message is cleared after successful re-login
   - Tests complete flow reset

### Manual Testing Scenarios
To manually test this feature:

1. **Simulate Token Expiration**:
   - Log in to the application
   - Open browser DevTools → Application → Local Storage
   - Note the current token value
   - Open Network tab and set up a breakpoint or override for API calls to return 401
   - Perform an action (e.g., send a chat message)
   - Observe automatic redirect to login with message

2. **Test Various API Endpoints**:
   - Test with chat API
   - Test with service management
   - Test with file browser
   - All should trigger the same expiration flow

## Technical Benefits

1. **Centralized Error Handling**: Single point of control for all API authentication errors
2. **Consistent UX**: All components behave the same way on token expiration
3. **Reduced Code Duplication**: Auth header management is centralized
4. **Better Security**: Immediate cleanup of expired credentials
5. **Clear User Communication**: Explicit message about session expiration
6. **Maintainability**: Easy to extend with additional error handling logic

## Files Modified

1. `cockpit-vue/src/services/apiService.js` (NEW)
2. `cockpit-vue/src/App.vue`
3. `cockpit-vue/src/components/LoginPanel.vue`
4. `cockpit-vue/src/components/ChatIA.vue`
5. `cockpit-vue/src/components/ServiceManagement.vue`
6. `cockpit-vue/src/components/AppHeader.vue`
7. `cockpit-vue/src/components/FileBrowser.vue`
8. `cockpit-vue/src/components/NotebookCell.vue`
9. `cockpit-vue/src/components/UnifiedSettingsPanel.vue`
10. `cockpit-vue/e2e/token-expiration-flow.spec.js` (NEW)

## Future Enhancements

Possible improvements for future iterations:

1. **Token Refresh**: Implement automatic token refresh before expiration
2. **Countdown Warning**: Show warning before token expires (e.g., "Session expires in 5 minutes")
3. **Background Refresh**: Silently refresh token during user activity
4. **Retry Mechanism**: Automatically retry failed requests after re-authentication
5. **Activity Tracking**: Extend session timeout based on user activity
6. **Multiple Token Types**: Handle different types of auth errors (expired, invalid, revoked)

## Acceptance Criteria Status

✅ User is redirected to login screen when token expires or is invalid  
✅ Clear message "Sessão expirada. Por favor, faça login novamente." is displayed  
✅ Flow tested for different scenarios of token expiration  
✅ All API-calling components updated to use centralized service  
✅ Authentication data properly cleared on expiration  
✅ Build passes without errors  
✅ E2E tests created for validation  

## Conclusion

This implementation provides a robust and user-friendly solution for handling token expiration in the ScareVerse Cockpit application. The centralized approach ensures consistency across all components while maintaining clean separation of concerns and following Vue.js best practices.
