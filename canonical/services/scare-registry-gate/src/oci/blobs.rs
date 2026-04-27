//! OCI v2 blob upload handlers.
//!
//! Uses Option-B (in-memory buffer) for simplicity:
//!   POST  → generate UUID, store empty session in Redis
//!   PATCH → accumulate body in `AppState.session_buffers`
//!   PUT   → verify SHA-256, `PutObject` to R2, clean up

use std::collections::HashMap;
use std::sync::Arc;

use axum::{
    body::{to_bytes, Body},
    extract::{Path, Query, State},
    http::{Request, Response, StatusCode},
};
use bytes::Bytes;
use redis::AsyncCommands;
use sha2::{Digest as _, Sha256};
use tracing::{error, info, warn};

use crate::oci::auth::require_auth;
use crate::oci::types::{make_error_response, UploadSession};
use crate::AppState;

// ── POST /v2/:registry/:planet/:name/blobs/uploads/ ──────────────────────────

/// Initialise a new blob upload session.
/// Returns 202 with `Location` and `Docker-Upload-UUID` headers.
pub async fn handle_blob_upload_init(
    State(state): State<Arc<AppState>>,
    Path((registry, planet, name)): Path<(String, String, String)>,
    req: Request<Body>,
) -> Response<Body> {
    if let Err(resp) = require_auth(req.headers(), &state.config) {
        return resp;
    }

    let uuid = uuid::Uuid::new_v4().to_string();
    let session = UploadSession::new(uuid.clone());

    let session_json = match session.to_redis_value() {
        Ok(s) => s,
        Err(e) => {
            error!("Session serialize error: {e}");
            return make_error_response(
                StatusCode::INTERNAL_SERVER_ERROR,
                "INTERNAL_ERROR",
                "Failed to create upload session",
            );
        }
    };

    let redis_key = format!("gate:upload:{uuid}");
    let mut conn = state.redis.clone();
    if let Err(e) = conn
        .set_ex::<_, _, ()>(&redis_key, &session_json, 3600_u64)
        .await
    {
        error!("Redis SET error: {e}");
        return make_error_response(
            StatusCode::INTERNAL_SERVER_ERROR,
            "INTERNAL_ERROR",
            "Failed to store upload session",
        );
    }

    let location = format!("/v2/{registry}/{planet}/{name}/blobs/uploads/{uuid}");
    Response::builder()
        .status(StatusCode::ACCEPTED)
        .header("Location", &location)
        .header("Docker-Upload-UUID", &uuid)
        .header("Docker-Distribution-API-Version", "registry/2.0")
        .header("Range", "0-0")
        .body(Body::empty())
        .unwrap_or_else(|_| Response::new(Body::empty()))
}

// ── PATCH /v2/:registry/:planet/:name/blobs/uploads/:uuid ────────────────────

/// Receive a chunk of blob data. Appends to the in-memory session buffer.
/// Returns 202 with `Range: 0-{offset}`.
pub async fn handle_blob_patch(
    State(state): State<Arc<AppState>>,
    Path((_registry, _planet, _name, uuid)): Path<(String, String, String, String)>,
    req: Request<Body>,
) -> Response<Body> {
    if let Err(resp) = require_auth(req.headers(), &state.config) {
        return resp;
    }

    // Validate session exists
    let redis_key = format!("gate:upload:{uuid}");
    let mut conn = state.redis.clone();
    let exists: Result<Option<String>, _> = conn.get(&redis_key).await;
    match exists {
        Ok(None) => {
            return make_error_response(
                StatusCode::NOT_FOUND,
                "BLOB_UPLOAD_UNKNOWN",
                "Upload session not found",
            );
        }
        Err(e) => {
            error!("Redis GET error: {e}");
            return make_error_response(
                StatusCode::INTERNAL_SERVER_ERROR,
                "INTERNAL_ERROR",
                "Redis error",
            );
        }
        Ok(Some(_)) => {}
    }

    let body_bytes = match to_bytes(req.into_body(), state.config.max_blob_size).await {
        Ok(b) => b,
        Err(e) => {
            error!("Body read error: {e}");
            return make_error_response(
                StatusCode::INTERNAL_SERVER_ERROR,
                "BLOB_UPLOAD_INVALID",
                "Failed to read request body",
            );
        }
    };

    // Append to in-memory buffer
    let new_size = {
        let mut entry = state
            .session_buffers
            .entry(uuid.clone())
            .or_insert_with(Vec::new);
        entry.extend_from_slice(&body_bytes);
        entry.len()
    };

    let range_end = if new_size > 0 { new_size - 1 } else { 0 };
    Response::builder()
        .status(StatusCode::ACCEPTED)
        .header("Range", format!("0-{range_end}"))
        .header("Docker-Upload-UUID", &uuid)
        .header("Docker-Distribution-API-Version", "registry/2.0")
        .body(Body::empty())
        .unwrap_or_else(|_| Response::new(Body::empty()))
}

// ── PUT /v2/:registry/:planet/:name/blobs/uploads/:uuid?digest=sha256:… ──────

