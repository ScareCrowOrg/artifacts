/**
 * Resolve the correct WebSocket URL for the Node-PTY service based on
 * the execution environment.
 *
 * - **Production (Tauri via Cloudflare Tunnel)**: `wss://{tunnel_fqdn}/wss/pty`
 *   Uses the FQDN from VITE_TUNNEL_FQDN, which is injected by the Launcher
 *   into the Vite build.  The path `/wss/pty` routes through Traefik →
 *   Auth-Proxy (session validation) → Node-PTY service.
 * - **Local / Docker**: `ws://node-pty-service:8000/ws`
 *   Direct container-to-container communication within the Docker network.
 *
 * This is a pure TypeScript function with zero dependencies.
 */
export function resolveWsUrl(): string {
  // Check import.meta.env (Vite build) and process.env (Vitest) for the FQDN.
  const fqdn =
    (typeof import.meta !== 'undefined' &&
      (import.meta as any).env?.VITE_TUNNEL_FQDN) ||
    (typeof process !== 'undefined' && process.env?.VITE_TUNNEL_FQDN) ||
    ''
  if (fqdn) {
    return `wss://${fqdn}/wss/pty`
  }
  return 'ws://node-pty-service:8000/ws'
}
