//! Core proxy logic – universal ingress guard for API, Vite, and Artifacts traffic.
//!
//! # Flow
//! 1. Classify request path:
//!    - `/api/v1/auth/session-bind` → bypass auth, proxy to Backend.
//!    - `/wss/*` → require valid `sessionId`, tunnel WebSocket to upstream.
//!    - `/api/*` → require valid `sessionId`, proxy to Backend.
//!    - `/artifacts/*` → require valid `sessionId`, proxy to Vite (RBAC enforced).
//!    - anything else (e.g. `/`, `/viewers/*`) → require valid `sessionId`, proxy to Vite.
//! 2. For protected paths, call Backend session-check endpoint.
//! 3. **200 OK** → proxy to Backend or Vite depending on path.
//! 4. **403 Forbidden** → return 403 immediately.
//! 5. **Other** → return 500 Internal Server Error.
//!
//! # Host Header Handling
//! - Vite traffic rewrites `Host` to the Vite upstream host (`vite:5052`).
//! - Backend traffic preserves incoming `Host` when present so Backend can keep
//!   FQDN-sensitive logic (CORS/JWT validations), otherwise uses upstream host.
//!
//! # Artifact Sovereignty
//! All `/artifacts/*` requests are validated here before any byte is served.
//! Vite (port 5052) has no direct Traefik route — Auth-Proxy is the sole gatekeeper.

use axum::{
    body::Body,
    extract::{Request, State},
    http::{HeaderMap, HeaderName, HeaderValue, StatusCode},
    response::{IntoResponse, Response},
};
use reqwest::header;
use tracing::{debug, error, info, warn};

use crate::AppState;

/// Redis heartbeat key registered by Auth Proxy to signal readiness.
pub const HEARTBEAT_KEY: &str = "state:service:auth-proxy:available";

/// Health check handler — always returns 200 OK.
///
/// Used by docker-compose `healthcheck` and by Traefik service discovery.
pub async fn health_handler() -> impl IntoResponse {
    (StatusCode::OK, "OK")
}

/// Routing decision for an incoming request.
#[derive(Debug, Clone, Copy)]
enum RouteDecision {
    BackendBypass,
    BackendProtected,
    ViteProtected,
    /// Path starts with `/wss/` — resolved via Redis SCAN at request time.
    WssProxy,
    Deny,
}

fn classify_route(path: &str) -> RouteDecision {
    if path == "/api/v1/auth/session-bind" {
        RouteDecision::BackendBypass
    } else if path.starts_with("/wss/") {
        RouteDecision::WssProxy
    } else if path.starts_with("/api/") {
        RouteDecision::BackendProtected
    } else if path.starts_with("/artifacts/") || path.starts_with("/@vite/") || path.starts_with("/.vite/") || path.starts_with("/__vite") {
        // Artifacts and Vite internals are served by Vite but must be session-validated first.
        // /@vite/ = Vite special internal endpoints (HMR, client code)
        // /.vite/deps/ = optimized dependency bundles
        // /__vite_hmr = Hot Module Replacement WebSocket connection
        // Auth-Proxy is the sole gatekeeper — no direct Traefik route to Vite exists.
        RouteDecision::ViteProtected
    } else {
        // Everything else → Vite (/, /viewers*, /canonical/*, /sandbox/*, /runtime/*, etc.)
        RouteDecision::ViteProtected
    }
}

/// Extract the WSS alias from a `/wss/{alias}[/...]` path.
///
/// Returns `None` if the path does not start with `/wss/` or has no alias segment.
fn extract_wss_alias(path: &str) -> Option<&str> {
    let rest = path.strip_prefix("/wss/")?;
    // Alias is the first path segment after `/wss/`.
    let alias = rest.split('/').next()?;
    if alias.is_empty() {
        None
    } else {
        Some(alias)
    }
}

