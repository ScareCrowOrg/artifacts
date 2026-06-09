//! File serving for canonical and runtime artifacts.
//!
//! The Auth Proxy (Rust/tokio) serves binary artifacts (.glb, .png, etc.)
//! directly from disk using async file I/O, bypassing Vite entirely.
//!
//! Runtime artifacts additionally require a self-access check: the session's
//! `userId` must match the `assignee_id` in the URL path before serving.

use std::path::Path;

use axum::{
    body::Body,
    http::{HeaderName, HeaderValue, StatusCode},
    response::Response,
};
use tokio::fs;
use tokio_util::io::ReaderStream;
use tracing::{debug, error, warn};

use crate::AppState;

/// Result of an artifact path resolution.
///
/// Distinguishes three outcomes that callers MUST handle differently:
/// - `Found(path)` — file exists and is within the allowed base directory.
/// - `NotFound` — file does not exist on disk (caller may fall back to proxy).
/// - `PathTraversal` — the path attempted to escape the base directory.
pub enum ArtifactResolution {
    Found(std::path::PathBuf),
    NotFound,
    PathTraversal,
}

/// Resolve a safe filesystem path for an artifact request.
///
/// Canonical artifacts are at `/app/artifacts/{rel_path}`. This function:
/// 1. Strips the `/artifacts/` prefix.
/// 2. Joins with the base directory.
/// 3. Uses `canonicalize()` to resolve symlinks and `..` segments.
/// 4. Verifies the resolved path is within the base directory.
///
/// Returns:
/// - `ArtifactResolution::Found(path)` — safe path to read the file.
/// - `ArtifactResolution::NotFound` — file does not exist (caller may proxy).
/// - `ArtifactResolution::PathTraversal` — path escapes the base directory.
pub fn resolve_artifact_path(base_dir: &str, path: &str) -> ArtifactResolution {
    use std::path::Path;

    // Strip the /artifacts/ prefix to get the relative path.
    let rel = match path.strip_prefix("/artifacts/") {
        Some(r) => r,
        None => return ArtifactResolution::NotFound,
    };
    let base = Path::new(base_dir);

    // Join and canonicalize to resolve any `..` or symlinks.
    let joined = base.join(rel);
    match joined.canonicalize() {
        Ok(resolved) => {
            if resolved.starts_with(base) {
                ArtifactResolution::Found(resolved)
            } else {
                warn!(
                    "[FileServer] Path traversal detected: {} resolves to {} outside base {}",
                    path,
                    resolved.display(),
                    base_dir
                );
                ArtifactResolution::PathTraversal
            }
        }
        Err(_) => {
            // File does not exist on disk — not an error, caller may fall back.
            ArtifactResolution::NotFound
        }
    }
}

/// Extract `assignee_id` from a runtime path.
///
/// Runtime paths follow the pattern:
/// `/artifacts/runtime/user/{assignee_id}/contents/{cell_id}/{filename}`
///
/// Returns `Some(assignee_id)` if the path matches, `None` otherwise.
pub fn extract_runtime_assignee(path: &str) -> Option<&str> {
    let rest = path.strip_prefix("/artifacts/runtime/user/")?;
    let assignee_id = rest.split('/').next()?;
    if assignee_id.is_empty() { None } else { Some(assignee_id) }
}

