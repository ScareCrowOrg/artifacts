// Vite HMR Bridge Plugin — External trigger endpoint for full-reload
// Receives HTTP requests from watcher-bridge.mjs and dispatches
// server.ws.send({ type: 'full-reload' }) to connected browsers.
//
// This works around Docker Desktop Windows bind mounts where inotify
// + chokidar polling do not propagate file changes.
//
// Usage: Registered in vite.config.ts plugins array (apply: 'serve' only)

import type { Plugin, ViteDevServer } from 'vite'

const ALLOWED_BASE = '/app/artifacts/'

function isPathSafe(filePath: string): boolean {
  // Reject paths with parent-directory traversal
  if (filePath.includes('..')) {
    return false
  }
  // Reject paths outside allowed base
  const resolved = filePath.startsWith('/') ? filePath : `/${filePath}`
  return resolved.startsWith(ALLOWED_BASE)
}

export function viteHmrBridgePlugin(): Plugin {
  return {
    name: 'vite-hmr-bridge',
    apply: 'serve',

    configureServer(server: ViteDevServer) {
      console.error('\n🔌 [HMR Bridge Plugin] configured\n')

      server.middlewares.use((req, res, next) => {
        const url = req.url || ''

        // Only handle our trigger endpoint
        if (!url.startsWith('/__trigger_hmr')) {
          return next()
        }

        // Extract and validate the file parameter
        const parsedUrl = new URL(url, `http://${req.headers.host || 'localhost'}`)
        const filePath = parsedUrl.searchParams.get('file')

        if (!filePath) {
          res.statusCode = 400
          res.end('Missing file parameter')
          return
        }

        // Path sanitization: must be within /app/artifacts/
        if (!isPathSafe(filePath)) {
          console.error(`⚠️  [HMR Bridge] rejected unsafe path: ${filePath}`)
          res.statusCode = 403
          res.end('Forbidden')
          return
        }

        console.error(`🔌 [HMR Bridge] full-reload for: ${filePath}`)

        // Send full-reload to all connected browsers
        // This is more robust than server.moduleGraph.invalidateModule()
        // because it clears transformCache, moduleGraph, and etag cache
        server.ws.send({
          type: 'full-reload',
          path: '/',
        })

        res.statusCode = 200
        res.end('OK')
      })
    },
  }
}
