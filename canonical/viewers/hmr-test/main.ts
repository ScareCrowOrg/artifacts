/**
 * HMR Test Viewer - Minimal with ViewerShell handshake
 *
 * Simple flow:
 * 1. HTML loads (served by Vite)
 * 2. ViewerShell sends INIT_WORKSPACE with sessionToken via postMessage
 * 3. main.ts receives token and validates session with Backend (/api/v1/auth/session-bind)
 * 4. If valid: show "HMR Ready" - test WebSocket
 * 5. If invalid: show error
 *
 * Auth via Bearer token (no cookies needed)
 */

const statusText = document.getElementById('status-text') as HTMLElement
const statusDetail = document.getElementById('status-detail') as HTMLElement
const statusDiv = document.getElementById('status') as HTMLElement

let sessionToken: string | null = null

function updateStatus(text: string, detail: string = '', isError: boolean = false) {
  statusText.textContent = `Status: ${text}`
  statusDetail.textContent = detail
  statusDiv.className = `status ${isError ? 'error' : 'success'}`
}

/**
 * Validate session via Backend session-bind API
 * Uses Bearer token from ViewerShell handshake
 */
async function validateSession(): Promise<{ valid: boolean; error?: string }> {
  try {
    console.log('[HMR-Test] Validating session with Backend...')
    updateStatus('Validating', 'Checking session with Backend...')

    if (!sessionToken) {
      return { valid: false, error: 'No session token provided by ViewerShell' }
    }

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
    return { valid: true }
  } catch (error) {
    const msg = error instanceof Error ? error.message : String(error)
    console.error(`[HMR-Test] Validation error: ${msg}`)
    return { valid: false, error: msg }
  }
}

/**
 * Initialize on page load
 */
async function init() {
  console.log('[HMR-Test] main.ts loaded, waiting for ViewerShell handshake...')
  updateStatus('Waiting', 'Waiting for authentication handshake...')

  const validation = await validateSession()

  if (!validation.valid) {
    const errorMsg = validation.error || 'Unknown error'
    console.error('[HMR-Test] Session invalid:', errorMsg)
    updateStatus(
      'Authentication Failed',
      `Backend rejected session: ${errorMsg}\n\nPlease ensure you're logged in.`,
      true,
    )
    return
  }

  // Session valid!
  console.log('[HMR-Test] Session valid, HMR ready')
  updateStatus('Ready', 'Session validated, HMR WebSocket ready\nEdit files to test HMR', false)

  // Update UI
  const container = document.querySelector('.container') as HTMLElement
  container.innerHTML = `
    <h1>✅ HMR Test Ready</h1>
    <p>Session validated, WebSocket connected</p>
    <div class="status success">
      <p id="status-text">Status: Ready</p>
      <p id="status-detail" style="margin-top: 10px;">
        HMR is active. Edit files and save to test hot reload.<br>
        Check browser console for WebSocket logs.
      </p>
    </div>
  `
}

/**
 * Listen for ViewerShell handshake message
 */
window.addEventListener('message', (event) => {
  const message = event.data

  if (message?.type === 'INIT_WORKSPACE') {
    console.log('[HMR-Test] Received INIT_WORKSPACE from ViewerShell')
    sessionToken = message.payload?.sessionToken

    if (sessionToken) {
      console.log('[HMR-Test] Session token received, starting initialization')
      init()
    } else {
      console.error('[HMR-Test] INIT_WORKSPACE received but no sessionToken in payload')
      updateStatus(
        'Authentication Failed',
        'ViewerShell did not provide session token',
        true,
      )
    }
  }
})
