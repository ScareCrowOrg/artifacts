/**
 * @file tests/gitHelper.test.js
 * @description Unit tests for gitHelper.
 *
 * child_process.execFile is mocked to avoid running real git commands.
 */

'use strict'

const path = require('path')

// Mock config so ARTIFACTS_PATH is predictable
jest.mock('../config/env', () => ({
  ARTIFACTS_PATH: '/tmp/test-artifacts',
  LOG_LEVEL: 'ERROR',
  SESSION_TIMEOUT: 0,
}))

// Mock child_process.execFile
const mockExecFile = jest.fn()
jest.mock('child_process', () => ({
  execFile: mockExecFile,
}))

// Mock fs.existsSync
jest.mock('fs', () => ({
  existsSync: jest.fn(),
}))

const fs = require('fs')
const gitHelper = require('../src/gitHelper')

function resolveInArtifacts(rel) {
  return path.resolve('/tmp/test-artifacts', rel)
}

describe('gitHelper.safePath()', () => {
  it('resolves a relative path inside artifacts', () => {
    const result = gitHelper.safePath('myrepo')
    expect(result).toBe(resolveInArtifacts('myrepo'))
  })

  it('resolves an empty string to artifacts root', () => {
    const result = gitHelper.safePath('')
    expect(result).toBe(path.resolve('/tmp/test-artifacts'))
  })

  it('throws on path traversal', () => {
    expect(() => gitHelper.safePath('../../etc/passwd')).toThrow(/path traversal/i)
  })
})

describe('gitHelper.status()', () => {
  it('returns clean status when git output is empty', async () => {
    mockExecFile.mockImplementation((_cmd, _args, _opts, cb) => cb(null, '', ''))

    const result = await gitHelper.status({ cwd: '' })
    expect(result.status).toBe('clean')
    expect(result.files).toHaveLength(0)
  })

  it('returns dirty status with files listed', async () => {
    mockExecFile.mockImplementation((_cmd, _args, _opts, cb) =>
      cb(null, ' M src/server.js\n?? newfile.txt\n', '')
    )

    const result = await gitHelper.status({ cwd: '' })
    expect(result.status).toBe('dirty')
    expect(result.files).toHaveLength(2)
  })

  it('rejects when git fails', async () => {
    mockExecFile.mockImplementation((_cmd, _args, _opts, cb) =>
      cb(new Error('not a git repo'), '', 'fatal: not a git repository')
    )

    await expect(gitHelper.status({ cwd: '' })).rejects.toThrow()
  })
})

describe('gitHelper.log()', () => {
  it('parses commit log lines', async () => {
    const fakeLine =
      'abc123|Alice|2024-01-01T00:00:00+00:00|feat: initial commit'
    mockExecFile.mockImplementation((_cmd, _args, _opts, cb) =>
      cb(null, fakeLine, '')
    )

    const result = await gitHelper.log({ cwd: '' })
    expect(result.commits).toHaveLength(1)
    expect(result.commits[0].hash).toBe('abc123')
    expect(result.commits[0].author).toBe('Alice')
    expect(result.commits[0].message).toBe('feat: initial commit')
  })

  it('returns empty array on empty log output', async () => {
    mockExecFile.mockImplementation((_cmd, _args, _opts, cb) => cb(null, '', ''))

    const result = await gitHelper.log({ cwd: '' })
    expect(result.commits).toHaveLength(0)
  })

  it('caps limit at 100', async () => {
    mockExecFile.mockImplementation((_cmd, args, _opts, cb) => {
      const maxCount = args.find((a) => a.startsWith('--max-count='))
      expect(maxCount).toBe('--max-count=100')
      cb(null, '', '')
    })
    await gitHelper.log({ cwd: '', limit: 999 })
  })
})

describe('gitHelper.clone()', () => {
  it('rejects when url is missing', async () => {
    await expect(gitHelper.clone({ dest: 'repo' })).rejects.toThrow(/url is required/i)
  })

  it('returns failure when destination exists', async () => {
    fs.existsSync.mockReturnValue(true)

    const result = await gitHelper.clone({ url: 'https://example.com/repo.git', dest: 'repo' })
    expect(result.success).toBe(false)
    expect(result.message).toMatch(/already exists/)
  })

  it('returns success on successful clone', async () => {
    fs.existsSync.mockReturnValue(false)
    mockExecFile.mockImplementation((_cmd, _args, _opts, cb) => cb(null, '', ''))

    const result = await gitHelper.clone({ url: 'https://example.com/repo.git', dest: 'myrepo' })
    expect(result.success).toBe(true)
    expect(result.message).toMatch(/Cloned/)
  })

  it('rejects on git clone failure', async () => {
    fs.existsSync.mockReturnValue(false)
    mockExecFile.mockImplementation((_cmd, _args, _opts, cb) =>
      cb(new Error('auth failed'), '', 'fatal: Authentication failed')
    )

    await expect(gitHelper.clone({ url: 'https://example.com/repo.git', dest: 'repo' })).rejects.toThrow()
  })
})
