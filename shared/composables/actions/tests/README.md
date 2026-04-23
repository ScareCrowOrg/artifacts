# Sessions Actions Tests

Unit tests for `sessionsActions.js` — the AgentLab action link that manages session creation, listing, and closing via the CentralHub API.

## Purpose

This directory validates the sessions action registration and all session management operations:
- **Action registration**: Validates that `registerSessionsActions` correctly registers all actions
- **create_session**: Tests success, missing parameters, API errors, and HTTP errors
- **list_user_sessions**: Tests success, missing parameters, API errors, and empty list handling
- **close_session**: Tests success, missing parameters, and API error handling
- **ChatStore integration**: Validates `insertContentIntoInput` and `addAttachment` interactions

## Directory Structure

```
tests/
└── sessionsActions.test.js   - Full test suite for sessionsActions.js action link
```

## How to Use

```bash
# Run from the cockpit-vue root
cd cockpit-vue
npm test

# Run only this test file
npx vitest run src/shared/composables/actions/tests/sessionsActions.test.js
```

## Content Index

| File | Description |
|---|---|
| `sessionsActions.test.js` | Tests for session CRUD actions: register, create, list, close, error handling |
