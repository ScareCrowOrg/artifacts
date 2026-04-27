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

use crate::AppState;
use auth::require_auth;

/// Build the OCI v2 Axum sub-router.
///
/// All routes require Basic Auth except the initial version-check (`GET /v2/`),
/// which returns 401 (prompting the client to send credentials) or 200 if
/// credentials are present and valid.
pub fn oci_router() -> Router<Arc<AppState>> {
    Router::new()
        // OCI version check
        .route("/v2/", get(handle_v2_check))
        // Blob upload lifecycle (3-component namespace: registry/planet/name)
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
        // Blob access
        .route(
            "/v2/:registry/:planet/:name/blobs/:digest",
            head(blobs::handle_blob_head),
        )
        .route(
            "/v2/:registry/:planet/:name/blobs/:digest",
            get(blobs::handle_blob_get),
        )
        // Manifest access
        .route(
            "/v2/:registry/:planet/:name/manifests/:reference",
            get(manifests::handle_manifest_get),
        )
        .route(
            "/v2/:registry/:planet/:name/manifests/:reference",
            put(manifests::handle_manifest_put),
        )
}

/// `GET /v2/` – OCI API version check.
///
/// Returns 401 when credentials are absent (prompts Docker client to
/// authenticate), or 200 when valid credentials are provided.
async fn handle_v2_check(
    State(state): State<Arc<AppState>>,
    req: Request<Body>,
) -> Response<Body> {
    match require_auth(req.headers(), &state.config) {
        Ok(_) => Response::builder()
            .status(StatusCode::OK)
            .header("Docker-Distribution-API-Version", "registry/2.0")
            .header("Content-Length", "0")
            .body(Body::empty())
            .unwrap_or_else(|_| Response::new(Body::empty())),
        Err(resp) => resp,
    }
}