/// Check if a session has access to a specific runtime assignee's artifacts.
///
/// Compares the session's `userId` with the `assignee_id` extracted from the URL path.
/// If they match, the user is accessing their own runtime content (self-access allowed).
/// If they differ, the session is attempting to access another user's artifacts (denied).
///
/// Planet owners bypass this check entirely (access all).
///
/// **Fail-closed**: Redis errors → access denied.
pub async fn check_runtime_access(
    state: &AppState,
    session_id: &str,
    assignee_id: &str,
) -> bool {
    let mut conn = state.redis_cm.clone();

    // Check if user is the planet owner (has access to all artifacts).
    let is_owner_key = format!("state:session:{}:is_owner", session_id);
    let is_owner: Option<String> = redis::cmd("GET")
        .arg(&is_owner_key)
        .query_async(&mut conn)
        .await
        .unwrap_or(None);

    if let Some(ref val) = is_owner {
        if val == "true" {
            debug!("[RuntimeFileServer] Runtime access allowed: session owner");
            return true;
        }
    }

    // Self-access check: compare the session's userId with the assignee_id from the URL path.
    //
    // Runtime artifacts live at /runtime/user/{assignee_id}/contents/{cell_id}/{filename}.
    // The assignee_id (UUID from the URL) identifies which user owns the artifact.
    // To allow access, the session's userId must match the assignee_id (self-access).
    //
    // This replaces the old SISMEMBER check which incorrectly compared assignee_id (UUID)
    // against the allowed_artifacts set (which contains cell type slugs, not UUIDs).
    let session_key = format!("state:session:{}", session_id);
    // DIAG [3d-mesh-guest-403-render]: Log context before self-access check
    warn!(
        "[RuntimeFileServer-DIAG] Self-access check: session_id={}, assignee_id={}, \
         is_owner={:?}, reading key='{}'",
        session_id, assignee_id, is_owner, session_key,
    );
    let session_data: Option<String> = redis::cmd("GET")
        .arg(&session_key)
        .query_async(&mut conn)
        .await
        .unwrap_or(None);

    match session_data {
        Some(json_str) => {
            match serde_json::from_str::<serde_json::Value>(&json_str) {
                Ok(val) => {
                    let user_id = val.get("userId").and_then(|v| v.as_str());
                    match user_id {
                        Some(uid) if uid == assignee_id => {
                            debug!(
                                "[RuntimeFileServer] Runtime access allowed: self-access \
                                 (userId={} matches assignee_id={})",
                                uid, assignee_id
                            );
                            true
                        }
                        Some(uid) => {
                            debug!(
                                "[RuntimeFileServer] Runtime access DENIED: session userId={} \
                                 != assignee_id={}",
                                uid, assignee_id
                            );
                            false
                        }
                        None => {
                            warn!(
                                "[RuntimeFileServer] Runtime access DENIED: no userId in \
                                 session data: {}",
                                json_str
                            );
                            false
                        }
                    }
                }
                Err(e) => {
                    warn!(
                        "[RuntimeFileServer] Runtime access DENIED: failed to parse session \
                         JSON: {}",
                        e
                    );
                    false
                }
            }
        }
        None => {
            warn!(
                "[RuntimeFileServer] Runtime access DENIED: session data not found for \
                 session_id={}",
                session_id
            );
            // DIAG [3d-mesh-guest-403-render]: Check the alternative key session:{sid}
            // which IS created by auth_session_router.py (unlike state:session:{sid}).
            // This confirms the Redis key mismatch root cause.
            let alt_key = format!("session:{}", session_id);
            let alt_data: Option<String> = redis::cmd("GET")
                .arg(&alt_key)
                .query_async(&mut conn)
                .await
                .unwrap_or(None);
            warn!(
                "[RuntimeFileServer-DIAG] Alternative key '{}' check: {}",
                alt_key,
                if alt_data.is_some() {
                    format!("EXISTS (len={}, prefix='{}')",
                        alt_data.as_ref().unwrap().len(),
                        &alt_data.as_ref().unwrap()[..std::cmp::min(80, alt_data.as_ref().unwrap().len())])
                } else {
                    "NIL".to_string()
                }
            );
            false
        }
    }
}

/// Check if a session has access to a specific viewer.
///
/// Reads Redis state keys written by `auth_session_router.py:bind_session()`:
/// - `state:session:{sessionId}:is_owner` → if "true", owner has access to all viewers.
/// - `state:session:{sessionId}:allowed_artifacts` → SISMEMBER check for guest allowances.
///
/// **Fail-closed**: If Redis errors, access is denied.
pub async fn check_viewer_access(
    state: &AppState,
    session_id: &str,
    viewer_id: &str,
) -> bool {
    let mut conn = state.redis_cm.clone();

    // Check if user is the planet owner (has access to all viewers)
    let is_owner_key = format!("state:session:{}:is_owner", session_id);
    let is_owner: Option<String> = redis::cmd("GET")
        .arg(&is_owner_key)
        .query_async(&mut conn)
        .await
        .unwrap_or(None);

    if let Some(ref val) = is_owner {
        if val == "true" {
            debug!("[AuthProxy] Viewer '{}' allowed: session owner", viewer_id);
            return true;
        }
    }

    // Check guest allowance via Redis Set membership
    let allowances_key = format!("state:session:{}:allowed_artifacts", session_id);
    let is_allowed: bool = redis::cmd("SISMEMBER")
        .arg(&allowances_key)
        .arg(viewer_id)
        .query_async(&mut conn)
        .await
        .unwrap_or(false);  // fail-closed: Redis error → deny

    debug!(
        "[AuthProxy] Viewer '{}' check: is_allowed={} (session={})",
        viewer_id, is_allowed, session_id
    );
    is_allowed
}

