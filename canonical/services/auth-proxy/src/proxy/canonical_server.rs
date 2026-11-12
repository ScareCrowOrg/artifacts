//! Canonical binary artifact delivery — raw bytes from disk, Vite as fallback.
//!
//! Extracted from the ingress `match` so `proxy.rs` stays within the RULESET 1.1
//! line limit. Behaviour is unchanged: the same resolution, the same MIME map,
//! the same "not on disk → let Vite answer" fallback.
//!
//! Canonical artifacts are git-managed (no user uploads reach this tree), so the
//! fallback is safe here. Runtime artifacts deliberately do **not** have it — see
//! [`super::runtime_server`].

use axum::{extract::Request, http::{header, StatusCode}, response::Response};
use tracing::{debug, info, warn};

use crate::file_server::{resolve_artifact_path, serve_file, ArtifactResolution, ARTIFACTS_BASE};
use crate::upstream::resolve_proxy_upstream;
use crate::AppState;

use super::{build_error_response, proxy_to_upstream};

/// Serve a canonical binary artifact, falling back to Vite when the file is absent.
///
/// Reached only for `/artifacts/canonical/**` paths whose extension is in the
/// binary allowlist (`classify::is_binary_artifact`); canonical code takes the
/// Vite branch instead.
pub(super) async fn serve_canonical_artifact(
    state: &AppState,
    req: Request,
    path: &str,
    full_path: &str,
) -> Response {
    match resolve_artifact_path(ARTIFACTS_BASE, path) {
        ArtifactResolution::Found(file_path) => {
            debug!(
                "[FileServer] Serving canonical artifact: {} (path: {})",
                path,
                file_path.display()
            );
            let origin = req.headers().get(header::ORIGIN).and_then(|v| v.to_str().ok());
            let host = req.headers().get(header::HOST).and_then(|v| v.to_str().ok());
            serve_file(&file_path, origin, host).await
        }
        ArtifactResolution::NotFound => {
            warn!("[FileServer] Artifact not found on disk, falling back: {}", path);
            match resolve_proxy_upstream(state).await {
                Ok(upstream) => {
                    info!("[FileServer] File not found, falling back to FastApiProxy: {}", path);
                    proxy_to_upstream(state, req, full_path, &upstream, None).await
                }
                Err(status) => build_error_response(status),
            }
        }
        ArtifactResolution::PathTraversal => {
            warn!("[FileServer] Path traversal BLOCKED: {}", path);
            build_error_response(StatusCode::NOT_FOUND)
        }
    }
}
