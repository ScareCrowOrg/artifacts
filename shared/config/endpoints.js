/**
 * Dynamic endpoint configuration for Cockpit
 * Falls back to current window origin if no explicit configuration is provided
 */

// Get API base URL from environment variable
const getApiBase = () => {
  // Check for explicit configuration first
  if (window.API_BASE_URL) {
    return window.API_BASE_URL
  }

  // Check for environment variable (Vite specific) - must be set in .env
  if (import.meta.env.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL
  }

  // Fallback - should not be used if .env is configured correctly
  // Default to http://localhost:5050 for local development
  return import.meta.env.DEV ? 'http://localhost:5050' : ''
}

// Get CentralHub API base URL (for OAuth endpoints)
const getCentralHubBase = () => {
  // Check for explicit configuration first
  if (window.CENTRALHUB_BASE_URL) {
    return window.CENTRALHUB_BASE_URL
  }

  // Check for environment variable (must match .env: VITE_CENTRALHUB_URL)
  if (import.meta.env.VITE_CENTRALHUB_URL) {
    return import.meta.env.VITE_CENTRALHUB_URL
  }

  // Fallback - Use Nginx proxy on port 8000 (which routes /api/* to CentralHub:5051)
  return import.meta.env.DEV ? 'http://localhost:8000' : ''
}

export const API_BASE = getApiBase()
export const API_BASE_URL = API_BASE // Alias for compatibility
export const CENTRALHUB_BASE = getCentralHubBase() // CentralHub API base (for OAuth)

