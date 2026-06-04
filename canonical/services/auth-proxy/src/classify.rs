//! Route classification — separates incoming request paths into routing decisions.
//!
//! # Flow
//! 1. `classify_route()` inspects the raw URL path.
//! 2. Returns a `RouteDecision` variant that tells `request_handler()` which
//!    upstream or handler to use.
//! 3. Binary artifacts (.glb, .png, etc.) bypass Vite entirely — Rust reads disk.
//! 4. Runtime content goes through RBAC check before file serving.
//! 5. Code + HMR goes through FastAPI (Python async buffer) to Vite.

use axum::http::StatusCode;
use axum::response::IntoResponse;
use tracing::info;

/// Redis heartbeat key registered by Auth Proxy to signal readiness.
pub const HEARTBEAT_KEY: &str = "state:service:auth-proxy:available";

/// Viewer paths that are publicly accessible without authentication.
///
/// These are standalone viewers served directly by Vite that do not require
/// any session validation (e.g. Planet Hall — a public landing viewer).
pub const PUBLIC_PREFIXES: &[&str] = &[
    "/artifacts/canonical/viewers/planet-hall",
];

/// Routing decision for an incoming request.
#[derive(Debug, Clone, Copy)]
pub enum RouteDecision {
    BackendBypass,
    BackendProtected,
    ViteProtected,
    /// Path starts with `/wss/` — resolved via Redis SCAN at request time.
    WssProxy,
    /// Code + HMR → proxy via FastAPI (Python async) to Vite.
    FastApiProxy,
    /// Canonical binary assets (.glb, .png, etc.) — Rust reads from disk directly.
    FileServer,
    /// Runtime content with RBAC check — Rust reads from disk + Redis.
    RuntimeFileServer,
    Deny,
}

/// Health check handler — always returns 200 OK.
///
/// Used by docker-compose `healthcheck` and by Traefik service discovery.
pub async fn health_handler() -> impl IntoResponse {
    (StatusCode::OK, "OK")
}

/// Check whether a request path is a binary artifact (does not need compilation).
///
/// Binary artifacts are served directly by Auth Proxy (Rust) without involving Vite:
/// - 3D models (.glb, .gltf)
/// - Images (.png, .jpg, .jpeg, .gif, .svg, .ico)
/// - Fonts (.woff, .woff2)
/// - Media (.mp3, .mp4, .webm)
/// - WebAssembly (.wasm)
/// - Documents (.pdf)
/// - Archives (.zip)
pub fn is_binary_artifact(path: &str) -> bool {
    let extensions = [
        ".glb", ".gltf", ".png", ".jpg", ".jpeg", ".gif",
        ".svg", ".ico", ".woff", ".woff2", ".mp3", ".mp4",
        ".webm", ".wasm", ".pdf", ".zip",
    ];
    extensions.iter().any(|ext| path.ends_with(ext))
}

pub fn classify_route(path: &str) -> RouteDecision {
    if path == "/api/v1/auth/session-bind" || path == "/api/ws/rpc" {
        RouteDecision::BackendBypass
    } else if path.starts_with("/wss/") {
        RouteDecision::WssProxy
    } else if path.starts_with("/api/") {
        RouteDecision::BackendProtected
    // Public viewers (planet-hall) bypass all auth — proxy directly to Vite.
    } else if is_public_path(path) {
        RouteDecision::ViteProtected
    // Canonical binary assets → Rust reads from disk directly (no Vite).
    } else if path.starts_with("/artifacts/canonical/") && is_binary_artifact(path) {
        RouteDecision::FileServer
    // Runtime content → Rust reads from disk with RBAC check via Redis.
    } else if path.starts_with("/artifacts/runtime/") {
        RouteDecision::RuntimeFileServer
    // Code + HMR → proxy via FastAPI (Python async buffers WAN traffic).
    } else if path.starts_with("/artifacts/") {
        RouteDecision::FastApiProxy
    // Vite internals and HMR WebSocket → proxy via FastAPI.
    } else if path.starts_with("/@vite/") || path.starts_with("/.vite/") || path.starts_with("/__vite") {
        RouteDecision::FastApiProxy
    } else {
        // Everything else → FastAPI proxy (Vite through Python async buffer).
        RouteDecision::FastApiProxy
    }
}

/// Extract the WSS alias from a `/wss/{alias}[/...]` path.
///
/// Returns `None` if the path does not start with `/wss/` or has no alias segment.
pub fn extract_wss_alias(path: &str) -> Option<&str> {
    let rest = path.strip_prefix("/wss/")?;
    // Alias is the first path segment after `/wss/`.
    let alias = rest.split('/').next()?;
    if alias.is_empty() {
        None
    } else {
        Some(alias)
    }
}

