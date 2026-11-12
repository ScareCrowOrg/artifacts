//! Runtime artifact delivery — ONE authorization gate, TWO ways to deliver.
//!
//! Every `/artifacts/runtime/**` request lands here regardless of extension:
//! the extension never decides *whether* the request is authorized, only *how*
//! the authorized bytes are delivered.
//!
//! ```text
//! /artifacts/runtime/**  →  authorize_runtime_access()        (the ONE rule)
//!                              ├─ Err(status) → 403, never a fallback
//!                              └─ Ok(())      → deliver
//!                                   ├─ RuntimeFileServer → serve_runtime_artifact (raw bytes)
//!                                   └─ RuntimeCodeProxy  → proxy_runtime_code     (Vite compiles)
//! ```
//!
//! # Why the gate lives here
//! Runtime artifacts are namespaced per user (`runtime/user/{id}/...`). That
//! segment identifies the **creator of the record** — it is an address, not a
//! permission. Access is granted by three independent facts, checked in this
//! order: the session is the **owner**, the owner granted an **allowance** for
//! this artifact, or the request is **self-access**. Anything else is denied.
//!
//! # Fail-closed
//! Every Redis read that fails leaves its fact `false`, and a path that yields no
//! slug never consults the allowance set at all. An unreadable state therefore
//! denies; it never falls through to an upstream that would serve the bytes.

use axum::{
    extract::Request,
    http::{header, StatusCode},
    response::Response,
};
use tracing::{debug, info, warn};

use crate::file_server::{
    extract_runtime_assignee, percent_decode_path, resolve_artifact_path, serve_file,
    ArtifactResolution, ARTIFACTS_BASE,
};
use crate::upstream::resolve_proxy_upstream;
use crate::AppState;

use super::session::extract_sub_from_jwt;
use super::{build_error_response, proxy_to_upstream};

/// Facts the gate decides on, gathered from Redis and the request.
///
/// Kept separate from the I/O so the decision table is exhaustively testable
/// without Redis.
#[derive(Debug, Default, Clone, Copy)]
struct RuntimeAccessFacts {
    /// Session belongs to the planet owner (`state:session:{sid}:is_owner`).
    is_owner: bool,
    /// The owner granted an allowance for the artifact slug addressed by the path.
    has_allowance: bool,
    /// The session's user id equals the assignee in the path (own namespace).
    is_self: bool,
}

/// The runtime access rule: owner · allowance · self-access, else 403.
///
/// The three paths are independent — an allowance does not require self-access,
/// and an owner does not need one. All-false means deny, which is what a Redis
/// failure produces.
fn evaluate_runtime_access(facts: RuntimeAccessFacts) -> Result<(), StatusCode> {
    if facts.is_owner || facts.has_allowance || facts.is_self {
        return Ok(());
    }
    Err(StatusCode::FORBIDDEN)
}

/// Authorize a `/artifacts/runtime/**` request. **The** implementation of the rule.
///
/// Called by both deliveries ([`serve_runtime_artifact`] and [`proxy_runtime_code`]);
/// there is no second copy of the decision anywhere in the ingress.
///
/// Three paths, in this order:
///   1. **owner** — `state:session:{sid}:is_owner == "true"`
///   2. **allowance** — `SISMEMBER state:session:{sid}:allowed_artifacts {slug}`
///   3. **self-access** — session `userId` == the assignee segment of the path
///
/// A request with no session cookie (cross-origin download) has no session state
/// to consult, so it can only be self-access — proven by the `sub` claim of the
/// Bearer token the Backend already validated. Such a request is never granted by
/// an allowance: the allowance set is per session, and there is no session.
///
/// `slug` is `None` when the path does not address a cell type: the allowance
/// check is then skipped (fail-closed) instead of guessing.
pub(super) async fn authorize_runtime_access(
    state: &AppState,
    session_id: Option<&str>,
    auth_header: Option<&str>,
    slug: Option<&str>,
    assignee_id: Option<&str>,
) -> Result<(), StatusCode> {
    // No assignee → the path is not a runtime artifact address at all.
    let Some(assignee) = assignee_id else {
        warn!("[RuntimeServer] Denied: no assignee in path (unexpected runtime shape)");
        return Err(StatusCode::FORBIDDEN);
    };

    if let Some(sid) = session_id {
        let facts = gather_session_facts(state, sid, slug, assignee).await;
        debug!(
            "[RuntimeServer] Gate facts: is_owner={}, has_allowance={}, is_self={} (slug={:?})",
            facts.is_owner, facts.has_allowance, facts.is_self, slug
        );
        let verdict = evaluate_runtime_access(facts);
        if verdict.is_err() {
            warn!(
                "[RuntimeServer] Denied: session {} is not owner, has no allowance for {:?}, \
                 and is not assignee {}",
                sid, slug, assignee
            );
        }
        return verdict;
    }

    // No session cookie — Bearer-only cross-origin download: self-access only.
    let is_self = auth_header
        .and_then(|value| value.strip_prefix("Bearer "))
        .and_then(extract_sub_from_jwt)
        .map_or(false, |user_id| user_id == assignee);
    debug!("[RuntimeServer] Gate facts (bearer): is_self={}", is_self);
    evaluate_runtime_access(RuntimeAccessFacts {
        is_self,
        ..Default::default()
    })
}

