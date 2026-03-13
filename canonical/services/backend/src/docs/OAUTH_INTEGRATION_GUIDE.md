---
processed: true
processed_date: 2025-12-08
themes:
  - oauth2
  - google
  - authentication
  - security
  - api
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# Google OAuth2 Integration Guide

This guide provides complete instructions for integrating Google OAuth2 authentication with the ScareVerse backend.

## Overview

The backend provides REST API endpoints for Google OAuth2 authentication that follow the standard OAuth2 authorization code flow:

1. **Initiate Login**: Frontend requests auth URL from backend
2. **User Authorization**: User is redirected to Google to authorize
3. **Callback**: Google redirects back to frontend with authorization code
4. **Token Exchange**: Frontend sends code to backend, receives JWT token
5. **Authenticated Requests**: Frontend uses JWT token for authenticated API calls

## API Endpoints

### 1. Check Authentication Status

**Endpoint**: `GET /api/auth/status`

**Description**: Check if OAuth is configured and authentication is enabled.

**Request**:
```bash
curl http://localhost:5051/api/auth/status
```

**Response**:
```json
{
  "authEnabled": true,
  "configured": true
}
```

**Use Case**: Check before showing login button or during app initialization.

---

### 2. Initiate Google Login

**Endpoint**: `GET /api/auth/google`

**Description**: Get Google OAuth authorization URL to start the login flow.

**Parameters**:
- `redirect_uri` (query, required): The URL where Google should redirect after authorization

**Request**:
```bash
curl "http://localhost:5051/api/auth/google?redirect_uri=http://localhost:3000/auth/callback"
```

**Success Response** (200):
```json
{
  "authUrl": "https://accounts.google.com/o/oauth2/v2/auth?client_id=...&redirect_uri=...&response_type=code&scope=openid+email+profile&access_type=online&prompt=select_account"
}
```

**Error Responses**:
- **400 Bad Request**: Missing redirect_uri parameter
  ```json
  {
    "detail": "redirect_uri é obrigatório"
  }
  ```
- **503 Service Unavailable**: OAuth not configured
  ```json
  {
    "detail": "Google OAuth não configurado"
  }
  ```

**Use Case**: Call this endpoint when user clicks "Login with Google" button, then redirect user to the returned `authUrl`.

---

### 3. Handle OAuth Callback

**Endpoint**: `POST /api/auth/google/callback`

**Description**: Exchange authorization code for JWT token and create user session.

**Request Body**:
```json
{
  "code": "4/0AY0e-g7...",
  "redirect_uri": "http://localhost:3000/auth/callback"
}
```

**Request**:
```bash
curl -X POST http://localhost:5051/api/auth/google/callback \
  -H "Content-Type: application/json" \
  -d '{
    "code": "4/0AY0e-g7...",
    "redirect_uri": "http://localhost:3000/auth/callback"
  }'
```

**Success Response** (200):
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "usuario": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "nome": "John Doe",
    "email": "john.doe@example.com",
    "googleId": "103547991597142817347",
    "dataRegistro": "2025-10-31T21:00:00Z",
    "galaxia": "GalaxiaPadrao",
    "nivel": 1,
    "mascote": {
      "nome": "ScaryBot",
      "tipo": "IA"
    }
  },
  "sessao": {
    "id": "650e8400-e29b-41d4-a716-446655440000",
    "usuarioId": "550e8400-e29b-41d4-a716-446655440000",
    "dataCriacao": "2025-10-31T21:00:00Z",
    "dataExpiracao": "2025-11-07T21:00:00Z",
    "ativa": true,
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
}
```

**Error Responses**:
- **400 Bad Request**: Missing required parameters
  ```json
  {
    "detail": "code e redirect_uri são obrigatórios"
  }
  ```
- **401 Unauthorized**: Invalid authorization code
  ```json
  {
    "detail": "Falha ao obter token do Google"
  }
  ```
- **503 Service Unavailable**: OAuth not configured
  ```json
  {
    "detail": "Google OAuth não configurado corretamente"
  }
  ```

**Use Case**: Call this endpoint from your OAuth callback route after Google redirects back with the authorization code.

**Notes**:
- The backend automatically creates a new user if this is their first login
- If a user with the same email exists, it links the Google ID to that user
- Sessions expire after 7 days

---

## Frontend Integration Example

Complete frontend integration examples (Vue.js, React, vanilla JavaScript) are available in:

📚 **[OAUTH_FRONTEND_EXAMPLES.md](./docs/auth/OAUTH_FRONTEND_EXAMPLES.md)**

The frontend integration examples include:
- Vue.js complete implementation
- React hooks and context-based authentication
- Vanilla JavaScript examples
- Best practices for token storage and error handling
- Manual testing procedures

### Quick Start (JavaScript)

Basic flow for any JavaScript framework:

```javascript
// 1. Check auth status
const res1 = await fetch('http://localhost:5051/api/auth/status');
const { authEnabled } = await res1.json();

// 2. Get auth URL
const redirectUri = `${window.location.origin}/auth/callback`;
const res2 = await fetch(`http://localhost:5051/api/auth/google?redirect_uri=${encodeURIComponent(redirectUri)}`);
const { authUrl } = await res2.json();

