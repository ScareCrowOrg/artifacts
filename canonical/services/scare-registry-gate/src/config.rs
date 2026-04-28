//! Configuration module – reads all settings from environment variables.
//!
//! Every field has a documented default so the service can run without
//! explicit configuration in a development environment.

/// Runtime configuration for ScareRegistryGate.
#[derive(Debug, Clone)]
pub struct Config {
    /// Port the gateway listens on (env: `GATE_PORT`, default: `5678`).
    pub port: u16,

    /// Cloudflare R2 account ID (env: `R2_ACCOUNT_ID`, required).
    pub r2_account_id: String,

    /// R2 S3-compatible access key (env: `R2_ACCESS_KEY_ID`, required).
    pub r2_access_key_id: String,

    /// R2 S3-compatible secret key (env: `R2_SECRET_ACCESS_KEY`, required).
    pub r2_secret_access_key: String,

    /// R2 bucket name (env: `R2_BUCKET`, default: `"scareverse-registry"`).
    pub r2_bucket: String,

    /// Public base URL for R2 objects (env: `R2_PUBLIC_URL`).
    pub r2_public_url: String,

    /// CentralHub base URL (env: `CENTRALHUB_URL`, required).
    pub centralhub_url: String,

    /// API key for CentralHub manifest registration (env: `CENTRALHUB_API_KEY`, required).
    pub centralhub_api_key: String,

    /// Redis L1 host (env: `REDIS_L1_HOST`, default: `"redis-local"`).
    pub redis_host: String,

    /// Redis L1 port (env: `REDIS_L1_PORT`, default: `6380`).
    pub redis_port: u16,

    /// Redis L1 password (env: `REDIS_L1_PASSWORD`, default: `"scarerunner"`).
    pub redis_password: String,

    /// Redis L1 database index (env: `REDIS_L1_DB`, default: `0`).
    pub redis_db: u8,

    /// Heartbeat refresh interval in seconds (env: `HEARTBEAT_INTERVAL`, default: `20`).
    pub heartbeat_interval: u64,

    /// Log level string (env: `LOG_LEVEL`, default: `"INFO"`).
    pub log_level: String,

    /// OCI registry username for Basic Auth (env: `REGISTRY_USERNAME`, default: `"scareverse"`).
    pub registry_username: String,

    /// OCI registry password for Basic Auth (env: `REGISTRY_PASSWORD`, default: `"scareverse"`).
    ///
    /// **SECURITY**: Default is "scareverse" for local development (inaccessible externally).
    /// Override with a strong password in production to prevent unauthorised pushes.
    pub registry_password: String,

    /// Maximum blob size in bytes for a single push (env: `MAX_BLOB_SIZE_MB`, default: `2048`).
    ///
    /// Requests exceeding this limit are rejected with `413 Payload Too Large` before
    /// any bytes are buffered.  Default is 2 GiB which covers typical Docker images.
    pub max_blob_size: usize,
}

impl Config {
    /// Load configuration from environment variables with defaults.
    pub fn from_env() -> Self {
        Self {
            port: env_u16("GATE_PORT", 5678),
            r2_account_id: env_str("R2_ACCOUNT_ID", ""),
            r2_access_key_id: env_str("R2_ACCESS_KEY_ID", ""),
            r2_secret_access_key: env_str("R2_SECRET_ACCESS_KEY", ""),
            r2_bucket: env_str("R2_BUCKET", "scareverse-registry"),
            r2_public_url: env_str("R2_PUBLIC_URL", ""),
            centralhub_url: env_str("CENTRALHUB_URL", ""),
            centralhub_api_key: env_str("CENTRALHUB_API_KEY", ""),
            redis_host: env_str("REDIS_L1_HOST", "redis-local"),
            redis_port: env_u16("REDIS_L1_PORT", 6380),
            redis_password: env_str("REDIS_L1_PASSWORD", "scarerunner"),
            redis_db: env_u8("REDIS_L1_DB", 0),
            heartbeat_interval: env_u64("HEARTBEAT_INTERVAL", 20),
            log_level: env_str("LOG_LEVEL", "INFO"),
            registry_username: env_str("REGISTRY_USERNAME", "scareverse"),
            registry_password: env_str("REGISTRY_PASSWORD", "scareverse"),
            max_blob_size: env_usize("MAX_BLOB_SIZE_MB", 2048) * 1024 * 1024,
        }
    }

    /// Build the Redis connection URL from components.
    pub fn redis_url(&self) -> String {
        format!(
            "redis://:{}@{}:{}/{}",
            self.redis_password, self.redis_host, self.redis_port, self.redis_db
        )
    }
}