/// Read the three facts from Redis for a cookie-borne session.
///
/// Every read is fail-closed: an error leaves its fact `false`.
async fn gather_session_facts(
    state: &AppState,
    session_id: &str,
    slug: Option<&str>,
    assignee: &str,
) -> RuntimeAccessFacts {
    let mut conn = state.redis_cm.clone();

    // 1. Owner bypass.
    let is_owner = redis::cmd("GET")
        .arg(format!("state:session:{}:is_owner", session_id))
        .query_async::<_, Option<String>>(&mut conn)
        .await
        .ok()
        .flatten()
        .map_or(false, |value| value == "true");

    // 2. Allowance pre-loaded by the Backend at session-bind time
    //    (`state:session:{sid}:allowed_artifacts` holds cell type slugs).
    let has_allowance = match slug {
        Some(slug) => redis::cmd("SISMEMBER")
            .arg(format!("state:session:{}:allowed_artifacts", session_id))
            .arg(slug)
            .query_async::<_, bool>(&mut conn)
            .await
            .unwrap_or(false),
        None => false,
    };

    // 3. Self-access. `session:{sid}` is the SSOT session record written by
    //    bind_session(); there is no separate `state:session:{sid}` copy.
    let is_self = redis::cmd("GET")
        .arg(format!("session:{}", session_id))
        .query_async::<_, Option<String>>(&mut conn)
        .await
        .ok()
        .flatten()
        .and_then(|raw| serde_json::from_str::<serde_json::Value>(&raw).ok())
        .and_then(|value| {
            value
                .get("userId")
                .and_then(|user_id| user_id.as_str())
                .map(str::to_owned)
        })
        .map_or(false, |user_id| user_id == assignee);

    RuntimeAccessFacts {
        is_owner,
        has_allowance,
        is_self,
    }
}

/// Derive the artifact slug from a runtime path.
///
/// Shape: `[/artifacts]/runtime/user/{assignee}/cell_types/{slug}[/...]`.
/// The `[artifacts]` prefix is optional and empty segments are ignored, so the
/// bare-`/runtime/...` form the ingress accepts and a doubled slash both resolve
/// to the same slug.
///
/// Returns `None` when the path does not address a cell type, or when the slug
/// segment is a structural `.`/`..` (also in percent-encoded form). A `None` here
/// makes the gate skip the allowance check — an unidentifiable path is never
/// granted by an allowance.
///
/// # Contract with the Backend
/// The same rule exists in Python (`backend/app/routers/auth_session_router.py`,
/// `_extract_runtime_slug`) because the Backend RBAC layer decides on the same
/// URI. Both sides are validated against the SAME vector file
/// (`tests/fixtures/runtime_slug_vectors.json`): the file is the contract, neither
/// language is the reference, and neither may edit a vector alone.
pub(super) fn extract_runtime_artifact_slug(path: &str) -> Option<&str> {
    let segments: Vec<&str> = path.split('/').filter(|s| !s.is_empty()).collect();
    // Optional `/artifacts` prefix.
    let base = if segments.first() == Some(&"artifacts") { 1 } else { 0 };

    if segments.get(base) != Some(&"runtime") {
        return None;
    }
    if segments.get(base + 1) != Some(&"user") {
        return None;
    }
    // base + 2 is the assignee id — the address of the creator, not a permission.
    if segments.get(base + 3) != Some(&"cell_types") {
        return None;
    }

    let slug = *segments.get(base + 4)?;
    if is_structural_segment(slug) {
        return None;
    }
    Some(slug)
}

