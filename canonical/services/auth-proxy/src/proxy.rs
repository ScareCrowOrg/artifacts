//! Core proxy logic – validates SessionID via Backend then tunnels to Vite.
//!
//! # Flow
//! 1. Extract `sessionId` cookie from the incoming request.
//! 2. `POST /api/v1/auth/session-check?uri=<path>` → Backend (passes cookie).
//! 3. **200 OK** → proxy request to Vite, stream response transparently.
//! 4. **403 Forbidden** → return 403 immediately (no Vite forwarding).
//! 5. **Other** → return 500 Internal Server Error.
//!
//! # Host Header Rewriting (Critical)
//! The incoming `Host` header carries the public FQDN (e.g. `scare.scareverse.net`).
//! Vite expects the internal Docker DNS name (`vite:5052`).  We rewrite `Host`
//! before forwarding to avoid Vite rejecting the request.

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
/// Used by docker-compose `healthcheck` and by `NginxUnitRouter.waitForService`.
pub async fn health_handler() -> impl IntoResponse {
    (StatusCode::OK, "OK")
}

/// Main artifact proxy handler.
///
/// Intercepts every `GET /artifacts/*` request, validates the session via
/// Backend, and streams the Vite response on success.
pub async fn artifact_handler(
    State(state): State<AppState>,
    req: Request,
) -> Response {
    let path = req.uri().path().to_owned();
    let query = req
        .uri()
        .query()
        .map(|q| format!("?{q}"))
        .unwrap_or_default();
    let full_path = format!("{path}{query}");
    let method = req.method().to_string();

    info!("[AuthProxy] → {} {}", method, full_path);

    // Step 1 – extract Cookie header from the request.
    let cookie_header = req
        .headers()
        .get(header::COOKIE)
        .and_then(|v| v.to_str().ok())
        .map(str::to_owned);

    // Step 2 – validate session via Backend.
    let has_cookie = cookie_header.is_some();
    let auth_result = check_session(&state, &cookie_header, &path).await;

    match auth_result {
        Ok(()) => {
            // Session valid → proxy to Vite.
            debug!("[AuthProxy] Auth OK for {} (SessionID={}), proxying to Vite", path, has_cookie);
            proxy_to_vite(state, req, &full_path).await
        }
        Err(status) => {
            if status == StatusCode::FORBIDDEN {
                warn!("[AuthProxy] Auth DENIED for {} (403) | SessionID present: {}", path, has_cookie);
            } else {
                error!("[AuthProxy] Auth ERROR for {} ({}) | SessionID present: {}", path, status, has_cookie);
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
        debug!("[AuthProxy] Checking auth: {} (with SessionID)", auth_url);
    } else {
        debug!("[AuthProxy] Checking auth: {} (NO SessionID)", auth_url);
    }

    let response = req_builder.send().await.map_err(|e| {
        error!("[AuthProxy] Backend request failed: {} (URL: {})", e, auth_url);
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
async fn proxy_to_vite(state: AppState, orig_req: Request, full_path: &str) -> Response {
    // Build the target URL at Vite.
    let vite_url = format!("{}{}", state.vite_upstream, full_path);

    debug!("[AuthProxy] Forwarding to Vite: {}", vite_url);

    // Extract Vite host for the Host header rewrite (strip http:// prefix).
    let vite_host = state
        .vite_upstream
        .trim_start_matches("http://")
        .trim_start_matches("https://");

    let method = orig_req.method().clone();

    // Forward a safe subset of original headers.  Exclude headers that must
    // not be forwarded (connection management, encoding) and rewrite Host.
    let mut fwd_headers = reqwest::header::HeaderMap::new();
    for (name, value) in orig_req.headers() {
        let name_str = name.as_str();
        // Skip hop-by-hop headers and Host (we set it explicitly below).
        if matches!(
            name_str,
            "host"
                | "connection"
                | "transfer-encoding"
                | "te"
                | "trailer"
                | "upgrade"
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

    // Rewrite Host header – Vite expects the internal Docker DNS name.
    if let Ok(host_val) = reqwest::header::HeaderValue::from_str(vite_host) {
        fwd_headers.insert(reqwest::header::HOST, host_val);
    }

    // Stream the request body to Vite.
    let body_bytes = match axum::body::to_bytes(orig_req.into_body(), usize::MAX).await {
        Ok(b) => b,
        Err(e) => {
            error!("[AuthProxy] Failed to read request body: {}", e);
            return build_error_response(StatusCode::INTERNAL_SERVER_ERROR);
        }
    };

    let vite_req = state
        .http_client
        .request(
            reqwest::Method::from_bytes(method.as_str().as_bytes())
                .unwrap_or(reqwest::Method::GET),
            &vite_url,
        )
        .headers(fwd_headers)
        .body(body_bytes);

    let vite_resp = match vite_req.send().await {
        Ok(r) => r,
        Err(e) => {
            error!("[AuthProxy] Vite upstream error: {}", e);
            return build_error_response(StatusCode::BAD_GATEWAY);
        }
    };

    // Convert reqwest response status + headers to axum response.
    let status = StatusCode::from_u16(vite_resp.status().as_u16())
        .unwrap_or(StatusCode::INTERNAL_SERVER_ERROR);

    let mut resp_headers = HeaderMap::new();
    for (name, value) in vite_resp.headers() {
        // Skip hop-by-hop headers from Vite's response.
        if matches!(
            name.as_str(),
            "connection" | "transfer-encoding" | "keep-alive" | "trailer" | "upgrade"
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

    // Stream the Vite response body back to the client.
    let body_stream = vite_resp.bytes_stream();
    let stream_body = Body::from_stream(body_stream);

    let mut response = Response::new(stream_body);
    *response.status_mut() = status;
    *response.headers_mut() = resp_headers;

    info!("[AuthProxy] Proxied {} → Vite ({})", full_path, status);
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

/// Register and refresh the heartbeat key in Redis L1.
///
/// Uses a fixed TTL of `interval * 3` seconds and refreshes every `interval`
/// seconds, matching the BaseService pattern used by Backend and Vite.
pub async fn run_heartbeat(
    redis_url: String,
    interval_secs: u64,
) {
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

    redis::cmd("SET")
        .arg(HEARTBEAT_KEY)
        .arg("1")
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
                b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'_' | b'.' | b'~'
                | b'/' | b'=' | b'?' | b'&' => encoded.push(byte as char),
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
}