/// Serve a file from disk with streaming body and appropriate Content-Type.
///
/// Uses `tokio::fs::File` + `ReaderStream` for **zero-copy streaming**:
/// the file is read in chunks (64 KiB default) and streamed directly to the
/// HTTP client without loading the entire file into memory.
///
/// This is critical for large binary artifacts (e.g. 50MB .glb files) to
/// prevent memory exhaustion under concurrent WAN requests.
pub async fn serve_file(file_path: &Path) -> Response {
    match fs::File::open(file_path).await {
        Ok(file) => {
            let content_type = match file_path.extension().and_then(|e| e.to_str()) {
                Some("glb") => "model/gltf-binary",
                Some("gltf") => "model/gltf+json",
                Some("png") => "image/png",
                Some("jpg") | Some("jpeg") => "image/jpeg",
                Some("gif") => "image/gif",
                Some("svg") => "image/svg+xml",
                Some("ico") => "image/x-icon",
                Some("woff") => "font/woff",
                Some("woff2") => "font/woff2",
                Some("mp3") => "audio/mpeg",
                Some("mp4") => "video/mp4",
                Some("webm") => "video/webm",
                Some("wasm") => "application/wasm",
                Some("pdf") => "application/pdf",
                Some("zip") => "application/zip",
                _ => "application/octet-stream",
            };

            // Create a streaming body from the file reader.
            // ReaderStream reads in 64 KiB chunks by default, so even a 50MB
            // .glb file is never fully loaded into memory.
            let stream = ReaderStream::new(file);
            let body = Body::from_stream(stream);

            let mut resp = Response::new(body);
            *resp.status_mut() = StatusCode::OK;
            resp.headers_mut().insert(
                axum::http::header::CONTENT_TYPE,
                axum::http::HeaderValue::from_static(content_type),
            );
            resp
        }
        Err(e) => {
            error!(
                "[FileServer] Failed to open file '{}': {}",
                file_path.display(),
                e
            );
            build_file_server_error(StatusCode::NOT_FOUND)
        }
    }
}

/// Build a 302 redirect response to the given location.
pub fn build_redirect_response(location: &str) -> Response {
    let mut resp = Response::new(Body::empty());
    *resp.status_mut() = StatusCode::FOUND;
    resp.headers_mut().insert(
        HeaderName::from_static("location"),
        HeaderValue::from_str(location).unwrap(),
    );
    resp
}

/// Build a minimal JSON error response.
fn build_file_server_error(status: StatusCode) -> Response {
    let reason = status.canonical_reason().unwrap_or("Error");
    let body = serde_json::json!({ "error": reason }).to_string();
    let mut resp = Response::new(Body::from(body));
    *resp.status_mut() = status;
    resp.headers_mut().insert(
        axum::http::header::CONTENT_TYPE,
        axum::http::HeaderValue::from_static("application/json"),
    );
    resp
}

// ─── Unit tests ───────────────────────────────────────────────────────────
#[cfg(test)]
mod tests {
    use super::*;
    use std::path::Path;

    #[test]
    fn test_resolve_artifact_path_valid() {
        // This test requires the file to exist on disk.
        // Run in the context where /app/artifacts or a test fixture dir exists.
        // For now, verify the function handles non-existent paths correctly.
        let result = resolve_artifact_path("/tmp", "/artifacts/nonexistent/file.glb");
        assert!(matches!(result, ArtifactResolution::NotFound));
    }

    #[test]
    fn test_resolve_artifact_path_strip_prefix_fail() {
        // Path without /artifacts/ prefix → NotFound
        let result = resolve_artifact_path("/app/artifacts", "/etc/passwd");
        assert!(matches!(result, ArtifactResolution::NotFound));
    }

    #[test]
    fn test_extract_runtime_assignee_basic() {
        assert_eq!(
            extract_runtime_assignee("/artifacts/runtime/user/550e8400/contents/x/model.glb"),
            Some("550e8400")
        );
    }

    #[test]
    fn test_extract_runtime_assignee_no_user_prefix() {
        assert_eq!(
            extract_runtime_assignee("/artifacts/canonical/viewers/gallery/chair.glb"),
            None
        );
    }

    #[test]
    fn test_extract_runtime_assignee_empty() {
        assert_eq!(
            extract_runtime_assignee("/artifacts/runtime/user/"),
            None
        );
    }

    #[test]
    fn test_extract_runtime_assignee_root() {
        assert_eq!(extract_runtime_assignee("/"), None);
    }

    #[test]
    fn test_serve_file_not_found() {
        let result = serve_file(Path::new("/tmp/nonexistent-file-for-test-12345.glb")).await;
        assert_eq!(result.status(), StatusCode::NOT_FOUND);
    }
}
