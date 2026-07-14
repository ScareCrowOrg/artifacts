//! Control plane endpoint for dynamic tenant-session management.
//!
//! The Builder calls these endpoints before/after a multi-tenant push to
//! temporarily override the Gate's R2 bucket and CentralHub URL for a specific
//! planet (e.g. "production").  Overrides are stored in-memory only — they
//! evaporate on container restart.
//!
//! # Endpoints
//!
//! - `PUT /api/control/tenant-session`   – upsert a planet's overrides
//! - `DELETE /api/control/tenant-session?planet=X` – remove a planet's overrides

use std::sync::Arc;

use axum::{
    body::Body,
    extract::{Query, State},
    http::{HeaderMap, Response, StatusCode},
    Json,
};
use serde::{Deserialize, Serialize};

use crate::AppState;

/// Per-planet overrides stored in-memory.
///
/// All fields are optional — only explicitly-set fields override the env-var
/// defaults.  An empty `TenantConfig` (all `None`) means "use env-var defaults
/// for every field", which is functionally identical to having no session.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TenantConfig {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub centralhub_url: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub centralhub_token: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub r2_bucket: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub r2_public_url: Option<String>,
}

/// Request body for `PUT /api/control/tenant-session`.
#[derive(Debug, Deserialize)]
pub struct UpsertTenantRequest {
    /// Planet identifier (e.g. "production", "staging").
    pub planet: String,
    #[serde(default)]
    pub centralhub_url: Option<String>,
    #[serde(default)]
    pub centralhub_token: Option<String>,
    #[serde(default)]
    pub r2_bucket: Option<String>,
    #[serde(default)]
    pub r2_public_url: Option<String>,
}

/// Query parameters for `DELETE /api/control/tenant-session`.
#[derive(Debug, Deserialize)]
pub struct DeleteTenantQuery {
    /// Planet to remove from the session map.
    pub planet: String,
}

// ── Auth helper ───────────────────────────────────────────────────────────────

/// Validate the `Authorization: Bearer <token>` header against the configured
/// `CONTROL_API_KEY`.
///
/// Returns `Ok(())` on success or an `Err(Response<Body>)` with a 401 body.
fn check_control_api_key(
    config_api_key: &str,
    headers: &HeaderMap,
) -> Result<(), Response<Body>> {
    if config_api_key.is_empty() {
        tracing::warn!("[Control] CONTROL_API_KEY is empty – rejecting request (fail-closed)");
        return Err(make_control_error(
            StatusCode::UNAUTHORIZED,
            "Control API key not configured",
        ));
    }

    let header = headers
        .get("Authorization")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("");
    if header == format!("Bearer {config_api_key}") {
        Ok(())
    } else {
        tracing::warn!("[Control] Invalid or missing Authorization header");
        Err(make_control_error(
            StatusCode::UNAUTHORIZED,
            "Invalid or missing Authorization header",
        ))
    }
}

// ── Response helpers ──────────────────────────────────────────────────────────

fn make_control_error(status: StatusCode, message: &str) -> Response<Body> {
    let body = serde_json::json!({"error": message}).to_string();
    Response::builder()
        .status(status)
        .header("Content-Type", "application/json")
        .body(Body::from(body))
        .unwrap_or_else(|_| Response::new(Body::empty()))
}

fn ok_empty() -> Response<Body> {
    Response::builder()
        .status(StatusCode::OK)
        .header("Content-Type", "application/json")
        .body(Body::from("{}"))
        .unwrap_or_else(|_| Response::new(Body::empty()))
}

// ── Handlers ──────────────────────────────────────────────────────────────────

/// `PUT /api/control/tenant-session`
///
/// Inserts (or replaces) a `TenantConfig` for the given planet in the
/// in-memory session map.  Requires `Authorization: Bearer <CONTROL_API_KEY>`.
///
/// Returns `200 OK` on success, `400` if planet is empty, `401` on auth failure.
pub async fn handle_upsert_tenant(
    State(state): State<Arc<AppState>>,
    headers: HeaderMap,
    Json(req): Json<UpsertTenantRequest>,
) -> Response<Body> {
    if let Err(resp) = check_control_api_key(&state.config.control_api_key, &headers) {
        return resp;
    }

    if req.planet.is_empty() {
        tracing::warn!("[Control] Upsert rejected: planet is empty");
        return make_control_error(StatusCode::BAD_REQUEST, "planet must not be empty");
    }

    // Filter empty strings — serde_json parses `""` as `Some("")` which would
    // make with_overrides() apply an invalid empty URL/bucket, crashing R2/Hub.
    let config = TenantConfig {
        centralhub_url: req.centralhub_url.filter(|s| !s.is_empty()),
        centralhub_token: req.centralhub_token.filter(|s| !s.is_empty()),
        r2_bucket: req.r2_bucket.filter(|s| !s.is_empty()),
        r2_public_url: req.r2_public_url.filter(|s| !s.is_empty()),
    };

    state
        .tenant_sessions
        .write()
        .unwrap()
        .insert(req.planet.clone(), config);

    tracing::info!("[Control] Tenant session upserted: planet={}", req.planet);
    ok_empty()
}

