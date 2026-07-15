//! Cloudflare R2 client wrapper (S3-compatible API).

pub mod multipart;

use aws_credential_types::Credentials;
use aws_sdk_s3::{
    config::{BehaviorVersion, Region},
    error::SdkError,
    primitives::ByteStream,
    Client,
    Config as S3Config,
};
use bytes::Bytes;
use tracing::{error, info, warn};

use multipart::{build_completed_multipart, PartInfo};

type R2Result<T> = Result<T, String>;

/// Emit a WARN log when `value` contains characters outside the expected set
/// (alphanumeric + `extra_allowed`).  Used to detect invisible chars
/// (e.g. `\n`, `\r`, Unicode spaces) injected by the Launcher env pipeline.
fn warn_if_suspicious(label: &str, value: &str, extra_allowed: &[char]) {
    if value.chars().any(|c| !c.is_ascii_alphanumeric() && !extra_allowed.contains(&c)) {
        warn!(
            "{} contains unexpected characters \
             (bytes: {:?}) – check for invisible chars injected by Launcher",
            label,
            value.as_bytes()
        );
    }
}

/// Extract a human-readable diagnostic string from any `SdkError`.
///
/// For `ServiceError` variants (i.e. when the R2 / Cloudflare server responded
/// with a non-success HTTP status) this extracts:
///   - The HTTP status code (e.g. 403, 404, 503)
///   - The full Debug representation of the parsed error (contains the R2 error
///     code such as `SignatureDoesNotMatch`, `AccessDenied`, `InvalidAccessKeyId`,
///     `NoSuchBucket`, etc.)
///
/// For all other error kinds (dispatch failure, timeout, etc.) the function
/// falls back to the Debug representation of the whole error.
///
/// **Security note:** This function never logs credential values; it only logs
/// error metadata returned by the remote server.
fn describe_sdk_error<E: std::fmt::Debug, R: std::fmt::Debug>(
    e: &SdkError<E, R>,
) -> String {
    match e {
        SdkError::ServiceError(se) => {
            // se.err() is the parsed SDK error struct (contains code + message,
            // e.g. SignatureDoesNotMatch, AccessDenied, NoSuchBucket).
            // We intentionally omit se.raw() (the full HTTP response) to avoid
            // logging potentially large response bodies for blob operations.
            format!("service_error err={:?}", se.err())
        }
        SdkError::DispatchFailure(df) => {
            format!("dispatch_failure err={:?}", df)
        }
        SdkError::TimeoutError(te) => {
            format!("timeout err={:?}", te)
        }
        other => {
            format!("sdk_error {:?}", other)
        }
    }
}

/// Thin wrapper around the AWS S3 client configured for Cloudflare R2.
#[derive(Clone)]
pub struct R2Client {
    client: Client,
    /// Bucket name used for every operation.
    pub bucket: String,
    /// Public base URL, e.g. `https://pub-xxx.r2.dev`.
    pub public_url: String,
}

