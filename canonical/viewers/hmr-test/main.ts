/**
 * HMR Test Viewer - Minimal handshake with session validation
 *
 * Flow:
 * 1. Receives INIT_WORKSPACE from ViewerShell (Cockpit)
 * 2. Validates sessionToken via Backend session-bind API
 * 3. If valid: mounts app + sends RUNNER_READY
 * 4. If invalid: displays error
 *
 * No full handshake required - just session validation
 */

const statusText = document.getElementById('status-text') as HTMLElement
const statusDetail = document.getElementById('status-detail') as HTMLElement
const statusDiv = document.getElementById('status') as HTMLElement

function updateStatus(text: string, detail: string = '', isError: boolean = false) {
  statusText.textContent = `Status: ${text}`
  statusDetail.textContent = detail
  statusDiv.className = `status ${isError ? 'error' : 'success'}`
}

// Expected Cockpit origins (same as dynamic-workspace)
const EXPECTED_COCKPIT_ORIGINS = [
  'http://localhost:5173',
  'http://127.0.0.1:5173',
  'http://localhost:8000',
  'https://scare.scareverse.net',
  'https://hub-staging.scareverse.net',
  'https://hub.scareverse.net',
]

interface InitWorkspaceMessage {
  type: 'INIT_WORKSPACE'
  payload: {
    workspaceId: string
    sessionToken: string
    cockpitOrigin: string
    userId: string
  }
  timestamp: number
}

interface RunnerReadyMessage {
  type: 'RUNNER_READY'
  payload: {
    workspaceId: string
    runnerOrigin: string
    version: string
    capabilities: string[]
    status: string
  }
  timestamp: number
}

interface RunnerErrorMessage {
  type: 'RUNNER_ERROR'
  payload: {
    workspaceId: string
    errorCode: string
    message: string
  }
  timestamp: number
}

let workspaceInitData: InitWorkspaceMessage['payload'] | null = null
let handshakeComplete = false

/**
 * Validate session via Backend session-bind API
 * This is the actual security boundary - validates JWT token with CentralHub
 */
async function validateSessionWithBackend(
  sessionToken: string,
): Promise<{ valid: boolean; userId?: string; error?: string }> {
  try {
    console.log('[HMR-Test] Calling /api/v1/auth/session-bind to validate token...')

    const response = await fetch('/api/v1/auth/session-bind', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${sessionToken}`,
      },
      body: JSON.stringify({}),
    })

    console.log(`[HMR-Test] session-bind response: ${response.status}`)

    if (!response.ok) {
      const error = await response.text()
      console.error(`[HMR-Test] Session validation failed: ${error}`)
      return { valid: false, error: `HTTP ${response.status}` }
    }

    const data = await response.json()
    console.log('[HMR-Test] Session valid:', data)
    return { valid: true, userId: data.userId }
  } catch (error) {
    const msg = error instanceof Error ? error.message : String(error)
    console.error(`[HMR-Test] Validation error: ${msg}`)
    return { valid: false, error: msg }
  }
}

/**
 * Handle INIT_WORKSPACE message from Cockpit
 */
async function handleInitWorkspace(event: MessageEvent) {
  const data = event.data as InitWorkspaceMessage

  // Security: validate origin
  if (!EXPECTED_COCKPIT_ORIGINS.includes(event.origin)) {
    console.warn(`[HMR-Test] Origin check failed: ${event.origin}`)
    updateStatus('Origin Mismatch', `Unexpected origin: ${event.origin}`, true)
    return
  }

  if (data.type !== 'INIT_WORKSPACE') return

  console.log('[HMR-Test] INIT_WORKSPACE received:', data)
  updateStatus('Validating Session', 'Checking credentials with backend...')

  workspaceInitData = data.payload
  const { sessionToken, workspaceId, cockpitOrigin } = data.payload

  // Validate session via Backend
  const validation = await validateSessionWithBackend(sessionToken)

  if (!validation.valid) {
    const errorMsg = validation.error || 'Unknown error'
    console.error('[HMR-Test] Session validation failed:', errorMsg)
    updateStatus('Validation Failed', `Backend rejected token: ${errorMsg}`, true)

    // Send RUNNER_ERROR
    sendError(workspaceId, 'VALIDATION_FAILED', errorMsg, cockpitOrigin, event.source)
    return
  }

  // Session valid!
  console.log('[HMR-Test] Session valid, mounting app...')
  updateStatus('Ready', `Workspace: ${workspaceId}`, false)

  // Mount minimal app
  mountApp()

  // Send RUNNER_READY to Cockpit
  sendReady(workspaceId, data.payload.cockpitOrigin, event.source)
}

function mountApp() {
  if (handshakeComplete) return

  handshakeComplete = true

  // Update UI to show HMR test is ready
  const container = document.querySelector('.container') as HTMLElement
  container.innerHTML = `
    <h1>✅ HMR Test Active</h1>
    <p>Session validated, HMR WebSocket ready</p>
    <div class="status success">
      <p id="status-text">Status: Ready</p>
      <p id="status-detail" style="margin-top: 10px;">
        Edit files and save to test HMR.<br>
        Check browser console for WebSocket logs.
      </p>
    </div>
  `

  console.log('[HMR-Test] App mounted, handshake complete')
}

function sendReady(
  workspaceId: string,
  cockpitOrigin: string,
  source: MessageEventSource | null,
) {
  const message: RunnerReadyMessage = {
    type: 'RUNNER_READY',
    payload: {
      workspaceId,
      runnerOrigin: window.location.origin,
      version: 'hmr-test-v1',
      capabilities: ['hm-test'],
      status: 'ready',
    },
    timestamp: Date.now(),
  }

  console.log('[HMR-Test] Sending RUNNER_READY to Cockpit:', message)

  if (source) {
    (source as Window).postMessage(message, cockpitOrigin)
  } else {
    window.parent.postMessage(message, cockpitOrigin)
  }
}

function sendError(
  workspaceId: string,
  errorCode: string,
  errorMessage: string,
  cockpitOrigin: string,
  source: MessageEventSource | null,
) {
  const message: RunnerErrorMessage = {
    type: 'RUNNER_ERROR',
    payload: {
      workspaceId,
      errorCode,
      message: errorMessage,
    },
    timestamp: Date.now(),
  }

  console.error('[HMR-Test] Sending RUNNER_ERROR to Cockpit:', message)

  if (source) {
    (source as Window).postMessage(message, cockpitOrigin)
  } else {
    window.parent.postMessage(message, cockpitOrigin)
  }
}

// Setup message listener
window.addEventListener('message', (event) => {
  console.log('[HMR-Test] Message event received:', event.data.type)
  handleInitWorkspace(event)
})

console.log('[HMR-Test] Main.ts loaded, waiting for INIT_WORKSPACE...')
updateStatus('Waiting for Handshake', 'Cockpit should send INIT_WORKSPACE soon...')