// 3. Redirect to Google
window.location.href = authUrl;

// 4. Handle callback (on /auth/callback page)
const code = new URLSearchParams(window.location.search).get('code');
const res3 = await fetch('http://localhost:5051/api/auth/google/callback', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ code, redirect_uri: redirectUri })
});
const { token, usuario } = await res3.json();

// 5. Store token and make authenticated requests
localStorage.setItem('auth_token', token);
fetch(endpoint, {
  headers: { 'Authorization': `Bearer ${token}` }
});
```

For complete examples with error handling, see [OAUTH_FRONTEND_EXAMPLES.md](./docs/auth/OAUTH_FRONTEND_EXAMPLES.md).

---

## Configuration

### Backend Configuration

The backend needs Google OAuth2 credentials. There are two ways to configure:

#### Option 1: Environment Variables (Recommended)

```bash
export GOOGLE_CLIENT_ID="your-client-id.apps.googleusercontent.com"
export GOOGLE_CLIENT_SECRET="your-client-secret"
```

Or create a `.env` file:
```env
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
```

#### Option 2: Database Configuration

Use the OAuth configuration endpoint:
```bash
curl -X POST http://localhost:5051/api/config/oauth \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -d '{
    "googleClientId": "your-client-id.apps.googleusercontent.com",
    "googleClientSecret": "your-client-secret"
  }'
```

Note: This endpoint requires authentication.

### Google Cloud Console Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable the Google+ API
4. Go to "APIs & Services" > "Credentials"
5. Create OAuth 2.0 Client ID (Web application)
6. Add authorized redirect URIs:
   - `http://localhost:3000/auth/callback` (development)
   - `https://yourdomain.com/auth/callback` (production)
7. Note down the Client ID and Client Secret

---

## Security Best Practices

1. **HTTPS in Production**: Always use HTTPS for production deployments
2. **Secure Token Storage**: Store JWT tokens securely (httpOnly cookies recommended)
3. **Token Expiration**: Tokens expire after 7 days, implement refresh logic
4. **CORS Configuration**: Configure proper CORS origins in production
5. **Never Expose Client Secret**: Keep Client Secret in backend only
6. **Validate Redirect URIs**: Only use registered redirect URIs

---

## Troubleshooting

### "Google OAuth não configurado"

**Cause**: Backend doesn't have OAuth credentials configured.

**Solution**: 
1. Set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` environment variables
2. Or configure via the OAuth config endpoint
3. Restart the backend server

### "redirect_uri é obrigatório"

**Cause**: Missing redirect_uri parameter in login request.

**Solution**: Always include redirect_uri parameter when calling `/api/auth/google`

### "Falha ao obter token do Google"

**Cause**: Invalid authorization code or misconfigured redirect URI.

**Solution**:
1. Ensure redirect_uri matches exactly what's registered in Google Console
2. Authorization codes are single-use and expire quickly
3. Check that Client ID and Secret are correct

### CORS Errors

**Cause**: Frontend origin not allowed.

**Solution**: Add your frontend origin to CORS_ORIGINS in backend `config.py`

---

## Testing

Run the comprehensive test suite:

```bash
cd backend
python3 tests/test_oauth_flow.py
```

This tests:
- Authentication status endpoint
- Google login endpoint (with and without config)
- OAuth callback endpoint
- Parameter validation
- Error handling

---

## API Flow Diagram

```
┌──────────┐                                    ┌──────────┐
│          │  1. GET /api/auth/google          │          │
│ Frontend ├───────────────────────────────────►│ Backend  │
│          │     ?redirect_uri=...             │          │
└────┬─────┘                                    └────┬─────┘
     │                                               │
     │  2. Return authUrl                            │
     │◄──────────────────────────────────────────────┘
     │
     │  3. Redirect to authUrl
     ├───────────────────────┐
     │                       ▼
     │                  ┌─────────┐
     │                  │         │
     │                  │ Google  │
     │                  │  OAuth  │
     │                  │         │
     │                  └────┬────┘
     │                       │
     │  4. User authorizes   │
     │     & Google redirects│
     │◄──────────────────────┘
     │     with code
     │
     │  5. POST /api/auth/google/callback
     ├───────────────────────────────────────────────┐
     │     { code, redirect_uri }                    │
     │                                               ▼
     │                                          ┌─────────┐
     │                                          │ Backend │
     │                                          └────┬────┘
     │                                               │
     │  6. Return { token, usuario, sessao }        │
     │◄──────────────────────────────────────────────┘
     │
     │  7. Store token & make authenticated requests
     ├───────────────────────────────────────────────┐
     │     Authorization: Bearer <token>             │
     │                                               ▼
     │                                          ┌─────────┐
     │                                          │   API   │
     │  8. Return protected data                │         │
     │◄──────────────────────────────────────────Backend │
                                                └─────────┘
```

---

## Summary

The OAuth2 REST endpoints are **fully implemented and tested**. The integration requires:

1. ✅ Backend endpoints exist and work correctly
2. ⚙️ Configure Google OAuth credentials
3. 🔧 Frontend needs to implement the OAuth flow using these endpoints
4. 🧪 Test end-to-end with real Google credentials

All endpoints follow REST best practices with proper error handling and validation.

