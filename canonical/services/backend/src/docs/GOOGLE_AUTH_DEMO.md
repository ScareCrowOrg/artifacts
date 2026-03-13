---
processed: true
processed_date: 2025-12-09
themes:
  - authentication
  - oauth
  - google
  - demo
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# Google OAuth2 Authentication Demo

This document demonstrates how to use Google OAuth2 authentication with the ScareVerse backend API.

## Setup

1. **Get Google OAuth2 Credentials**:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select an existing one
   - Enable the Google+ API
   - Go to "APIs & Services" > "Credentials"
   - Create OAuth 2.0 Client ID (Web application)
   - Note down the Client ID and Client Secret

2. **Configure Backend**:
   ```bash
   # Set environment variables
   export GOOGLE_CLIENT_ID="your-client-id.apps.googleusercontent.com"
   export GOOGLE_CLIENT_SECRET="your-client-secret"
   
   # Or create a .env file
   cp .env.example .env
   # Edit .env and add your credentials
   ```

3. **Start Backend**:
   ```bash
   python -m uvicorn app.main:app --reload
   ```

## Testing Authentication

### 1. Test Public Endpoints (No Auth Required)

```bash
# Health check
curl http://localhost:8000/api/health

# Status
curl http://localhost:8000/api/status

# OAuth configuration
curl http://localhost:8000/api/config/oauth
```

### 2. Test Protected Endpoints Without Auth

```bash
# Should return 401 Unauthorized
curl -X POST http://localhost:8000/api/celulas/criar \
  -H "Content-Type: application/json" \
  -d '{"tipoCelulaId":"test","assignee_id":"test"}'

# Response:
# {"detail":"Not authenticated - missing Authorization header"}
```

### 3. Test Protected Endpoints With Invalid Token

```bash
# Should return 401 Unauthorized
curl -X POST http://localhost:8000/api/celulas/criar \
  -H "Authorization: Bearer invalid_token_123" \
  -H "Content-Type: application/json" \
  -d '{"tipoCelulaId":"test","assignee_id":"test"}'

# Response:
# {"detail":"Invalid Google token"}
```

### 4. Test With Valid Google Token (Frontend Integration)

In a real frontend application:

```javascript
// After Google OAuth login
const googleToken = googleUser.getAuthResponse().id_token;

// Make authenticated request
const response = await fetch('http://localhost:8000/api/celulas/criar', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${googleToken}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    tipoCelulaId: 'tipo-celula-uuid',
    assignee_id: 'user-uuid'
  })
});

const data = await response.json();
console.log('Cell created:', data);
```

## Frontend Integration Example

### Vue.js with Google Sign-In

```javascript
// 1. Install Google Sign-In library
// <script src="https://accounts.google.com/gsi/client" async defer></script>

// 2. Initialize Google Sign-In
google.accounts.id.initialize({
  client_id: 'YOUR_GOOGLE_CLIENT_ID',
  callback: handleCredentialResponse
});

// 3. Handle the credential response
function handleCredentialResponse(response) {
  const googleToken = response.credential; // This is the JWT token
  
  // Store token for API requests
  localStorage.setItem('google_token', googleToken);
  
  // Make API request
  makeAuthenticatedRequest(googleToken);
}

// 4. Make authenticated API requests
async function makeAuthenticatedRequest(token) {
  try {
    const response = await fetch('http://localhost:8000/api/celulas/criar', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        tipoCelulaId: 'test-tipo',
        assignee_id: 'test-user'
      })
    });
    
    if (!response.ok) {
      const error = await response.json();
      console.error('API Error:', error.detail);
      
      // Handle specific error cases
      if (response.status === 401) {
        // Token expired or invalid - prompt user to login again
        console.log('Please login again');
      } else if (response.status === 503) {
        // OAuth not configured
        console.error('Server OAuth not configured');
      }
      return;
    }
    
    const data = await response.json();
    console.log('Success:', data);
  } catch (error) {
    console.error('Network error:', error);
  }
}

// 5. Display Sign-In button
google.accounts.id.renderButton(
  document.getElementById('google-signin-button'),
  { theme: 'outline', size: 'large' }
);
```

### React with Google Sign-In

```javascript
import { GoogleLogin } from '@react-oauth/google';

function App() {
  const handleSuccess = async (credentialResponse) => {
    const googleToken = credentialResponse.credential;
    
    // Make API call
    try {
      const response = await fetch('http://localhost:8000/api/status', {
        headers: {
          'Authorization': `Bearer ${googleToken}`
        }
      });
      
      const data = await response.json();
      console.log('Authenticated!', data);
    } catch (error) {
      console.error('Error:', error);
    }
  };

  return (
    <div>
      <GoogleLogin
        onSuccess={handleSuccess}
        onError={() => console.log('Login Failed')}
      />
    </div>
  );
}
```

## Error Codes

| Status Code | Error | Meaning | Solution |
|-------------|-------|---------|----------|
| 401 | "Not authenticated - missing Authorization header" | No token provided | Add `Authorization: Bearer <token>` header |
| 401 | "Invalid Google token" | Token is invalid or expired | Refresh Google token |
| 401 | "Invalid token payload - missing user info" | Token doesn't contain required fields | Check Google OAuth scope includes email and profile |
| 503 | "Google OAuth not configured - GOOGLE_CLIENT_ID missing" | Server not configured | Set GOOGLE_CLIENT_ID environment variable |

## Token Information

Google JWT tokens contain:
- `sub`: Google user ID (unique identifier)
- `email`: User's email address
- `name`: User's full name
- `iss`: Token issuer (accounts.google.com)
- `aud`: Your Google Client ID
- `exp`: Token expiration time
- `iat`: Token issued at time

The backend extracts this information and:
1. Creates a user automatically on first login
2. Links the Google ID to the user account
3. Returns the user object for the session

## Security Notes

1. **Never expose GOOGLE_CLIENT_SECRET** in frontend code
2. **Always use HTTPS** in production
3. **Validate tokens on every request** (backend does this automatically)
4. **Set appropriate CORS origins** in production
5. **Google tokens expire** after 1 hour - frontend should handle token refresh
6. **Backend auto-creates users** on first Google login

## Troubleshooting

### "Invalid Google token" despite valid login

- Check that GOOGLE_CLIENT_ID matches the one used in frontend
- Ensure token is being sent in Authorization header correctly
- Verify token hasn't expired (tokens expire after 1 hour)

### "Google OAuth not configured"

- Verify GOOGLE_CLIENT_ID is set in environment
- Restart the backend server after setting environment variables

### CORS errors

- Check CORS_ORIGINS in backend config.py
- Add your frontend origin to allowed origins
- Example: `http://localhost:3000` for local development

## Next Steps

1. Configure Google OAuth credentials
2. Update frontend to use Google Sign-In
3. Test authentication flow end-to-end
4. Add token refresh logic in frontend
5. Set up proper CORS for production
6. Add logout functionality
