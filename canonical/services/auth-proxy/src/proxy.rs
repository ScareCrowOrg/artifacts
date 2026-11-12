//! Core proxy logic – universal ingress guard for API, Vite, and Artifacts traffic.
//!
//! # Flow
//! 1. Classify request path via `classify_route()` (see [`classify`] module).
//! 2. For protected paths, call Backend session-check endpoint.
//! 3. **200 OK** → proxy to Backend or Vite depending on route decision.
//! 4. **403 Forbidden** → return 403 immediately.
//! 5. **Other** → return 500 Internal Server Error.
//!
//! # Host Header Handling
//! - Vite traffic rewrites `Host` to the Vite upstream DNS name so Vite processes the
//!   request correctly (Vite dev server is host-aware).
//! - Backend traffic preserves incoming `Host` when present so Backend can keep
//!   FQDN-sensitive logic (CORS/JWT validations), otherwise uses upstream host.
//!
//! # Artifact Sovereignty
//! All `/artifacts/*` requests are validated here before any byte is served.
//! Vite (port 5052) has no direct Traefik route — Auth-Proxy is the sole gatekeeper.
//!
//! # Path normalization
//! The ingress normalizes the path **once**, before classification
//! ([`normalize_ingress_path`]): a segment that is `.`/`..` after percent-decoding
//! — or that would decode into extra segments — is rejected with 400 rather than
//! collapsed. Classification, the RBAC gate and the bytes read from disk therefore
//! all describe the same path.
//!
//! # Module Split
//! - [`classify`] — route classification (RouteDecision, classify_route, extractors)
//! - [`file_server`] — decoding, path resolution, MIME, streaming primitives
//! - [`proxy::session`] — session/JWT identity + Backend session-check
//! - [`proxy::canonical_server`] — canonical binary delivery (disk, Vite fallback)
//! - [`proxy::runtime_server`] — runtime RBAC gate + its two deliveries
//! - [`upstream`] — Redis SCAN upstream resolvers (WSS, FastAPI proxy)

use axum::{
    body::Body,
    extract::{Request, State},
    http::{HeaderMap, HeaderName, HeaderValue, StatusCode},
    response::Response,
};
use reqwest::header;
use tracing::{debug, error, info, warn};

use crate::AppState;

// ── Nested modules ────────────────────────────────────────────────────────
// Declared as children of this module so they can use its private helpers
// (`proxy_to_upstream`, `build_error_response`) without widening visibility.
mod canonical_server;
mod runtime_server;
mod session;

// ── Re-exports from sub-modules ───────────────────────────────────────────
pub use crate::classify::{health_handler, HEARTBEAT_KEY, RouteDecision};
use crate::classify::{classify_route, extract_viewer_id, extract_wss_alias, is_public_path};
use crate::file_server::{build_redirect_response, check_viewer_access, percent_decode_path};
use crate::upstream::{resolve_proxy_upstream, resolve_wss_upstream};

use session::{check_session, extract_session_id};

