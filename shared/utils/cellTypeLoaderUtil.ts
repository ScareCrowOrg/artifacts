/**
 * @file cellTypeLoaderUtil.ts
 * @description Shared utility for loading cell type definitions from canonical artifacts
 *
 * Architecture:
 * - Vite serves artifacts via /artifacts/ prefix (root=/app/artifacts, base=/artifacts/)
 * - Auth-Proxy routes /artifacts/* → vite:5052/artifacts/*
 * - Dynamic Workspace (iframe) fetches cell types directly from /artifacts/canonical/...
 * - Uses window.location.origin for proper CORS/origin handling in iframe context
 *
 * Why fetch() and not import()?
 * - JSON files are static assets, not ES modules
 * - import() fails on .json without special Vite config
 * - fetch() treats JSON as HTTP asset (correct semantic)
 * - Browser handles CORS/origin automatically with window.location.origin
 *
 * Why /artifacts/ and not Backend?
 * - Vite is the source of truth for artifacts in this architecture
 * - No need for Backend /local endpoint anymore
 * - Auth-Proxy ensures all /artifacts/* requests are validated before reaching Vite
 *
 * Used by:
 * - BaseCell.loadCellTypeFromDiscovery (direct artifact loading in viewers)
 * - useCellTypeLoader composable (ScareRunner integration)
 */

/**
 * Load cell type JSON from artifacts via Vite HTTP service
 * Handles both direct JSON and reference files with recursive resolution
 *
 * @param url - Path to load (supports #artifacts/, /artifacts/, /local/, or relative)
 * @param depth - Recursion depth for reference file chain (max 3)
 * @returns Parsed JSON object or resolved content
 * @throws Error if loading fails or reference chain exceeds depth limit
 */
export async function loadCellTypeJson(url: string, depth: number = 0): Promise<any> {
  const MAX_DEPTH = 3

  if (depth > MAX_DEPTH) {
    throw new Error(`Max reference chain depth (${MAX_DEPTH}) exceeded while loading ${url}`)
  }

  try {
    console.log('📥 [loadCellTypeJson] Loading from artifacts:', { url, depth })

    // Normalize any input format to /artifacts/ HTTP path
    // This is the URL Vite actually serves artifacts from
    let fetchPath = url
    if (fetchPath.startsWith('#artifacts/')) {
      fetchPath = fetchPath.replace('#artifacts/', '/artifacts/')
    } else if (fetchPath.startsWith('/local/')) {
      // Legacy /local paths → convert to /artifacts/
      fetchPath = fetchPath.replace('/local/', '/artifacts/')
    } else if (!fetchPath.startsWith('/artifacts/')) {
      // Assume it's a relative path, convert to /artifacts/
      fetchPath = '/artifacts/' + fetchPath
    }

    console.log('🔄 [loadCellTypeJson] Normalized path:', { original: url, normalized: fetchPath })

    // Build absolute fetch URL
    // In iframe: window.location.origin ensures same-origin request
    // In SSR: fallback to localhost:5052 (Vite dev server)
    let fetchUrl: string
    if (fetchPath.startsWith('http')) {
      fetchUrl = fetchPath
    } else if (typeof window !== 'undefined') {
      // Browser context (iframe): use current origin
      // This ensures /artifacts/canonical/... → https://scare.scareverse.net/artifacts/canonical/...
      fetchUrl = window.location.origin + fetchPath
    } else {
      // Non-browser context (SSR): use Vite dev server
      fetchUrl = 'http://localhost:5052' + fetchPath
    }

    console.log('📡 [loadCellTypeJson] Fetching:', { fetchUrl })
    const response = await fetch(fetchUrl)

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }

    let content = await response.text()

    // ⚠️ SAFETY CHECK: Detect HTML responses (SPA fallback pages or error pages)
    // This prevents JSON.parse from trying to parse error HTML
    if (content.trim().startsWith('<!doctype') || content.trim().startsWith('<html')) {
      throw new Error(`Received HTML instead of JSON/reference. URL may not exist: ${url}`)
    }

    // Determine if content is JSON or reference file
    if (content.trim().startsWith('{') || content.trim().startsWith('[')) {
      // It's valid JSON
      console.log('✅ [loadCellTypeJson] Loaded JSON:', { url })
      return JSON.parse(content)
    }

    // It's a reference file - extract referenced file and load recursively
    const refPath = content.trim()
    console.log('🔗 [loadCellTypeJson] Reference file found:', { refPath, depth })

    const filename = refPath.split('/').pop()
    if (!filename) {
      throw new Error(`Invalid reference file format: ${refPath}`)
    }

    // Load the referenced notebook item type
    // ../../notebook_item_types/chat-ia.json → #artifacts/canonical/notebook_item_types/chat-ia.json
    const notebookItemTypePath = `#artifacts/canonical/notebook_item_types/${filename}`
    console.log('📥 [loadCellTypeJson] Loading referenced file:', {
      notebookItemTypePath,
      nextDepth: depth + 1,
    })

    return await loadCellTypeJson(notebookItemTypePath, depth + 1)
  } catch (error) {
    const errorMsg = error instanceof Error ? error.message : String(error)
    console.error('❌ [loadCellTypeJson] Failed:', { url, depth, error: errorMsg })
    throw new Error(`Failed to load cell type from ${url}: ${errorMsg}`)
  }
}
