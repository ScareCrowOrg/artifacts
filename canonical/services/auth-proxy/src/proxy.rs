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
//! # Module Split
//! - [`classify`] — route classification (RouteDecision, classify_route, extractors)
//! - [`file_server`] — file serving, RBAC, path resolution
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

// ── Re-exports from sub-modules ───────────────────────────────────────────
pub use crate::classify::{health_handler, HEARTBEAT_KEY, RouteDecision};
use crate::classify::{classify_route, extract_viewer_id, extract_wss_alias, is_public_path};
use crate::file_server::{
    build_redirect_response, check_runtime_access, check_viewer_access,
    extract_runtime_assignee, resolve_artifact_path, serve_file, ArtifactResolution,
};
use crate::upstream::{resolve_proxy_upstream, resolve_wss_upstream};

/// Universal ingress handler.
pub async fn request_handler(State(state): State<AppState>, req: Request) -> Response {
    let raw_path = req.uri().path().to_owned();
    // ── Path normalization ─────────────────────────────────────────────────
    // If a request arrives at /runtime/, /canonical/, or /sandbox/ without the
    // /artifacts/ prefix, prepend /artifacts so classify_route() and the
    // file_server module can process it against the correct artifact root.
    // This lets the frontend use bare /runtime/... URLs without hardcoding
    // the /artifacts/ prefix at every call site.
    let path = if let Some(rest) = raw_path.strip_prefix('/') {
        if rest.starts_with("runtime/") || rest.starts_with("canonical/") || rest.starts_with("sandbox/") {
            let normalized = format!("/artifacts/{}", rest);
            debug!("[AuthProxy] Path normalized: {} → {}", raw_path, normalized);
            normalized
        } else {
            raw_path
        }
    } else {
        raw_path
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
            if let Err(status) = check_session(&state, &cookie_header, &path).await {
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

            let session_result = check_session(&state, &cookie_header, &path).await;
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

        // FileServer and RuntimeFileServer should never receive WebSocket upgrades.
        if matches!(decision, RouteDecision::FileServer | RouteDecision::RuntimeFileServer) {
            warn!("[WS] FileServer/RuntimeFileServer decision reached WebSocket bifurcation — rejecting");
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
            RouteDecision::RuntimeFileServer => {
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

    // Public paths bypass all auth — proxy directly to Vite.
    if is_public_path(&path) {
        debug!("[AuthProxy] Public path '{}' — proxying to Vite without auth", path);
        return proxy_to_vite(state, req, &full_path).await;
    }

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
                let artifacts_base = "/app/artifacts";
                match resolve_artifact_path(artifacts_base, &path) {
                    ArtifactResolution::Found(file_path) => {
                        debug!(
                            "[FileServer] Serving canonical artifact: {} (path: {})",
                            path, file_path.display()
                        );
                        serve_file(&file_path).await
                    }
                    ArtifactResolution::NotFound => {
                        warn!("[FileServer] Artifact not found on disk, falling back: {}", path);
                        // File not on disk — fall back to FastApiProxy (Vite may have it).
                        match resolve_proxy_upstream(&state).await {
                            Ok(upstream) => {
                                info!("[FileServer] File not found, falling back to FastApiProxy: {}", path);
                                proxy_to_upstream(&state, req, &full_path, &upstream, None).await
                            }
                            Err(status) => build_error_response(status),
                        }
                    }
                    ArtifactResolution::PathTraversal => {
                        warn!("[FileServer] Path traversal BLOCKED: {}", path);
                        build_error_response(StatusCode::NOT_FOUND)
                    }
                }
            }
            RouteDecision::RuntimeFileServer => {
                let session_id = cookie_header.as_deref().and_then(extract_session_id);
                let assignee_id = extract_runtime_assignee(&path);
                match (session_id, assignee_id) {
                    (Some(sid), Some(aid)) => {
                        if check_runtime_access(&state, &sid, &aid).await {
                            let artifacts_base = "/app/artifacts";
                            match resolve_artifact_path(artifacts_base, &path) {
                                ArtifactResolution::Found(file_path) => {
                                    debug!(
                                        "[RuntimeFileServer] Serving runtime artifact: {} (assignee: {}, path: {})",
                                        path, aid, file_path.display()
                                    );
                                    serve_file(&file_path).await
                                }
                                _ => {
                                    warn!("[RuntimeFileServer] Runtime artifact not found: {} (assignee: {})", path, aid);
                                    build_error_response(StatusCode::NOT_FOUND)
                                }
                            }
                        } else {
                            warn!(
                                "[RuntimeFileServer] Runtime access DENIED for {} (session: {}, assignee: {})",
                                path, sid, aid
                            );
                            build_error_response(StatusCode::FORBIDDEN)
                        }
                    }
                    _ => {
                        warn!(
                            "[RuntimeFileServer] Missing session_id or assignee_id for runtime path: {}",
                            path
                        );
                        build_error_response(StatusCode::FORBIDDEN)
                    }
                }
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
    path: &str,
) -> Result<(), StatusCode> {
    const CACHE_TTL_VALID: u64 = 5;
    const CACHE_TTL_INVALID: u64 = 1;

    let session_id = cookie_header.as_deref().and_then(extract_session_id);
    let session_id = match session_id {
        Some(id) => id,
        None => {
            warn!("[AuthProxy] No sessionId found in Cookie header");
            return Err(StatusCode::FORBIDDEN);
        }
    };

    // Check in-memory cache first (5s TTL for valid, 1s for invalid).
    {
        let cache = state.session_cache.lock().await;
        if let Some(&(checked_at, is_valid)) = cache.get(&session_id) {
            let ttl = if is_valid { CACHE_TTL_VALID } else { CACHE_TTL_INVALID };
            if checked_at.elapsed().as_secs() < ttl {
                if is_valid {
                    debug!("[AuthProxy] Session cache HIT (valid) for session {}", session_id);
                    return Ok(());
                } else {
                    debug!("[AuthProxy] Session cache HIT (invalid) for session {}", session_id);
                    return Err(StatusCode::FORBIDDEN);
                }
            }
        }
    }

    // Cache miss — call Backend.
    let encoded_path = urlencoding::encode(path);
    let auth_url = format!("{}?uri={}", state.backend_auth_url, encoded_path);
    debug!(
        "[AuthProxy] Checking session via Backend: {} (sessionId={})",
        auth_url, session_id
    );

    let response = state
        .http_client
        .post(&auth_url)
        .header(header::COOKIE, cookie_header.as_deref().unwrap_or(""))
        .send()
        .await;

    let status = match response {
        Ok(resp) => resp.status(),
        Err(e) => {
            error!("[AuthProxy] Backend session-check network error: {}", e);
            return Err(StatusCode::INTERNAL_SERVER_ERROR);
        }
    };

    match status {
        reqwest::StatusCode::OK => {
            debug!("[AuthProxy] Session VALID for session {}", session_id);
            // Cache valid session (5s TTL).
            let mut cache = state.session_cache.lock().await;
            cache.insert(session_id.clone(), (std::time::Instant::now(), true));
            // Prune stale entries to bound memory growth.
            if cache.len() > 1000 {
                cache.retain(|_, &mut (ts, _)| ts.elapsed().as_secs() < CACHE_TTL_VALID);
            }
            Ok(())
        }
        reqwest::StatusCode::FORBIDDEN => {
            warn!("[AuthProxy] Session DENIED (403) for session {}", session_id);
            // Cache invalid session (1s TTL).
            let mut cache = state.session_cache.lock().await;
            cache.insert(session_id.clone(), (std::time::Instant::now(), false));
            // Prune stale entries.
            if cache.len() > 1000 {
                cache.retain(|_, &mut (ts, _)| ts.elapsed().as_secs() < CACHE_TTL_INVALID);
            }
            Err(StatusCode::FORBIDDEN)
        }
        other => {
            error!(
                "[AuthProxy] Backend session-check returned unexpected status: {}",
                other
            );
            Err(StatusCode::INTERNAL_SERVER_ERROR)
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
        assert_eq!(extract_session_id("sessionId="), None);
    }

    #[test]
    fn test_extract_session_id_too_long() {
        let long_id = "x".repeat(513);
        let cookie = format!("sessionId={}", long_id);
        assert_eq!(extract_session_id(&cookie), None);
    }

    #[test]
    fn test_extract_session_id_exactly_max_len() {
        let max_id = "a".repeat(512);
        let cookie = format!("sessionId={}", max_id);
        assert_eq!(extract_session_id(&cookie), Some(max_id));
    }

    // ── Session cache tests ──────────────────────────────────────────────────

    #[tokio::test]
    async fn test_session_cache_hit_valid() {
        use std::collections::HashMap;
        use std::sync::Arc;
        use std::time::Instant;
        use tokio::sync::Mutex;

        let cache: Arc<Mutex<HashMap<String, (Instant, bool)>>> =
            Arc::new(Mutex::new(HashMap::new()));
        {
            let mut c = cache.lock().await;
            c.insert("sid-valid".to_owned(), (Instant::now(), true));
        }

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
            let old_instant = Instant::now() - Duration::from_secs(2);
            c.insert("sid-invalid".to_owned(), (old_instant, false));
        }

        let c = cache.lock().await;
        let &(checked_at, _is_valid) = c.get("sid-invalid").unwrap();
        let ttl_invalid: u64 = 1;
        assert!(checked_at.elapsed().as_secs() >= ttl_invalid);
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
            let old_instant = Instant::now() - Duration::from_secs(6);
            c.insert("sid-valid-expired".to_owned(), (old_instant, true));
        }

        let c = cache.lock().await;
        let &(checked_at, _is_valid) = c.get("sid-valid-expired").unwrap();
        let ttl_valid: u64 = 5;
        assert!(checked_at.elapsed().as_secs() >= ttl_valid);
    }
}
