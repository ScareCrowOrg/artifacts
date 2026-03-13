---
processed: true
processed_date: 2025-12-09
themes:
  - authentication
  - oauth
  - password
  - jwt
  - security
  - index
modules:
  - backend
  - security
code_verified: true
dead_docs_found: false
---
# Authentication Documentation

Complete authentication system documentation for ScareVerse, covering OAuth2, password-based auth, token management, and E2E testing.

## Index

### Implementation Guides
- `AUTH_IMPLEMENTATION.md` - Core authentication implementation details
- `IMPLEMENTATION_SUMMARY_AUTH.md` - Authentication implementation summary
- `PASSWORD_AUTH.md` - Password authentication implementation
- `TOKEN_EXPIRATION_IMPLEMENTATION.md` - Token expiration and refresh handling

### OAuth2 Integration
- `OAUTH_PR_SUMMARY.md` - OAuth2 pull request summary and changes

### Testing
- `E2E_AUTH_IMPLEMENTATION.md` - End-to-end authentication test implementation

## Authentication Methods

### Google OAuth2
Primary authentication method using Google Sign-In:
- User redirected to Google for authentication
- Callback receives authorization code
- Backend exchanges code for tokens
- JWT tokens issued for API access
- Automatic token refresh

See [AUTH_IMPLEMENTATION.md](./AUTH_IMPLEMENTATION.md) for implementation details.

### Password Authentication
Alternative authentication for users without Google accounts:
- User registration with email/password
- Secure password hashing (bcrypt)
- Email verification (optional)
- Password reset flow
- Session management

See [PASSWORD_AUTH.md](./PASSWORD_AUTH.md) for implementation details.

## Token Management

### JWT Tokens
- Access tokens for API authentication
- Refresh tokens for token renewal
- Token expiration handling
- Secure token storage

### Token Lifecycle
1. User authenticates (OAuth2 or password)
2. Backend issues access + refresh tokens
3. Frontend stores tokens securely
4. Access token used for API calls
5. Automatic refresh before expiration
6. Logout invalidates tokens

See [TOKEN_EXPIRATION_IMPLEMENTATION.md](./TOKEN_EXPIRATION_IMPLEMENTATION.md) for details.

## Security Features

### Authentication Flow
- HTTPS required for production
- Secure cookie settings
- CORS configuration
- CSRF protection
- Rate limiting on auth endpoints

### Token Security
- Short-lived access tokens (1 hour)
- Long-lived refresh tokens (7 days)
- Secure storage (httpOnly cookies or localStorage)
- Token rotation on refresh
- Blacklist for revoked tokens

### Password Security
- Minimum password strength requirements
- Bcrypt hashing with salt
- No plain text storage
- Password reset with time-limited tokens
- Account lockout after failed attempts

## API Endpoints

### OAuth2 Endpoints
- `GET /api/auth/google` - Initiate Google OAuth flow
- `GET /api/auth/callback` - OAuth callback handler
- `GET /api/auth/status` - Check authentication status
- `POST /api/auth/logout` - Logout and invalidate tokens

### Password Auth Endpoints
- `POST /api/auth/register` - User registration
- `POST /api/auth/login` - Password-based login
- `POST /api/auth/refresh` - Refresh access token
- `POST /api/auth/forgot-password` - Initiate password reset
- `POST /api/auth/reset-password` - Complete password reset

## Frontend Integration

### OAuth2 Flow
```javascript
// Initiate OAuth flow
window.location.href = '/api/auth/google'

// Handle callback (automatic redirect)
// Backend sets authentication cookies

// Check auth status
const response = await fetch('/api/auth/status')
const { authenticated, user } = await response.json()
```

### Password Flow
```javascript
// Login
const response = await fetch('/api/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email, password })
})
const { access_token, refresh_token, user } = await response.json()

// Store tokens
localStorage.setItem('access_token', access_token)
localStorage.setItem('refresh_token', refresh_token)
```

### Token Refresh
```javascript
// Automatic refresh before expiration
const refreshToken = async () => {
  const refresh = localStorage.getItem('refresh_token')
  const response = await fetch('/api/auth/refresh', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refresh })
  })
  const { access_token } = await response.json()
  localStorage.setItem('access_token', access_token)
}
```

## Testing

### E2E Authentication Tests
Complete test suite for authentication flows documented in [E2E_AUTH_IMPLEMENTATION.md](./E2E_AUTH_IMPLEMENTATION.md).

Tests cover:
- OAuth2 complete flow
- Password authentication
- Token refresh mechanism
- Logout and session cleanup
- Error handling scenarios

### Running Tests
```bash
# Unit tests for auth logic
pytest tests/unit/test_auth.py

# Integration tests for auth endpoints
pytest tests/integration/test_auth_endpoints.py

# E2E auth flow tests
pytest tests/e2e/test_auth_flow.py
```

## Configuration

### Environment Variables
Required in `.env`:
```bash
# OAuth2 Configuration
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret
GOOGLE_REDIRECT_URI=http://localhost:8000/api/auth/callback

# JWT Configuration
JWT_SECRET_KEY=your_secret_key
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7

# Application
FRONTEND_URL=http://localhost:5173
```

### Google OAuth2 Setup
1. Create project in Google Cloud Console
2. Enable Google+ API
3. Configure OAuth consent screen
4. Create OAuth 2.0 credentials
5. Add authorized redirect URIs
6. Copy client ID and secret to `.env`

## Troubleshooting

### Common Issues

**OAuth redirect mismatch**
- Ensure `GOOGLE_REDIRECT_URI` matches Google Console configuration
- Check HTTPS requirement for production

**Token expiration errors**
- Verify token refresh logic is working
- Check system clock synchronization
- Validate token expiration settings

**CORS errors**
- Configure CORS middleware with frontend URL
- Allow credentials in CORS settings
- Check preflight request handling

## Related Documentation

- [Backend App Code](../../app/) - Authentication implementation
- [API Documentation](../api/) - API endpoint details
- [Frontend Auth Components](../../../cockpit-vue/src/components/auth/) - UI components
- [Test Architecture](../../../docs/ARQUITETURA_TESTES.md) - Testing strategy

## Notes

- Always use HTTPS in production
- Never commit secrets to repository
- Implement rate limiting on auth endpoints
- Monitor for suspicious authentication attempts
- Regular security audits recommended
