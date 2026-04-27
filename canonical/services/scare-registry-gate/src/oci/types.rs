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
