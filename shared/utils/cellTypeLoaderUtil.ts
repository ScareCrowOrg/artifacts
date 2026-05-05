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
 * Load cell type JSON from artifacts, handling both direct JSON and reference files
 * Uses Vite import map to resolve #artifacts/ prefix locally
 *
 * Architecture:
 * - Dynamic workspace is now an artifact viewer (served by Vite service)
 * - Can resolve #artifacts/ paths directly via Vite import map
 * - No longer needs /local HTTP endpoint (that was old architecture)
 * - Uses dynamic import() which respects import maps
 *
 * Why #artifacts and not /local:
 * - Import maps apply to import() statements (fetch() does NOT use them)
 * - Vite dev server resolves #artifacts/ → /app/artifacts/
 * - This works in both dev (localhost) and production (all artifacts bundled)
 * - Eliminates dependency on /local HTTP endpoint from backend
 *
 * @param url - Path to load (supports #artifacts/ or relative path)
 * @returns Parsed JSON object or resolved content
 * @throws Error if loading fails or reference cannot be resolved
 */
export async function loadCellTypeJson(url: string, depth: number = 0): Promise<any> {
  // Prevent infinite recursion on reference files
  const MAX_DEPTH = 3

  if (depth > MAX_DEPTH) {
    throw new Error(`Max reference chain depth (${MAX_DEPTH}) exceeded while loading ${url}`)
  }

  try {
    console.log('📥 [loadCellTypeJson] Loading from artifacts:', { url, depth })

    // Normalize to #artifacts/ prefix for import map resolution
    let importPath = url
    if (!importPath.startsWith('#artifacts/')) {
      if (importPath.startsWith('/local/')) {
        // Legacy /local paths → convert to #artifacts/
        importPath = importPath.replace('/local/', '#artifacts/')
      } else if (!importPath.startsWith('#artifacts/')) {
        // Assume it's a relative path, convert to #artifacts/
        importPath = '#artifacts/' + importPath
      }
    }

    console.log('🔄 [loadCellTypeJson] Normalized import path:', { original: url, normalized: importPath })

    // Use dynamic import() to load via Vite import map
    // import(path) respects import maps, whereas fetch() does not
    let content: any
    try {
      // Try to import as a module first (if it's a .json or .ts/js file)
      const module = await import(importPath)
      content = module.default || module
      console.log('✅ [loadCellTypeJson] Loaded as module:', { importPath })
    } catch (importError) {
      // If import fails, it might be a text file (reference file)
      // Fall back to fetch with proper error handling
      console.log('⚠️ [loadCellTypeJson] Import failed, trying fetch as text:', { importError, importPath })

      // Convert #artifacts/ to a path that Vite can serve
      // In dev: #artifacts/... → http://localhost:5052/...
      // In prod: #artifacts/... is bundled, use import instead
      let fetchUrl = importPath.replace('#artifacts/', '/artifacts/')

      // Use window.location.origin for relative paths (iframe context)
      // This ensures we fetch from the same origin as the iframe, not from Backend
      if (!fetchUrl.startsWith('http')) {
        if (typeof window !== 'undefined') {
          fetchUrl = window.location.origin + fetchUrl
        } else {
          // Fallback for non-browser contexts (SSR, Node.js)
          const backendUrl = import.meta.env.VITE_SCARERUNNER_URL || 'http://localhost:5050'
          fetchUrl = backendUrl.replace(/\/$/, '') + fetchUrl
        }
      }

      console.log('📡 [loadCellTypeJson] Fetching as text:', { fetchUrl })
      const response = await fetch(fetchUrl)

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      content = await response.text()
    }

    // ⚠️ SAFETY CHECK: Detect HTML responses (error pages)
    if (typeof content === 'string' && (content.trim().startsWith('<!doctype') || content.trim().startsWith('<html'))) {
      throw new Error(
        `Received HTML instead of JSON/reference. URL may not exist: ${url}`
      )
    }

    // Check if it's JSON or a reference file
    if (typeof content === 'string') {
      if (content.trim().startsWith('{') || content.trim().startsWith('[')) {
        // It's valid JSON string
        console.log('✅ [loadCellTypeJson] Loaded JSON from text:', { url })
        return JSON.parse(content)
      }

      // It's a reference file - extract and load the referenced file
      const refPath = content.trim()
      console.log('🔗 [loadCellTypeJson] Reference file found:', { refPath, depth })

      const filename = refPath.split('/').pop()
      if (!filename) {
        throw new Error(`Invalid reference file format: ${refPath}`)
      }

      // Load the referenced notebook item type
      // Convert relative path to #artifacts/ path
      // ../../notebook_item_types/chat-ia.json → #artifacts/canonical/notebook_item_types/chat-ia.json
      const notebookItemTypePath = `#artifacts/canonical/notebook_item_types/${filename}`
      console.log('📥 [loadCellTypeJson] Loading referenced file:', {
        notebookItemTypePath,
        nextDepth: depth + 1,
      })

      // Recursively call to load the referenced file (increment depth)
      return await loadCellTypeJson(notebookItemTypePath, depth + 1)
    }

    // Already parsed object from import
    console.log('✅ [loadCellTypeJson] Loaded object:', { url })
    return content
  } catch (error) {
    const errorMsg = error instanceof Error ? error.message : String(error)
    console.error('❌ [loadCellTypeJson] Failed:', { url, depth, error: errorMsg })
    throw new Error(`Failed to load cell type from ${url}: ${errorMsg}`)
  }
}
