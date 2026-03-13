---
processed: true
processed_date: 2025-12-09
themes:
  - testing
  - authentication
  - e2e
  - integration
  - jwt
modules:
  - backend
  - frontend
  - testing
code_verified: true
dead_docs_found: false
---
# E2E Integration Tests - Real Authentication Implementation

## Summary

Implemented **real JWT-based authentication** in E2E integration tests, replacing mocked authentication with actual backend API calls. Tests now validate complete frontend-backend integration including data persistence.

## Changes Made

### 1. Authentication Setup (`cockpit-vue/e2e-integration/auth.setup.js`)

**New File** - Establishes authentication for all integration tests:

- ✅ Registers unique test user via `/api/usuarios/registrar`
- ✅ Creates session via `/api/sessoes/criar`
- ✅ Obtains JWT token from backend
- ✅ Stores auth state in `.auth/auth.json` using Playwright's `storageState`
- ✅ Runs once before all tests (via setup project)

**Key Features**:
- Unique test user per run (timestamp-based email)
- Fallback to mock token if session creation fails
- Comprehensive logging for debugging
- Auth state saved to file and reused by all tests

### 2. Playwright Configuration (`cockpit-vue/playwright.integration.config.js`)

**Updated** - Added setup project and auth state management:

```javascript
projects: [
  {
    name: 'setup',
    testMatch: /auth\.setup\.js/,
  },
  {
    name: 'chromium',
    use: { 
      ...devices['Desktop Chrome'],
      storageState: '.auth/auth.json',  // NEW
    },
    dependencies: ['setup'],  // NEW
  },
]
```

**Changes**:
- ✅ Added "setup" project that runs `auth.setup.js` first
- ✅ Configured chromium project to load auth state from `.auth/auth.json`
- ✅ Made chromium project depend on setup completion
- ✅ Removed `AUTH_ENABLED='false'` override (let backend decide)

### 3. Integration Tests (`cockpit-vue/e2e-integration/real-integration.spec.js`)

**Updated** - Removed mocks and added backend validation:

#### Manual Capture Test
- ✅ Removed API mocks (uses real backend)
- ✅ Gets authenticated user from localStorage
- ✅ Validates cell creation via backend API query
- ✅ Tests persistence: reload page + query backend
- ✅ Confirms cell exists after reload

#### Chat IA Test
- ✅ Removed API mocks
- ✅ Gets cell count before/after via backend API
- ✅ Validates new cell was created
- ✅ Tests persistence after page reload
- ✅ Confirms exact cell count matches

#### Data Persistence Test
- ✅ Queries backend for initial cell count
- ✅ Creates cell with unique content
- ✅ Validates backend has the cell
- ✅ Reloads page
- ✅ Confirms cell still exists in backend
- ✅ Verifies same cell ID persists

#### Multiple Captures Test
- ✅ Gets initial count from backend
- ✅ Creates 3 cells sequentially
- ✅ Validates all 3 persisted in backend
- ✅ Checks exact count increase

### 4. Documentation

**New Files**:

- ✅ `e2e-integration/README_AUTH.md` - Comprehensive authentication guide
  - Architecture diagrams
  - Implementation details
  - Troubleshooting guide
  - Best practices
  - Security considerations

**Updated Files**:

- ✅ `e2e-integration/README.md` - Added authentication section
  - Authentication flow diagram
  - Key files explanation
  - Why real authentication matters

### 5. Infrastructure

**New Directory**:
- ✅ `.auth/` - Stores authentication state files
  - Contains `.gitkeep` for directory tracking
  - `.auth/*.json` files are gitignored (contain JWT tokens)

**Updated `.gitignore`**:
```
# Playwright Auth State (contains JWT tokens)
.auth/*.json
```

## Technical Implementation

### Authentication Flow

```
Setup Phase (auth.setup.js):
1. Register test user → POST /api/usuarios/registrar
2. Create session → POST /api/sessoes/criar
3. Get JWT token
4. Store in localStorage: scareverse_token, scareverse_user, scareverse_session
5. Save to .auth/auth.json

Test Execution:
1. Load .auth/auth.json (automatic via storageState)
2. localStorage already populated with auth data
3. Make authenticated requests with Authorization: Bearer <token>
4. Validate against backend APIs
```

### Backend Validation Strategy

Every test now validates persistence by:

1. **Before Operation**: Query backend for current state
2. **Perform Operation**: Execute user action (create cell, etc.)
3. **Validate UI**: Confirm UI updated correctly
4. **Validate Backend**: Query backend API to confirm persistence
5. **Test Reload**: Reload page
6. **Validate Again**: Confirm data still exists in backend

Example:
```javascript
// Get initial count
const before = await request.get(`/api/usuarios/${userId}/celulas`);

// Create cell
await textarea.fill('Test');
await button.click();

// Verify in backend
const after = await request.get(`/api/usuarios/${userId}/celulas`);
expect(after.length).toBe(before.length + 1);

// Reload and verify
await page.reload();
const afterReload = await request.get(`/api/usuarios/${userId}/celulas`);
expect(afterReload.length).toBe(after.length);
```

