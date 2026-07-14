//! Shared OCI types: error bodies, upload sessions, and response helpers.

use axum::body::Body;
use axum::http::{Response, StatusCode};
use serde::{Deserialize, Serialize};
use std::time::{SystemTime, UNIX_EPOCH};

/// Single OCI error detail entry.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[allow(dead_code)]
pub struct OciErrorDetail {
    pub code: String,
    pub message: String,
}

/// OCI v2 error response body.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[allow(dead_code)]
pub struct OciErrorBody {
    pub errors: Vec<OciErrorDetail>,
}

/// Tracks an in-progress blob upload session.
/// Stored in Redis as JSON under `gate:upload:{uuid}`.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UploadSession {
    /// Upload UUID (equals the Redis key suffix).
    pub upload_id: String,
    /// Total bytes received so far (used for Range header).
    pub offset: u64,
    /// S3 part numbers recorded (unused in Option-B buffer mode).
    pub part_numbers: Vec<i32>,
    /// S3 ETags recorded (unused in Option-B buffer mode).
    pub etags: Vec<String>,
    /// Unix timestamp when the session was created.
    pub started_at: u64,
}

impl UploadSession {
    /// Create a new, empty upload session.
    pub fn new(upload_id: String) -> Self {
        let started_at = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();
        Self {
            upload_id,
            offset: 0,
            part_numbers: Vec::new(),
            etags: Vec::new(),
            started_at,
        }
    }

    /// Serialize to a Redis-compatible JSON string.
    pub fn to_redis_value(&self) -> Result<String, serde_json::Error> {
        serde_json::to_string(self)
    }

    /// Deserialize from a Redis JSON string.
    #[allow(dead_code)]
    pub fn from_redis_value(s: &str) -> Result<Self, serde_json::Error> {
        serde_json::from_str(s)
    }
}

/// Split a repository path into (registry, planet, image) for the CentralHub payload
/// and tenant-session lookup.
///
/// For 3-segment paths (`registry/planet/name`) the split is natural.
/// For 2-segment paths (`ns/name`) the first segment serves double duty — it is
/// used as both registry AND planet — so that tenant-session lookups still work
/// when the Builder pushes with a 2-segment tag (e.g. `staging/scareverse-backend`).
/// For 1-segment paths all three fields are empty.
pub(crate) fn split_repo_for_hub(repo: &str) -> (String, String, String) {
    let parts: Vec<&str> = repo.splitn(3, '/').collect();
    match parts.as_slice() {
        [registry, planet, image] => {
            (registry.to_string(), planet.to_string(), image.to_string())
        }
        [ns, name] => (ns.to_string(), ns.to_string(), name.to_string()),
        [single] => (String::new(), String::new(), single.to_string()),
        _ => (String::new(), String::new(), repo.to_string()),
    }
}

#[cfg(test)]
mod tests {
    use super::split_repo_for_hub;

    #[test]
    fn test_split_3seg() {
        let (r, p, i) = split_repo_for_hub("scareverse/earth/backend");
        assert_eq!(r, "scareverse");
        assert_eq!(p, "earth");
        assert_eq!(i, "backend");
    }

    #[test]
    fn test_split_3seg_with_slashes_in_name() {
        let (r, p, i) = split_repo_for_hub("scareverse/earth/backend/extra");
        assert_eq!(r, "scareverse");
        assert_eq!(p, "earth");
        assert_eq!(i, "backend/extra");
    }

    #[test]
    fn test_split_2seg() {
        // 2-segment paths use the first segment as both registry AND planet
        // so that tenant-session lookups work for Builder-style tags.
        let (r, p, i) = split_repo_for_hub("staging/scareverse-backend");
        assert_eq!(r, "staging");
        assert_eq!(p, "staging");
        assert_eq!(i, "scareverse-backend");
    }

    #[test]
    fn test_split_1seg() {
        let (r, p, i) = split_repo_for_hub("backend");
        assert_eq!(r, "");
        assert_eq!(p, "");
        assert_eq!(i, "backend");
    }

    #[test]
    fn test_split_empty() {
        let (r, p, i) = split_repo_for_hub("");
        assert_eq!(r, "");
        assert_eq!(p, "");
        assert_eq!(i, "");
    }
}

/// Build a minimal OCI error JSON value.
pub fn oci_error_json(code: &str, message: &str) -> serde_json::Value {
    serde_json::json!({
        "errors": [{"code": code, "message": message}]
    })
}

/// Build a JSON error `Response<Body>` with the OCI `Docker-Distribution-API-Version` header.
pub fn make_error_response(status: StatusCode, code: &str, message: &str) -> Response<Body> {
    let body = oci_error_json(code, message).to_string();
    Response::builder()
        .status(status)
        .header("Content-Type", "application/json")
        .header("Docker-Distribution-API-Version", "registry/2.0")
        .body(Body::from(body))
        .unwrap_or_else(|_| Response::new(Body::empty()))
}
