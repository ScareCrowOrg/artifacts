//! Core proxy logic – universal ingress guard for API and Vite traffic.
//!
//! # Flow
//! 1. Classify request path:
//!    - `/api/v1/auth/session-bind` → bypass auth, proxy to Backend.
//!    - `/api/*` or `/viewers*` or `/` → require valid `sessionId`.
//!    - anything else → 403.
//! 2. For protected paths, call Backend session-check endpoint.
//! 3. **200 OK** → proxy to Backend or Vite depending on path.
//! 4. **403 Forbidden** → return 403 immediately.
//! 5. **Other** → return 500 Internal Server Error.
//!
//! # Host Header Handling
//! - Vite traffic rewrites `Host` to the Vite upstream host (`vite:5052`).
//! - Backend traffic preserves incoming `Host` when present so Backend can keep
//!   FQDN-sensitive logic (CORS/JWT validations), otherwise uses upstream host.
//! para rebuild

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

#[derive(Debug, Clone, Copy)]
enum RouteDecision {
    BackendBypass,
    BackendProtected,
    ViteProtected,
    Deny,
}

fn classify_route(path: &str) -> RouteDecision {
    if path == "/api/v1/auth/session-bind" {
        RouteDecision::BackendBypass
    } else if path.starts_with("/api/") {
        RouteDecision::BackendProtected
    } else {
        // Everything else → Vite (/, /viewers*, /canonical/*, /sandbox/*, /runtime/*, etc.)
        RouteDecision::ViteProtected
    }
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
        info!("[AuthProxy] CORS preflight OPTIONS for {}", path);
        return build_cors_response(StatusCode::OK);
    }

    if matches!(decision, RouteDecision::Deny) {
        warn!("[AuthProxy] Request denied by route policy: {}", path);
        return build_error_response(StatusCode::FORBIDDEN);
    }

    // Debug: Log all headers to diagnose Traefik passthrough
    debug!("[AuthProxy] Headers: {:?}", req.headers());

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
            RouteDecision::BackendBypass | RouteDecision::Deny => {
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

/// Call Backend's `/api/v1/auth/session-check` endpoint.
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

    match response.status().as_u16() {
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
    }
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
fn build_cors_response(status: StatusCode) -> Response {
    let mut resp = Response::new(Body::empty());
    *resp.status_mut() = status;

    // Allow all origins for CORS preflight
    resp.headers_mut().insert(
        HeaderName::from_static("access-control-allow-origin"),
        HeaderValue::from_static("*"),
    );

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

    // Allow credentials (cookies)
    resp.headers_mut().insert(
        HeaderName::from_static("access-control-allow-credentials"),
        HeaderValue::from_static("true"),
    );

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
            classify_route("/api/v1/auth/session-bind", false),
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
    fn test_classify_route_denies_unknown_path() {
        assert!(matches!(classify_route("/metrics"), RouteDecision::Deny));
    }
}
