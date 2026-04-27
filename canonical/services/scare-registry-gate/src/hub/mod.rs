//! CentralHub HTTP client.
//!
//! After a successful manifest push, the gateway notifies CentralHub so it
//! can index the image and make it discoverable in the ScareVerse UI.

use tracing::{info, warn};

/// Thin HTTP client for CentralHub registry notifications.
pub struct HubClient {
    http: reqwest::Client,
    base_url: String,
    api_key: String,
}

impl HubClient {
    /// Build a new client.
    ///
    /// `base_url` – e.g. `http://centralhub:5050`
    /// `api_key`  – bearer token sent in the `Authorization` header
    pub fn new(base_url: &str, api_key: &str) -> Self {
        let http = reqwest::Client::builder()
            .timeout(std::time::Duration::from_secs(30))
            .build()
            .unwrap_or_else(|_| reqwest::Client::new());
        Self {
            http,
            base_url: base_url.trim_end_matches('/').to_owned(),
            api_key: api_key.to_owned(),
        }
    }

    /// `POST {base_url}/api/registry/manifests` with the manifest payload.
    ///
    /// Returns `Ok(())` for any 2xx status code.
    /// Failures are logged as warnings but do **not** propagate to the caller –
    /// registry operations must succeed even if CentralHub is unreachable.
    pub async fn notify_manifest(&self, payload: &serde_json::Value) -> Result<(), String> {
        let url = format!("{}/api/registry/manifests", self.base_url);
        let resp = self
            .http
            .post(&url)
            .header("Authorization", format!("Bearer {}", self.api_key))
            .header("Content-Type", "application/json")
            .json(payload)
            .send()
            .await
            .map_err(|e| format!("HTTP send error: {e}"))?;

        let status = resp.status();
        if status.is_success() {
            info!("CentralHub notified: POST {} → {}", url, status);
            Ok(())
        } else {
            let body = resp.text().await.unwrap_or_default();
            warn!("CentralHub returned {}: {}", status, body);
            Err(format!("CentralHub HTTP {status}: {body}"))
        }
    }
}

impl std::fmt::Debug for HubClient {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("HubClient")
            .field("base_url", &self.base_url)
            .finish()
    }
}