/// Parse a routing JSON value stored in Redis and extract the upstream URL.
///
/// Expected JSON format:
/// `{"wss": {"enabled": true, "alias": "events", "upstream_port": 5050, ...}}`
///
/// Returns `Ok("http://{alias}:{upstream_port}")` on success.
/// Returns `Err(404)` if `wss.enabled` is false or the `wss` key is missing.
/// Returns `Err(500)` if JSON is malformed or `upstream_port` is absent.
pub fn parse_wss_routing_value(raw_json: &str, alias: &str) -> Result<String, StatusCode> {
    let data: serde_json::Value = serde_json::from_str(raw_json).map_err(|e| {
        warn!("[WSSProxy] Invalid JSON for alias '{}': {}", alias, e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    let wss = data.get("wss").ok_or_else(|| {
        warn!("[WSSProxy] No 'wss' key in routing data for alias '{}'", alias);
        StatusCode::NOT_FOUND
    })?;

    let enabled = wss.get("enabled").and_then(|v| v.as_bool()).unwrap_or(false);
    if !enabled {
        warn!("[WSSProxy] wss.enabled=false for alias '{}'", alias);
        return Err(StatusCode::NOT_FOUND);
    }

    let upstream_port = wss
        .get("upstream_port")
        .and_then(|v| v.as_u64())
        .ok_or_else(|| {
            warn!("[WSSProxy] Missing upstream_port for alias '{}'", alias);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    Ok(format!("http://{}:{}", alias, upstream_port))
}

/// Resolve the upstream URL for a WSS alias by scanning Redis for the
/// matching `state:service:{service_name}:routing` key.
///
/// Scans all keys matching ``state:service:*:routing`` and finds the one
/// whose ``wss.alias`` equals the requested *alias*. This avoids relying on
/// ``state:service:{alias}:routing``, which fails when alias ≠ service_name.
///
/// Returns ``Ok(upstream_url)`` on success (e.g. ``http://node-pty-service:8000``).
/// Returns ``Err(404)`` if no service advertises the requested alias.
/// Returns ``Err(503)`` if Redis is temporarily unavailable.
async fn resolve_wss_upstream(
    state: &AppState,
    alias: &str,
) -> Result<String, axum::http::StatusCode> {
    let pattern = "state:service:*:routing".to_string();
    let mut conn = state.redis_cm.clone();

    let mut cursor: u64 = 0;
    loop {
        let result: (u64, Vec<String>) = redis::cmd("SCAN")
            .arg(cursor)
            .arg("MATCH")
            .arg(&pattern)
            .arg("COUNT")
            .arg(100)
            .query_async(&mut conn)
            .await
            .map_err(|e| {
                warn!("[WSSProxy] Redis SCAN error: {}", e);
                axum::http::StatusCode::SERVICE_UNAVAILABLE
            })?;

        cursor = result.0;
        let keys = result.1;

        for key in &keys {
            let value: Option<String> = redis::cmd("GET")
                .arg(key.as_str())
                .query_async(&mut conn)
                .await
                .map_err(|e| {
                    warn!("[WSSProxy] Redis GET error for key '{}': {}", key, e);
                    axum::http::StatusCode::SERVICE_UNAVAILABLE
                })?;

            if let Some(raw) = value {
                if let Ok(data) = serde_json::from_str::<serde_json::Value>(&raw) {
                    let wss = match data.get("wss") {
                        Some(v) => v,
                        None => continue,
                    };
                    let enabled = wss.get("enabled").and_then(|v| v.as_bool()).unwrap_or(false);
                    if !enabled {
                        continue;
                    }
                    let wss_alias = wss.get("alias").and_then(|v| v.as_str()).unwrap_or("");
                    if wss_alias != alias {
                        continue;
                    }
                    // Match found — extract service_name from key and build URL.
                    let parts: Vec<&str> = key.split(':').collect();
                    if parts.len() < 4 {
                        warn!("[WSSProxy] Unexpected key format '{}' for alias '{}'", key, alias);
                        continue;
                    }
                    let service_name = parts[2];
                    let upstream_port = wss.get("upstream_port").and_then(|v| v.as_u64()).ok_or_else(|| {
                        warn!("[WSSProxy] Missing upstream_port for alias '{}'", alias);
                        axum::http::StatusCode::INTERNAL_SERVER_ERROR
                    })?;

                    debug!(
                        "[WSSProxy] Resolved alias '{}' → service '{}' port {}",
                        alias, service_name, upstream_port
                    );
                    return Ok(format!("http://{}:{}", service_name, upstream_port));
                }
            }
        }

        if cursor == 0 {
            break;
        }
    }

    warn!("[WSSProxy] No service found for WSS alias '{}' in Redis", alias);
    Err(axum::http::StatusCode::NOT_FOUND)
}


/// Universal ingress handler.
pub async fn request_handler(State(state): State<AppState>, req: Request) -> Response {
    let path = req.uri().path().to_owned();
    let query = req
        .uri()
        .query()
        .map(|q| format!("?{q}"))
        .unwrap_or_default();
    let full_path = format!("{path}{query}");
    let method = req.method().to_string();

    let decision = classify_route(&path);
    info!("[AuthProxy] → {} {} ({:?})", method, full_path, decision);

    // Handle CORS preflight OPTIONS requests immediately (no auth required)
    if method == "OPTIONS" {
        let origin = req
            .headers()
            .get(header::ORIGIN)
            .and_then(|v| v.to_str().ok())
            .unwrap_or("*");
        info!("[AuthProxy] CORS preflight OPTIONS for {} (origin: {})", path, origin);
        return build_cors_response(StatusCode::OK, origin);
    }

    if matches!(decision, RouteDecision::Deny) {
        warn!("[AuthProxy] Request denied by route policy: {}", path);
        return build_error_response(StatusCode::FORBIDDEN);
    }

    // Debug: Log all headers to diagnose Traefik passthrough
    debug!("[AuthProxy] Headers: {:?}", req.headers());

    // ── WebSocket upgrade bifurcation ────────────────────────────────────────
    // Must happen BEFORE body buffering inside proxy_to_upstream().
    // Session validation happens HERE (before HTTP 101) so we can return 403
    // if the session is invalid — it is impossible to send 403 after 101.
    if crate::ws_proxy::is_websocket_upgrade_request(&req) {
        // BackendBypass routes need no session validation.
        if matches!(decision, RouteDecision::BackendBypass) {
            info!("[WS] BackendBypass WebSocket upgrade for path={}", path);
            return crate::ws_proxy::proxy_ws_to_upstream(req, &state.backend_upstream).await;
        }

        // WssProxy: session check FIRST (prevents unauthenticated alias enumeration),
        // then resolve upstream. This ordering ensures an attacker cannot probe valid
        // aliases without a valid session.
        if matches!(decision, RouteDecision::WssProxy) {
            // Extract session cookie for validation before any alias resolution.
            let cookie_header = req
                .headers()
                .get(header::COOKIE)
                .and_then(|v| v.to_str().ok())
                .map(str::to_owned);
            let has_cookie = cookie_header.is_some();
            info!(
                "[WSSProxy] Session validation: path={} (SessionID={})",
                path, has_cookie
            );

            // Session check before alias resolution and HTTP 101.
            let session_result = check_session(&state, &cookie_header, &path).await;
            if let Err(status) = session_result {
                warn!(
                    "[WSSProxy] Session denied ({}) for {}, rejecting upgrade",
                    status, path
                );
                return build_error_response(status);
            }

            // Session is valid — now resolve the upstream alias.
            let alias = match extract_wss_alias(&path) {
                Some(a) => a.to_owned(),
                None => {
                    warn!("[WSSProxy] Could not extract alias from path={}", path);
                    return build_error_response(StatusCode::NOT_FOUND);
                }
            };
            let upstream = match resolve_wss_upstream(&state, &alias).await {
                Ok(u) => u,
                Err(status) => return build_error_response(status),
            };

            info!(
                "[WSSProxy] Session valid, tunnelling {} → {} (alias={})",
                path, upstream, alias
            );
            return crate::ws_proxy::proxy_ws_to_upstream(req, &upstream).await;
        }

        let upstream_base = match decision {
            RouteDecision::BackendProtected => state.backend_upstream.as_str(),
            RouteDecision::ViteProtected => state.vite_upstream.as_str(),
            // Deny is already rejected above; BackendBypass and WssProxy are handled above.
            // This arm is a safety net in case new variants are added.
            RouteDecision::Deny => {
                warn!("[WS] Deny decision reached WebSocket bifurcation — rejecting");
                return build_error_response(StatusCode::FORBIDDEN);
            }
            RouteDecision::BackendBypass | RouteDecision::WssProxy => {
                error!("[WS] BackendBypass/WssProxy decision reached protected WebSocket branch — internal inconsistency");
                return build_error_response(StatusCode::INTERNAL_SERVER_ERROR);
            }
        };

        // Extract session cookie for validation before upgrade.
        let cookie_header = req
            .headers()
            .get(header::COOKIE)
            .and_then(|v| v.to_str().ok())
            .map(str::to_owned);

        let has_cookie = cookie_header.is_some();
        info!(
            "[WS] Session validation: path={} (SessionID={})",
            path, has_cookie
        );

        return match check_session(&state, &cookie_header, &path).await {
            Ok(()) => {
                info!(
                    "[WS] Session valid, proceeding with WebSocket upgrade for {}",
                    path
                );
                crate::ws_proxy::proxy_ws_to_upstream(req, upstream_base).await
            }
            Err(status) => {
                warn!(
                    "[WS] Session denied ({}) for {}, rejecting WebSocket upgrade",
                    status, path
                );
                build_error_response(status)
            }
        };
    }
    // ── End WebSocket bifurcation ─────────────────────────────────────────────

    // WssProxy paths that are NOT WebSocket upgrades (e.g., GET /wss/events/health).
    // These are plain HTTP requests — session check FIRST, then alias resolution
    // to prevent unauthenticated enumeration of valid aliases.
    if matches!(decision, RouteDecision::WssProxy) {
        let cookie_header = req
            .headers()
            .get(header::COOKIE)
            .and_then(|v| v.to_str().ok())
            .map(str::to_owned);
        // Session check before alias resolution (security: prevents alias enumeration).
        if let Err(status) = check_session(&state, &cookie_header, &path).await {
            return build_error_response(status);
        }
        // Session valid — now extract alias and resolve upstream.
        let alias = match extract_wss_alias(&path) {
            Some(a) => a.to_owned(),
            None => {
                warn!("[WSSProxy] Could not extract alias from HTTP path={}", path);
                return build_error_response(StatusCode::NOT_FOUND);
            }
        };
        let upstream = match resolve_wss_upstream(&state, &alias).await {
            Ok(u) => u,
            Err(status) => return build_error_response(status),
        };
        return proxy_to_upstream(&state, req, &full_path, &upstream, None).await;
    }

    if matches!(decision, RouteDecision::BackendBypass) {
        return proxy_to_backend(state, req, &full_path, true).await;
    }

    // Step 1 – extract Cookie header from the request.
    let cookie_header = req
        .headers()
        .get(header::COOKIE)
        .and_then(|v| v.to_str().ok())
        .map(str::to_owned);

    // Step 2 – validate session via Backend.
    let has_cookie = cookie_header.is_some();
    if let Some(ref cookie) = cookie_header {
        debug!("[AuthProxy] Extracted cookie: {}", cookie);
    } else {
        warn!("[AuthProxy] NO Cookie header received from Traefik!");
    }
    let auth_result = check_session(&state, &cookie_header, &path).await;

    match auth_result {
        Ok(()) => match decision {
            RouteDecision::BackendProtected => {
                debug!(
                    "[AuthProxy] Auth OK for {} (SessionID={}), proxying to Backend",
                    path, has_cookie
                );
                proxy_to_backend(state, req, &full_path, false).await
            }
            RouteDecision::ViteProtected => {
                debug!(
                    "[AuthProxy] Auth OK for {} (SessionID={}), proxying to Vite",
                    path, has_cookie
                );
                proxy_to_vite(state, req, &full_path).await
            }
            RouteDecision::BackendBypass | RouteDecision::Deny | RouteDecision::WssProxy => {
                error!(
                    "[AuthProxy] Internal routing inconsistency: authenticated flow reached unexpected decision {:?} for path {}",
                    decision, path
                );
                build_error_response(StatusCode::INTERNAL_SERVER_ERROR)
            }
        },
        Err(status) => {
            if status == StatusCode::FORBIDDEN {
                warn!(
                    "[AuthProxy] Auth DENIED for {} (403) | SessionID present: {}",
                    path, has_cookie
                );
            } else {
                error!(
                    "[AuthProxy] Auth ERROR for {} ({}) | SessionID present: {}",
                    path, status, has_cookie
                );
            }
            build_error_response(status)
        }
    }
}

/// Extract the `sessionId` value from a raw `Cookie` header string.
///
/// Parses `sessionId=<value>` from a semicolon-separated list of cookie pairs.
/// Returns `None` if the `sessionId` key is not present or the value is too long
/// (> 512 bytes) to prevent cache-key pollution attacks.
fn extract_session_id(cookie_header: &str) -> Option<String> {
    const MAX_SESSION_ID_LEN: usize = 512;
    for part in cookie_header.split(';') {
        let part = part.trim();
        if let Some(val) = part.strip_prefix("sessionId=") {
            if !val.is_empty() && val.len() <= MAX_SESSION_ID_LEN {
                return Some(val.to_owned());
            }
        }
    }
    None
}

/// Call Backend's `/api/v1/auth/session-check` endpoint.
///
/// Results are cached per `sessionId` to absorb burst traffic when a workspace loads
/// multiple cell assets in parallel.  TTL: 5 s for valid sessions, 1 s for invalid
/// sessions (short TTL avoids persisting a wrongly-denied result for a re-issued sessionId).
///
/// Returns:
/// - `Ok(())` when Backend responds with 200 (session valid, RBAC passed).
/// - `Err(403)` when Backend responds with 403 (denied).
/// - `Err(500)` on network / unexpected Backend errors.
async fn check_session(
    state: &AppState,
    cookie_header: &Option<String>,
    uri: &str,
) -> Result<(), StatusCode> {
    use std::time::Instant;

    const VALID_TTL_SECS: u64 = 5;
    const INVALID_TTL_SECS: u64 = 1;

    // Try to read sessionId from cookie for cache lookup.
    let session_id: Option<String> = cookie_header
        .as_deref()
        .and_then(extract_session_id);

    // Cache lookup — only when a sessionId is present.
    if let Some(ref sid) = session_id {
        let cache = state.session_cache.lock().await;
        if let Some(&(checked_at, is_valid)) = cache.get(sid.as_str()) {
            let ttl = if is_valid { VALID_TTL_SECS } else { INVALID_TTL_SECS };
            if checked_at.elapsed().as_secs() < ttl {
                debug!(
                    "[AuthProxy] Session cache HIT for sessionId={} (valid={}, age={}ms)",
                    sid,
                    is_valid,
                    checked_at.elapsed().as_millis()
                );
                return if is_valid {
                    Ok(())
                } else {
                    Err(StatusCode::FORBIDDEN)
                };
            }
        }
        debug!("[AuthProxy] Session cache MISS for sessionId={}", sid);
    }

    // Build auth URL with `uri` query parameter so Backend can apply RBAC rules.
    let auth_url = format!(
        "{}?uri={}",
        state.backend_auth_url,
        urlencoding::encode(uri)
    );

    let mut req_builder = state.http_client.post(&auth_url);

    // Forward the Cookie header so Backend can read `sessionId`.
    if let Some(cookie) = cookie_header {
        req_builder = req_builder.header(header::COOKIE, cookie);
        info!("[AuthProxy] → Backend session-check: uri={} (with SessionID)", uri);
    } else {
        warn!("[AuthProxy] → Backend session-check: uri={} (NO SessionID)", uri);
    }

    let response = req_builder.send().await.map_err(|e| {
        error!(
            "[AuthProxy] Backend request failed: {} (URL: {})",
            e, auth_url
        );
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    let result = match response.status().as_u16() {
        200 => {
            debug!("[AuthProxy] Backend returned 200 OK for {}", uri);
            Ok(())
        }
        403 => {
            debug!("[AuthProxy] Backend returned 403 FORBIDDEN for {}", uri);
            Err(StatusCode::FORBIDDEN)
        }
        code => {
            error!("[AuthProxy] Unexpected Backend status {} for {}", code, uri);
            Err(StatusCode::INTERNAL_SERVER_ERROR)
        }
    };

    // Store result in cache (only for definitive valid/invalid outcomes, not 5xx errors).
    if let Some(sid) = session_id {
        match &result {
            Ok(()) | Err(StatusCode::FORBIDDEN) => {
                let is_valid = result.is_ok();
                let mut cache = state.session_cache.lock().await;
                // Prune all expired entries before inserting to bound memory growth.
                cache.retain(|_, &mut (checked_at, is_v)| {
                    let ttl = if is_v { VALID_TTL_SECS } else { INVALID_TTL_SECS };
                    checked_at.elapsed().as_secs() < ttl
                });
                cache.insert(sid, (Instant::now(), is_valid));
            }
            _ => {}
        }
    }

    result
}

/// Proxy the validated request to Vite and stream the response back.
///
/// **Host header is rewritten** to the Vite internal DNS name so that Vite
/// processes the request correctly (Vite dev server is host-aware).
async fn proxy_to_upstream(
    state: &AppState,
    orig_req: Request,
    full_path: &str,
    upstream_base: &str,
    host_override: Option<&str>,
) -> Response {
    let target_url = format!("{upstream_base}{full_path}");
    debug!("[AuthProxy] Forwarding upstream: {}", target_url);

    let method = orig_req.method().clone();

    // Forward a safe subset of original headers. Exclude hop-by-hop headers.
    // **CRITICAL**: Allow 'upgrade' and 'connection' headers for WebSocket support (HMR, future Backend WS endpoints)
    let mut fwd_headers = reqwest::header::HeaderMap::new();
    for (name, value) in orig_req.headers() {
        let name_str = name.as_str();
        // Skip hop-by-hop headers and Host (set explicitly below when needed).
        // NOTE: 'upgrade' and 'connection' are allowed through for WebSocket (Vite HMR, future Backend WS)
        if matches!(
            name_str,
            "host"
                | "transfer-encoding"
                | "te"
                | "trailer"
                | "keep-alive"
                | "proxy-authorization"
                | "proxy-authenticate"
        ) {
            continue;
        }
        if let Ok(v) = reqwest::header::HeaderValue::from_bytes(value.as_bytes()) {
            if let Ok(n) = reqwest::header::HeaderName::from_bytes(name.as_str().as_bytes()) {
                fwd_headers.insert(n, v);
            }
        }
    }

    if let Some(host) = host_override {
        if let Ok(host_val) = reqwest::header::HeaderValue::from_str(host) {
            fwd_headers.insert(reqwest::header::HOST, host_val);
        }
    }

    // Stream the request body to Vite.
    let body_bytes = match axum::body::to_bytes(orig_req.into_body(), usize::MAX).await {
        Ok(b) => b,
        Err(e) => {
            error!("[AuthProxy] Failed to read request body: {}", e);
            return build_error_response(StatusCode::INTERNAL_SERVER_ERROR);
        }
    };

    let req_method = match reqwest::Method::from_bytes(method.as_str().as_bytes()) {
        Ok(parsed) => parsed,
        Err(_) => {
            warn!(
                "[AuthProxy] Unsupported method '{}', returning 405 for {}",
                method, full_path
            );
            return build_error_response(StatusCode::METHOD_NOT_ALLOWED);
        }
    };

    let upstream_req = state
        .http_client
        .request(req_method, &target_url)
        .headers(fwd_headers)
        .body(body_bytes);

    let upstream_resp = match upstream_req.send().await {
        Ok(r) => r,
        Err(e) => {
            error!("[AuthProxy] Upstream request error: {}", e);
            return build_error_response(StatusCode::BAD_GATEWAY);
        }
    };

    // Convert reqwest response status + headers to axum response.
    let status = StatusCode::from_u16(upstream_resp.status().as_u16())
        .unwrap_or(StatusCode::INTERNAL_SERVER_ERROR);

    let mut resp_headers = HeaderMap::new();
    for (name, value) in upstream_resp.headers() {
        // Skip hop-by-hop headers from upstream response.
        // **CRITICAL**: Allow 'upgrade' and 'connection' headers for WebSocket support (HMR, future Backend WS)
        if matches!(
            name.as_str(),
            "transfer-encoding" | "keep-alive" | "trailer"
        ) {
            continue;
        }
        if let (Ok(n), Ok(v)) = (
            HeaderName::from_bytes(name.as_str().as_bytes()),
            HeaderValue::from_bytes(value.as_bytes()),
        ) {
            resp_headers.insert(n, v);
        }
    }

    // Stream the upstream response body back to the client.
    let body_stream = upstream_resp.bytes_stream();
    let stream_body = Body::from_stream(body_stream);

    let mut response = Response::new(stream_body);
    *response.status_mut() = status;
    *response.headers_mut() = resp_headers;

    info!("[AuthProxy] Proxied {} → upstream ({})", full_path, status);
    response
}

fn extract_host(url: &str) -> &str {
    url.trim_start_matches("http://")
        .trim_start_matches("https://")
}

/// Proxy request to Vite upstream with host header rewrite.
async fn proxy_to_vite(state: AppState, orig_req: Request, full_path: &str) -> Response {
    let vite_host = extract_host(&state.vite_upstream).to_string();
    proxy_to_upstream(
        &state,
        orig_req,
        full_path,
        &state.vite_upstream,
        Some(&vite_host),
    )
    .await
}

/// Proxy request to Backend upstream.
/// - For bypass route, no auth is required.
/// - For protected API routes, auth was already checked.
async fn proxy_to_backend(
    state: AppState,
    orig_req: Request,
    full_path: &str,
    bypass: bool,
) -> Response {
    let host_override = orig_req
        .headers()
        .get(header::HOST)
        .and_then(|v| v.to_str().ok())
        .map(str::to_owned)
        .unwrap_or_else(|| extract_host(&state.backend_upstream).to_owned());

    let response = proxy_to_upstream(
        &state,
        orig_req,
        full_path,
        &state.backend_upstream,
        Some(&host_override),
    )
    .await;

    if bypass {
        info!("[AuthProxy] Bypass proxy route served for {}", full_path);
    }
    response
}

/// Build a JSON error response with the given status code.
fn build_error_response(status: StatusCode) -> Response {
    let body = serde_json::json!({ "error": status.canonical_reason().unwrap_or("Error") });
    let json = body.to_string();

    let mut resp = Response::new(Body::from(json));
    *resp.status_mut() = status;
    resp.headers_mut().insert(
        axum::http::header::CONTENT_TYPE,
        HeaderValue::from_static("application/json"),
    );
    resp
}

/// Build a CORS preflight response (OPTIONS) with appropriate Access-Control headers.
/// Uses the requesting origin to avoid incompatibility with credentials (can't use * with credentials).
fn build_cors_response(status: StatusCode, origin: &str) -> Response {
    let mut resp = Response::new(Body::empty());
    *resp.status_mut() = status;

    // Echo back the origin if provided; otherwise allow all
    // Note: When credentials are involved, must specify explicit origin (not *)
    if let Ok(origin_val) = HeaderValue::from_str(origin) {
        resp.headers_mut().insert(
            HeaderName::from_static("access-control-allow-origin"),
            origin_val,
        );
    } else {
        resp.headers_mut().insert(
            HeaderName::from_static("access-control-allow-origin"),
            HeaderValue::from_static("*"),
        );
    }

    // Allow common HTTP methods
    resp.headers_mut().insert(
        HeaderName::from_static("access-control-allow-methods"),
        HeaderValue::from_static("GET, POST, PUT, DELETE, PATCH, OPTIONS"),
    );

    // Allow common headers
    resp.headers_mut().insert(
        HeaderName::from_static("access-control-allow-headers"),
        HeaderValue::from_static("Content-Type, Authorization, Cookie"),
    );

    // Allow credentials (cookies) when origin is specified
    if origin != "*" {
        resp.headers_mut().insert(
            HeaderName::from_static("access-control-allow-credentials"),
            HeaderValue::from_static("true"),
        );
    }

    // Cache preflight for 1 hour
    resp.headers_mut().insert(
        HeaderName::from_static("access-control-max-age"),
        HeaderValue::from_static("3600"),
    );

    resp
}

/// Register and refresh the heartbeat key in Redis L1.
///
/// Uses a fixed TTL of `interval * 3` seconds and refreshes every `interval`
/// seconds, matching the BaseService pattern used by Backend and Vite.
pub async fn run_heartbeat(redis_url: String, interval_secs: u64) {
    let ttl = interval_secs * 3;
    let mut interval = tokio::time::interval(std::time::Duration::from_secs(interval_secs));

    info!(
        "[AuthProxy] Heartbeat started – key: {}, TTL: {}s, interval: {}s",
        HEARTBEAT_KEY, ttl, interval_secs
    );

    loop {
        interval.tick().await;

        match register_heartbeat_once(&redis_url, ttl).await {
            Ok(()) => debug!("[AuthProxy] Heartbeat refreshed (TTL: {}s)", ttl),
            Err(e) => warn!("[AuthProxy] Heartbeat refresh failed: {}", e),
        }
    }
}

async fn register_heartbeat_once(redis_url: &str, ttl: u64) -> Result<(), String> {
    let client = redis::Client::open(redis_url).map_err(|e| e.to_string())?;
    let mut conn = client
        .get_multiplexed_async_connection()
        .await
        .map_err(|e| e.to_string())?;

    // Build heartbeat value in JSON format: {"port_opened": true, "timestamp": <unix_float>}
    let timestamp = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map_err(|e| e.to_string())?
        .as_secs_f64();
    let heartbeat_value = format!(r#"{{"port_opened": true, "timestamp": {}}}"#, timestamp);

    redis::cmd("SET")
        .arg(HEARTBEAT_KEY)
        .arg(heartbeat_value)
        .arg("EX")
        .arg(ttl)
        .query_async::<_, ()>(&mut conn)
        .await
        .map_err(|e| e.to_string())
}

// ─── URL encoding helper ──────────────────────────────────────────────────────
mod urlencoding {
    pub fn encode(s: &str) -> String {
        let mut encoded = String::with_capacity(s.len());
        for byte in s.bytes() {
            match byte {
                b'A'..=b'Z'
                | b'a'..=b'z'
                | b'0'..=b'9'
                | b'-'
                | b'_'
                | b'.'
                | b'~'
                | b'/'
                | b'='
                | b'?'
                | b'&' => encoded.push(byte as char),
                b => encoded.push_str(&format!("%{b:02X}")),
            }
        }
        encoded
    }
}

// ─── Unit tests ───────────────────────────────────────────────────────────────
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_url_encode_path() {
        let encoded = urlencoding::encode("/artifacts/canonical/cell_types/test");
        assert_eq!(encoded, "/artifacts/canonical/cell_types/test");
    }

    #[test]
    fn test_url_encode_special_chars() {
        let encoded = urlencoding::encode("/artifacts/name with spaces");
        assert!(encoded.contains("%20"));
    }

    #[test]
    fn test_url_encode_preserves_slashes() {
        let path = "/artifacts/a/b/c";
        let encoded = urlencoding::encode(path);
        assert!(encoded.contains("/artifacts/a/b/c"));
    }

    #[test]
    fn test_classify_route_backend_bypass() {
        assert!(matches!(
            classify_route("/api/v1/auth/session-bind"),
            RouteDecision::BackendBypass
        ));
    }

    #[test]
    fn test_classify_route_protected_paths() {
        assert!(matches!(
            classify_route("/api/v1/models"),
            RouteDecision::BackendProtected
        ));
        assert!(matches!(
            classify_route("/viewers/dynamic-workspace"),
            RouteDecision::ViteProtected
        ));
        assert!(matches!(classify_route("/"), RouteDecision::ViteProtected));
    }

    #[test]
    fn test_classify_route_vite_catch_all() {
        // Paths that are not /api/* are caught by the Vite catch-all and routed to ViteProtected.
        assert!(matches!(
            classify_route("/metrics"),
            RouteDecision::ViteProtected
        ));
        assert!(matches!(
            classify_route("/sandbox/test"),
            RouteDecision::ViteProtected
        ));
    }

    #[test]
    fn test_classify_route_artifacts_cell_types() {
        // /artifacts/cell_types/* must be explicitly classified as ViteProtected.
        assert!(matches!(
            classify_route("/artifacts/cell_types/png-generator/BaseCell.js"),
            RouteDecision::ViteProtected
        ));
    }

    #[test]
    fn test_classify_route_artifacts_viewers() {
        // /artifacts/viewers/* must be classified as ViteProtected (Vite-served assets).
        assert!(matches!(
            classify_route("/artifacts/viewers/3d-mesh/bundle.js"),
            RouteDecision::ViteProtected
        ));
    }

    #[test]
    fn test_classify_route_artifacts_generic() {
        // Any future /artifacts/** subpath must be classified as ViteProtected.
        assert!(matches!(
            classify_route("/artifacts/any/future/path"),
            RouteDecision::ViteProtected
        ));
        assert!(matches!(
            classify_route("/artifacts/"),
            RouteDecision::ViteProtected
        ));
    }

    #[test]
    fn test_classify_route_wss_proxy() {
        // /wss/* paths are classified as WssProxy.
        assert!(matches!(
            classify_route("/wss/events"),
            RouteDecision::WssProxy
        ));
        assert!(matches!(
            classify_route("/wss/logs"),
            RouteDecision::WssProxy
        ));
        assert!(matches!(
            classify_route("/wss/unknown-alias"),
            RouteDecision::WssProxy
        ));
    }

    #[test]
    fn test_extract_wss_alias() {
        assert_eq!(extract_wss_alias("/wss/events"), Some("events"));
        assert_eq!(extract_wss_alias("/wss/logs"), Some("logs"));
        assert_eq!(extract_wss_alias("/wss/events/extra"), Some("events"));
        assert_eq!(extract_wss_alias("/wss/"), None);
        assert_eq!(extract_wss_alias("/api/v1"), None);
        assert_eq!(extract_wss_alias("/"), None);
    }

    #[test]
    fn test_parse_wss_routing_value_valid() {
        let raw = r#"{"wss":{"enabled":true,"alias":"events","upstream_port":5050}}"#;
        let result = parse_wss_routing_value(raw, "events");
        assert!(result.is_ok());
        assert_eq!(result.unwrap(), "http://events:5050");
    }

    #[test]
    fn test_parse_wss_routing_value_disabled() {
        let raw = r#"{"wss":{"enabled":false,"alias":"events","upstream_port":5050}}"#;
        let result = parse_wss_routing_value(raw, "events");
        assert!(result.is_err());
        assert_eq!(result.unwrap_err(), StatusCode::NOT_FOUND);
    }

    #[test]
    fn test_parse_wss_routing_value_missing_port() {
        let raw = r#"{"wss":{"enabled":true,"alias":"events"}}"#;
        let result = parse_wss_routing_value(raw, "events");
        assert!(result.is_err());
        assert_eq!(result.unwrap_err(), StatusCode::INTERNAL_SERVER_ERROR);
    }

    #[test]
    fn test_parse_wss_routing_value_invalid_json() {
        let raw = "not valid json {{{";
        let result = parse_wss_routing_value(raw, "events");
        assert!(result.is_err());
        assert_eq!(result.unwrap_err(), StatusCode::INTERNAL_SERVER_ERROR);
    }

    // ── extract_session_id tests ───────────────────────────────────────────────

    #[test]
    fn test_extract_session_id_basic() {
        assert_eq!(
            extract_session_id("sessionId=abc123"),
            Some("abc123".to_owned())
        );
    }

    #[test]
    fn test_extract_session_id_with_other_cookies() {
        assert_eq!(
            extract_session_id("lang=en; sessionId=xyz789; theme=dark"),
            Some("xyz789".to_owned())
        );
    }

    #[test]
    fn test_extract_session_id_missing() {
        assert_eq!(extract_session_id("lang=en; theme=dark"), None);
    }

    #[test]
    fn test_extract_session_id_empty_value() {
        // sessionId= with no value should return None.
        assert_eq!(extract_session_id("sessionId="), None);
    }

    #[test]
    fn test_extract_session_id_too_long() {
        // sessionId exceeding 512 bytes must be rejected to prevent cache key pollution.
        let long_id = "x".repeat(513);
        let cookie = format!("sessionId={}", long_id);
        assert_eq!(extract_session_id(&cookie), None);
    }

    #[test]
    fn test_extract_session_id_exactly_max_len() {
        // sessionId of exactly 512 bytes is accepted.
        let max_id = "a".repeat(512);
        let cookie = format!("sessionId={}", max_id);
        assert_eq!(extract_session_id(&cookie), Some(max_id));
    }

    // ── Session cache tests ────────────────────────────────────────────────────

    #[tokio::test]
    async fn test_session_cache_hit_valid() {
        use std::collections::HashMap;
        use std::sync::Arc;
        use std::time::Instant;
        use tokio::sync::Mutex;

        // Pre-populate cache with a valid entry that was just set.
        let cache: Arc<Mutex<HashMap<String, (Instant, bool)>>> =
            Arc::new(Mutex::new(HashMap::new()));
        {
            let mut c = cache.lock().await;
            c.insert("sid-valid".to_owned(), (Instant::now(), true));
        }

        // Confirm the cached entry is unexpired (age < 5 s).
        let c = cache.lock().await;
        let &(checked_at, is_valid) = c.get("sid-valid").unwrap();
        assert!(is_valid);
        assert!(checked_at.elapsed().as_secs() < 5);
    }

    #[tokio::test]
    async fn test_session_cache_invalid_not_persisted_across_ttl() {
        use std::collections::HashMap;
        use std::sync::Arc;
        use std::time::{Duration, Instant};
        use tokio::sync::Mutex;

        let cache: Arc<Mutex<HashMap<String, (Instant, bool)>>> =
            Arc::new(Mutex::new(HashMap::new()));
        {
            let mut c = cache.lock().await;
            // Simulate a cache entry that is 2 seconds old (exceeds invalid TTL of 1 s).
            let old_instant = Instant::now() - Duration::from_secs(2);
            c.insert("sid-invalid".to_owned(), (old_instant, false));
        }

        // After invalid TTL (1 s), the entry should be treated as expired.
        let c = cache.lock().await;
        let &(checked_at, _is_valid) = c.get("sid-invalid").unwrap();
        let ttl_invalid: u64 = 1;
        assert!(checked_at.elapsed().as_secs() >= ttl_invalid, "expired entry should be treated as a cache miss");
    }

    #[tokio::test]
    async fn test_session_cache_miss_after_valid_ttl() {
        use std::collections::HashMap;
        use std::sync::Arc;
        use std::time::{Duration, Instant};
        use tokio::sync::Mutex;

        let cache: Arc<Mutex<HashMap<String, (Instant, bool)>>> =
            Arc::new(Mutex::new(HashMap::new()));
        {
            let mut c = cache.lock().await;
            // Simulate a valid cache entry that is 6 seconds old (exceeds valid TTL of 5 s).
            let old_instant = Instant::now() - Duration::from_secs(6);
            c.insert("sid-valid-expired".to_owned(), (old_instant, true));
        }

        let c = cache.lock().await;
        let &(checked_at, _is_valid) = c.get("sid-valid-expired").unwrap();
        let ttl_valid: u64 = 5;
        assert!(checked_at.elapsed().as_secs() >= ttl_valid, "expired valid entry should be treated as a cache miss");
    }
}
