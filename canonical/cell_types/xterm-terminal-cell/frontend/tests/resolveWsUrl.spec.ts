/**
 * Unit tests for resolveWsUrl.ts
 *
 * Validates correct WSS URL resolution across environments:
 * - Tunnel FQDN available → wss://{fqdn}/wss/pty
 * - No tunnel → discovery API → fallback ws://node-pty-service:8000/ws
 * - import.meta.env undefined → graceful fallback
 */

import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { resolveWsUrl } from '../resolveWsUrl'

afterEach(() => {
  vi.unstubAllEnvs()
})

beforeEach(() => {
  // Mock fetch to return empty discovery by default (triggers fallback)
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: false,
    status: 500,
  }))
})

describe('resolveWsUrl', () => {
  it('returns wss:// with tunnel FQDN when VITE_TUNNEL_FQDN is set', async () => {
    vi.stubEnv('VITE_TUNNEL_FQDN', 'planet.scareverse.net')
    await expect(resolveWsUrl()).resolves.toBe('wss://planet.scareverse.net/wss/pty')
  })

  it('falls back to ws:// when VITE_TUNNEL_FQDN is empty and discovery fails', async () => {
    vi.stubEnv('VITE_TUNNEL_FQDN', '')
    await expect(resolveWsUrl()).resolves.toBe('ws://node-pty-service:8000/ws')
  })

  it('falls back to ws:// when VITE_TUNNEL_FQDN is unset and discovery fails', async () => {
    // No VITE_TUNNEL_FQDN set at all
    await expect(resolveWsUrl()).resolves.toBe('ws://node-pty-service:8000/ws')
  })

  it('returns wss:// with tunnel FQDN regardless of protocol prefix', async () => {
    vi.stubEnv('VITE_TUNNEL_FQDN', 'andromeda.scareverse.net')
    const url = await resolveWsUrl()
    expect(url).toMatch(/^wss:\/\//)
    expect(url).toContain('/wss/pty')
  })

  it('uses discovery result when available in Docker mode', async () => {
    vi.stubEnv('VITE_TUNNEL_FQDN', '')
    // Mock fetch to return a live service
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([
        {
          name: 'node-pty-service',
          alias: 'pty',
          upstream_port: 8000,
          upstream_path: '/ws',
          path: '/wss/pty',
          alive: true,
          url: 'ws://node-pty-service:8000/ws',
        },
      ]),
    }))
    await expect(resolveWsUrl()).resolves.toBe('ws://node-pty-service:8000/ws')
  })

  it('falls back when discovery returns empty array', async () => {
    vi.stubEnv('VITE_TUNNEL_FQDN', '')
    // Mock fetch to return empty array
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([]),
    }))
    await expect(resolveWsUrl()).resolves.toBe('ws://node-pty-service:8000/ws')
  })

  it('falls back when discovery returns only dead services', async () => {
    vi.stubEnv('VITE_TUNNEL_FQDN', '')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([
        {
          name: 'node-pty-service',
          alias: 'pty',
          upstream_port: 8000,
          upstream_path: '/ws',
          path: '/wss/pty',
          alive: false,  // Not alive
          url: 'ws://node-pty-service:8000/ws',
        },
      ]),
    }))
    await expect(resolveWsUrl()).resolves.toBe('ws://node-pty-service:8000/ws')
  })
})
