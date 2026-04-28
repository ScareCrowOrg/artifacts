//! Cloudflare R2 client wrapper (S3-compatible API).

pub mod multipart;

use aws_credential_types::Credentials;
use aws_sdk_s3::{
    config::{BehaviorVersion, Region},
    primitives::ByteStream,
    Client,
    Config as S3Config,
};
use bytes::Bytes;
use tracing::{info, warn};

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

/// Thin wrapper around the AWS S3 client configured for Cloudflare R2.
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

        // Warn on any suspicious characters in the account_id or bucket name.
        // `account_id` is alphanumeric + hyphens; `bucket` may also contain dots.
        warn_if_suspicious("[R2Client] ⚠ R2_ACCOUNT_ID", account_id, &['-']);
        warn_if_suspicious("[R2Client] ⚠ R2_BUCKET",     bucket,     &['-', '.']);

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
                    warn!(
                        "[R2Client] dispatch failure for key={} | endpoint=https://{}.r2.cloudflarestorage.com | chain: {}",
                        key, self.bucket, source_chain
                    );
                }
                if msg.contains("404")
                    || msg.contains("NotFound")
                    || msg.contains("NoSuchKey")
                {
                    Ok(None)
                } else {
                    Err(format!("head_object error: {msg}"))
                }
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
            .map_err(|e| e.to_string())?;
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
            .map_err(|e| e.to_string())?;
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
            .map_err(|e| e.to_string())?;
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
            .map_err(|e| e.to_string())?;
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
            warn!("abort_multipart error (key={key}): {e}");
            return Err(e.to_string());
        }
        Ok(())
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


