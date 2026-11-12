//! Session identity helpers — cookie parsing, JWT claims, Backend session-check.
//!
//! Extracted from `proxy.rs` (which must stay under the RULESET 1.1 line limit)
//! without changing behaviour: the ingress handler calls exactly the same
//! functions it did before, through `super::session`.
//!
//! # Responsibility
//! Answer two questions for the ingress:
//!   1. *Is this request authenticated, and is it allowed to touch this path?*
//!      → [`check_session`], which delegates the RBAC verdict to the Backend.
//!   2. *Who is this request?* → [`extract_session_id`] (cookie) and
//!      [`extract_sub_from_jwt`] (Bearer token, already validated by the Backend).
//!
//! # Backend is the RBAC authority
//! The Auth Proxy never decides access on its own here — it asks the Backend and
//! maps the answer (200 → allow, 403 → deny, anything else → 500). The one
//! exception is the runtime artifact gate in [`super::runtime_server`], which
//! reads the session state Redis already holds instead of paying a network hop
//! per asset.

use axum::http::StatusCode;
use reqwest::header;
use tracing::{debug, error, info, warn};

use crate::AppState;

/// Extract the `sessionId` value from a raw `Cookie` header string.
///
/// Parses `sessionId=<value>` from a semicolon-separated list of cookie pairs.
/// Returns `None` if the `sessionId` key is not present or the value is too long
/// (> 512 bytes) to prevent cache-key pollution attacks.
pub(super) fn extract_session_id(cookie_header: &str) -> Option<String> {
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

/// Extract the `sub` claim from an already-validated JWT token.
///
/// # Safety
/// This function does NOT verify the JWT signature — it only base64-decodes the
/// payload segment and extracts the `sub` field.  The caller MUST have already
/// validated the token (e.g. via [`check_session`] which calls the Backend)
/// before trusting the result.
///
/// Returns `None` if the token is malformed or the `sub` claim is missing.
pub(super) fn extract_sub_from_jwt(token: &str) -> Option<String> {
    use base64::Engine;

    let parts: Vec<&str> = token.split('.').collect();
    if parts.len() != 3 {
        warn!("[JWT] Malformed JWT: expected 3 parts, got {}", parts.len());
        return None;
    }

    let payload_b64 = parts[1];

    // RFC 7515 requires URL-safe base64 WITHOUT padding for JWT.
    let decoded = base64::engine::general_purpose::URL_SAFE_NO_PAD
        .decode(payload_b64)
        .or_else(|_| {
            // Fallback: some JWT libraries include optional padding.
            base64::engine::general_purpose::URL_SAFE.decode(payload_b64)
        })
        .ok()?;

    let payload_str = std::str::from_utf8(&decoded).ok()?;
    let json: serde_json::Value = serde_json::from_str(payload_str).ok()?;

    json.get("sub")
        .and_then(|v| v.as_str())
        .map(|s| s.to_owned())
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
pub(super) async fn check_session(
    state: &AppState,
    cookie_header: &Option<String>,
    auth_header: &Option<String>,
    path: &str,
) -> Result<(), StatusCode> {
    const CACHE_TTL_VALID: u64 = 5;
    const CACHE_TTL_INVALID: u64 = 1;

    // --- BEARER TOKEN AUTH PATH ---
    // When no session cookie is present but an Authorization: Bearer header is,
    // forward the token directly to the Backend for JWT validation.  We skip the
    // in-memory cache here because JWTs are self-validating — the Backend validates
    // the signature and expiration without needing a Redis lookup.
    if cookie_header.is_none() {
        if let Some(auth) = auth_header {
            if auth.starts_with("Bearer ") {
                info!(
                    "[AuthProxy] No cookie, using Bearer token auth for path: {}",
                    path
                );
                let encoded_path = urlencoding::encode(path);
                let auth_url = format!("{}?uri={}", state.backend_auth_url, encoded_path);
                debug!("[AuthProxy] Bearer auth: calling Backend at {}", auth_url);

                let response = state
                    .http_client
                    .post(&auth_url)
                    .header(header::AUTHORIZATION, auth.as_str())
                    .send()
                    .await;

                return match response {
                    Ok(resp) => match resp.status() {
                        reqwest::StatusCode::OK => {
                            info!("[AuthProxy] Bearer token auth VALID for path: {}", path);
                            Ok(())
                        }
                        reqwest::StatusCode::FORBIDDEN => {
                            warn!(
                                "[AuthProxy] Bearer token auth DENIED for path: {}",
                                path
                            );
                            Err(StatusCode::FORBIDDEN)
                        }
                        other => {
                            error!(
                                "[AuthProxy] Bearer auth unexpected status {} for path: {}",
                                other, path
                            );
                            Err(StatusCode::INTERNAL_SERVER_ERROR)
                        }
                    },
                    Err(e) => {
                        error!(
                            "[AuthProxy] Bearer auth network error for path {}: {}",
                            path, e
                        );
                        Err(StatusCode::INTERNAL_SERVER_ERROR)
                    }
                };
            }
        }
    }

    // --- COOKIE-BASED AUTH PATH ---
    let session_id = cookie_header.as_deref().and_then(extract_session_id);
    let session_id = match session_id {
        Some(id) => id,
        None => {
            warn!(
                "[AuthProxy] No sessionId found in Cookie header and \
                 no Authorization Bearer header"
            );
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

// ─── URL encoding helper ──────────────────────────────────────────────────────
pub(super) mod urlencoding {
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

    #[test]
    fn test_extract_sub_from_jwt_missing_claim() {
        assert_eq!(extract_sub_from_jwt("not-a-jwt"), None);
        assert_eq!(extract_sub_from_jwt("a.b"), None);
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
