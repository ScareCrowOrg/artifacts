/**
 * @file src/gitHelper.js
 * @description Git utility functions for the Node-PTY service.
 *
 * Provides HTTP API endpoints for common Git operations executed as
 * child processes. Results are returned as structured JSON.
 */

'use strict'

const { execFile } = require('child_process')
const path = require('path')
const fs = require('fs')
const config = require('../config/env')

/**
 * Execute a git command in a given directory.
 *
 * @param {string[]} args - Git command arguments
 * @param {string} cwd - Working directory
 * @param {number} [timeout=30000] - Timeout in milliseconds
 * @returns {Promise<{ stdout: string, stderr: string }>}
 */
function runGit(args, cwd, timeout = 30000) {
  return new Promise((resolve, reject) => {
    execFile('git', args, { cwd, timeout, maxBuffer: 1024 * 1024 }, (err, stdout, stderr) => {
      if (err) {
        reject(new Error(stderr || err.message))
        return
      }
      resolve({ stdout: stdout.trim(), stderr: stderr.trim() })
    })
  })
}

/**
 * Resolve and validate a path is within the artifacts directory.
 * Prevents path-traversal attacks.
 *
 * @param {string} relativePath - Caller-provided path (may be relative or absolute)
 * @returns {string} Resolved safe path
 * @throws {Error} If path escapes the artifacts directory
 */
function safePath(relativePath) {
  const base = config.ARTIFACTS_PATH
  const resolved = path.resolve(base, relativePath || '')
  if (!resolved.startsWith(path.resolve(base))) {
    throw new Error(`Path traversal detected: "${relativePath}"`)
  }
  return resolved
}

/**
 * Get the git status of a repository.
 *
 * @param {object} opts
 * @param {string} opts.cwd - Directory to inspect (relative to ARTIFACTS_PATH)
 * @returns {Promise<{ status: 'clean'|'dirty', files: string[], raw: string }>}
 */
async function status(opts) {
  const cwd = safePath(opts.cwd || '')
  const { stdout } = await runGit(['status', '--short'], cwd)
  const files = stdout
    .split('\n')
    .filter(Boolean)
    .map((line) => line.trim())
  return {
    status: files.length === 0 ? 'clean' : 'dirty',
    files,
    raw: stdout,
  }
}

/**
 * Get the git log of a repository.
 *
 * @param {object} opts
 * @param {string} opts.cwd - Directory to inspect (relative to ARTIFACTS_PATH)
 * @param {number} [opts.limit=20] - Maximum number of commits to return
 * @returns {Promise<{ commits: Array<{ hash: string, author: string, date: string, message: string }> }>}
 */
async function log(opts) {
  const cwd = safePath(opts.cwd || '')
  const limit = Math.min(Math.max(1, parseInt(opts.limit, 10) || 20), 100)
  const format = '%H|%an|%ai|%s'
  const { stdout } = await runGit(['log', `--max-count=${limit}`, `--format=${format}`], cwd)
  const commits = stdout
    .split('\n')
    .filter(Boolean)
    .map((line) => {
      const [hash, author, date, ...msgParts] = line.split('|')
      return { hash, author, date, message: msgParts.join('|') }
    })
  return { commits }
}

/**
 * Clone a git repository into the artifacts directory.
 *
 * @param {object} opts
 * @param {string} opts.url - Remote URL to clone
 * @param {string} opts.dest - Destination path (relative to ARTIFACTS_PATH)
 * @returns {Promise<{ success: boolean, message: string }>}
 */
async function clone(opts) {
  if (!opts.url) throw new Error('url is required')
  const dest = safePath(opts.dest || path.basename(opts.url, '.git'))

  if (fs.existsSync(dest)) {
    return { success: false, message: `Destination already exists: ${dest}` }
  }

  await runGit(['clone', opts.url, dest], config.ARTIFACTS_PATH, 120000)
  return { success: true, message: `Cloned ${opts.url} → ${dest}` }
}

module.exports = { status, log, clone, safePath }