/// Extract the viewer name from a path containing `/viewers/{viewerName}[/...]`.
///
/// Matches the first occurrence of `/viewers/` anywhere in the path, supporting
/// multiple staging contexts:
/// - `/viewers/{viewerName}` (Vue Router SPA route)
/// - `/artifacts/canonical/viewers/{viewerName}` (canonical viewer)
/// - `/artifacts/sandbox/viewers/{viewerName}` (sandbox draft)
/// - `/artifacts/runtime/user/{id}/viewers/{viewerName}` (user runtime)
///
/// Returns `None` if the path contains no `/viewers/` segment or has no viewer name.
pub fn extract_viewer_id(path: &str) -> Option<&str> {
    let pos = path.find("/viewers/")?;
    let rest = &path[pos + "/viewers/".len()..];
    let viewer_id = rest.split('/').next()?;
    if viewer_id.is_empty() { None } else { Some(viewer_id) }
}

/// Check whether a request path matches any public prefix.
///
/// Public prefixes bypass all auth checks and are proxied directly to Vite.
/// This enables standalone viewers (e.g. Planet Hall) to serve unauthenticated
/// users without requiring a session or viewer allowance.
pub fn is_public_path(path: &str) -> bool {
    PUBLIC_PREFIXES.iter().any(|prefix| path.starts_with(prefix))
}