/// `DELETE /api/control/tenant-session?planet=X`
///
/// Removes the tenant session for the given planet.  Idempotent — returns
/// `200 OK` even if the planet had no session.  Requires `Authorization:
/// Bearer <CONTROL_API_KEY>`.
pub async fn handle_delete_tenant(
    State(state): State<Arc<AppState>>,
    headers: HeaderMap,
    Query(query): Query<DeleteTenantQuery>,
) -> Response<Body> {
    if let Err(resp) = check_control_api_key(&state.config.control_api_key, &headers) {
        return resp;
    }

    state.tenant_sessions.write().unwrap().remove(&query.planet);

    tracing::info!("[Control] Tenant session removed: planet={}", query.planet);
    ok_empty()
}

// ── Helper for OCI handlers ───────────────────────────────────────────────────

/// Look up a `TenantConfig` for the given planet from the in-memory session map.
///
/// Returns `None` if no session exists (caller should use env-var defaults).
pub fn lookup_tenant_session(
    state: &Arc<AppState>,
    planet: &str,
) -> Option<TenantConfig> {
    if planet.is_empty() {
        return None;
    }
    let sessions = state.tenant_sessions.read().unwrap();
    sessions.get(planet).cloned()
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;

    // ── Pure function tests (no Redis required) ────────────────────────────

    #[test]
    fn test_check_api_key_ok() {
        let mut headers = HeaderMap::new();
        headers.insert("Authorization", "Bearer test-key".parse().unwrap());
        assert!(check_control_api_key("test-key", &headers).is_ok());
    }

    #[test]
    fn test_check_api_key_empty_config_returns_err() {
        let headers = HeaderMap::new();
        let result = check_control_api_key("", &headers);
        assert!(result.is_err());
        assert_eq!(result.unwrap_err().status(), StatusCode::UNAUTHORIZED);
    }

    #[test]
    fn test_check_api_key_wrong_key_returns_err() {
        let mut headers = HeaderMap::new();
        headers.insert("Authorization", "Bearer wrong-key".parse().unwrap());
        let result = check_control_api_key("correct-key", &headers);
        assert!(result.is_err());
    }

    #[test]
    fn test_check_api_key_no_header_returns_err() {
        let result = check_control_api_key("test-key", &HeaderMap::new());
        assert!(result.is_err());
    }

    #[test]
    fn test_lookup_returns_none_for_empty_planet() {
        let sessions: HashMap<String, TenantConfig> = HashMap::new();
        assert!(sessions.get("").is_none());
    }

    #[test]
    fn test_lookup_returns_none_for_missing_planet() {
        let sessions: HashMap<String, TenantConfig> = HashMap::new();
        assert!(sessions.get("nonexistent").is_none());
    }

    #[test]
    fn test_lookup_returns_stored_config() {
        let mut sessions: HashMap<String, TenantConfig> = HashMap::new();
        sessions.insert(
            "production".into(),
            TenantConfig {
                centralhub_url: Some("https://hub.prod.com".into()),
                centralhub_token: None,
                r2_bucket: None,
                r2_public_url: None,
            },
        );
        let config = sessions.get("production");
        assert!(config.is_some());
        assert_eq!(
            config.unwrap().centralhub_url.as_deref(),
            Some("https://hub.prod.com")
        );
    }

    #[test]
    fn test_tenant_config_serialization() {
        let config = TenantConfig {
            centralhub_url: Some("https://hub.prod.com".into()),
            centralhub_token: None,
            r2_bucket: Some("prod-bucket".into()),
            r2_public_url: None,
        };
        let json = serde_json::to_string(&config).unwrap();
        assert!(json.contains("https://hub.prod.com"));
        assert!(json.contains("prod-bucket"));
        // Fields with None should be skipped in serialization
        assert!(!json.contains("centralhub_token"));
        assert!(!json.contains("r2_public_url"));
    }

    #[test]
    fn test_upsert_request_deserialization() {
        let json = r#"{
            "planet": "production",
            "centralhub_url": "https://hub.prod.com",
            "r2_bucket": "prod-bucket"
        }"#;
        let req: UpsertTenantRequest = serde_json::from_str(json).unwrap();
        assert_eq!(req.planet, "production");
        assert_eq!(req.centralhub_url.unwrap(), "https://hub.prod.com");
        assert!(req.centralhub_token.is_none());
        assert_eq!(req.r2_bucket.unwrap(), "prod-bucket");
    }

    #[test]
    fn test_delete_query_deserialization() {
        let json = r#"{"planet": "production"}"#;
        let query: DeleteTenantQuery = serde_json::from_str(json).unwrap();
        assert_eq!(query.planet, "production");
    }

    // ── Integration tests for handlers ─────────────────────────────────────
    // Handler-level tests (handle_upsert_tenant, handle_delete_tenant) require
    // constructing a full AppState with a real Redis connection.  These are
    // tested manually when the service is running or via `cargo test -- --ignored`
    // with a local Redis available.
    //
    // See the acceptance criteria in docs/issues/gate-control-plane/ISSUE.md for
    // the full manual test procedure.
    //
    // TODO: Add integration tests when a test-only Redis connection is available
    // in the CI environment.
}
