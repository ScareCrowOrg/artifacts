//! OCI v2 manifest handlers.
//!
//! GET  → 307 redirect to the public R2 URL
//! PUT  → upload to R2 (under both tag and digest keys) + notify CentralHub

use std::sync::Arc;

use axum::{
    body::{to_bytes, Body},
    extract::{Path, State},
    http::{Request, Response, StatusCode},
};
use sha2::{Digest as _, Sha256};
use tracing::{error, info, warn};

use crate::oci::auth::require_auth;
use crate::oci::types::make_error_response;
use crate::AppState;

// ── GET /v2/:registry/:planet/:name/manifests/:reference ─────────────────────

/// Redirect to the public R2 URL for the requested manifest.
/// The `reference` may be either a tag (`latest`) or a digest (`sha256:…`).
pub async fn handle_manifest_get(
    State(state): State<Arc<AppState>>,
    Path((registry, planet, name, reference)): Path<(String, String, String, String)>,
    req: Request<Body>,
) -> Response<Body> {
    if let Err(resp) = require_auth(req.headers(), &state.config) {
        return resp;
    }

    let r2_key = format!("manifests/{registry}/{planet}/{name}/{reference}");
    let url = state.r2.public_url_for(&r2_key);
    Response::builder()
        .status(StatusCode::TEMPORARY_REDIRECT)
        .header("Location", &url)
        .header("Docker-Distribution-API-Version", "registry/2.0")
        .body(Body::empty())
        .unwrap_or_else(|_| Response::new(Body::empty()))
}

// ── PUT /v2/:registry/:planet/:name/manifests/:reference ─────────────────────

/// Store a manifest in R2 and notify CentralHub.
///
/// The manifest is written to two R2 keys:
///   - `manifests/{registry}/{planet}/{name}/{reference}` (tag or digest ref)
///   - `manifests/{registry}/{planet}/{name}/sha256:{hex}` (content digest)
///
/// Returns 201 with `Docker-Content-Digest`.
pub async fn handle_manifest_put(
    State(state): State<Arc<AppState>>,
    Path((registry, planet, name, reference)): Path<(String, String, String, String)>,
    req: Request<Body>,
) -> Response<Body> {
    if let Err(resp) = require_auth(req.headers(), &state.config) {
        return resp;
    }

    // Capture Content-Type before consuming request
    let content_type = req
        .headers()
        .get("Content-Type")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("application/vnd.docker.distribution.manifest.v2+json")
        .to_owned();

    let body_bytes = match to_bytes(req.into_body(), 10 * 1024 * 1024).await {
        Ok(b) => b,
        Err(e) => {
            error!("Failed to read manifest body: {e}");
            return make_error_response(
                StatusCode::PAYLOAD_TOO_LARGE,
                "MANIFEST_INVALID",
                "Manifest body too large or unreadable",
            );
        }
    };

    // Compute SHA-256 content digest
    let hash = Sha256::digest(&body_bytes);
    let digest_hex = hex::encode(hash);
    let content_digest = format!("sha256:{digest_hex}");

    // Build R2 keys
    let ref_key = format!("manifests/{registry}/{planet}/{name}/{reference}");
    let digest_key = format!("manifests/{registry}/{planet}/{name}/sha256:{digest_hex}");

    // Store under reference key
    if let Err(e) = state
        .r2
        .put_object(&ref_key, body_bytes.clone(), &content_type)
        .await
    {
        error!("R2 put_object (ref) error for {ref_key}: {e}");
        return make_error_response(
            StatusCode::INTERNAL_SERVER_ERROR,
            "INTERNAL_ERROR",
            "Failed to store manifest",
        );
    }

    // Store under digest key (idempotent cross-reference)
    if let Err(e) = state
        .r2
        .put_object(&digest_key, body_bytes.clone(), &content_type)
        .await
    {
        // Log but don't fail – primary key succeeded
        warn!("R2 put_object (digest) error for {digest_key}: {e}");
    }

    // Parse manifest JSON — reject malformed manifests early
    let manifest_json: serde_json::Value = match serde_json::from_slice(&body_bytes) {
        Ok(v) => v,
        Err(e) => {
            warn!("Invalid manifest JSON for {registry}/{planet}/{name}:{reference}: {e}");
            return make_error_response(
                StatusCode::BAD_REQUEST,
                "MANIFEST_INVALID",
                "Manifest body is not valid JSON",
            );
        }
    };
    let layers = manifest_json
        .get("layers")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default();

    let payload = serde_json::json!({
        "registry": registry,
        "planet": planet,
        "image": name,
        "tag": reference,
        "digest": content_digest,
        "manifest_json": String::from_utf8_lossy(&body_bytes),
        "layers": layers,
    });

    if let Err(e) = state.hub.notify_manifest(&payload).await {
        warn!("CentralHub notification failed (non-fatal): {e}");
    }

    info!(
        "Manifest stored: {registry}/{planet}/{name}:{reference} digest={content_digest}"
    );

    Response::builder()
        .status(StatusCode::CREATED)
        .header("Docker-Content-Digest", &content_digest)
        .header(
            "Location",
            format!("/v2/{registry}/{planet}/{name}/manifests/{reference}"),
        )
        .header("Docker-Distribution-API-Version", "registry/2.0")
        .body(Body::empty())
        .unwrap_or_else(|_| Response::new(Body::empty()))
}


