/**
 * @file cellTypeLoaderUtil.ts
 * @description Shared utility for loading cell type definitions from canonical artifacts
 *
 * Handles both:
 * 1. Direct JSON files (canonical notebook_item_types)
 * 2. Text reference files (symlink workaround for Windows builds)
 *
 * Architecture:
 * - Uses /local endpoint served by Backend (http://localhost:5050/local/)
 * - Backend mounts /app/artifacts as /local static files
 * - Accepts both #artifacts and /local URL formats, normalizes to /local
 *
 * Why /local instead of #artifacts:
 * - fetch() does NOT understand import map aliases (only import() statements do)
 * - /local is the actual HTTP endpoint that works with fetch()
 *
 * Used by:
 * - useCellTypeLoader composable (ScareRunner integration)
 * - BaseCell.loadCellTypeFromDiscovery (direct artifact loading)
 */

/**
 * Load cell type JSON from URL, handling both direct JSON and reference files
 * Uses /local endpoint served by Backend (port 5050)
 *
 * Architecture:
 * - Backend mounts /app/artifacts as /local (main.py lines 359-373)
 * - Frontend fetch('http://localhost:5050/local/canonical/...') → Backend serves from /app/artifacts/canonical/...
 * - This bypasses import map translation issues with fetch()
 *
 * Why /local and not #artifacts:
 * - Import maps only apply to import() statements and <script type="importmap">
 * - fetch() does NOT automatically translate #artifacts aliases
 * - /local is the actual HTTP endpoint available on port 5050
 *
 * Important: Must use FULL URL (http://localhost:5050) not relative path!
 * - fetch('/local/...') would go to http://localhost:5173/local/ (frontend, wrong!)
 * - fetch('http://localhost:5050/local/...') goes to backend (correct!)
 *
 * @param url - URL to load (supports #artifacts or /local prefix)
 * @returns Parsed JSON object or null if not found
 * @throws Error if loading fails or reference cannot be resolved
 */
export async function loadCellTypeJson(url: string, depth: number = 0): Promise<any> {
  // Prevent infinite recursion on reference files
  const MAX_DEPTH = 3

  if (depth > MAX_DEPTH) {
    throw new Error(`Max reference chain depth (${MAX_DEPTH}) exceeded while loading ${url}`)
  }

  try {
    console.log('📥 [loadCellTypeJson] Fetching URL:', { url, depth })

    // Backend URL from environment (VITE_SCARERUNNER_URL or default localhost:5050)
    const backendUrl = import.meta.env.VITE_SCARERUNNER_URL || 'http://localhost:5050'

    // Normalize URL: convert #artifacts to /local and ensure full URL with backend host
    // #artifacts/canonical/... → http://localhost:5050/local/canonical/...
    // /local/canonical/... → http://localhost:5050/local/canonical/...
    let fetchUrl = url
    if (url.startsWith('#artifacts/')) {
      fetchUrl = url.replace('#artifacts/', '/local/')
    }

    // Ensure we have a full URL, not a relative path
    if (!fetchUrl.startsWith('http://') && !fetchUrl.startsWith('https://')) {
      if (fetchUrl.startsWith('/')) {
        fetchUrl = backendUrl + fetchUrl
      } else {
        fetchUrl = backendUrl + '/' + fetchUrl
      }
    }

    console.log('🔄 [loadCellTypeJson] Resolved URL:', { original: url, resolved: fetchUrl, backendUrl })

    const response = await fetch(fetchUrl)

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }

    const text = await response.text()

    // ⚠️ SAFETY CHECK: Detect HTML responses (error pages)
    if (text.trim().startsWith('<!doctype') || text.trim().startsWith('<html')) {
      throw new Error(
        `Received HTML instead of JSON/reference. URL may not exist or import map not initialized: ${url}`
      )
    }

    // Check if it's JSON or a reference file
    if (text.trim().startsWith('{') || text.trim().startsWith('[')) {
      // It's valid JSON
      console.log('✅ [loadCellTypeJson] Loaded JSON:', { url })
      return JSON.parse(text)
    }

    // It's a reference file - extract and load the referenced file
    const refPath = text.trim()
    console.log('🔗 [loadCellTypeJson] Reference file found:', { refPath, depth })

    const filename = refPath.split('/').pop()
    if (!filename) {
      throw new Error(`Invalid reference file format: ${refPath}`)
    }

    // Load the referenced notebook item type via /local endpoint
    // Note: Pass relative path, loadCellTypeJson will resolve to full URL
    const notebookItemTypePath = `/local/canonical/notebook_item_types/${filename}`
    console.log('📥 [loadCellTypeJson] Loading referenced file:', {
      notebookItemTypePath,
      nextDepth: depth + 1,
    })

    // Recursively call to load the referenced file (increment depth)
    return await loadCellTypeJson(notebookItemTypePath, depth + 1)
  } catch (error) {
    const errorMsg = error instanceof Error ? error.message : String(error)
    console.error('❌ [loadCellTypeJson] Failed:', { url, depth, error: errorMsg })
    throw new Error(`Failed to load cell type from ${url}: ${errorMsg}`)
  }
}
