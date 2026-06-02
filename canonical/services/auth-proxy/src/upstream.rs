//! Upstream resolution — discovers backend/Vite services via Redis SCAN at request time.
//!
//! Both `resolve_wss_upstream()` and `resolve_proxy_upstream()` follow the same
//! pattern: SCAN Redis for `state:service:*:routing` keys → JSON parse → match
//! on the relevant field → extract service name + port → return upstream URL.
//!
//! This avoids hardcoding any upstream addresses in the Auth Proxy binary.

use axum::http::StatusCode;
use tracing::{debug, info, warn};

use crate::AppState;

/// Resolve a WSS upstream by alias via Redis SCAN.
///
/// Looks for a `state:service:*:routing` key whose JSON contains a `wss` block
/// where `enabled: true` and `alias` matches the requested alias.
///
/// Returns `Ok(upstream_url)` on success (e.g. `http://node-pty-service:8000`).
/// Returns `Err(404)` if no service advertises the requested alias.
/// Returns `Err(503)` if Redis is temporarily unavailable.
pub async fn resolve_wss_upstream(
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
                    let upstream_path = wss.get("upstream_path")
                        .and_then(|v| v.as_str())
                        .unwrap_or("");

                    if !upstream_path.is_empty() {
                        info!(
                            "[WSSProxy] Using upstream path '{}' for alias '{}' (original request path was '/wss/{}')",
                            upstream_path, alias, alias
                        );
                    }

                    return Ok(format!("http://{}:{}{}", service_name, upstream_port, upstream_path));
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

/// Resolves the FastAPI proxy upstream via Redis SCAN.
///
/// Follows the identical pattern of `resolve_wss_upstream()`. SCANs Redis
/// for `state:service:*:routing` keys, looks for `proxy.enabled: true`,
/// and returns the upstream URL (e.g. `"http://backend:5050"`).
///
/// Returns:
/// - `Ok(upstream_url)` on success.
/// - `Err(503)` if Redis is unavailable.
/// - `Err(404)` if no proxy upstream is registered.
pub async fn resolve_proxy_upstream(
    state: &AppState,
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
                warn!("[FastApiProxy] Redis SCAN error: {}", e);
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
                    warn!("[FastApiProxy] Redis GET error for key '{}': {}", key, e);
                    axum::http::StatusCode::SERVICE_UNAVAILABLE
                })?;

            if let Some(raw) = value {
                if let Ok(data) = serde_json::from_str::<serde_json::Value>(&raw) {
                    let proxy = match data.get("proxy") {
                        Some(v) => v,
                        None => continue,
                    };
                    let enabled = proxy.get("enabled").and_then(|v| v.as_bool()).unwrap_or(false);
                    if !enabled {
                        continue;
                    }

                    // Match found — extract service_name from key and build URL.
                    let parts: Vec<&str> = key.split(':').collect();
                    if parts.len() < 4 {
                        warn!("[FastApiProxy] Unexpected key format '{}'", key);
                        continue;
                    }
                    let service_name = parts[2];
                    let upstream_port = proxy.get("upstream_port").and_then(|v| v.as_u64()).ok_or_else(|| {
                        warn!("[FastApiProxy] Missing upstream_port");
                        axum::http::StatusCode::INTERNAL_SERVER_ERROR
                    })?;

                    info!(
                        "[FastApiProxy] Resolved proxy upstream → service '{}' port {}",
                        service_name, upstream_port
                    );

                    return Ok(format!("http://{}:{}", service_name, upstream_port));
                }
            }
        }

        if cursor == 0 {
            break;
        }
    }

    warn!("[FastApiProxy] No proxy upstream found in Redis");
    Err(axum::http::StatusCode::NOT_FOUND)
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
        warn!("[WSSProxy] Invalid JSON in routing value: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    let wss = data.get("wss").ok_or_else(|| {
        warn!("[WSSProxy] No 'wss' key in routing JSON");
        StatusCode::NOT_FOUND
    })?;

    let enabled = wss.get("enabled").and_then(|v| v.as_bool()).unwrap_or(false);
    if !enabled {
        warn!("[WSSProxy] WSS routing is disabled for alias '{}'", alias);
        return Err(StatusCode::NOT_FOUND);
    }

    let upstream_port = wss.get("upstream_port").and_then(|v| v.as_u64()).ok_or_else(|| {
        warn!("[WSSProxy] Missing upstream_port in routing JSON for alias '{}'", alias);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    info!("[WSSProxy] Parsed routing: alias='{}' upstream_port={}", alias, upstream_port);
    Ok(format!("http://{}:{}", alias, upstream_port))
}

// ─── Unit tests ───────────────────────────────────────────────────────────
#[cfg(test)]
mod tests {
    use super::*;

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
}
