#!/bin/bash
# Test script for authentication flow

API_BASE="http://localhost:5051/api"

echo "======================================"
echo "Testing Authentication Flow"
echo "======================================"
echo ""

echo "1. Check authentication status (should be disabled initially)"
echo "GET ${API_BASE}/auth/status"
curl -s "${API_BASE}/auth/status" | python3 -m json.tool
echo ""
echo ""

echo "2. Configure OAuth credentials"
echo "POST ${API_BASE}/config/oauth"
curl -s -X POST "${API_BASE}/config/oauth" \
  -H "Content-Type: application/json" \
  -d '{
    "googleClientId": "test-client-id.apps.googleusercontent.com",
    "googleClientSecret": "test-client-secret"
  }' | python3 -m json.tool
echo ""
echo ""

echo "3. Check authentication status (should be enabled now)"
echo "GET ${API_BASE}/auth/status"
curl -s "${API_BASE}/auth/status" | python3 -m json.tool
echo ""
echo ""

echo "4. Get OAuth configuration (secret should not be visible)"
echo "GET ${API_BASE}/config/oauth"
curl -s "${API_BASE}/config/oauth" | python3 -m json.tool
echo ""
echo ""

echo "5. Register a new user"
echo "POST ${API_BASE}/usuarios/registrar"
USER_RESPONSE=$(curl -s -X POST "${API_BASE}/usuarios/registrar" \
  -H "Content-Type: application/json" \
  -d '{
    "nome": "Test User",
    "email": "test@example.com"
  }')
echo "$USER_RESPONSE" | python3 -m json.tool
USER_ID=$(echo "$USER_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])")
echo ""
echo "User ID: $USER_ID"
echo ""
echo ""

echo "6. Create a session for the user"
echo "POST ${API_BASE}/sessoes/criar"
SESSION_RESPONSE=$(curl -s -X POST "${API_BASE}/sessoes/criar" \
  -H "Content-Type: application/json" \
  -d "{\"usuarioId\": \"$USER_ID\"}")
echo "$SESSION_RESPONSE" | python3 -m json.tool
SESSION_ID=$(echo "$SESSION_RESPONSE" | python3 -c "import sys, json; data = json.load(sys.stdin); print(data['sessao']['id'])")
TOKEN=$(echo "$SESSION_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['token'])")
echo ""
echo "Session ID: $SESSION_ID"
echo "Token: ${TOKEN:0:50}..."
echo ""
echo ""

echo "7. List sessions for the user"
echo "GET ${API_BASE}/sessoes/usuario/${USER_ID}"
curl -s "${API_BASE}/sessoes/usuario/${USER_ID}" | python3 -m json.tool
echo ""
echo ""

echo "8. Close the session"
echo "POST ${API_BASE}/sessoes/${SESSION_ID}/fechar"
curl -s -X POST "${API_BASE}/sessoes/${SESSION_ID}/fechar" | python3 -m json.tool
echo ""
echo ""

echo "======================================"
echo "Authentication Flow Test Complete"
echo "======================================"