impl R2Client {
    /// Construct a new R2Client from static credentials.
    pub fn new(
        account_id: &str,
        access_key: &str,
        secret_key: &str,
        bucket: &str,
        public_url: &str,
    ) -> Self {
        // Trim all string parameters defensively.  The Launcher injects env vars
        // from Vault/TOML which can include trailing newlines or whitespace that
        // silently corrupt the endpoint URL and produce "dispatch failure" errors.
        let account_id = account_id.trim();
        let access_key = access_key.trim();
        let secret_key = secret_key.trim();
        let bucket = bucket.trim();
        let public_url = public_url.trim();

        // Diagnostic: log endpoint URL and its byte length to detect invisible chars.
        let endpoint = format!("https://{}.r2.cloudflarestorage.com", account_id);
        info!(
            "[R2Client] Initialising: account_id_len={} bucket_len={} endpoint=\"{}\" endpoint_bytes={}",
            account_id.len(),
            bucket.len(),
            endpoint,
            endpoint.len()
        );
        // Log credential lengths (never log values) to confirm Launcher injection.
        // R2 access key IDs are typically 32 hex chars; secret keys are 64 hex chars.
        if access_key.is_empty() {
            warn!("[R2Client] R2_ACCESS_KEY_ID is EMPTY – R2 requests will fail with auth error");
        } else {
            let ak_chars: Vec<char> = access_key.chars().collect();
            if ak_chars.is_empty() {
                warn!("[R2Client] R2_ACCESS_KEY_ID produced no printable chars after trim – check for invisible-only value");
            } else {
                info!(
                    "[R2Client] R2_ACCESS_KEY_ID: start='{}', end='{}', len={}",
                    ak_chars[0],
                    ak_chars[ak_chars.len() - 1],
                    access_key.len()
                );
            }
        }
        if secret_key.is_empty() {
            warn!("[R2Client] R2_SECRET_ACCESS_KEY is EMPTY – R2 requests will fail with auth error");
        } else {
            let sk_chars: Vec<char> = secret_key.chars().collect();
            if sk_chars.is_empty() {
                warn!("[R2Client] R2_SECRET_ACCESS_KEY produced no printable chars after trim – check for invisible-only value");
            } else {
                info!(
                    "[R2Client] R2_SECRET_ACCESS_KEY: start='{}', end='{}', len={}",
                    sk_chars[0],
                    sk_chars[sk_chars.len() - 1],
                    secret_key.len()
                );
            }
        }

        // Validate the endpoint as a well-formed URI BEFORE handing it to the AWS
        // SDK.  An invalid URI (e.g. an empty host when R2_ACCOUNT_ID is unset)
        // causes the SDK to fail with the opaque "failed to construct request"
        // error, which gives no indication of the actual cause.
        //
        // `panic!` here is intentional: a missing or corrupt R2_ACCOUNT_ID is a
        // fatal misconfiguration and there is no sensible recovery path.
        match endpoint.parse::<http::Uri>() {
            Ok(uri) => {
                // Additionally assert that the host segment is non-empty.
                // http::Uri can technically parse "https://.example.com" as valid
                // even though DNS would reject it.
                let host = uri.host().unwrap_or("");
                if host.is_empty() || host.starts_with('.') {
                    panic!(
                        "[R2Client] FATAL: endpoint '{}' has an invalid host '{}'. \
                         R2_ACCOUNT_ID is empty or malformed ({} chars). \
                         Ensure the Launcher injects R2_ACCOUNT_ID correctly.",
                        endpoint, host, account_id.len()
                    );
                }
            }
            Err(e) => {
                panic!(
                    "[R2Client] FATAL: endpoint '{}' is not a valid URI: {}. \
                     R2_ACCOUNT_ID contains {} chars. \
                     Ensure R2_ACCOUNT_ID is a plain alphanumeric Cloudflare account ID.",
                    endpoint, e, account_id.len()
                );
            }
        }

        // Warn on any suspicious characters in the account_id or bucket name.
        // `account_id` is alphanumeric + hyphens; `bucket` may also contain dots.
        warn_if_suspicious("[R2Client] ⚠ R2_ACCOUNT_ID", account_id, &['-']);
        warn_if_suspicious("[R2Client] ⚠ R2_BUCKET",     bucket,     &['-', '.']);
        // Access key IDs are alphanumeric; secret keys are base64 (alphanumeric + +/=).
        // Any other characters indicate invisible chars from the Launcher injection pipeline.
        warn_if_suspicious("[R2Client] ⚠ R2_ACCESS_KEY_ID",     access_key, &[]);
        warn_if_suspicious("[R2Client] ⚠ R2_SECRET_ACCESS_KEY", secret_key, &['+', '/', '=', '-', '_']);

        let creds = Credentials::new(access_key, secret_key, None, None, "r2-static");
        // R2 requires path-style URLs (no virtual-hosted subdomain support).
        // Without force_path_style(true) the SDK would construct
        // `https://{bucket}.{account}.r2.cloudflarestorage.com/…` which fails
        // with a "dispatch failure" (DNS resolution error or TLS mismatch).
        let s3_cfg = S3Config::builder()
            .behavior_version(BehaviorVersion::latest())
            .credentials_provider(creds)
            .endpoint_url(&endpoint)
            .region(Region::new("auto"))
            .force_path_style(true)
            .build();
        Self {
            client: Client::from_conf(s3_cfg),
            bucket: bucket.to_owned(),
            public_url: public_url.to_owned(),
        }
    }

    /// Return the `Content-Length` of an object, or `None` if it does not exist.
    pub async fn head_object(&self, key: &str) -> R2Result<Option<i64>> {
        match self.client.head_object().bucket(&self.bucket).key(key).send().await {
            Ok(resp) => Ok(resp.content_length()),
            Err(e) => {
                let detail = describe_sdk_error(&e);
                let msg = e.to_string();

                // "dispatch failure" means the HTTP connector could not send the
                // request at all (DNS failure, TLS handshake error, or malformed
                // endpoint URL).  Log the full error source chain to aid diagnosis.
                if msg.contains("dispatch failure") {
                    let source_chain = {
                        use std::error::Error;
                        let mut chain = vec![msg.clone()];
                        let mut cur: &dyn Error = &e;
                        while let Some(src) = cur.source() {
                            chain.push(src.to_string());
                            cur = src;
                        }
                        chain.join(" → ")
                    };
                    error!(
                        "[R2Client] dispatch failure for key={} | endpoint=https://{}.r2.cloudflarestorage.com | chain: {}",
                        key, self.bucket, source_chain
                    );
                }

                // 404 / NotFound / NoSuchKey → blob does not exist; this is the normal
                // path during a docker push (Docker probes which blobs are already in
                // the registry before uploading).  Return Ok(None) so the handler can
                // respond with 404 and let Docker proceed to the upload phase.
                //
                // We check both `msg` (e.to_string(), usually "service error") and
                // `detail` (the Debug repr of the parsed SDK error, which contains the
                // R2 error code such as "NotFound", "NoSuchKey") because the exact
                // display text varies across SDK versions and error types.
                if msg.contains("404")
                    || msg.contains("NotFound")
                    || msg.contains("NoSuchKey")
                    || detail.contains("NotFound")
                    || detail.contains("NoSuchKey")
                    || detail.contains("status: 404")
                {
                    tracing::debug!(
                        "[R2Client] head_object: key={} → 404 Not Found (blob absent, expected during push)",
                        key
                    );
                    return Ok(None);
                }

                // For all other errors (service errors, auth errors, etc.) log the
                // full detail extracted from the SDK error so operators can see the
                // exact R2 error code (e.g. SignatureDoesNotMatch, AccessDenied).
                error!(
                    "[R2Client] head_object FAILED | key={} | {}",
                    key, detail
                );
                Err(format!("head_object error: {detail}"))
            }
        }
    }

