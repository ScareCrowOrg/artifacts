/**
 * Resolve the correct WebSocket URL for the Node-PTY service based on
 * the execution environment.
 *
 * - **Tunnel mode** (``VITE_TUNNEL_FQDN`` set): ``wss://{tunnel_fqdn}/wss/pty``
 *   Uses the FQDN from VITE_TUNNEL_FQDN, injected by the Launcher.
 *   The path routes through Traefik → Auth-Proxy → Node-PTY service.
 * - **Docker mode** (no FQDN): discovers available WSS PTY services via the
 *   Backend discovery API (``/api/services/discover?capability=pty-wss``)
 *   and returns the first alive service's URL.
 * - **Fallback**: if discovery fails, returns ``ws://node-pty-service:8000/ws``
 *   for backward compatibility.
 */
import { discoverServices } from './useWssPtyDiscovery'

export async function resolveWsUrl(): Promise<string> {
  const fqdn =
    (typeof import.meta !== 'undefined' &&
      (import.meta as any).env?.VITE_TUNNEL_FQDN) ||
    (typeof process !== 'undefined' && process.env?.VITE_TUNNEL_FQDN) ||
    ''
  if (fqdn) {
    return `wss://${fqdn}/wss/pty`
  }

  // Docker mode: discover available WSS PTY services dynamically
  try {
    const services = await discoverServices()
    const alive = services.filter(s => s.alive)
    if (alive.length > 0) {
      return alive[0].url
    }
  } catch {
    // Fall through to fallback
  }

  // Ultimate fallback (backward-compat)
  return 'ws://node-pty-service:8000/ws'
}
