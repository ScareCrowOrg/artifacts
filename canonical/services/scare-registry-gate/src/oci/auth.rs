//! OCI Basic-Auth helpers.

use axum::body::Body;
use axum::http::{HeaderMap, Response, StatusCode};
use base64::{engine::general_purpose::STANDARD, Engine};

use crate::config::Config;
use crate::oci::types::oci_error_json;

/// Extract `(username, password)` from an `Authorization: Basic …` header.
/// Returns `None` when the header is absent, malformed, or not Basic scheme.
pub fn extract_basic_auth(headers: &HeaderMap) -> Option<(String, String)> {
    let auth = headers.get("Authorization")?.to_str().ok()?;
    let encoded = auth.strip_prefix("Basic ")?;
    let decoded = STANDARD.decode(encoded).ok()?;
    let decoded_str = String::from_utf8(decoded).ok()?;
    let (user, pass) = decoded_str.split_once(':')?;
    Some((user.to_owned(), pass.to_owned()))
}

/// Compare credentials against the registry configuration.
pub fn validate_credentials(user: &str, pass: &str, cfg: &Config) -> bool {
    user == cfg.registry_username && pass == cfg.registry_password
}

/// Build a 401 Unauthorized response with the required `WWW-Authenticate` header.
pub fn unauthorized_response() -> Response<Body> {
    let body = oci_error_json("UNAUTHORIZED", "authentication required").to_string();
    Response::builder()
        .status(StatusCode::UNAUTHORIZED)
        .header("WWW-Authenticate", r#"Basic realm="ScareRegistryGate""#)
        .header("Content-Type", "application/json")
        .header("Docker-Distribution-API-Version", "registry/2.0")
        .body(Body::from(body))
        .unwrap_or_else(|_| Response::new(Body::empty()))
}

/// Validate Basic Auth from the request headers.
///
/// Returns `Ok(())` when the credentials are valid, or `Err(Response)` with a
/// 401 response ready to return from the handler.
pub fn require_auth(headers: &HeaderMap, cfg: &Config) -> Result<(), Response<Body>> {
    match extract_basic_auth(headers) {
        Some((user, pass)) if validate_credentials(&user, &pass, cfg) => Ok(()),
        _ => Err(unauthorized_response()),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use base64::{engine::general_purpose::STANDARD, Engine};

    fn make_config(username: &str, password: &str) -> Config {
        Config {
            port: 5678,
            r2_account_id: String::new(),
            r2_access_key_id: String::new(),
            r2_secret_access_key: String::new(),
            r2_bucket: "bucket".into(),
            r2_public_url: String::new(),
            centralhub_url: String::new(),
            centralhub_service_token: String::new(),
            redis_host: "localhost".into(),
            redis_port: 6380,
            redis_password: String::new(),
            redis_db: 0,
            heartbeat_interval: 20,
            log_level: "INFO".into(),
            registry_username: username.into(),
            registry_password: password.into(),
            control_api_key: String::new(),
            max_blob_size: 2048 * 1024 * 1024,
        }
    }

    fn basic_auth_header(user: &str, pass: &str) -> String {
        let encoded = STANDARD.encode(format!("{user}:{pass}"));
        format!("Basic {encoded}")
    }

    #[test]
    fn test_extract_basic_auth_valid() {
        let mut headers = HeaderMap::new();
        headers.insert(
            "Authorization",
            basic_auth_header("alice", "s3cr3t").parse().unwrap(),
        );
        let result = extract_basic_auth(&headers);
        assert_eq!(result, Some(("alice".into(), "s3cr3t".into())));
    }

    #[test]
    fn test_extract_basic_auth_missing() {
        let headers = HeaderMap::new();
        assert!(extract_basic_auth(&headers).is_none());
    }

    #[test]
    fn test_extract_basic_auth_bad_scheme() {
        let mut headers = HeaderMap::new();
        headers.insert("Authorization", "Bearer token123".parse().unwrap());
        assert!(extract_basic_auth(&headers).is_none());
    }

    #[test]
    fn test_validate_credentials_ok() {
        let cfg = make_config("bob", "pass123");
        assert!(validate_credentials("bob", "pass123", &cfg));
    }

    #[test]
    fn test_validate_credentials_wrong_password() {
        let cfg = make_config("bob", "correct");
        assert!(!validate_credentials("bob", "wrong", &cfg));
    }

    #[test]
    fn test_validate_credentials_wrong_user() {
        let cfg = make_config("bob", "pass");
        assert!(!validate_credentials("alice", "pass", &cfg));
    }

    #[test]
    fn test_require_auth_valid() {
        let cfg = make_config("admin", "secret");
        let mut headers = HeaderMap::new();
        headers.insert(
            "Authorization",
            basic_auth_header("admin", "secret").parse().unwrap(),
        );
        assert!(require_auth(&headers, &cfg).is_ok());
    }

    #[test]
    fn test_require_auth_invalid_returns_err() {
        let cfg = make_config("admin", "secret");
        let headers = HeaderMap::new(); // no auth
        assert!(require_auth(&headers, &cfg).is_err());
    }

    #[test]
    fn test_unauthorized_response_status_code() {
        let resp = unauthorized_response();
        assert_eq!(resp.status(), StatusCode::UNAUTHORIZED);
    }
}
