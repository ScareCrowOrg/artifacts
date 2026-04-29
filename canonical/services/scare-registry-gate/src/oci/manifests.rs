//! OCI v2 manifest handlers.
//!
//! HEAD → check existence via R2 head_object (no redirect)
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

// ── Inner: manifest head ──────────────────────────────────────────────────────

/// Core logic for `HEAD .../manifests/:reference`.
///
/// Docker sends HEAD before PUT to check if the manifest already exists.
/// Returns 200 with size/digest headers if found, 404 MANIFEST_UNKNOWN if not.
///
/// **Does NOT redirect** — redirecting to the R2 S3 API causes 400 because
/// Docker follows the redirect without S3 request signing.
async fn manifest_head_inner(
    state: Arc<AppState>,
    repo: String,
    reference: String,
    req: Request<Body>,
) -> Response<Body> {
    info!(
        "[manifest-head] HEAD /v2/{}/manifests/{} | has_auth: {}",
        repo,
        reference,
        req.headers().get("Authorization").is_some()
    );

    if let Err(resp) = require_auth(req.headers(), &state.config) {
        warn!("[manifest-head] Auth failed: repo={} ref={}", repo, reference);
        return resp;
    }

    let r2_key = format!("manifests/{repo}/{reference}");
    info!("[manifest-head] Checking R2: key={}", r2_key);

    match state.r2.head_object(&r2_key).await {
        Ok(Some(size)) => {
            info!("[manifest-head] Manifest found: key={} size={}", r2_key, size);
            Response::builder()
                .status(StatusCode::OK)
                .header("Content-Length", size.to_string())
                .header("Docker-Content-Digest", &reference)
                .header("Content-Type", "application/vnd.docker.distribution.manifest.v2+json")
                .header("Docker-Distribution-API-Version", "registry/2.0")
                .body(Body::empty())
                .unwrap_or_else(|_| Response::new(Body::empty()))
        }
        Ok(None) => {
            info!("[manifest-head] Manifest not found: key={}", r2_key);
            make_error_response(StatusCode::NOT_FOUND, "MANIFEST_UNKNOWN", "Manifest not found")
        }
        Err(e) => {
            error!("[manifest-head] R2 head_object error for {r2_key}: {e}");
            make_error_response(
                StatusCode::INTERNAL_SERVER_ERROR,
                "INTERNAL_ERROR",
                "Storage error",
            )
        }
    }
}

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

    // [it9:redirect-source] Log the exact URL the Gate uses for this redirect so it can
    // be compared with r2_public_url_base stored in CentralHub (notified during PUT).
    // Both must share the same base URL for docker pull via CentralHub to be consistent.
    info!(
        "[manifest-get] [it9:redirect-source] r2client_public_url='{}' | redirect_url='{}'",
        state.r2.public_url, url
    );

    // Warn if the redirect URL points to the R2 S3 API endpoint rather than a
    // public CDN URL.  Docker (and other OCI clients) follow the 307 without
    // adding S3 request signing, so an S3 API URL will produce a 400 response.
    if url.contains("r2.cloudflarestorage.com") {
        warn!(
            "[manifest-get] Redirect URL contains 'r2.cloudflarestorage.com' – \
             this is the S3 API endpoint, not a public CDN URL. \
             Unauthenticated clients will receive 400 when following this redirect. \
             Set R2_PUBLIC_URL to the public bucket URL (e.g. https://pub-xxx.r2.dev). \
             key={} url={}",
            r2_key, url
        );
    } else {
        info!("[manifest-get] Redirecting: key={} → {}", r2_key, url);
    }

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

    info!(
        "[manifest-put] Body received: repo={} ref={} body_size={}",
        repo, reference, body_bytes.len()
    );

    let hash = Sha256::digest(&body_bytes);
    let digest_hex = hex::encode(hash);
    let content_digest = format!("sha256:{digest_hex}");

    info!(
        "[manifest-put] Computed digest: repo={} ref={} digest={}",
        repo, reference, content_digest
    );

    let ref_key = format!("manifests/{repo}/{reference}");
    let digest_key = format!("manifests/{repo}/sha256:{digest_hex}");

    info!(
        "[manifest-put] R2 keys: ref_key={} digest_key={}",
        ref_key, digest_key
    );

    match state
        .r2
        .put_object(&ref_key, body_bytes.clone(), &content_type)
        .await
    {
        Ok(()) => {
            info!("[manifest-put] R2 put_object OK: key={}", ref_key);
        }
        Err(e) => {
            error!("[manifest-put] R2 put_object (ref) error for {ref_key}: {e}");
            return make_error_response(
                StatusCode::INTERNAL_SERVER_ERROR,
                "INTERNAL_ERROR",
                "Failed to store manifest",
            );
        }
    }

    match state
        .r2
        .put_object(&digest_key, body_bytes.clone(), &content_type)
        .await
    {
        Ok(()) => {
            info!("[manifest-put] R2 put_object OK: key={}", digest_key);
        }
        Err(e) => {
            warn!("[manifest-put] R2 put_object (digest) error for {digest_key}: {e}");
        }
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

    let schema_version = manifest_json
        .get("schemaVersion")
        .and_then(|v| v.as_u64())
        .unwrap_or(0);
    let media_type = manifest_json
        .get("mediaType")
        .and_then(|v| v.as_str())
        .unwrap_or("unknown");

    info!(
        "[manifest-put] Manifest parsed: repo={} ref={} schemaVersion={} mediaType={} layers_count={}",
        repo, reference, schema_version, media_type, layers.len()
    );

    let (hub_registry, hub_planet, hub_image) = split_repo_for_hub(&repo);

    info!(
        "[manifest-put] Hub split: registry={} planet={} image={}",
        hub_registry, hub_planet, hub_image
    );

    // [it9:dry-check] Both fields carry the same R2_PUBLIC_URL env var value; logging
    // them together makes any future divergence immediately visible in gate logs.
    info!(
        "[manifest-put] [it9:r2-url-sources] \
         config_r2_public_url='{}' (len={}) | \
         r2client_public_url='{}' (len={}) | \
         same={}",
        state.config.r2_public_url,
        state.config.r2_public_url.len(),
        state.r2.public_url,
        state.r2.public_url.len(),
        state.config.r2_public_url == state.r2.public_url,
    );

    // Include the public R2 URL that was used for this push so CentralHub can
    // redirect pulls to the exact same bucket/CDN without relying on a global env var.
    //
    // Use state.r2.public_url — the canonical source used by all GET redirect handlers
    // (manifest_get_inner, blob_get_inner) via public_url_for().  This is the single
    // source of truth: whatever URL the Gate itself would serve as a redirect is exactly
    // what CentralHub must store and serve back on docker pull.
    //
    // Using state.config.r2_public_url (a separate copy of the same env var) was a DRY
    // violation that risked divergence if the two fields ever differed.
    let payload = serde_json::json!({
        "registry": hub_registry,
        "planet": hub_planet,
        "image": hub_image,
        "tag": reference,
        "digest": content_digest,
        "manifest_json": String::from_utf8_lossy(&body_bytes),
        "layers": layers,
        "r2_public_url_base": state.r2.public_url,
    });

    // [it9:payload-r2-url] Log the exact r2_public_url_base value persisted in CentralHub.
    let notified_r2_url = payload
        .get("r2_public_url_base")
        .and_then(|v| v.as_str())
        .unwrap_or("<missing>");
    info!(
        "[manifest-put] [it9:notified-r2-url] r2_public_url_base_in_payload='{}' | repo={} ref={}",
        notified_r2_url, repo, reference
    );

    if let Err(e) = state.hub.notify_manifest(&payload).await {
        warn!("[manifest-put] CentralHub notification failed (non-fatal): {e}");
    }

    info!(
        "[manifest-put] Responding 201 CREATED: repo={} ref={} digest={} location=/v2/{}/manifests/{}",
        repo, reference, content_digest, repo, reference
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

/// `HEAD /v2/:registry/:planet/:name/manifests/:reference`
pub async fn handle_manifest_head(
    State(state): State<Arc<AppState>>,
    Path((registry, planet, name, reference)): Path<(String, String, String, String)>,
    req: Request<Body>,
) -> Response<Body> {
    manifest_head_inner(state, format!("{registry}/{planet}/{name}"), reference, req).await
}

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

/// `HEAD /v2/:ns/:name/manifests/:reference`
pub async fn handle_manifest_head_2seg(
    State(state): State<Arc<AppState>>,
    Path((ns, name, reference)): Path<(String, String, String)>,
    req: Request<Body>,
) -> Response<Body> {
    manifest_head_inner(state, format!("{ns}/{name}"), reference, req).await
}

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
