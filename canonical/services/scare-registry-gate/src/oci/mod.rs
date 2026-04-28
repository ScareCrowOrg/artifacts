//! OCI v2 router and version-check handler.

pub mod auth;
pub mod blobs;
pub mod manifests;
pub mod types;

use std::sync::Arc;

use axum::{
    body::Body,
    extract::State,
    http::{Request, Response, StatusCode},
    routing::{get, head, patch, post, put},
    Router,
};
use tracing::{info, warn};

use crate::AppState;
use auth::require_auth;
use types::make_error_response;

/// Build the OCI v2 Axum sub-router.
///
/// Registers routes for both 3-segment namespaces (`registry/planet/name`, the
/// canonical TO-BE design) and 2-segment namespaces (`ns/name`, used by the
/// Builder when tagging images as `{targetName}/scareverse-{service}`).
///
/// All routes require Basic Auth except the initial version-check (`GET /v2/`),
/// which returns 401 (prompting the client to send credentials) or 200 if
/// credentials are present and valid.
pub fn oci_router() -> Router<Arc<AppState>> {
    Router::new()
        // OCI version check
        .route("/v2/", get(handle_v2_check))

        // ── 3-segment blob routes (registry/planet/name) ───────────────────
        .route(
            "/v2/:registry/:planet/:name/blobs/uploads/",
            post(blobs::handle_blob_upload_init),
        )
        .route(
            "/v2/:registry/:planet/:name/blobs/uploads/:uuid",
            patch(blobs::handle_blob_patch),
        )
        .route(
            "/v2/:registry/:planet/:name/blobs/uploads/:uuid",
            put(blobs::handle_blob_put),
        )
        .route(
            "/v2/:registry/:planet/:name/blobs/:digest",
            head(blobs::handle_blob_head),
        )
        .route(
            "/v2/:registry/:planet/:name/blobs/:digest",
            get(blobs::handle_blob_get),
        )

        // ── 3-segment manifest routes (registry/planet/name) ───────────────
        .route(
            "/v2/:registry/:planet/:name/manifests/:reference",
            get(manifests::handle_manifest_get),
        )
        .route(
            "/v2/:registry/:planet/:name/manifests/:reference",
            put(manifests::handle_manifest_put),
        )

        // ── 2-segment blob routes (ns/name) — used by Builder push ─────────
        .route(
            "/v2/:ns/:name/blobs/uploads/",
            post(blobs::handle_blob_upload_init_2seg),
        )
        .route(
            "/v2/:ns/:name/blobs/uploads/:uuid",
            patch(blobs::handle_blob_patch_2seg),
        )
        .route(
            "/v2/:ns/:name/blobs/uploads/:uuid",
            put(blobs::handle_blob_put_2seg),
        )
        .route(
            "/v2/:ns/:name/blobs/:digest",
            head(blobs::handle_blob_head_2seg),
        )
        .route(
            "/v2/:ns/:name/blobs/:digest",
            get(blobs::handle_blob_get_2seg),
        )

        // ── 2-segment manifest routes (ns/name) ────────────────────────────
        .route(
            "/v2/:ns/:name/manifests/:reference",
            get(manifests::handle_manifest_get_2seg),
        )
        .route(
            "/v2/:ns/:name/manifests/:reference",
            put(manifests::handle_manifest_put_2seg),
        )

        // Catch-all: log any unmatched path to aid debugging
        .fallback(handle_not_found)
}

/// `GET /v2/` – OCI API version check.
///
/// Returns 401 when credentials are absent (prompts Docker client to
/// authenticate), or 200 when valid credentials are provided.
async fn handle_v2_check(
    State(state): State<Arc<AppState>>,
    req: Request<Body>,
) -> Response<Body> {
    info!(
        "[v2-check] GET /v2/ | has_auth_header: {}",
        req.headers().get("Authorization").is_some()
    );

    match require_auth(req.headers(), &state.config) {
        Ok(_) => {
            info!("[v2-check] Auth passed, returning 200");
            Response::builder()
                .status(StatusCode::OK)
                .header("Docker-Distribution-API-Version", "registry/2.0")
                .header("Content-Length", "0")
                .body(Body::empty())
                .unwrap_or_else(|_| Response::new(Body::empty()))
        }
        Err(resp) => {
            info!("[v2-check] Auth failed, returning 401");
            resp
        }
    }
}

/// Fallback handler for unmatched routes.
///
/// Logs the method and URI so that routing mismatches (e.g. wrong namespace
/// depth) are immediately visible in the service logs.
async fn handle_not_found(req: Request<Body>) -> Response<Body> {
    warn!(
        "[ScareRegistryGate] 404 – no route matched: {} {} | \
         hint: check namespace depth (2-seg vs 3-seg) and trailing slash on blob upload POST",
        req.method(),
        req.uri()
    );
    make_error_response(StatusCode::NOT_FOUND, "NOT_FOUND", "No route matched")
}