export const ENDPOINTS = {
  // File operations (migrated to backend API)
  saveFile: `${API_BASE}/api/files/save`,
  listFiles: `${API_BASE}/api/files/list`,
  loadFile: `${API_BASE}/api/files/load`,
  moveItem: `${API_BASE}/api/files/move`,
  deleteFile: `${API_BASE}/api/files/delete`,

  // Tree endpoint (alternative to listFiles)
  tree: `${API_BASE}/api/tree`,
  treeRefresh: `${API_BASE}/api/tree-refresh`,

  // Service Management endpoints
  servicesStatus: `${API_BASE}/api/services/status`,
  servicesConfig: `${API_BASE}/api/services/config`,
  servicesConfigTest: `${API_BASE}/api/services/config/test`,
  serviceStart: (serviceId) => `${API_BASE}/api/services/${serviceId}/start`,
  serviceStop: (serviceId) => `${API_BASE}/api/services/${serviceId}/stop`,
  serviceRestart: (serviceId) =>
    `${API_BASE}/api/services/${serviceId}/restart`,
  serviceLogs: (serviceId) => `${API_BASE}/api/services/${serviceId}/logs`,

  // Authentication endpoints
  authStatus: `${CENTRALHUB_BASE}/api/auth/status`,

  // Google OAuth endpoints - NOTE: These are in CentralHub (port 5051), not ScareRunner (5050)
  googleLogin: `${CENTRALHUB_BASE}/api/auth/google`,
  googleCallback: `${CENTRALHUB_BASE}/api/auth/google/callback`,

  // Password auth endpoints - MIGRATED TO CENTRALHUB (Complete Authentication Strangling)
  passwordRegister: `${CENTRALHUB_BASE}/api/auth/password/register`,
  passwordLogin: `${CENTRALHUB_BASE}/api/auth/password/login`,
  authRefresh: `${CENTRALHUB_BASE}/api/auth/refresh`,
  logout: `${CENTRALHUB_BASE}/api/auth/logout`,
  logoutAll: `${CENTRALHUB_BASE}/api/auth/logout-all`,

  // Google OAuth status/config endpoints - also in CentralHub (deprecated - use authStatus instead)
  authGoogleStatus: `${CENTRALHUB_BASE}/api/auth/status`,
  authGoogleConfig: `${CENTRALHUB_BASE}/api/auth/google/config`,

  // OAuth Configuration endpoints - in CentralHub
  oauthConfig: `${CENTRALHUB_BASE}/api/config/oauth`,

  // Session endpoints - MIGRATED TO CENTRALHUB (Phase: Session Centralization)
  createSession: `${CENTRALHUB_BASE}/api/sessions/create`,
  listSessions: (userId) => `${CENTRALHUB_BASE}/api/sessions/user/${userId}`,
  closeSession: (sessionId) => `${CENTRALHUB_BASE}/api/sessions/${sessionId}/close`,

  // User endpoints
  registerUser: `${API_BASE}/api/users/register`,
  listUsers: `${API_BASE}/api/users`,

  // Roles endpoints
  listRoles: `${API_BASE}/api/roles`,
  getRole: (roleName) => `${API_BASE}/api/roles/${roleName}`,
  assignRole: (userId) => `${API_BASE}/api/roles/users/${userId}/roles`,
  removeRole: (userId, roleName) => `${API_BASE}/api/roles/users/${userId}/roles/${roleName}`,

  // Chat IA endpoints
  chatProcess: `${API_BASE}/api/chat/processar`,

  // Cells endpoints (English - migrated from celulas)
  cells: `${API_BASE}/api/cells`,
  getCell: (cellId) => `${API_BASE}/api/cells/${cellId}`,
  executeCell: (cellId) => `${API_BASE}/api/cells/${cellId}/execute`,
  executeEphemeralCell: `${API_BASE}/api/cells/execute-ephemeral`,

  // Party rooms registry (Calls — shared by party-cell / puyo / party-game)
  listActiveRooms: `${API_BASE}/api/calls/rooms`,
  roomSessions: (roomId) => `${API_BASE}/api/calls/rooms/${roomId}/sessions`,
  roomSession: (roomId, sessionId) => `${API_BASE}/api/calls/rooms/${roomId}/sessions/${sessionId}`,
  updateCell: (cellId) => `${API_BASE}/api/cells/${cellId}/update`,
  createCell: `${API_BASE}/api/cells/create`,
  listCells: `${API_BASE}/api/cells/list`,
  listCellTypes: `${API_BASE}/api/cells/types/list`,

  // Books endpoints (migrated from livros)
  books: `${API_BASE}/api/books`,
  bookGet: (bookId) => `${API_BASE}/api/books/${bookId}`,
  bookUpdate: (bookId) => `${API_BASE}/api/books/${bookId}`,
  bookDelete: (bookId) => `${API_BASE}/api/books/${bookId}`,

  // AI Models endpoints (CRUD)
  aiModelsList: `${API_BASE}/api/ai-models/list`,
  aiModelsGet: (modelId) => `${API_BASE}/api/ai-models/${modelId}`,
  aiModelsCreate: `${API_BASE}/api/ai-models/create`,
  aiModelsUpdate: (modelId) =>
    `${API_BASE}/api/ai-models/${modelId}/update`,
  aiModelsActivate: (modelId) =>
    `${API_BASE}/api/ai-models/${modelId}/activate`,
  aiModelsDelete: (modelId) =>
    `${API_BASE}/api/ai-models/${modelId}/delete`,

  // Ngrok Share endpoints
  shareStart: `${API_BASE}/api/share/start`,
  shareAdd: `${API_BASE}/api/share/add`,
  shareRemove: `${API_BASE}/api/share/remove`,
  shareStop: `${API_BASE}/api/share/stop`,
  shareStatus: `${API_BASE}/api/share/status`,

  // Traces endpoints
  tracesBase: `${API_BASE}/api/traces`,
  traceByConversation: (conversationId) =>
    `${API_BASE}/api/traces/conversation/${conversationId}`,
  tracesRecent: `${API_BASE}/api/traces/recent`,

  // System endpoints
  systemStatus: `${API_BASE}/api/status`,
  systemHealth: `${API_BASE}/api/health`,  // Lightweight health check (public, no auth/scans)
  systemSeedData: `${API_BASE}/api/seed-data`,

  // Layout persistence endpoints
  userLayout: (userId) => `${API_BASE}/api/users/${userId}/layout`,
}
