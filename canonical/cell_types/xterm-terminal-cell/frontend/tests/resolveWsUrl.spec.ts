/**
 * Unit tests for resolveWsUrl.ts
 *
 * Validates correct WSS URL resolution across environments:
 * - Tunnel FQDN available → wss://{fqdn}/wss/pty
 * - No tunnel → ws://node-pty-service:8000/ws (Docker local fallback)
 * - import.meta.env undefined → graceful fallback
 */

import { describe, it, expect, vi, afterEach } from 'vitest'
import { resolveWsUrl } from '../resolveWsUrl'

afterEach(() => {
  vi.unstubAllEnvs()
})

describe('resolveWsUrl', () => {
  it('returns wss:// with tunnel FQDN when VITE_TUNNEL_FQDN is set', () => {
    vi.stubEnv('VITE_TUNNEL_FQDN', 'planet.scareverse.net')
    expect(resolveWsUrl()).toBe('wss://planet.scareverse.net/wss/pty')
  })

  it('returns ws:// fallback when VITE_TUNNEL_FQDN is empty', () => {
    vi.stubEnv('VITE_TUNNEL_FQDN', '')
    expect(resolveWsUrl()).toBe('ws://node-pty-service:8000/ws')
  })

  it('returns ws:// fallback when VITE_TUNNEL_FQDN is unset', () => {
    // No VITE_TUNNEL_FQDN set at all
    expect(resolveWsUrl()).toBe('ws://node-pty-service:8000/ws')
  })

  it('returns wss:// with tunnel FQDN regardless of protocol prefix', () => {
    vi.stubEnv('VITE_TUNNEL_FQDN', 'andromeda.scareverse.net')
    const url = resolveWsUrl()
    expect(url).toMatch(/^wss:\/\//)
    expect(url).toContain('/wss/pty')
  })

  it('returns ws:// for Docker-local alias when no FQDN', () => {
    vi.stubEnv('VITE_TUNNEL_FQDN', '')
    const url = resolveWsUrl()
    expect(url).toBe('ws://node-pty-service:8000/ws')
  })
})