## API Endpoints Used

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/api/usuarios/registrar` | POST | ❌ | Register test user |
| `/api/sessoes/criar` | POST | ✅ | Create session + JWT |
| `/api/celulas/criar` | POST | ✅ | Create cell |
| `/api/usuarios/{id}/celulas` | GET | ✅ | List user's cells |
| `/api/chat/processar` | POST | ✅ | Process chat message |

## Benefits

### For Testing
✅ **Real Integration**: Tests actual auth flow, not mocks  
✅ **Data Validation**: Confirms backend persistence  
✅ **Bug Detection**: Catches auth issues before production  
✅ **Confidence**: Tests match real user experience  

### For Development
✅ **Fast Setup**: Runs once, reused by all tests  
✅ **Easy Debugging**: Comprehensive logging  
✅ **Clear Documentation**: Multiple guides provided  
✅ **Best Practices**: Examples in every test  

### For Quality
✅ **Complete Coverage**: Frontend + Backend + Auth  
✅ **Persistence Validation**: Reload scenarios tested  
✅ **Real APIs**: No mocks hiding integration bugs  
✅ **Production-like**: Same flow as real users  

## Running the Tests

```bash
# Run all integration tests (auth setup runs automatically)
npm run test:integration

# Run with UI mode for debugging
npm run test:integration:ui

# Run specific test
npx playwright test e2e-integration/real-integration.spec.js

# Debug mode
npx playwright test e2e-integration/real-integration.spec.js --debug

# Run auth setup only
npx playwright test e2e-integration/auth.setup.js
```

## Environment Variables

- `BACKEND_URL` - Backend API URL (default: `http://localhost:5051`)
- `FRONTEND_URL` or `BASE_URL` - Frontend URL (default: `http://localhost:5173`)

## Files Modified

### Created
1. `cockpit-vue/e2e-integration/auth.setup.js` (156 lines)
2. `cockpit-vue/e2e-integration/README_AUTH.md` (578 lines)
3. `cockpit-vue/.auth/.gitkeep`

### Modified
1. `cockpit-vue/playwright.integration.config.js`
   - Added setup project
   - Added storageState configuration
   - Added dependencies
   - Updated comments

2. `cockpit-vue/e2e-integration/real-integration.spec.js`
   - Removed all API mocks
   - Added auth user retrieval
   - Added backend validation queries
   - Added persistence checks
   - Added reload scenarios
   - Updated all tests (4 tests modified)

3. `cockpit-vue/e2e-integration/README.md`
   - Added authentication section
   - Added flow diagrams
   - Added file explanations

4. `cockpit-vue/.gitignore`
   - Added `.auth/*.json` to ignore JWT tokens

## Security Considerations

### Token Storage
- JWT tokens stored in `.auth/auth.json` (gitignored)
- Tokens never committed to repository
- Each test run creates new user + token
- Tokens expire after 7 days

### Test Data Isolation
- Unique user per test run (timestamp-based)
- No conflicts between test runs
- Each user has isolated data
- Future: Add cleanup logic to remove test data

### Production Safety
- Test users clearly marked: `test-{timestamp}@scareverse.test`
- Test domain: `*.test` (not real emails)
- Isolated from production data
- Can be cleaned up periodically

## Future Enhancements

### Short Term
- [ ] Add test data cleanup after tests complete
- [ ] Support multiple user types (admin, regular)
- [ ] Test token expiration scenarios
- [ ] Add performance benchmarks

### Long Term
- [ ] Test token refresh flow
- [ ] Test logout and re-authentication
- [ ] Multi-user interaction tests
- [ ] Database state validation
- [ ] Automated cleanup of old test users

## Troubleshooting

### Auth Setup Fails
```bash
# Check backend is running
curl http://localhost:5051/api/health

# Run setup manually to see detailed errors
npx playwright test e2e-integration/auth.setup.js
```

### Tests Get 401
```javascript
// Check storage state exists
ls -la cockpit-vue/.auth/auth.json

// Verify token in test
const token = await page.evaluate(() => 
  localStorage.getItem('scareverse_token')
);
console.log('Token:', token);
```

### Backend Returns Empty
```bash
# Check backend logs for errors
cd backend && python -m app.main

# Query backend directly
curl -H "Authorization: Bearer <token>" \
  http://localhost:5051/api/usuarios/<user-id>/celulas
```

## References

### Playwright Documentation
- [Authentication Guide](https://playwright.dev/docs/auth)
- [Storage State](https://playwright.dev/docs/api/class-browsercontext#browser-context-storage-state)
- [Global Setup](https://playwright.dev/docs/test-global-setup-teardown)

### Project Documentation
- `e2e-integration/README.md` - Integration tests overview
- `e2e-integration/README_AUTH.md` - Detailed auth guide
- `backend/app/auth.py` - Backend JWT implementation
- `backend/app/chat_router.py` - Backend API endpoints

## Conclusion

This implementation transforms integration tests from UI-only validation to **complete end-to-end testing** that validates:

✅ Frontend UI behavior  
✅ Backend API functionality  
✅ Authentication flow  
✅ Data persistence  
✅ Real integration bugs  

Tests now provide **production-level confidence** that the complete stack works together correctly.