// ─── Unit tests ───────────────────────────────────────────────────────────
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_classify_route_backend_bypass() {
        assert!(matches!(
            classify_route("/api/v1/auth/session-bind"),
            RouteDecision::BackendBypass
        ));
    }

    #[test]
    fn test_classify_route_protected_paths() {
        assert!(matches!(
            classify_route("/api/v1/models"),
            RouteDecision::BackendProtected
        ));
        // /viewers/* is now catch-all → FastApiProxy (through FastAPI to Vite for WAN buffering)
        assert!(matches!(
            classify_route("/viewers/dynamic-workspace"),
            RouteDecision::FastApiProxy
        ));
        // Root / is catch-all → FastApiProxy
        assert!(matches!(classify_route("/"), RouteDecision::FastApiProxy));
    }

    #[test]
    fn test_classify_route_vite_catch_all() {
        // Paths that are not /api/* or /artifacts/* are caught by catch-all → FastApiProxy.
        assert!(matches!(
            classify_route("/metrics"),
            RouteDecision::FastApiProxy
        ));
        assert!(matches!(
            classify_route("/sandbox/test"),
            RouteDecision::FastApiProxy
        ));
    }

    #[test]
    fn test_classify_route_artifacts_code_proxy() {
        // /artifacts/* code paths (non-binary, non-canonical, non-runtime) → FastApiProxy.
        assert!(matches!(
            classify_route("/artifacts/cell_types/png-generator/BaseCell.js"),
            RouteDecision::FastApiProxy
        ));
        assert!(matches!(
            classify_route("/artifacts/shared/utils/logger.ts"),
            RouteDecision::FastApiProxy
        ));
        assert!(matches!(
            classify_route("/artifacts/sandbox/test/View.vue"),
            RouteDecision::FastApiProxy
        ));
    }

    #[test]
    fn test_classify_route_artifacts_binary_file_server() {
        // Canonical binary artifacts → FileServer (Rust reads from disk).
        assert!(matches!(
            classify_route("/artifacts/canonical/viewers/gallery/chair.glb"),
            RouteDecision::FileServer
        ));
        assert!(matches!(
            classify_route("/artifacts/canonical/assets/logo.png"),
            RouteDecision::FileServer
        ));
        // Non-binary canonical paths (code) → FastApiProxy.
        assert!(matches!(
            classify_route("/artifacts/canonical/cell_types/x/View.vue"),
            RouteDecision::FastApiProxy
        ));
    }

    #[test]
    fn test_classify_route_runtime() {
        assert!(matches!(
            classify_route("/artifacts/runtime/user/550e8400/contents/x/model.glb"),
            RouteDecision::RuntimeFileServer
        ));
        assert!(matches!(
            classify_route("/artifacts/runtime/user/1234/viewers/my-viewer"),
            RouteDecision::RuntimeFileServer
        ));
    }

    #[test]
    fn test_classify_route_vite_internals() {
        assert!(matches!(
            classify_route("/@vite/client"),
            RouteDecision::FastApiProxy
        ));
        assert!(matches!(
            classify_route("/.vite/deps/vue.js"),
            RouteDecision::FastApiProxy
        ));
        assert!(matches!(
            classify_route("/__vite_hmr"),
            RouteDecision::FastApiProxy
        ));
        assert!(matches!(
            classify_route("/__vite_ping"),
            RouteDecision::FastApiProxy
        ));
    }

    #[test]
    fn test_classify_route_public_viewer() {
        assert!(matches!(
            classify_route("/artifacts/canonical/viewers/planet-hall"),
            RouteDecision::ViteProtected
        ));
        assert!(matches!(
            classify_route("/artifacts/canonical/viewers/planet-hall/index.html"),
            RouteDecision::ViteProtected
        ));
    }

    #[test]
    fn test_classify_route_artifacts_generic() {
        assert!(matches!(
            classify_route("/artifacts/any/future/path"),
            RouteDecision::FastApiProxy
        ));
        assert!(matches!(
            classify_route("/artifacts/"),
            RouteDecision::FastApiProxy
        ));
    }

    #[test]
    fn test_classify_route_wss_proxy() {
        assert!(matches!(
            classify_route("/wss/events"),
            RouteDecision::WssProxy
        ));
        assert!(matches!(
            classify_route("/wss/logs"),
            RouteDecision::WssProxy
        ));
        assert!(matches!(
            classify_route("/wss/unknown-alias"),
            RouteDecision::WssProxy
        ));
    }

    #[test]
    fn test_extract_wss_alias() {
        assert_eq!(extract_wss_alias("/wss/events"), Some("events"));
        assert_eq!(extract_wss_alias("/wss/logs"), Some("logs"));
        assert_eq!(extract_wss_alias("/wss/events/extra"), Some("events"));
        assert_eq!(extract_wss_alias("/wss/"), None);
        assert_eq!(extract_wss_alias("/api/v1"), None);
        assert_eq!(extract_wss_alias("/"), None);
    }

    #[test]
    fn test_extract_viewer_id_viewers_gallery() {
        assert_eq!(extract_viewer_id("/viewers/gallery"), Some("gallery"));
    }

    #[test]
    fn test_extract_viewer_id_with_extra_path() {
        assert_eq!(
            extract_viewer_id("/viewers/gallery/extra/path"),
            Some("gallery")
        );
    }

    #[test]
    fn test_extract_viewer_id_non_viewer_path() {
        assert_eq!(extract_viewer_id("/artifacts/canonical/..."), None);
    }

    #[test]
    fn test_extract_viewer_id_root() {
        assert_eq!(extract_viewer_id("/"), None);
    }

    #[test]
    fn test_extract_viewer_id_viewers_only() {
        assert_eq!(extract_viewer_id("/viewers/"), None);
    }

    #[test]
    fn test_extract_viewer_id_api_path() {
        assert_eq!(extract_viewer_id("/api/v1/auth/session-check"), None);
    }

    #[test]
    fn test_extract_viewer_id_canonical_artifact() {
        assert_eq!(
            extract_viewer_id("/artifacts/canonical/viewers/dynamic-workspace"),
            Some("dynamic-workspace")
        );
    }

    #[test]
    fn test_extract_viewer_id_sandbox_artifact() {
        assert_eq!(
            extract_viewer_id("/artifacts/sandbox/viewers/my-viewer"),
            Some("my-viewer")
        );
    }

    #[test]
    fn test_extract_viewer_id_runtime_artifact() {
        assert_eq!(
            extract_viewer_id("/artifacts/runtime/user/550e8400/viewers/my-viewer"),
            Some("my-viewer")
        );
    }

    #[test]
    fn test_extract_viewer_id_canonical_asset_subpath() {
        assert_eq!(
            extract_viewer_id("/artifacts/canonical/viewers/gallery/main.js"),
            Some("gallery")
        );
    }

    #[test]
    fn test_extract_viewer_id_non_viewer_segment() {
        assert_eq!(extract_viewer_id("/artifacts/viewers-images/cell.png"), None);
    }

    #[test]
    fn test_is_binary_artifact_glb() {
        assert!(is_binary_artifact("/artifacts/canonical/viewers/gallery/chair.glb"));
    }

    #[test]
    fn test_is_binary_artifact_png() {
        assert!(is_binary_artifact("/artifacts/canonical/assets/logo.png"));
    }

    #[test]
    fn test_is_binary_artifact_jpg() {
        assert!(is_binary_artifact("image.jpg"));
        assert!(is_binary_artifact("image.jpeg"));
    }

    #[test]
    fn test_is_binary_artifact_vue() {
        assert!(!is_binary_artifact("/artifacts/canonical/cell_types/x/View.vue"));
    }

    #[test]
    fn test_is_binary_artifact_ts() {
        assert!(!is_binary_artifact("/artifacts/shared/utils/logger.ts"));
    }

    #[test]
    fn test_is_binary_artifact_wasm() {
        assert!(is_binary_artifact("module.wasm"));
    }

    #[test]
    fn test_is_binary_artifact_pdf() {
        assert!(is_binary_artifact("document.pdf"));
    }

    #[test]
    fn test_is_binary_artifact_svg() {
        assert!(is_binary_artifact("icon.svg"));
    }

    #[test]
    fn test_is_binary_artifact_no_extension() {
        assert!(!is_binary_artifact("/artifacts/canonical/viewers/planet-hall"));
    }

    #[test]
    fn test_is_binary_artifact_woff() {
        assert!(is_binary_artifact("font.woff"));
        assert!(is_binary_artifact("font.woff2"));
    }

    #[test]
    fn test_is_binary_artifact_media() {
        assert!(is_binary_artifact("audio.mp3"));
        assert!(is_binary_artifact("video.mp4"));
        assert!(is_binary_artifact("video.webm"));
    }

    #[test]
    fn test_is_binary_artifact_zip() {
        assert!(is_binary_artifact("archive.zip"));
    }

}
