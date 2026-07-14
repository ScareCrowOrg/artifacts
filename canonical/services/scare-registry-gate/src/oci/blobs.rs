//! OCI v2 blob upload handlers.
//!
//! Uses Option-B (in-memory buffer) for simplicity:
//!   POST  → generate UUID, store empty session in Redis
//!   PATCH → accumulate body in `AppState.session_buffers`
//!   PUT   → verify SHA-256, `PutObject` to R2, clean up
//!
//! Both 3-segment (`registry/planet/name`) and 2-segment (`ns/name`) namespace
//! paths are supported.  2-segment variants call the same inner functions with
//! the full repo path string (e.g. `"staging/scareverse-backend"`).

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

use crate::control::lookup_tenant_session;
use crate::oci::auth::require_auth;
use crate::oci::types::{make_error_response, split_repo_for_hub, UploadSession};
use crate::AppState;

// ── Inner: blob upload init ───────────────────────────────────────────────────

/// Core logic for `POST .../blobs/uploads/`.
/// `repo` is the full repository path, e.g. `"registry/planet/name"` or `"ns/name"`.
async fn blob_upload_init_inner(
    state: Arc<AppState>,
    repo: String,
    req: Request<Body>,
) -> Response<Body> {
    info!(
        "[blob-upload-init] POST /v2/{}/blobs/uploads/ | has_auth: {}",
        repo,
        req.headers().get("Authorization").is_some()
    );

    if let Err(resp) = require_auth(req.headers(), &state.config) {
        warn!("[blob-upload-init] Auth failed for repo={}", repo);
        return resp;
    }

    info!("[blob-upload-init] Auth passed for repo={}", repo);

    let uuid = uuid::Uuid::new_v4().to_string();
    let session = UploadSession::new(uuid.clone());
    info!("[blob-upload-init] Created session UUID: {} for repo={}", uuid, repo);

    let session_json = match session.to_redis_value() {
        Ok(s) => s,
        Err(e) => {
            error!("[blob-upload-init] Session serialize error: {e}");
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
        error!("[blob-upload-init] Redis SET error: {e}");
        return make_error_response(
            StatusCode::INTERNAL_SERVER_ERROR,
            "INTERNAL_ERROR",
            "Failed to store upload session",
        );
    }

    let location = format!("/v2/{repo}/blobs/uploads/{uuid}");
    info!("[blob-upload-init] Session ready: uuid={} location={}", uuid, location);
    Response::builder()
        .status(StatusCode::ACCEPTED)
        .header("Location", &location)
        .header("Docker-Upload-UUID", &uuid)
        .header("Docker-Distribution-API-Version", "registry/2.0")
        .header("Range", "0-0")
        .body(Body::empty())
        .unwrap_or_else(|_| Response::new(Body::empty()))
}

// ── Inner: blob patch ─────────────────────────────────────────────────────────

/// Core logic for `PATCH .../blobs/uploads/:uuid`.
async fn blob_patch_inner(
    state: Arc<AppState>,
    repo: String,
    uuid: String,
    req: Request<Body>,
) -> Response<Body> {
    info!(
        "[blob-patch] PATCH /v2/{}/blobs/uploads/{} | has_auth: {}",
        repo,
        uuid,
        req.headers().get("Authorization").is_some()
    );

    if let Err(resp) = require_auth(req.headers(), &state.config) {
        warn!("[blob-patch] Auth failed: uuid={}", uuid);
        return resp;
    }

    let redis_key = format!("gate:upload:{uuid}");
    let mut conn = state.redis.clone();
    let exists: Result<Option<String>, _> = conn.get(&redis_key).await;
    match exists {
        Ok(None) => {
            warn!("[blob-patch] Upload session not found in Redis: uuid={}", uuid);
            return make_error_response(
                StatusCode::NOT_FOUND,
                "BLOB_UPLOAD_UNKNOWN",
                "Upload session not found",
            );
        }
        Err(e) => {
            error!("[blob-patch] Redis GET error: {e}");
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
            error!("[blob-patch] Body read error: {e}");
            return make_error_response(
                StatusCode::INTERNAL_SERVER_ERROR,
                "BLOB_UPLOAD_INVALID",
                "Failed to read request body",
            );
        }
    };

    let chunk_len = body_bytes.len();
    let new_size = {
        let mut entry = state
            .session_buffers
            .entry(uuid.clone())
            .or_insert_with(Vec::new);
        entry.extend_from_slice(&body_bytes);
        entry.len()
    };

    info!(
        "[blob-patch] Chunk received: uuid={} chunk_bytes={} total_buffered={}",
        uuid, chunk_len, new_size
    );

    let range_end = if new_size > 0 { new_size - 1 } else { 0 };
    Response::builder()
        .status(StatusCode::ACCEPTED)
        .header("Range", format!("0-{range_end}"))
        .header("Docker-Upload-UUID", &uuid)
        .header("Docker-Distribution-API-Version", "registry/2.0")
        .body(Body::empty())
        .unwrap_or_else(|_| Response::new(Body::empty()))
}

// ── Inner: blob put ───────────────────────────────────────────────────────────

/// Core logic for `PUT .../blobs/uploads/:uuid?digest=sha256:…`.
async fn blob_put_inner(
    state: Arc<AppState>,
    repo: String,
    uuid: String,
    params: HashMap<String, String>,
    req: Request<Body>,
) -> Response<Body> {
    info!(
        "[blob-put] PUT /v2/{}/blobs/uploads/{} | has_auth: {}",
        repo,
        uuid,
        req.headers().get("Authorization").is_some()
    );

    if let Err(resp) = require_auth(req.headers(), &state.config) {
        warn!("[blob-put] Auth failed: uuid={}", uuid);
        return resp;
    }

    let provided_digest = match params.get("digest") {
        Some(d) => d.clone(),
        None => {
            warn!("[blob-put] Missing digest param: uuid={}", uuid);
            return make_error_response(
                StatusCode::BAD_REQUEST,
                "DIGEST_INVALID",
                "Missing digest query parameter",
            );
        }
    };

    info!(
        "[blob-put] Finalising upload: uuid={} digest_param={}",
        uuid, provided_digest
    );

    let final_bytes = match to_bytes(req.into_body(), state.config.max_blob_size).await {
        Ok(b) => b,
        Err(e) => {
            error!("[blob-put] Body read error: {e}");
            return make_error_response(
                StatusCode::INTERNAL_SERVER_ERROR,
                "BLOB_UPLOAD_INVALID",
                "Failed to read final body",
            );
        }
    };

    let mut buffer = state
        .session_buffers
        .remove(&uuid)
        .map(|(_, v)| v)
        .unwrap_or_default();
    if !final_bytes.is_empty() {
        buffer.extend_from_slice(&final_bytes);
    }

    let hash = Sha256::digest(&buffer);
    let computed_hex = hex::encode(hash);
    let expected = format!("sha256:{computed_hex}");
    if provided_digest != expected {
        warn!(
            "[blob-put] Digest mismatch: uuid={} got={} expected={}",
            uuid, provided_digest, expected
        );
        return make_error_response(
            StatusCode::BAD_REQUEST,
            "DIGEST_INVALID",
            "Provided digest does not match blob content",
        );
    }

    let size = buffer.len();
    info!(
        "[blob-put] Digest verified OK: uuid={} digest={} size={}",
        uuid, provided_digest, size
    );

    // Tenant-aware R2 override
    let (_hub_registry, hub_planet, _hub_image) = split_repo_for_hub(&repo);
    let tenant_config = lookup_tenant_session(&state, &hub_planet);
    let effective_r2 = tenant_config.as_ref().map_or_else(
        || (*state.r2).clone(),
        |t| state.r2.with_overrides(t.r2_bucket.as_deref(), t.r2_public_url.as_deref()),
    );

    let r2_key = format!("blobs/{repo}/{provided_digest}");
    if let Err(e) = effective_r2
        .put_object(&r2_key, Bytes::from(buffer), "application/octet-stream")
        .await
    {
        error!("[blob-put] R2 put_object error for {r2_key}: {e}");
        return make_error_response(
            StatusCode::INTERNAL_SERVER_ERROR,
            "INTERNAL_ERROR",
            "Failed to upload blob to R2",
        );
    }

    let redis_key = format!("gate:upload:{uuid}");
    let mut conn = state.redis.clone();
    conn.del::<_, ()>(&redis_key).await.ok();

    info!("[blob-put] Blob stored: key={r2_key} size={size}");
    Response::builder()
        .status(StatusCode::CREATED)
        .header("Docker-Content-Digest", &provided_digest)
        .header("Location", format!("/v2/{repo}/blobs/{provided_digest}"))
        .header("Docker-Distribution-API-Version", "registry/2.0")
        .body(Body::empty())
        .unwrap_or_else(|_| Response::new(Body::empty()))
}

// ── Inner: blob head ──────────────────────────────────────────────────────────

/// Core logic for `HEAD .../blobs/:digest`.
async fn blob_head_inner(
    state: Arc<AppState>,
    repo: String,
    digest: String,
    req: Request<Body>,
) -> Response<Body> {
    info!(
        "[blob-head] HEAD /v2/{}/blobs/{} | has_auth: {}",
        repo,
        digest,
        req.headers().get("Authorization").is_some()
    );

    if let Err(resp) = require_auth(req.headers(), &state.config) {
        return resp;
    }

    // Tenant-aware R2 override
    let (_hub_registry, hub_planet, _hub_image) = split_repo_for_hub(&repo);
    let tenant_config = lookup_tenant_session(&state, &hub_planet);
    let effective_r2 = tenant_config.as_ref().map_or_else(
        || (*state.r2).clone(),
        |t| state.r2.with_overrides(t.r2_bucket.as_deref(), t.r2_public_url.as_deref()),
    );

    let r2_key = format!("blobs/{repo}/{digest}");
    match effective_r2.head_object(&r2_key).await {
        Ok(Some(size)) => {
            info!("[blob-head] Blob found: key={} size={}", r2_key, size);
            Response::builder()
                .status(StatusCode::OK)
                .header("Content-Length", size.to_string())
                .header("Docker-Content-Digest", &digest)
                .header("Docker-Distribution-API-Version", "registry/2.0")
                .body(Body::empty())
                .unwrap_or_else(|_| Response::new(Body::empty()))
        }
        Ok(None) => {
            info!("[blob-head] Blob not found: key={}", r2_key);
            make_error_response(StatusCode::NOT_FOUND, "BLOB_UNKNOWN", "Blob not found")
        }
        Err(e) => {
            error!("[blob-head] R2 head_object error for {r2_key}: {e}");
            make_error_response(
                StatusCode::INTERNAL_SERVER_ERROR,
                "INTERNAL_ERROR",
                "Storage error",
            )
        }
    }
}

// ── Inner: blob get ───────────────────────────────────────────────────────────

/// Core logic for `GET .../blobs/:digest`.
async fn blob_get_inner(
    state: Arc<AppState>,
    repo: String,
    digest: String,
    req: Request<Body>,
) -> Response<Body> {
    info!("[blob-get] GET /v2/{}/blobs/{} → redirect to R2", repo, digest);

    if let Err(resp) = require_auth(req.headers(), &state.config) {
        return resp;
    }

    // Tenant-aware R2 override for redirect URL
    let (_hub_registry, hub_planet, _hub_image) = split_repo_for_hub(&repo);
    let tenant_config = lookup_tenant_session(&state, &hub_planet);
    let effective_r2 = tenant_config.as_ref().map_or_else(
        || (*state.r2).clone(),
        |t| state.r2.with_overrides(t.r2_bucket.as_deref(), t.r2_public_url.as_deref()),
    );

    let r2_key = format!("blobs/{repo}/{digest}");
    let url = effective_r2.public_url_for(&r2_key);
    info!("[blob-get] Redirecting: key={} → {}", r2_key, url);
    Response::builder()
        .status(StatusCode::TEMPORARY_REDIRECT)
        .header("Location", &url)
        .header("Docker-Content-Digest", &digest)
        .header("Docker-Distribution-API-Version", "registry/2.0")
        .body(Body::empty())
        .unwrap_or_else(|_| Response::new(Body::empty()))
}

// ── 3-segment public handlers ─────────────────────────────────────────────────

/// `POST /v2/:registry/:planet/:name/blobs/uploads/`
pub async fn handle_blob_upload_init(
    State(state): State<Arc<AppState>>,
    Path((registry, planet, name)): Path<(String, String, String)>,
    req: Request<Body>,
) -> Response<Body> {
    blob_upload_init_inner(state, format!("{registry}/{planet}/{name}"), req).await
}

/// `PATCH /v2/:registry/:planet/:name/blobs/uploads/:uuid`
pub async fn handle_blob_patch(
    State(state): State<Arc<AppState>>,
    Path((_registry, _planet, _name, uuid)): Path<(String, String, String, String)>,
    req: Request<Body>,
) -> Response<Body> {
    let repo = format!("{_registry}/{_planet}/{_name}");
    blob_patch_inner(state, repo, uuid, req).await
}

/// `PUT /v2/:registry/:planet/:name/blobs/uploads/:uuid`
pub async fn handle_blob_put(
    State(state): State<Arc<AppState>>,
    Path((registry, planet, name, uuid)): Path<(String, String, String, String)>,
    Query(params): Query<HashMap<String, String>>,
    req: Request<Body>,
) -> Response<Body> {
    blob_put_inner(state, format!("{registry}/{planet}/{name}"), uuid, params, req).await
}

/// `HEAD /v2/:registry/:planet/:name/blobs/:digest`
pub async fn handle_blob_head(
    State(state): State<Arc<AppState>>,
    Path((registry, planet, name, digest)): Path<(String, String, String, String)>,
    req: Request<Body>,
) -> Response<Body> {
    blob_head_inner(state, format!("{registry}/{planet}/{name}"), digest, req).await
}

/// `GET /v2/:registry/:planet/:name/blobs/:digest`
pub async fn handle_blob_get(
    State(state): State<Arc<AppState>>,
    Path((registry, planet, name, digest)): Path<(String, String, String, String)>,
    req: Request<Body>,
) -> Response<Body> {
    blob_get_inner(state, format!("{registry}/{planet}/{name}"), digest, req).await
}

// ── 2-segment public handlers (for Builder-style `{env}/{service}` tags) ─────

/// `POST /v2/:ns/:name/blobs/uploads/`
pub async fn handle_blob_upload_init_2seg(
    State(state): State<Arc<AppState>>,
    Path((ns, name)): Path<(String, String)>,
    req: Request<Body>,
) -> Response<Body> {
    blob_upload_init_inner(state, format!("{ns}/{name}"), req).await
}

/// `PATCH /v2/:ns/:name/blobs/uploads/:uuid`
pub async fn handle_blob_patch_2seg(
    State(state): State<Arc<AppState>>,
    Path((ns, name, uuid)): Path<(String, String, String)>,
    req: Request<Body>,
) -> Response<Body> {
    blob_patch_inner(state, format!("{ns}/{name}"), uuid, req).await
}

/// `PUT /v2/:ns/:name/blobs/uploads/:uuid`
pub async fn handle_blob_put_2seg(
    State(state): State<Arc<AppState>>,
    Path((ns, name, uuid)): Path<(String, String, String)>,
    Query(params): Query<HashMap<String, String>>,
    req: Request<Body>,
) -> Response<Body> {
    blob_put_inner(state, format!("{ns}/{name}"), uuid, params, req).await
}

/// `HEAD /v2/:ns/:name/blobs/:digest`
pub async fn handle_blob_head_2seg(
    State(state): State<Arc<AppState>>,
    Path((ns, name, digest)): Path<(String, String, String)>,
    req: Request<Body>,
) -> Response<Body> {
    blob_head_inner(state, format!("{ns}/{name}"), digest, req).await
}

/// `GET /v2/:ns/:name/blobs/:digest`
pub async fn handle_blob_get_2seg(
    State(state): State<Arc<AppState>>,
    Path((ns, name, digest)): Path<(String, String, String)>,
    req: Request<Body>,
) -> Response<Body> {
    blob_get_inner(state, format!("{ns}/{name}"), digest, req).await
}
