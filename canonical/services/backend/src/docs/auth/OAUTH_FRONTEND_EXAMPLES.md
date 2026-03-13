---
processed: true
processed_date: 2025-12-09
themes:
  - oauth
  - google-auth
  - authentication
  - frontend
  - vue
  - react
modules:
  - frontend
  - security
code_verified: true
dead_docs_found: false
---
# OAuth Frontend Integration Examples

This document provides complete code examples for integrating Google OAuth2 authentication in your frontend application.

## Overview

These examples show how to implement the complete OAuth2 flow in your frontend:

1. Check authentication status
2. Initiate Google login
3. Handle OAuth callback
4. Make authenticated API requests
5. Logout

## Vue.js / JavaScript Example

### 1. Check Authentication Status

```javascript
// Check if authentication is available
async function checkAuthStatus() {
  const response = await fetch('http://localhost:5051/api/auth/status');
  const data = await response.json();
  
  if (data.authEnabled) {
    // Show login button
    showLoginButton();
  }
}
```

### 2. Initiate Google Login

```javascript
// Initiate Google login
async function initiateGoogleLogin() {
  try {
    // Get redirect URI (where Google will send user back)
    const redirectUri = `${window.location.origin}/auth/callback`;
    
    // Get auth URL from backend
    const response = await fetch(
      `http://localhost:5051/api/auth/google?redirect_uri=${encodeURIComponent(redirectUri)}`
    );
    
    if (!response.ok) {
      throw new Error('Failed to initiate login');
    }
    
    const data = await response.json();
    
    // Redirect user to Google
    window.location.href = data.authUrl;
  } catch (error) {
    console.error('Login error:', error);
    alert('Failed to start login process');
  }
}
```

### 3. Handle OAuth Callback

```javascript
// Handle OAuth callback (in your /auth/callback route)
async function handleOAuthCallback() {
  // Get authorization code from URL
  const urlParams = new URLSearchParams(window.location.search);
  const code = urlParams.get('code');
  
  if (!code) {
    console.error('No authorization code received');
    return;
  }
  
  try {
    const redirectUri = `${window.location.origin}/auth/callback`;
    
    // Exchange code for token
    const response = await fetch('http://localhost:5051/api/auth/google/callback', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        code: code,
        redirect_uri: redirectUri
      })
    });
    
    if (!response.ok) {
      throw new Error('Authentication failed');
    }
    
    const data = await response.json();
    
    // Store token and user data
    localStorage.setItem('auth_token', data.token);
    localStorage.setItem('user', JSON.stringify(data.usuario));
    localStorage.setItem('session', JSON.stringify(data.sessao));
    
    // Redirect to home page or dashboard
    window.location.href = '/';
    
  } catch (error) {
    console.error('Callback error:', error);
    alert('Authentication failed');
    window.location.href = '/login';
  }
}
```

### 4. Make Authenticated API Requests

```javascript
// Make authenticated API requests
async function makeAuthenticatedRequest(endpoint, options = {}) {
  const token = localStorage.getItem('auth_token');
  
  if (!token) {
    throw new Error('Not authenticated');
  }
  
  const response = await fetch(endpoint, {
    ...options,
    headers: {
      ...options.headers,
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    }
  });
  
  if (response.status === 401) {
    // Token expired or invalid
    localStorage.clear();
    window.location.href = '/login';
    throw new Error('Session expired');
  }
  
  return response;
}

// Example usage
async function fetchUserData() {
  const response = await makeAuthenticatedRequest('http://localhost:5051/api/usuarios/me');
  const user = await response.json();
  return user;
}

async function createCell(cellData) {
  const response = await makeAuthenticatedRequest(
    'http://localhost:5051/api/celulas/criar',
    {
      method: 'POST',
      body: JSON.stringify(cellData)
    }
  );
  return response.json();
}
```

### 5. Logout

```javascript
// Logout
async function logout() {
  const session = JSON.parse(localStorage.getItem('session') || '{}');
  const token = localStorage.getItem('auth_token');
  
  // Close session on server
  if (session.id && token) {
    try {
      await fetch(`http://localhost:5051/api/sessoes/${session.id}/fechar`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
    } catch (error) {
      console.error('Error closing session:', error);
    }
  }
  
  // Clear local storage
  localStorage.clear();
  
  // Redirect to login
  window.location.href = '/login';
}
```

### Complete Vue Component Example

```javascript
// LoginPage.vue
export default {
  data() {
    return {
      authEnabled: false,
      loading: true
    };
  },
  
  async mounted() {
    await this.checkAuthStatus();
  },
  
  methods: {
    async checkAuthStatus() {
      try {
        const response = await fetch('http://localhost:5051/api/auth/status');
        const data = await response.json();
        this.authEnabled = data.authEnabled;
      } catch (error) {
        console.error('Auth status check failed:', error);
      } finally {
        this.loading = false;
      }
    },
    
    async initiateGoogleLogin() {
      try {
        const redirectUri = `${window.location.origin}/auth/callback`;
        const response = await fetch(
          `http://localhost:5051/api/auth/google?redirect_uri=${encodeURIComponent(redirectUri)}`
        );
        const data = await response.json();
        window.location.href = data.authUrl;
      } catch (error) {
        console.error('Login error:', error);
        alert('Failed to start login process');
      }
    }
  }
};
```

## React Example

### Login Component

```jsx
import { useState, useEffect } from 'react';

function LoginPage() {
  const [authEnabled, setAuthEnabled] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check if auth is available
    fetch('http://localhost:5051/api/auth/status')
      .then(res => res.json())
      .then(data => {
        setAuthEnabled(data.authEnabled);
        setLoading(false);
      })
      .catch(err => {
        console.error(err);
        setLoading(false);
      });
  }, []);

  const handleGoogleLogin = async () => {
    try {
      const redirectUri = `${window.location.origin}/auth/callback`;
      const response = await fetch(
        `http://localhost:5051/api/auth/google?redirect_uri=${encodeURIComponent(redirectUri)}`
      );
      const data = await response.json();
      
      // Redirect to Google
      window.location.href = data.authUrl;
    } catch (error) {
      console.error('Login error:', error);
      alert('Failed to start login');
    }
  };

  if (loading) {
    return <div>Loading...</div>;
  }

  if (!authEnabled) {
    return <div>Authentication not available</div>;
  }

  return (
    <div className="login-page">
      <h1>Login</h1>
      <button onClick={handleGoogleLogin} className="google-login-btn">
        <img src="/google-icon.png" alt="Google" />
        Login with Google
      </button>
    </div>
  );
}

