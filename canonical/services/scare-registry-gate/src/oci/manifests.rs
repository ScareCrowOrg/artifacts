//! OCI v2 manifest handlers.
//!
//! GET  → 307 redirect to the public R2 URL
//! PUT  → upload to R2 (under both tag and digest keys) + notify CentralHub
//!
//! Both 3-segment (`registry/planet/name`) and 2-segment (`ns/name`) namespace
//! paths are supported.

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

// ── Inner: manifest get ───────────────────────────────────────────────────────

/// Core logic for `GET .../manifests/:reference`.
async fn manifest_get_inner(
    state: Arc<AppState>,
    repo: String,
    reference: String,
    req: Request<Body>,
) -> Response<Body> {
    info!(
        "[manifest-get] GET /v2/{}/manifests/{} | has_auth: {}",
        repo,
        reference,
        req.headers().get("Authorization").is_some()
    );

    if let Err(resp) = require_auth(req.headers(), &state.config) {
        warn!("[manifest-get] Auth failed: repo={} ref={}", repo, reference);
        return resp;
    }

    let r2_key = format!("manifests/{repo}/{reference}");
    let url = state.r2.public_url_for(&r2_key);
    info!(
        "[manifest-get] Redirecting: key={} → {}",
        r2_key, url
    );
    Response::builder()
        .status(StatusCode::TEMPORARY_REDIRECT)
        .header("Location", &url)
        .header("Docker-Distribution-API-Version", "registry/2.0")
        .body(Body::empty())
        .unwrap_or_else(|_| Response::new(Body::empty()))
}

// ── Inner: manifest put ───────────────────────────────────────────────────────

