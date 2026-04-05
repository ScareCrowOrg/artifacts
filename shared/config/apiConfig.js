/**
 * API Configuration for ScareVerse Frontend
 *
 * Frontend knows two API bases:
 * - CentralHub: Centralized infrastructure (via Nginx in Kubernetes cluster)
 * - ScareRunner: Local-first execution (ScareRunner direct connection)
 *
 * Architecture:
 * - CentralHub handles: Authentication, System config, User management
 * - ScareRunner handles: Cell execution, AI processing, Local artifacts, Translations
 */

// Get CentralHub base URL (cluster infrastructure via Nginx)
const getCentralHubBase = () => {
  // Check for explicit configuration
  if (window.VITE_CENTRAL_HUB_URL) {
    return window.VITE_CENTRAL_HUB_URL
  }

  // Check for environment variable (Vite specific)
  if (import.meta.env.VITE_CENTRAL_HUB_URL) {
    return import.meta.env.VITE_CENTRAL_HUB_URL
  }

  // Fallback to Nginx proxy (standard cluster setup)
  return 'http://localhost:8000'
}

// Get ScareRunner base URL (local-first execution)
const getScareRunnerBase = () => {
  // Check for explicit configuration
  if (window.VITE_SCARERUNNER_URL) {
    return window.VITE_SCARERUNNER_URL
  }

  // Check for environment variable (Vite specific)
  if (import.meta.env.VITE_SCARERUNNER_URL) {
    return import.meta.env.VITE_SCARERUNNER_URL
  }

  // Fallback to ScareRunner default port
  return 'http://localhost:5050'
}

export const CENTRAL_HUB_BASE = getCentralHubBase()
export const SCARERUNNER_BASE = getScareRunnerBase()

// Legacy aliases for backward compatibility
export const LOCAL_RUNNER_BASE = SCARERUNNER_BASE
export const API_BASE = CENTRAL_HUB_BASE
export const API_BASE_URL = API_BASE

/**
 * API Base Selection Guide:
 *
 * Use CENTRAL_HUB_BASE for:
 * - Authentication (login, logout, tokens)
 * - User management (create, update, permissions)
 * - System configuration (global settings)
 * - Cluster-wide operations
 *
 * Use SCARERUNNER_BASE for:
 * - Cell execution (run cells, get results)
 * - AI operations (Gemini, OpenAI, local models)
 * - Artifact access (load cells, books, translations)
 * - Local-first operations that work offline
 *
 * Example:
 * ```javascript
 * // System operation - use CentralHub
 * fetch(`${CENTRAL_HUB_BASE}/api/auth/login`, {...})
 *
 * // Cell execution - use ScareRunner
 * fetch(`${SCARERUNNER_BASE}/api/cells/${cellId}/execute`, {...})
 *
 * // Artifact access - use ScareRunner
 * fetch(`${SCARERUNNER_BASE}/local/canonical/cell_types/...`, {...})
 * ```
 */

console.log('🌐 API Configuration:')
console.log('  CentralHub (cluster):', CENTRAL_HUB_BASE)
console.log('  ScareRunner (local):', SCARERUNNER_BASE)
console.log('  Legacy API_BASE:', API_BASE)