fn env_str(key: &str, default: &str) -> String {
    let raw = std::env::var(key).unwrap_or_else(|_| default.to_owned());
    // Trim leading/trailing ASCII whitespace and Unicode whitespace characters
    // (including \r, \n, BOM, NBSP) that may be injected by the Launcher's
    // env-var pipeline (e.g. newlines from TOML multiline values or Vault output).
    // NOTE: we trim all string env-vars uniformly because invisible chars in any
    // URL, ID or credential field cause silent "dispatch failure" errors in the
    // AWS S3 SDK and connection errors in reqwest.
    raw.trim().to_owned()
}

fn env_u16(key: &str, default: u16) -> u16 {
    std::env::var(key)
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(default)
}

fn env_u64(key: &str, default: u64) -> u64 {
    std::env::var(key)
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(default)
}

fn env_u8(key: &str, default: u8) -> u8 {
    std::env::var(key)
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(default)
}

fn env_usize(key: &str, default: usize) -> usize {
    std::env::var(key)
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(default)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_defaults() {
        // Remove any env overrides for these keys
        std::env::remove_var("GATE_PORT");
        std::env::remove_var("R2_BUCKET");
        std::env::remove_var("REDIS_L1_HOST");
        std::env::remove_var("REGISTRY_USERNAME");

        let cfg = Config::from_env();
        assert_eq!(cfg.port, 5678);
        assert_eq!(cfg.r2_bucket, "scareverse-registry");
        assert_eq!(cfg.redis_host, "redis-local");
        assert_eq!(cfg.redis_port, 6380);
        assert_eq!(cfg.heartbeat_interval, 20);
        assert_eq!(cfg.registry_username, "scareverse");
        assert_eq!(cfg.log_level, "INFO");
    }

    #[test]
    fn test_env_override() {
        std::env::set_var("GATE_PORT", "8888");
        std::env::set_var("R2_BUCKET", "my-bucket");
        std::env::set_var("REGISTRY_USERNAME", "admin");

        let cfg = Config::from_env();
        assert_eq!(cfg.port, 8888);
        assert_eq!(cfg.r2_bucket, "my-bucket");
        assert_eq!(cfg.registry_username, "admin");

        std::env::remove_var("GATE_PORT");
        std::env::remove_var("R2_BUCKET");
        std::env::remove_var("REGISTRY_USERNAME");
    }

    #[test]
    fn test_redis_url() {
        let cfg = Config {
            port: 5678,
            r2_account_id: String::new(),
            r2_access_key_id: String::new(),
            r2_secret_access_key: String::new(),
            r2_bucket: "bucket".into(),
            r2_public_url: String::new(),
            centralhub_url: String::new(),
            centralhub_api_key: String::new(),
            redis_host: "redis-local".into(),
            redis_port: 6380,
            redis_password: "secret".into(),
            redis_db: 1,
            heartbeat_interval: 20,
            log_level: "INFO".into(),
            registry_username: "u".into(),
            registry_password: "p".into(),
            max_blob_size: 2048 * 1024 * 1024,
        };
        assert_eq!(cfg.redis_url(), "redis://:secret@redis-local:6380/1");
    }

    #[test]
    fn test_max_blob_size_default() {
        std::env::remove_var("MAX_BLOB_SIZE_MB");
        let cfg = Config::from_env();
        // Default is 2048 MiB
        assert_eq!(cfg.max_blob_size, 2048 * 1024 * 1024);
    }

    #[test]
    fn test_env_str_trims_whitespace() {
        // `env_str()` is a single helper called for ALL string env vars.
        // Testing three representative vars (URL, bucket name, generic string)
        // is sufficient to validate the trimming behaviour — the logic is
        // identical for every call site.
        std::env::set_var("R2_ACCOUNT_ID", "abc123\n");
        std::env::set_var("R2_BUCKET", " my-bucket\r\n");
        std::env::set_var("CENTRALHUB_URL", "  https://hub.example.com  ");

        let cfg = Config::from_env();
        assert_eq!(cfg.r2_account_id, "abc123",     "trailing newline must be stripped");
        assert_eq!(cfg.r2_bucket,     "my-bucket",  "leading/trailing whitespace must be stripped");
        assert_eq!(cfg.centralhub_url, "https://hub.example.com", "surrounding spaces must be stripped");

        std::env::remove_var("R2_ACCOUNT_ID");
        std::env::remove_var("R2_BUCKET");
        std::env::remove_var("CENTRALHUB_URL");
    }
}