/// A segment that would change the structure of the path if it were decoded.
///
/// `.` and `..` move the path to another resource, and an encoded `/` splits one
/// segment into two — both are rejected rather than resolved, so that the path
/// that is authorized is the path that is read.
pub(super) fn is_structural_segment(segment: &str) -> bool {
    let decoded = percent_decode_path(segment);
    decoded == "." || decoded == ".." || decoded.contains('/')
}

/// Deliver a runtime artifact as raw bytes from disk.
///
/// The safe default: any extension that is not explicitly known to be compiled
/// (see `classify::is_compilable_artifact`) is streamed with a non-renderable
/// MIME type, i.e. it downloads instead of executing on the planet origin.
pub(super) async fn serve_runtime_artifact(
    state: &AppState,
    req: Request,
    path: &str,
    session_id: Option<&str>,
    auth_header: Option<&str>,
) -> Response {
    let assignee_id = extract_runtime_assignee(path);
    let slug = extract_runtime_artifact_slug(path);

    if let Err(status) =
        authorize_runtime_access(state, session_id, auth_header, slug, assignee_id).await
    {
        return build_error_response(status);
    }

    match resolve_artifact_path(ARTIFACTS_BASE, path) {
        ArtifactResolution::Found(file_path) => {
            debug!(
                "[RuntimeServer] Serving runtime artifact: {} (path: {})",
                path,
                file_path.display()
            );
            let origin = req.headers().get(header::ORIGIN).and_then(|v| v.to_str().ok());
            let host = req.headers().get(header::HOST).and_then(|v| v.to_str().ok());
            serve_file(&file_path, origin, host).await
        }
        ArtifactResolution::PathTraversal => {
            warn!("[RuntimeServer] Path traversal BLOCKED: {}", path);
            build_error_response(StatusCode::BAD_REQUEST)
        }
        ArtifactResolution::NotFound => {
            warn!("[RuntimeServer] Runtime artifact not found: {}", path);
            build_error_response(StatusCode::NOT_FOUND)
        }
    }
}

/// Deliver runtime code through Vite, which compiles it.
///
/// Same gate as the raw delivery — the only difference is the downstream. The
/// path is forwarded unchanged to the Backend, which is the WAN buffer in front
/// of Vite and re-sends the same `/artifacts/...` path
/// (`backend/app/routers/artifacts_proxy_router.py`).
pub(super) async fn proxy_runtime_code(
    state: &AppState,
    req: Request,
    path: &str,
    full_path: &str,
    session_id: Option<&str>,
    auth_header: Option<&str>,
) -> Response {
    let assignee_id = extract_runtime_assignee(path);
    let slug = extract_runtime_artifact_slug(path);

    if let Err(status) =
        authorize_runtime_access(state, session_id, auth_header, slug, assignee_id).await
    {
        return build_error_response(status);
    }

    match resolve_proxy_upstream(state).await {
        Ok(upstream) => {
            info!(
                "[RuntimeServer] Runtime code authorized, proxying {} → {}",
                path, upstream
            );
            proxy_to_upstream(state, req, full_path, &upstream, None).await
        }
        Err(status) => build_error_response(status),
    }
}

// ─── Unit tests ───────────────────────────────────────────────────────────
#[cfg(test)]
mod tests {
    use super::*;