    /// Initiate an S3 multipart upload and return the `upload_id`.
    pub async fn create_multipart_upload(&self, key: &str) -> R2Result<String> {
        let resp = self
            .client
            .create_multipart_upload()
            .bucket(&self.bucket)
            .key(key)
            .send()
            .await
            .map_err(|e| {
                let detail = describe_sdk_error(&e);
                error!("[R2Client] create_multipart_upload FAILED | key={} | {}", key, detail);
                detail
            })?;
        resp.upload_id()
            .ok_or_else(|| "No upload_id in CreateMultipartUpload response".to_string())
            .map(|s| s.to_owned())
    }

    /// Upload a single part and return its ETag.
    pub async fn upload_part(
        &self,
        key: &str,
        upload_id: &str,
        part_number: i32,
        data: Bytes,
    ) -> R2Result<String> {
        let resp = self
            .client
            .upload_part()
            .bucket(&self.bucket)
            .key(key)
            .upload_id(upload_id)
            .part_number(part_number)
            .body(ByteStream::from(data))
            .send()
            .await
            .map_err(|e| {
                let detail = describe_sdk_error(&e);
                error!("[R2Client] upload_part FAILED | key={} part={} | {}", key, part_number, detail);
                detail
            })?;
        Ok(resp.e_tag().unwrap_or("").to_owned())
    }

    /// Finalise a multipart upload.
    pub async fn complete_multipart(
        &self,
        key: &str,
        upload_id: &str,
        parts: Vec<PartInfo>,
    ) -> R2Result<()> {
        let completed = build_completed_multipart(&parts);
        self.client
            .complete_multipart_upload()
            .bucket(&self.bucket)
            .key(key)
            .upload_id(upload_id)
            .multipart_upload(completed)
            .send()
            .await
            .map_err(|e| {
                let detail = describe_sdk_error(&e);
                error!("[R2Client] complete_multipart FAILED | key={} | {}", key, detail);
                detail
            })?;
        Ok(())
    }

    /// Upload a complete object in a single request.
    pub async fn put_object(&self, key: &str, data: Bytes, content_type: &str) -> R2Result<()> {
        self.client
            .put_object()
            .bucket(&self.bucket)
            .key(key)
            .content_type(content_type)
            .body(ByteStream::from(data))
            .send()
            .await
            .map_err(|e| {
                let detail = describe_sdk_error(&e);
                error!("[R2Client] put_object FAILED | key={} | {}", key, detail);
                detail
            })?;
        Ok(())
    }

    /// Abort an in-progress multipart upload.
    pub async fn abort_multipart(&self, key: &str, upload_id: &str) -> R2Result<()> {
        if let Err(e) = self
            .client
            .abort_multipart_upload()
            .bucket(&self.bucket)
            .key(key)
            .upload_id(upload_id)
            .send()
            .await
        {
            let detail = describe_sdk_error(&e);
            warn!("[R2Client] abort_multipart error (key={key}): {detail}");
            return Err(detail);
        }
        Ok(())
    }

    /// Create a copy with overridden bucket and/or public_url.
    ///
    /// The underlying S3 client (credentials, endpoint, connection pool) is shared,
    /// so this is cheap.  Only the bucket and public URL are replaced.
    pub fn with_overrides(&self, bucket: Option<&str>, public_url: Option<&str>) -> Self {
        Self {
            client: self.client.clone(),
            bucket: bucket.map(|s| s.to_owned()).unwrap_or_else(|| self.bucket.clone()),
            public_url: public_url.map(|s| s.to_owned()).unwrap_or_else(|| self.public_url.clone()),
        }
    }

    /// Build the public URL for a stored object key.
    pub fn public_url_for(&self, key: &str) -> String {
        format!("{}/{}", self.public_url.trim_end_matches('/'), key)
    }
}

impl std::fmt::Debug for R2Client {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("R2Client")
            .field("bucket", &self.bucket)
            .field("public_url", &self.public_url)
            .finish()
    }
}


