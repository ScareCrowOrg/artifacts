// Watcher Bridge — Agnostic file-change detector for Docker Desktop Windows
//
// Polls known directories with raw fs.statSync and notifies Vite via HTTP
// when file changes are detected. This bypasses chokidar/inotify which are
// broken under Docker Desktop Windows bind mounts.
//
// Usage: node watcher-bridge.mjs &
//
// Zero external dependencies (fs, http, path from Node).
// Fail-soft: all fs.statSync calls are wrapped in try/catch.

import fs from 'fs'
import http from 'http'
import path from 'path'

// ── Configuration ──────────────────────────────────────────────────

const POLL_INTERVAL_MS = 1500
const VITE_HMR_URL = 'http://localhost:5052/__trigger_hmr'
const ARTIFACTS_ROOT = '/app/artifacts'

const WATCH_DIRS = [
  'canonical/viewers',
  'canonical/cell_types',
  'shared',
]

const WATCH_EXTENSIONS = new Set(['.vue', '.ts', '.js', '.css'])

// ── State ──────────────────────────────────────────────────────────

/** @type {Map<string, number>} Known file state: fullPath → mtimeMs */
const knownState = new Map()

// ── Helpers ────────────────────────────────────────────────────────

/**
 * Recursively walk a directory and yield file paths.
 * @param {string} dirPath
 */
function* walkDir(dirPath) {
  try {
    const entries = fs.readdirSync(dirPath, { withFileTypes: true })
    for (const entry of entries) {
      const fullPath = path.join(dirPath, entry.name)
      if (entry.isDirectory()) {
        yield* walkDir(fullPath)
      } else if (entry.isFile()) {
        yield fullPath
      }
    }
  } catch {
    // Directory may not exist yet or permission denied — skip silently
  }
}

/**
 * Notify Vite that a file has changed.
 * @param {string} filePath Absolute path to the changed file
 */
function notifyVite(filePath) {
  // Send relative path from artifacts root for cleaner logs
  const relativePath = filePath.startsWith(ARTIFACTS_ROOT)
    ? filePath.slice(ARTIFACTS_ROOT.length)
    : filePath

  const url = `${VITE_HMR_URL}?file=${encodeURIComponent(filePath)}`

  http.get(url, (res) => {
    // Consume response data to free memory
    res.resume()
  }).on('error', () => {
    // Vite might not be ready yet — silently ignore
  })

  console.error(`🎯 [HMR Bridge] change detected: ${relativePath}`)
}

/**
 * Scan one watch directory for changes.
 * @param {string} watchDir Relative path from artifacts root
 */
function scanDirectory(watchDir) {
  const absDir = path.join(ARTIFACTS_ROOT, watchDir)

  /** @type {Set<string>} */
  const seen = new Set()

  for (const filePath of walkDir(absDir)) {
    const ext = path.extname(filePath)
    if (!WATCH_EXTENSIONS.has(ext)) {
      continue
    }

    seen.add(filePath)

    let stat
    try {
      stat = fs.statSync(filePath)
    } catch (err) {
      // Fail-soft: ignore transient filesystem errors
      if (err.code === 'ENOENT' || err.code === 'EBUSY' || err.code === 'EACCES') {
        continue
      }
      throw err
    }

    const prevMtime = knownState.get(filePath)
    const curMtime = stat.mtimeMs

    if (prevMtime === undefined) {
      // First scan — record state but don't trigger
      knownState.set(filePath, curMtime)
    } else if (curMtime !== prevMtime) {
      // File changed — update state and notify
      knownState.set(filePath, curMtime)
      notifyVite(filePath)
    }
  }

  // Remove stale entries (files that were deleted between polls)
  for (const key of knownState.keys()) {
    if (key.startsWith(absDir) && !seen.has(key)) {
      knownState.delete(key)
    }
  }
}

// ── Main Loop ──────────────────────────────────────────────────────

console.error(`🎯 [HMR Bridge] started (poll every ${POLL_INTERVAL_MS}ms)`)

function tick() {
  for (const watchDir of WATCH_DIRS) {
    scanDirectory(watchDir)
  }
}

// Immediate first scan, then poll
tick()
setInterval(tick, POLL_INTERVAL_MS)