    /// The single source of truth for the slug rule, shared with the Python suite.
    const SLUG_VECTOR_FIXTURE: &str = concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/tests/fixtures/runtime_slug_vectors.json"
    );

    // ── Gate decision table ──────────────────────────────────────────────

    #[test]
    fn test_gate_owner_allows() {
        let facts = RuntimeAccessFacts {
            is_owner: true,
            ..Default::default()
        };
        assert_eq!(evaluate_runtime_access(facts), Ok(()));
    }

    #[test]
    fn test_gate_allowance_allows() {
        let facts = RuntimeAccessFacts {
            has_allowance: true,
            ..Default::default()
        };
        assert_eq!(evaluate_runtime_access(facts), Ok(()));
    }

    #[test]
    fn test_gate_self_access_allows() {
        let facts = RuntimeAccessFacts {
            is_self: true,
            ..Default::default()
        };
        assert_eq!(evaluate_runtime_access(facts), Ok(()));
    }

    #[test]
    fn test_gate_no_path_denies() {
        // This is also the Redis-failure shape: every fact false → 403.
        assert_eq!(
            evaluate_runtime_access(RuntimeAccessFacts::default()),
            Err(StatusCode::FORBIDDEN)
        );
    }

    #[test]
    fn test_gate_allowance_is_honoured_without_self_access() {
        // The gap this feature closes: a guest whose only fact is the allowance.
        let facts = RuntimeAccessFacts {
            is_owner: false,
            has_allowance: true,
            is_self: false,
        };
        assert_eq!(evaluate_runtime_access(facts), Ok(()));
    }

    // ── Slug derivation (shared conformance vectors) ─────────────────────

    #[test]
    fn test_extract_runtime_artifact_slug_conformance_vectors() {
        let raw = std::fs::read_to_string(SLUG_VECTOR_FIXTURE)
            .expect("shared slug vector fixture must be readable");
        let parsed: serde_json::Value =
            serde_json::from_str(&raw).expect("slug vector fixture must be valid JSON");
        let vectors = parsed
            .as_array()
            .expect("slug vector fixture must be a JSON array");
        assert!(!vectors.is_empty(), "slug vector fixture must not be empty");

        for vector in vectors {
            let input = vector
                .get("input")
                .and_then(|v| v.as_str())
                .expect("each vector needs an 'input' string");
            let expect = vector.get("expect").and_then(|v| v.as_str());
            assert_eq!(
                extract_runtime_artifact_slug(input),
                expect,
                "slug mismatch for input {input:?}"
            );
        }
    }

    #[test]
    fn test_extract_runtime_artifact_slug_canonical_shape() {
        assert_eq!(
            extract_runtime_artifact_slug("/artifacts/runtime/user/u1/cell_types/my-cell/type.json"),
            Some("my-cell")
        );
    }

    #[test]
    fn test_extract_runtime_artifact_slug_never_returns_structural_segment() {
        // A slug is used as a lookup key for an allowance — it must never be a
        // segment that moves the path somewhere else.
        assert_eq!(
            extract_runtime_artifact_slug("/artifacts/runtime/user/u1/cell_types/../x/type.json"),
            None
        );
        assert_eq!(
            extract_runtime_artifact_slug("/artifacts/runtime/user/u1/cell_types/%2e%2e/x"),
            None
        );
    }

    #[test]
    fn test_extract_runtime_artifact_slug_legit_dots_in_name() {
        // `foo..bar` is a legitimate folder name — only exact `.`/`..` are rejected.
        assert_eq!(
            extract_runtime_artifact_slug("/artifacts/runtime/user/u1/cell_types/foo..bar/type.json"),
            Some("foo..bar")
        );
    }

    // ── Structural segment detection ─────────────────────────────────────

    #[test]
    fn test_is_structural_segment() {
        assert!(is_structural_segment("."));
        assert!(is_structural_segment(".."));
        assert!(is_structural_segment("%2e"));
        assert!(is_structural_segment("%2E%2E"));
        // Encoded separator: one segment would become two once decoded.
        assert!(is_structural_segment("a%2Fb"));
        assert!(is_structural_segment("%2e%2e%2f"));
    }

    #[test]
    fn test_is_structural_segment_legit_names() {
        assert!(!is_structural_segment("foo..bar"));
        assert!(!is_structural_segment("my-cell"));
        assert!(!is_structural_segment("..foo"));
        assert!(!is_structural_segment("foo.."));
        assert!(!is_structural_segment("boneca%20roxa.png"));
    }
}
