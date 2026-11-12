//! File serving for canonical and runtime artifacts.
//!
//! The Auth Proxy (Rust/tokio) serves binary artifacts (.glb, .png, etc.)
//! directly from disk using async file I/O, bypassing Vite entirely.
//!
//! This module owns the *primitives* — decoding, path resolution, MIME, streaming.
//! The *decisions* live with the routes that use them: `proxy::runtime_server`
//! (the runtime RBAC gate and its two deliveries) and `proxy::canonical_server`
//! (canonical binaries).

use std::path::Path;

use axum::{
    body::Body,
    http::{HeaderName, HeaderValue, StatusCode},
    response::Response,
};
use tokio::fs;
use tokio_util::io::ReaderStream;
use tracing::{debug, error, warn};

use crate::proxy::add_cors_headers;
use crate::AppState;

/// Root of the artifact tree inside the container (mounted read-only).
///
/// Both artifact servers resolve against this base, so classification, the RBAC
/// gate and the bytes on disk all describe the same file.
pub const ARTIFACTS_BASE: &str = "/app/artifacts";

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

/// Decode percent-encoded sequences in a URL path segment.
///
/// Converts `%XX` sequences to their decoded byte value (e.g. `%20` → space,
/// `%2F` → `/`). Handles multi-byte UTF-8 sequences (e.g. `%C3%A1` → `á`).
///
/// **Backward compatibility**: If any percent sequence is malformed (a lone `%`,
/// or `%` followed by non-hex characters), the original string is returned
/// unchanged so existing behavior is preserved.
///
/// Shared with the ingress: the query-free path check (`proxy::normalize_ingress_path`)
/// and the runtime slug derivation (`proxy::runtime_server`) must decode exactly
/// the way path resolution does, or a path could be authorized as one resource
/// and read as another.
pub(crate) fn percent_decode_path(path: &str) -> String {
    if !path.contains('%') {
        return path.to_string();
    }

    let mut bytes: Vec<u8> = Vec::with_capacity(path.len());
    let mut chars = path.chars();

    while let Some(c) = chars.next() {
        if c == '%' {
            let hex_chars: Vec<char> = chars.by_ref().take(2).collect();
            if hex_chars.len() < 2 {
                // Truncated: lone % at end — return original unchanged
                return path.to_string();
            }
            let hex_str: String = hex_chars.into_iter().collect();
            match u8::from_str_radix(&hex_str, 16) {
                Ok(byte) => bytes.push(byte),
                Err(_) => {
                    // Invalid hex digits — return original unchanged
                    return path.to_string();
                }
            }
        } else {
            // Preserve non-ASCII as UTF-8 bytes
            let mut buf = [0u8; 4];
            let encoded = c.encode_utf8(&mut buf);
            bytes.extend_from_slice(encoded.as_bytes());
        }
    }

    // Decode the byte sequence as UTF-8; fall back to original on failure
    String::from_utf8(bytes).unwrap_or_else(|_| path.to_string())
}

/// Resolve a safe filesystem path for an artifact request.
///
/// Canonical artifacts are at `/app/artifacts/{rel_path}`. This function:
/// 1. Strips the `/artifacts/` prefix.
/// 2. URL-decodes the relative path (handles `%20`, `%C3%A1`, etc.).
/// 3. Joins with the base directory.
/// 4. Uses `canonicalize()` to resolve symlinks and `..` segments.
/// 5. Verifies the resolved path is within the base directory.
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

    // URL-decode the relative path to handle spaces and special chars in
    // filenames (e.g. "boneca%20roxa.png" → "boneca roxa.png").
    let decoded = percent_decode_path(rel);
    let joined = base.join(&decoded);
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

/// Check if a session has access to a specific viewer.
///
/// Reads Redis state keys written by `auth_session_router.py:bind_session()`:
/// - `state:session:{sessionId}:is_owner` → if "true", owner has access to all viewers.
/// - `state:session:{sessionId}:allowed_artifacts` → SISMEMBER check for guest allowances.
///
/// **Fail-closed**: If Redis errors, access is denied.
///
/// ⚠️ **Currently unreachable over HTTP.** Its only caller is the `ViteProtected`
/// arm of the ingress `match`, and every path that produces `ViteProtected`
/// (`is_public_path` → `PUBLIC_PREFIXES`) returns earlier, in the public-path
/// short-circuit — so the "viewer denied → planet-hall" redirect never fires. The
/// WebSocket `ViteProtected` arm is a different arm and is live. Kept as-is;
/// tracked as technical debt (see `AUTH_PROXY_GATEWAY_FLOW.md`).
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
pub async fn serve_file(file_path: &Path, origin: Option<&str>, host: Option<&str>) -> Response {
    match fs::File::open(file_path).await {
        Ok(file) => {
            // DIAG: Log file metadata when serving
            match file.metadata().await {
                Ok(meta) => debug!("[DIAG-DOWNLOAD] serve_file: path={}, exists=true, size={}", file_path.display(), meta.len()),
                Err(_) => debug!("[DIAG-DOWNLOAD] serve_file: path={}, exists=true, metadata_unavailable", file_path.display()),
            }

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
            // Add CORS headers so cross-origin requests (e.g. from cockpit at
            // hub-staging.scareverse.net) can read the file response. Uses dynamic
            // same-origin validation: origin hostname is compared against the Host
            // header instead of a static allowlist.
            add_cors_headers(&mut resp, origin, host);
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
    fn test_percent_decode_noop_when_no_pct() {
        // No percent sequences → returned as-is
        assert_eq!(percent_decode_path("simple_file.png"), "simple_file.png");
        assert_eq!(percent_decode_path(""), "");
    }

    #[test]
    fn test_percent_decode_space() {
        // %20 → space
        assert_eq!(
            percent_decode_path("runtime/user/abc/boneca%20roxa.png"),
            "runtime/user/abc/boneca roxa.png"
        );
    }

    #[test]
    fn test_percent_decode_multi_byte() {
        // %C3%A1 → á (U+00E1, 2-byte UTF-8)
        let decoded = percent_decode_path("caf%C3%A9.png");
        assert_eq!(decoded, "caf\u{e9}.png");
    }

    #[test]
    fn test_percent_decode_mixed() {
        // Mix of spaces and regular chars
        let decoded = percent_decode_path("my%20folder/nested%20file.glb");
        assert_eq!(decoded, "my folder/nested file.glb");
    }

    #[test]
    fn test_percent_decode_malformed_lone_pct() {
        // Lone % at end → return original unchanged
        let original = "file%";
        assert_eq!(percent_decode_path(original), original);
    }

    #[test]
    fn test_percent_decode_malformed_invalid_hex() {
        // %XY where XY is not valid hex → return original unchanged
        let original = "file%ZZ.png";
        assert_eq!(percent_decode_path(original), original);
    }

    #[test]
    fn test_percent_decode_truncated_hex() {
        // % followed by single valid hex char → truncated → return original
        let original = "file%2";
        assert_eq!(percent_decode_path(original), original);
    }

    #[tokio::test]
    async fn test_serve_file_not_found() {
        let result = serve_file(Path::new("/tmp/nonexistent-file-for-test-12345.glb"), None, None).await;
        assert_eq!(result.status(), StatusCode::NOT_FOUND);
    }
}