/// Core logic for `PUT .../manifests/:reference`.
async fn manifest_put_inner(
    state: Arc<AppState>,
    repo: String,
    reference: String,
    req: Request<Body>,
) -> Response<Body> {
    let content_type = req
        .headers()
        .get("Content-Type")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("application/vnd.docker.distribution.manifest.v2+json")
        .to_owned();

    info!(
        "[manifest-put] PUT /v2/{}/manifests/{} | has_auth: {} | content_type={}",
        repo,
        reference,
        req.headers().get("Authorization").is_some(),
        content_type
    );

    if let Err(resp) = require_auth(req.headers(), &state.config) {
        warn!("[manifest-put] Auth failed: repo={} ref={}", repo, reference);
        return resp;
    }

    let body_bytes = match to_bytes(req.into_body(), 10 * 1024 * 1024).await {
        Ok(b) => b,
        Err(e) => {
            error!("[manifest-put] Failed to read manifest body: {e}");
            return make_error_response(
                StatusCode::PAYLOAD_TOO_LARGE,
                "MANIFEST_INVALID",
                "Manifest body too large or unreadable",
            );
        }
    };

    let hash = Sha256::digest(&body_bytes);
    let digest_hex = hex::encode(hash);
    let content_digest = format!("sha256:{digest_hex}");

    let ref_key = format!("manifests/{repo}/{reference}");
    let digest_key = format!("manifests/{repo}/sha256:{digest_hex}");

    if let Err(e) = state
        .r2
        .put_object(&ref_key, body_bytes.clone(), &content_type)
        .await
    {
        error!("[manifest-put] R2 put_object (ref) error for {ref_key}: {e}");
        return make_error_response(
            StatusCode::INTERNAL_SERVER_ERROR,
            "INTERNAL_ERROR",
            "Failed to store manifest",
        );
    }

    if let Err(e) = state
        .r2
        .put_object(&digest_key, body_bytes.clone(), &content_type)
        .await
    {
        warn!("[manifest-put] R2 put_object (digest) error for {digest_key}: {e}");
    }

    let manifest_json: serde_json::Value = match serde_json::from_slice(&body_bytes) {
        Ok(v) => v,
        Err(e) => {
            warn!("[manifest-put] Invalid manifest JSON for {repo}:{reference}: {e}");
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

    let (hub_registry, hub_planet, hub_image) = split_repo_for_hub(&repo);
    let payload = serde_json::json!({
        "registry": hub_registry,
        "planet": hub_planet,
        "image": hub_image,
        "tag": reference,
        "digest": content_digest,
        "manifest_json": String::from_utf8_lossy(&body_bytes),
        "layers": layers,
    });

    if let Err(e) = state.hub.notify_manifest(&payload).await {
        warn!("[manifest-put] CentralHub notification failed (non-fatal): {e}");
    }

    info!(
        "[manifest-put] Stored: repo={} ref={} digest={}",
        repo, reference, content_digest
    );

    Response::builder()
        .status(StatusCode::CREATED)
        .header("Docker-Content-Digest", &content_digest)
        .header("Location", format!("/v2/{repo}/manifests/{reference}"))
        .header("Docker-Distribution-API-Version", "registry/2.0")
        .body(Body::empty())
        .unwrap_or_else(|_| Response::new(Body::empty()))
}

/// Split a repo path into (registry, planet, image) for the CentralHub payload.
///
/// For 3-segment paths (`registry/planet/name`) the split is natural.
/// For 2-segment paths (`ns/name`) the first segment is used as registry,
/// an empty string for planet, and the second as image — so CentralHub can
/// still index the push even if the planet field is absent.
fn split_repo_for_hub(repo: &str) -> (String, String, String) {
    let parts: Vec<&str> = repo.splitn(3, '/').collect();
    match parts.as_slice() {
        [registry, planet, image] => {
            (registry.to_string(), planet.to_string(), image.to_string())
        }
        [ns, name] => (ns.to_string(), String::new(), name.to_string()),
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
        // splitn(3) ensures the third segment absorbs any extra slashes.
        let (r, p, i) = split_repo_for_hub("scareverse/earth/backend/extra");
        assert_eq!(r, "scareverse");
        assert_eq!(p, "earth");
        assert_eq!(i, "backend/extra");
    }

    #[test]
    fn test_split_2seg() {
        let (r, p, i) = split_repo_for_hub("staging/scareverse-backend");
        assert_eq!(r, "staging");
        assert_eq!(p, "");
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

// ── 3-segment public handlers ─────────────────────────────────────────────────

/// `GET /v2/:registry/:planet/:name/manifests/:reference`
pub async fn handle_manifest_get(
    State(state): State<Arc<AppState>>,
    Path((registry, planet, name, reference)): Path<(String, String, String, String)>,
    req: Request<Body>,
) -> Response<Body> {
    manifest_get_inner(state, format!("{registry}/{planet}/{name}"), reference, req).await
}

/// `PUT /v2/:registry/:planet/:name/manifests/:reference`
pub async fn handle_manifest_put(
    State(state): State<Arc<AppState>>,
    Path((registry, planet, name, reference)): Path<(String, String, String, String)>,
    req: Request<Body>,
) -> Response<Body> {
    manifest_put_inner(state, format!("{registry}/{planet}/{name}"), reference, req).await
}

// ── 2-segment public handlers ─────────────────────────────────────────────────

/// `GET /v2/:ns/:name/manifests/:reference`
pub async fn handle_manifest_get_2seg(
    State(state): State<Arc<AppState>>,
    Path((ns, name, reference)): Path<(String, String, String)>,
    req: Request<Body>,
) -> Response<Body> {
    manifest_get_inner(state, format!("{ns}/{name}"), reference, req).await
}

/// `PUT /v2/:ns/:name/manifests/:reference`
pub async fn handle_manifest_put_2seg(
    State(state): State<Arc<AppState>>,
    Path((ns, name, reference)): Path<(String, String, String)>,
    req: Request<Body>,
) -> Response<Body> {
    manifest_put_inner(state, format!("{ns}/{name}"), reference, req).await
}