export default LoginPage;
```

### OAuth Callback Component

```jsx
import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

function OAuthCallback() {
  const navigate = useNavigate();

  useEffect(() => {
    const handleCallback = async () => {
      const urlParams = new URLSearchParams(window.location.search);
      const code = urlParams.get('code');
      
      if (!code) {
        console.error('No authorization code');
        navigate('/login');
        return;
      }
      
      try {
        const redirectUri = `${window.location.origin}/auth/callback`;
        const response = await fetch('http://localhost:5051/api/auth/google/callback', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ 
            code, 
            redirect_uri: redirectUri 
          })
        });
        
        if (!response.ok) {
          throw new Error('Authentication failed');
        }
        
        const data = await response.json();
        
        // Store auth data
        localStorage.setItem('auth_token', data.token);
        localStorage.setItem('user', JSON.stringify(data.usuario));
        localStorage.setItem('session', JSON.stringify(data.sessao));
        
        // Redirect to home
        navigate('/');
      } catch (error) {
        console.error('Auth error:', error);
        navigate('/login');
      }
    };
    
    handleCallback();
  }, [navigate]);

  return (
    <div className="auth-callback">
      <div className="spinner">Authenticating...</div>
    </div>
  );
}

export default OAuthCallback;
```

### Auth Context Hook (Advanced)

```jsx
import { createContext, useContext, useState, useEffect } from 'react';

const AuthContext = createContext();

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [token, setToken] = useState(localStorage.getItem('auth_token'));

  useEffect(() => {
    if (token) {
      // Load user data
      const userData = localStorage.getItem('user');
      if (userData) {
        setUser(JSON.parse(userData));
      }
    }
    setLoading(false);
  }, [token]);

  const login = async (authData) => {
    localStorage.setItem('auth_token', authData.token);
    localStorage.setItem('user', JSON.stringify(authData.usuario));
    localStorage.setItem('session', JSON.stringify(authData.sessao));
    setToken(authData.token);
    setUser(authData.usuario);
  };

  const logout = async () => {
    const session = JSON.parse(localStorage.getItem('session') || '{}');
    
    if (session.id && token) {
      try {
        await fetch(`http://localhost:5051/api/sessoes/${session.id}/fechar`, {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${token}` }
        });
      } catch (error) {
        console.error('Error closing session:', error);
      }
    }
    
    localStorage.clear();
    setToken(null);
    setUser(null);
  };

  const makeAuthRequest = async (url, options = {}) => {
    if (!token) {
      throw new Error('Not authenticated');
    }

    const response = await fetch(url, {
      ...options,
      headers: {
        ...options.headers,
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    });

    if (response.status === 401) {
      logout();
      throw new Error('Session expired');
    }

    return response;
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, makeAuthRequest }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}

// Usage in component:
// const { user, logout, makeAuthRequest } = useAuth();
```

## Best Practices

### Token Storage

- **Use localStorage** for web apps (persistent across sessions)
- **Use sessionStorage** for single-session apps (cleared on tab close)
- **Consider secure HttpOnly cookies** for maximum security (requires backend support)

### Error Handling

```javascript
async function handleAuthRequest(requestFn) {
  try {
    return await requestFn();
  } catch (error) {
    if (error.message === 'Session expired') {
      // Redirect to login
      window.location.href = '/login';
    } else {
      // Show user-friendly error
      alert('An error occurred. Please try again.');
      console.error(error);
    }
  }
}
```

### Redirect URI Configuration

Ensure redirect URIs match in:
1. Google Cloud Console OAuth credentials
2. Backend `.env` configuration
3. Frontend code

```javascript
// Development
const redirectUri = 'http://localhost:3000/auth/callback';

// Production
const redirectUri = 'https://yourdomain.com/auth/callback';

// Dynamic (recommended)
const redirectUri = `${window.location.origin}/auth/callback`;
```

## Testing

### Manual Testing Flow

1. Start backend: `python -m backend.app.main`
2. Start frontend: `npm run dev`
3. Open browser to `http://localhost:3000`
4. Click "Login with Google"
5. Authorize with Google account
6. Verify redirect to callback page
7. Verify token stored in localStorage
8. Make authenticated request to verify token works
9. Logout and verify token cleared

### Common Issues

**Issue**: "Failed to initiate login"
- **Solution**: Check backend is running and OAuth is configured

**Issue**: "Authentication failed" after callback
- **Solution**: Check redirect URI matches Google Console configuration

**Issue**: "Session expired" on every request
- **Solution**: Verify token is being sent in Authorization header

## Related Documentation

- [OAuth Integration Guide](../OAUTH_INTEGRATION_GUIDE.md) - Main OAuth guide
- [Auth Implementation](./docs/auth/README.md) - Backend auth implementation
- [API Endpoints](./docs/api/README.md) - Complete API reference

---

**Last Updated**: 2025-11-17  
**Frontend Support**: Vue.js, React, vanilla JavaScript
