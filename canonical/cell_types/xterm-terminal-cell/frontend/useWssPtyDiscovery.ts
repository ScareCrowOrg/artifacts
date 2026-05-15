/**
 * @file frontend/useWssPtyDiscovery.ts
 * @description Service discovery for WSS PTY endpoints.
 *
 * Fetches available WSS PTY services from the Backend API and resolves
 * the best connection URL based on the current environment.
 *
 * Usage:
 * ```typescript
 * import { discoverServices } from './useWssPtyDiscovery'
 * const services = await discoverServices()
 * if (services.length > 0) {
 *   const url = services[0].url  // First alive service
 * }
 * ```
 */

// ─── Types ────────────────────────────────────────────────────────────────────

export interface WssPtyService {
  name: string
  alias: string | null
  upstream_port: number
  upstream_path: string
  path: string
  alive: boolean
  url: string  // Docker-net URL: ws://{name}:{port}/{upstream_path}
}

// ─── Discovery ────────────────────────────────────────────────────────────────

const DISCOVERY_PATH = '/api/services/discover'

/**
 * Discover WSS PTY-capable services from the Backend API.
 *
 * Calls ``GET /api/services/discover?capability=pty-wss`` and returns
 * the list of discovered services. Returns an empty array if the API
 * is unreachable or no services are available (soft-fail).
 */
export async function discoverServices(): Promise<WssPtyService[]> {
  try {
    const response = await fetch(`${DISCOVERY_PATH}?capability=pty-wss`)
    if (!response.ok) {
      console.warn('[WssPtyDiscovery] API returned', response.status)
      return []
    }
    const services: WssPtyService[] = await response.json()
    return services.filter(s => s.alive)
  } catch (err) {
    console.warn('[WssPtyDiscovery] Failed to discover services:', err)
    return []
  }
}

/**
 * Get the best WebSocket URL for the current environment.
 *
 * - **Tunnel mode** (``VITE_TUNNEL_FQDN`` set): returns ``wss://{fqdn}/{service.path}``
 * - **Docker mode**: returns the first alive service's ``url`` field
 *
 * Returns ``null`` when no service is available.
 *
 * @param fqdn  Tunnel FQDN from VITE_TUNNEL_FQDN (empty string = Docker mode)
 */
export async function getBestWsUrl(fqdn: string): Promise<string | null> {
  if (fqdn) {
    // Tunnel mode: discover to get the path, but use wss://{fqdn}/{path}
    const services = await discoverServices()
    const alive = services.filter(s => s.alive)
    if (alive.length > 0 && alive[0].path) {
      return `wss://${fqdn}${alive[0].path}`
    }
    // Fallback: use known path
    return `wss://${fqdn}/wss/pty`
  }

  // Docker mode: first alive service URL
  const services = await discoverServices()
  const alive = services.filter(s => s.alive)
  if (alive.length > 0) {
    return alive[0].url
  }

  return null
}
