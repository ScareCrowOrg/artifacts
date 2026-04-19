/**
 * HMR Test Viewer - Minimal, no handshake
 *
 * Simple flow:
 * 1. HTML loads (Auth-Proxy ensures session is valid via cookies)
 * 2. main.ts validates session with Backend (/api/v1/auth/session-bind)
 * 3. If valid: show "HMR Ready" - test WebSocket
 * 4. If invalid: show error
 *
 * No ViewerShell, no postMessage, no handshake
 * Just auth validation + HMR testing
 */

const statusText = document.getElementById('status-text') as HTMLElement
const statusDetail = document.getElementById('status-detail') as HTMLElement
const statusDiv = document.getElementById('status') as HTMLElement

function updateStatus(text: string, detail: string = '', isError: boolean = false) {
  statusText.textContent = `Status: ${text}`
  statusDetail.textContent = detail
  statusDiv.className = `status ${isError ? 'error' : 'success'}`
}

/**
 * Validate session via Backend session-bind API
 * This validates that the session cookie is still valid
 */
async function validateSession(): Promise<{ valid: boolean; error?: string }> {
  try {
    console.log('[HMR-Test] Validating session with Backend...')
    updateStatus('Validating', 'Checking session with Backend...')

    const response = await fetch('/api/v1/auth/session-bind', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include', // Include cookies
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
  console.log('[HMR-Test] main.ts loaded, validating session...')

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

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init)
} else {
  init()
}