/// Universal ingress handler.
pub async fn request_handler(State(state): State<AppState>, req: Request) -> Response {
    let raw_path = req.uri().path().to_owned();
    // ── Path normalization (once, before anything looks at the path) ────────
    // Structural segments are rejected here, and bare stage paths get the
    // /artifacts prefix. Everything downstream — classification, the RBAC gate
    // and the bytes read from disk — then sees this exact path.
    let path = match normalize_ingress_path(&raw_path) {
        Ok(normalized) => normalized,
        Err(status) => {
            warn!("[AuthProxy] Rejecting malformed path: {}", raw_path);
            return build_error_response(status);
        }
    };
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
        let host = req
            .headers()
            .get(header::HOST)
            .and_then(|v| v.to_str().ok());
        info!("[AuthProxy] CORS preflight OPTIONS for {} (origin: {}, host: {:?})", path, origin, host);
        return build_cors_response(StatusCode::OK, origin, host);
    }

    // [DIAG] CORS context for non-OPTIONS requests
    let cors_origin = req
        .headers()
        .get(header::ORIGIN)
        .and_then(|v| v.to_str().ok())
        .unwrap_or("(none)");
    debug!("[DIAG] CORS-nonOPTIONS: method={}, origin={}, decision={:?}", method, cors_origin, decision);

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
        info!("[WS] BIFURCATION: decision={:?}, path={}", decision, path);
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
            if let Err(status) = check_session(&state, &cookie_header, &None, &path).await {
                warn!(
                    "[WS] Session denied ({}) for WSS path={}, rejecting WebSocket upgrade",
                    status, path
                );
                return build_error_response(status);
            }
            // Session valid — now extract alias and resolve upstream.
            let alias = match extract_wss_alias(&path) {
                Some(a) => a,
                None => {
                    warn!("[WS] Could not extract alias from path={}", path);
                    return build_error_response(StatusCode::NOT_FOUND);
                }
            };
            return match resolve_wss_upstream(&state, alias).await {
                Ok(upstream) => crate::ws_proxy::proxy_ws_to_upstream(req, &upstream).await,
                Err(status) => build_error_response(status),
            };
        }

        // FastApiProxy: HMR WebSocket – session check FIRST, then resolve proxy upstream.
        if matches!(decision, RouteDecision::FastApiProxy) {
            let cookie_header = req
                .headers()
                .get(header::COOKIE)
                .and_then(|v| v.to_str().ok())
                .map(str::to_owned);
            let has_cookie = cookie_header.is_some();
            info!(
                "[FastApiProxy] HMR WebSocket session validation: path={} (SessionID={})",
                path, has_cookie
            );

            let session_result = check_session(&state, &cookie_header, &None, &path).await;
            if let Err(status) = session_result {
                warn!(
                    "[FastApiProxy] Session denied ({}) for {}, rejecting HMR WebSocket upgrade",
                    status, path
                );
                return build_error_response(status);
            }

            // Session valid — now resolve the proxy upstream dynamically.
            let upstream = match resolve_proxy_upstream(&state).await {
                Ok(u) => u,
                Err(status) => return build_error_response(status),
            };

            info!(
                "[FastApiProxy] HMR WebSocket upgrade: {} → {}",
                path, upstream
            );
            return crate::ws_proxy::proxy_ws_to_upstream(req, &upstream).await;
        }

        // File deliveries should never receive WebSocket upgrades.
        if matches!(
            decision,
            RouteDecision::FileServer
                | RouteDecision::RuntimeFileServer
                | RouteDecision::RuntimeCodeProxy
        ) {
            warn!(
                "[WS] Artifact delivery decision {:?} reached WebSocket bifurcation — rejecting",
                decision
            );
            return build_error_response(StatusCode::BAD_REQUEST);
        }

        let upstream_base = match decision {
            RouteDecision::BackendProtected => state.backend_upstream.as_str(),
            RouteDecision::ViteProtected => state.vite_upstream.as_str(),
            RouteDecision::Deny => {
                warn!("[WS] Deny decision reached WebSocket bifurcation — rejecting");
                return build_error_response(StatusCode::FORBIDDEN);
            }
            RouteDecision::BackendBypass | RouteDecision::WssProxy |
            RouteDecision::FastApiProxy | RouteDecision::FileServer |
            RouteDecision::RuntimeFileServer | RouteDecision::RuntimeCodeProxy => {
                error!("[WS] Unexpected decision {:?} reached protected WebSocket branch — internal inconsistency", decision);
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

        return match check_session(&state, &cookie_header, &None, &path).await {
            Ok(()) => {
                info!(
                    "[WS] Session valid, proceeding with WebSocket upgrade for {} to {}",
                    path, upstream_base
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
        if let Err(status) = check_session(&state, &cookie_header, &None, &path).await {
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

    // Step 1b – extract Authorization header (Bearer token) for cross-origin downloads.
    // The session cookie has SameSite=Strict, so the browser does NOT send it on
    // cross-origin fetch requests.  The frontend sends a planet-scoped JWT as Bearer
    // token to authenticate the download without relying on a cookie.
    let auth_header = req
        .headers()
        .get(header::AUTHORIZATION)
        .and_then(|v| v.to_str().ok())
        .map(str::to_owned);

    // Public paths bypass all auth — proxy directly to Vite.
    if is_public_path(&path) {
        debug!("[AuthProxy] Public path '{}' — proxying to Vite without auth", path);
        return proxy_to_vite(state, req, &full_path).await;
    }

    // Step 2 – validate session via Backend.
    let has_cookie = cookie_header.is_some();
    if let Some(ref cookie) = cookie_header {
        debug!("[AuthProxy] Extracted cookie: {}", cookie);
    } else if let Some(ref auth) = auth_header {
        if auth.starts_with("Bearer ") {
            info!("[AuthProxy] No cookie, using Bearer token auth (token_prefix: {}...)", &auth[7..].chars().take(16).collect::<String>());
        } else {
            warn!("[AuthProxy] Authorization header present but not Bearer format");
        }
    } else {
        warn!("[AuthProxy] NO Cookie header AND no Authorization header received from Traefik!");
    }
    let auth_result = check_session(&state, &cookie_header, &auth_header, &path).await;

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
                // Viewer access check for /viewers/* paths
                if let Some(viewer_id) = extract_viewer_id(&path) {
                    let session_id = cookie_header.as_deref().and_then(extract_session_id);
                    if let Some(ref sid) = session_id {
                        if !check_viewer_access(&state, sid, viewer_id).await {
                            info!(
                                "[AuthProxy] Viewer '{}' denied for session {}, redirecting to /artifacts/canonical/viewers/planet-hall",
                                viewer_id, sid
                            );
                            return build_redirect_response("/artifacts/canonical/viewers/planet-hall");
                        }
                    }
                }
                debug!(
                    "[AuthProxy] Auth OK for {} (SessionID={}), proxying to Vite",
                    path, has_cookie
                );
                proxy_to_vite(state, req, &full_path).await
            }
            RouteDecision::FastApiProxy => {
                // Resolve upstream dynamically via Redis SCAN (same pattern as WSS).
                match resolve_proxy_upstream(&state).await {
                    Ok(upstream) => {
                        info!(
                            "[FastApiProxy] Auth OK for {} (SessionID={}), proxying to {}",
                            path, has_cookie, upstream
                        );
                        proxy_to_upstream(&state, req, &full_path, &upstream, None).await
                    }
                    Err(status) => build_error_response(status),
                }
            }
            RouteDecision::FileServer => {
                canonical_server::serve_canonical_artifact(&state, req, &path, &full_path).await
            }
            RouteDecision::RuntimeFileServer => {
                // Raw bytes: binary artifacts, or any extension nobody has
                // classified as compilable yet. The RBAC gate runs inside the
                // handler — the same gate the code path uses, so the extension
                // only chooses the delivery, never whether access is allowed.
                let session_id = cookie_header.as_deref().and_then(extract_session_id);
                runtime_server::serve_runtime_artifact(
                    &state,
                    req,
                    &path,
                    session_id.as_deref(),
                    auth_header.as_deref(),
                )
                .await
            }
            RouteDecision::RuntimeCodeProxy => {
                // Compilable runtime code: same gate first, then Vite compiles it.
                let session_id = cookie_header.as_deref().and_then(extract_session_id);
                runtime_server::proxy_runtime_code(
                    &state,
                    req,
                    &path,
                    &full_path,
                    session_id.as_deref(),
                    auth_header.as_deref(),
                )
                .await
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

/// Proxy the validated request to upstream and stream the response back.
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

        // Skip hop-by-hop headers that should not be forwarded.
        match name_str {
            "host" => continue,
            "transfer-encoding" | "content-length" => continue,
            "connection" | "keep-alive" | "upgrade" => continue,
            "proxy-authorization" | "proxy-authenticate" | "te" | "trailer" => continue,
            _ => {}
        }

        fwd_headers.insert(name.clone(), value.clone());
    }

    // Apply Host header: use override (when rewriting for Vite), else use incoming Host.
    let host_value = host_override.unwrap_or(
        orig_req
            .headers()
            .get(header::HOST)
            .and_then(|v| v.to_str().ok())
            .unwrap_or(upstream_base),
    );
    fwd_headers.insert(
        header::HOST,
        reqwest::header::HeaderValue::from_str(host_value).unwrap(),
    );

    // Extract Origin and Host headers BEFORE consuming orig_req (into_body moves it).
    // Convert to owned String so the values survive orig_req being moved.
    let origin = orig_req
        .headers()
        .get(header::ORIGIN)
        .and_then(|v| v.to_str().ok())
        .map(|v| v.to_string());
    let host = orig_req
        .headers()
        .get(header::HOST)
        .and_then(|v| v.to_str().ok())
        .map(|v| v.to_string());

    // Build upstream request.
    let mut upstream_req = state
        .http_client
        .request(method, &target_url)
        .headers(fwd_headers);

    // Forward body for POST/PUT/PATCH requests.
    let body_bytes = axum::body::to_bytes(orig_req.into_body(), usize::MAX).await;
    if let Ok(bytes) = body_bytes {
        if !bytes.is_empty() {
            upstream_req = upstream_req.body(bytes.to_vec());
        }
    }

    let response = match upstream_req.send().await {
        Ok(resp) => resp,
        Err(e) => {
            error!("[AuthProxy] Upstream request failed for {}: {}", target_url, e);
            return build_error_response(StatusCode::BAD_GATEWAY);
        }
    };

    let status = response.status();

    // Build the downstream Axum response from the reqwest response.
    let mut resp_headers = HeaderMap::new();
    for (name, value) in response.headers() {
        let name_str = name.as_str();
        // Strip hop-by-hop headers from upstream response.
        match name_str {
            "transfer-encoding" | "connection" | "keep-alive" => continue,
            "proxy-authenticate" | "proxy-authorization" | "te" | "trailer" => continue,
            "upgrade" => continue,
            _ => {}
        }
        // Transfer Content-Length as-is so the client knows the response size.
        resp_headers.insert(
            HeaderName::from_bytes(name_str.as_bytes()).unwrap(),
            HeaderValue::from_str(value.to_str().unwrap_or("")).unwrap(),
        );
    }

    let body_bytes = response.bytes().await.unwrap_or_default();
    let mut response = Response::new(Body::from(body_bytes));
    *response.status_mut() = status;
    *response.headers_mut() = resp_headers;

    info!("[AuthProxy] Proxied {} → upstream ({})", full_path, status);
    // [DIAG] Check if upstream response has CORS headers
    let has_acao = response.headers().get("access-control-allow-origin").is_some();
    let has_acac = response.headers().get("access-control-allow-credentials").is_some();
    debug!("[DIAG] proxy_to_upstream: status={}, ACAO={}, ACAC={}", status, has_acao, has_acac);
    // Add CORS headers from the original request's Origin and Host (already extracted before body consume).
    add_cors_headers(&mut response, origin.as_deref(), host.as_deref());
    response
}

/// Normalize the request path once, at the ingress, before anything acts on it.
///
/// Two structural jobs:
///
/// 1. **Reject** any path segment that is `.` or `..` once percent-decoded, or
///    that decodes to a value containing `/`. Encoded separators and dot segments
///    are the two ways one path string can denote two different resources. They
///    are rejected rather than collapsed because the path that is *authorized*
///    must be the path that is *read*: collapsing first (`/a/../b` → `/b`) while
///    authorizing the original is exactly the IDOR this closes.
///
///    Substring matching is deliberately not used — `foo..bar.png` and
///    `boneca%20roxa.png` are legitimate names and must keep working. Only an
///    exact `.`/`..`/separator is structural.
///
/// 2. **Add** the `/artifacts` prefix when a client used a bare stage path
///    (`/runtime/...`, `/canonical/...`, `/sandbox/...`), so classification and
///    path resolution agree on which tree is being addressed.
///
/// The returned path keeps its original percent-encoding — it is forwarded
/// upstream verbatim; only the check above looks at decoded segments.
fn normalize_ingress_path(raw_path: &str) -> Result<String, StatusCode> {
    for segment in raw_path.split('/').filter(|s| !s.is_empty()) {
        let decoded = percent_decode_path(segment);
        if decoded == "." || decoded == ".." || decoded.contains('/') {
            warn!(
                "[AuthProxy] Rejecting structural path segment {:?} (decodes to {:?})",
                segment, decoded
            );
            return Err(StatusCode::BAD_REQUEST);
        }
    }

    let Some(rest) = raw_path.strip_prefix('/') else {
        return Ok(raw_path.to_owned());
    };
    if rest.starts_with("runtime/") || rest.starts_with("canonical/") || rest.starts_with("sandbox/")
    {
        let normalized = format!("/artifacts/{}", rest);
        debug!("[AuthProxy] Path normalized: {} → {}", raw_path, normalized);
        return Ok(normalized);
    }
    Ok(raw_path.to_owned())
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

/// Extract the hostname portion from an Origin URL by stripping the scheme prefix.
///
/// Examples:
/// - `"https://scare.scareverse.net"` → `"scare.scareverse.net"`
/// - `"http://localhost:5173"` → `"localhost:5173"`
/// - `"https://qualquer-planeta.scareverse.net"` → `"qualquer-planeta.scareverse.net"`
fn extract_hostname(origin: &str) -> &str {
    origin
        .strip_prefix("https://")
        .or_else(|| origin.strip_prefix("http://"))
        .unwrap_or(origin)
}

/// Add CORS headers to a response (only inserts if absent -- does not overwrite).
///
/// This ensures that every response leaving auth-proxy carries CORS headers,
/// preventing "CORS error" opacity when upstream errors occur.
///
/// **Security**: Uses **dynamic same-origin validation** instead of a static
/// allowlist. The origin's hostname (extracted from the Origin URL) is compared
/// against the request's `Host` header. If they match, the origin is echoed with
/// credentials (same-origin). `localhost:5173` is always permitted (dev mode).
/// Unknown or missing origins fall back to `*` to prevent credential theft
/// via CORS reflection.
pub(crate) fn add_cors_headers(resp: &mut Response, origin: Option<&str>, host: Option<&str>) {
    // Dynamic same-origin validation: compare Origin hostname against Host header.
    // This works for any planet FQDN without requiring a hardcoded allowlist.
    let origin_val = match (origin, host) {
        // Same-origin: Origin hostname matches Host header → echo origin + credentials.
        // This handles all planets (scare.scareverse.net, qualquer-planeta.scareverse.net, etc.)
        // dynamically without a static allowlist.
        (Some(o), Some(h)) if extract_hostname(o) == h => o,
        // Localhost origins always allowed for development (belt-and-suspenders
        // with the same-origin check above — catches cases where Host header
        // might not be forwarded in some proxy setups).
        (Some(o), _) if o == "http://localhost:5173" || o == "https://localhost:5173" => o,
        // Hub allowlist: fixed infrastructure hubs that are cross-origin to the
        // planets they serve. These use `credentials: 'include'` and therefore
        // require an explicit origin echo (not `*`) in Access-Control-Allow-Origin.
        (Some(o), _)
            if o == "https://hub-staging.scareverse.net"
                || o == "https://hub.scareverse.net" =>
        {
            o
        }
        // Fallback: unknown or missing origin → wildcard, no credentials.
        _ => "*",
    };

    // Access-Control-Allow-Origin: echo the request origin or *
    if let Ok(val) = HeaderValue::from_str(origin_val) {
        resp.headers_mut()
            .entry(HeaderName::from_static("access-control-allow-origin"))
            .or_insert(val);
    } else {
        resp.headers_mut()
            .entry(HeaderName::from_static("access-control-allow-origin"))
            .or_insert(HeaderValue::from_static("*"));
    }

    // Access-Control-Allow-Methods
    resp.headers_mut()
        .entry(HeaderName::from_static("access-control-allow-methods"))
        .or_insert(HeaderValue::from_static("GET, POST, PUT, DELETE, PATCH, OPTIONS"));

    // Access-Control-Allow-Headers
    resp.headers_mut()
        .entry(HeaderName::from_static("access-control-allow-headers"))
        .or_insert(HeaderValue::from_static("Content-Type, Authorization, Cookie"));

    // Access-Control-Allow-Credentials: only when origin is explicit (not *)
    if origin_val != "*" {
        resp.headers_mut()
            .entry(HeaderName::from_static("access-control-allow-credentials"))
            .or_insert(HeaderValue::from_static("true"));
    }

    // Access-Control-Expose-Headers
    resp.headers_mut()
        .entry(HeaderName::from_static("access-control-expose-headers"))
        .or_insert(HeaderValue::from_static("Content-Type, Authorization"));
}

/// Build a JSON error response with the given status code.
///
/// CORS headers are added (with `*` as fallback origin) so that the browser
/// does not hide the error behind an opaque "CORS error".
fn build_error_response(status: StatusCode) -> Response {
    let body = serde_json::json!({ "error": status.canonical_reason().unwrap_or("Error") });
    let json = body.to_string();

    let mut resp = Response::new(Body::from(json));
    *resp.status_mut() = status;
    resp.headers_mut().insert(
        axum::http::header::CONTENT_TYPE,
        HeaderValue::from_static("application/json"),
    );
    warn!("[DIAG] build_error_response: status={}, NO CORS headers attached", status);
    add_cors_headers(&mut resp, None, None);
    resp
}

/// Build a CORS preflight response (OPTIONS) with appropriate Access-Control headers.
/// Uses the requesting origin to avoid incompatibility with credentials (can't use * with credentials).
/// Delegates common CORS headers to [`add_cors_headers`].
fn build_cors_response(status: StatusCode, origin: &str, host: Option<&str>) -> Response {
    let mut resp = Response::new(Body::empty());
    *resp.status_mut() = status;
    add_cors_headers(&mut resp, Some(origin), host);
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

// ─── Unit tests ───────────────────────────────────────────────────────────────
#[cfg(test)]
mod tests {
    use super::*;

    // ── Ingress path normalization ───────────────────────────────────────────
    // Session/JWT helpers live in `session.rs`; slug vectors in `runtime_server.rs`.

    #[test]
    fn test_normalize_ingress_rejects_dot_segments() {
        // Traversal: the gate would authorize `{me}` while the bytes came from
        // `{victim}` — both are the same string to a naive resolver.
        assert_eq!(
            normalize_ingress_path("/artifacts/runtime/user/me/../victim/contents/x/data.json"),
            Err(StatusCode::BAD_REQUEST)
        );
        assert_eq!(
            normalize_ingress_path("/artifacts/runtime/user/me/./contents/x/data.json"),
            Err(StatusCode::BAD_REQUEST)
        );
        assert_eq!(
            normalize_ingress_path("/artifacts/sandbox/../runtime/user/me/x.json"),
            Err(StatusCode::BAD_REQUEST)
        );
    }

    #[test]
    fn test_normalize_ingress_rejects_encoded_dot_segments() {
        // %2e is `.` — decoding happens before the check, so the encoded form is
        // rejected exactly like the literal one.
        assert_eq!(
            normalize_ingress_path("/artifacts/runtime/user/me/%2e%2e/victim/x.json"),
            Err(StatusCode::BAD_REQUEST)
        );
        assert_eq!(
            normalize_ingress_path("/artifacts/runtime/user/me/%2E%2E/victim/x.json"),
            Err(StatusCode::BAD_REQUEST)
        );
    }

    #[test]
    fn test_normalize_ingress_rejects_encoded_separator() {
        // %2F is `/`: one segment would become three once decoded, so the path
        // checked here and the path resolved later would differ.
        assert_eq!(
            normalize_ingress_path("/artifacts/runtime/user/me/contents%2f..%2f..%2fvictim/x.png"),
            Err(StatusCode::BAD_REQUEST)
        );
    }

    #[test]
    fn test_normalize_ingress_keeps_legit_double_dots() {
        // Only an exact `.`/`..` segment is structural — `foo..bar.png` is a name.
        assert_eq!(
            normalize_ingress_path("/artifacts/runtime/user/me/contents/foo..bar.png"),
            Ok("/artifacts/runtime/user/me/contents/foo..bar.png".to_owned())
        );
        assert_eq!(
            normalize_ingress_path("/artifacts/runtime/user/me/cell_types/a..b/type.json"),
            Ok("/artifacts/runtime/user/me/cell_types/a..b/type.json".to_owned())
        );
    }

    #[test]
    fn test_normalize_ingress_prefixes_bare_stage_paths() {
        assert_eq!(
            normalize_ingress_path("/runtime/user/me/cell_types/x/type.json"),
            Ok("/artifacts/runtime/user/me/cell_types/x/type.json".to_owned())
        );
        assert_eq!(
            normalize_ingress_path("/sandbox/cell_types/x/View.vue"),
            Ok("/artifacts/sandbox/cell_types/x/View.vue".to_owned())
        );
    }

    #[test]
    fn test_normalize_ingress_leaves_other_paths_alone() {
        assert_eq!(
            normalize_ingress_path("/api/v1/models"),
            Ok("/api/v1/models".to_owned())
        );
        assert_eq!(normalize_ingress_path("/"), Ok("/".to_owned()));
        // Already prefixed — not double-prefixed.
        assert_eq!(
            normalize_ingress_path("/artifacts/runtime/user/me/x.json"),
            Ok("/artifacts/runtime/user/me/x.json".to_owned())
        );
    }

    #[test]
    fn test_normalize_ingress_preserves_encoding_of_legit_names() {
        // A space in a filename must survive: the upstream gets the same string.
        assert_eq!(
            normalize_ingress_path("/artifacts/runtime/user/me/contents/boneca%20roxa.png"),
            Ok("/artifacts/runtime/user/me/contents/boneca%20roxa.png".to_owned())
        );
    }
}