/// Finalise a blob upload: verify digest, upload to R2, clean up.
/// Returns 201 with `Docker-Content-Digest`.
pub async fn handle_blob_put(
    State(state): State<Arc<AppState>>,
    Path((registry, planet, name, uuid)): Path<(String, String, String, String)>,
    Query(params): Query<HashMap<String, String>>,
    req: Request<Body>,
) -> Response<Body> {
    if let Err(resp) = require_auth(req.headers(), &state.config) {
        return resp;
    }

    let provided_digest = match params.get("digest") {
        Some(d) => d.clone(),
        None => {
            return make_error_response(
                StatusCode::BAD_REQUEST,
                "DIGEST_INVALID",
                "Missing digest query parameter",
            );
        }
    };

    // Read any final body bytes (may be empty for chunked uploads)
    let final_bytes = match to_bytes(req.into_body(), state.config.max_blob_size).await {
        Ok(b) => b,
        Err(e) => {
            error!("Body read error: {e}");
            return make_error_response(
                StatusCode::INTERNAL_SERVER_ERROR,
                "BLOB_UPLOAD_INVALID",
                "Failed to read final body",
            );
        }
    };

    // Merge buffered + final bytes
    let mut buffer = state
        .session_buffers
        .remove(&uuid)
        .map(|(_, v)| v)
        .unwrap_or_default();
    if !final_bytes.is_empty() {
        buffer.extend_from_slice(&final_bytes);
    }

    // Verify SHA-256 digest
    let hash = Sha256::digest(&buffer);
    let computed_hex = hex::encode(hash);
    let expected = format!("sha256:{computed_hex}");
    if provided_digest != expected {
        warn!("Digest mismatch for {uuid}: got {provided_digest}, expected {expected}");
        return make_error_response(
            StatusCode::BAD_REQUEST,
            "DIGEST_INVALID",
            "Provided digest does not match blob content",
        );
    }

    let size = buffer.len();
    let r2_key = format!("blobs/{registry}/{planet}/{name}/{provided_digest}");
    if let Err(e) = state
        .r2
        .put_object(&r2_key, Bytes::from(buffer), "application/octet-stream")
        .await
    {
        error!("R2 put_object error for {r2_key}: {e}");
        return make_error_response(
            StatusCode::INTERNAL_SERVER_ERROR,
            "INTERNAL_ERROR",
            "Failed to upload blob to R2",
        );
    }

    // Clean up Redis session (best-effort)
    let redis_key = format!("gate:upload:{uuid}");
    let mut conn = state.redis.clone();
    conn.del::<_, ()>(&redis_key).await.ok();

    info!("Blob stored: key={r2_key} size={size}");
    Response::builder()
        .status(StatusCode::CREATED)
        .header("Docker-Content-Digest", &provided_digest)
        .header(
            "Location",
            format!("/v2/{registry}/{planet}/{name}/blobs/{provided_digest}"),
        )
        .header("Docker-Distribution-API-Version", "registry/2.0")
        .body(Body::empty())
        .unwrap_or_else(|_| Response::new(Body::empty()))
}

// ── HEAD /v2/:registry/:planet/:name/blobs/:digest ───────────────────────────

/// Check whether a blob exists in R2.
/// Returns 200 with `Content-Length`, or 404.
pub async fn handle_blob_head(
    State(state): State<Arc<AppState>>,
    Path((registry, planet, name, digest)): Path<(String, String, String, String)>,
    req: Request<Body>,
) -> Response<Body> {
    if let Err(resp) = require_auth(req.headers(), &state.config) {
        return resp;
    }

    let r2_key = format!("blobs/{registry}/{planet}/{name}/{digest}");
    match state.r2.head_object(&r2_key).await {
        Ok(Some(size)) => Response::builder()
            .status(StatusCode::OK)
            .header("Content-Length", size.to_string())
            .header("Docker-Content-Digest", &digest)
            .header("Docker-Distribution-API-Version", "registry/2.0")
            .body(Body::empty())
            .unwrap_or_else(|_| Response::new(Body::empty())),
        Ok(None) => make_error_response(StatusCode::NOT_FOUND, "BLOB_UNKNOWN", "Blob not found"),
        Err(e) => {
            error!("R2 head_object error for {r2_key}: {e}");
            make_error_response(
                StatusCode::INTERNAL_SERVER_ERROR,
                "INTERNAL_ERROR",
                "Storage error",
            )
        }
    }
}

// ── GET /v2/:registry/:planet/:name/blobs/:digest ────────────────────────────

/// Redirect to the public R2 URL for the requested blob.
pub async fn handle_blob_get(
    State(state): State<Arc<AppState>>,
    Path((registry, planet, name, digest)): Path<(String, String, String, String)>,
    req: Request<Body>,
) -> Response<Body> {
    if let Err(resp) = require_auth(req.headers(), &state.config) {
        return resp;
    }

    let r2_key = format!("blobs/{registry}/{planet}/{name}/{digest}");
    let url = state.r2.public_url_for(&r2_key);
    Response::builder()
        .status(StatusCode::TEMPORARY_REDIRECT)
        .header("Location", &url)
        .header("Docker-Content-Digest", &digest)
        .header("Docker-Distribution-API-Version", "registry/2.0")
        .body(Body::empty())
        .unwrap_or_else(|_| Response::new(Body::empty()))
}
