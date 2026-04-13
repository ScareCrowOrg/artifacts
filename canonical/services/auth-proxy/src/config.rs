//! Configuration module – reads all settings from environment variables.
//!
//! Every field has a documented default so the service can run out of the box
//! in a development environment without any explicit configuration.

/// Runtime configuration loaded from environment variables.
#[derive(Debug, Clone)]
pub struct Config {
    /// Port the proxy listens on (env: `PROXY_PORT`, default: `5055`).
    pub port: u16,

    /// Upstream Vite server URL (env: `VITE_UPSTREAM`, default: `http://vite:5052`).
    pub vite_upstream: String,

    /// Backend session-check URL (env: `BACKEND_AUTH_URL`,
    /// default: `http://backend:5050/api/v1/auth/session-check`).
    pub backend_auth_url: String,

    /// Redis L1 host for heartbeat registration (env: `REDIS_L1_HOST`, default: `redis-local`).
    pub redis_host: String,

    /// Redis L1 port (env: `REDIS_L1_PORT`, default: `6380`).
    pub redis_port: u16,

    /// Redis L1 password (env: `REDIS_L1_PASSWORD`, default: `scarerunner`).
    pub redis_password: String,

    /// Redis L1 database index (env: `REDIS_L1_DB`, default: `0`).
    pub redis_db: u8,

    /// Heartbeat refresh interval in seconds (env: `HEARTBEAT_INTERVAL`, default: `20`).
    pub heartbeat_interval: u64,

    /// Log level string (env: `LOG_LEVEL`, default: `INFO`).
    pub log_level: String,
}

impl Config {
    /// Load configuration from environment variables with defaults.
    pub fn from_env() -> Self {
        Self {
            port: env_u16("PROXY_PORT", 5055),
            vite_upstream: env_str("VITE_UPSTREAM", "http://vite:5052"),
            backend_auth_url: env_str(
                "BACKEND_AUTH_URL",
                "http://backend:5050/api/v1/auth/session-check",
            ),
            redis_host: env_str("REDIS_L1_HOST", "redis-local"),
            redis_port: env_u16("REDIS_L1_PORT", 6380),
            redis_password: env_str("REDIS_L1_PASSWORD", "scarerunner"),
            redis_db: env_u8("REDIS_L1_DB", 0),
            heartbeat_interval: env_u64("HEARTBEAT_INTERVAL", 20),
            log_level: env_str("LOG_LEVEL", "INFO"),
        }
    }
}

fn env_str(key: &str, default: &str) -> String {
    std::env::var(key).unwrap_or_else(|_| default.to_owned())
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_defaults() {
        // Ensure no relevant env vars pollute this test.
        std::env::remove_var("PROXY_PORT");
        std::env::remove_var("VITE_UPSTREAM");
        std::env::remove_var("BACKEND_AUTH_URL");

        let cfg = Config::from_env();
        assert_eq!(cfg.port, 5055);
        assert_eq!(cfg.vite_upstream, "http://vite:5052");
        assert!(cfg.backend_auth_url.contains("session-check"));
        assert_eq!(cfg.heartbeat_interval, 20);
    }

    #[test]
    fn test_env_override() {
        std::env::set_var("PROXY_PORT", "9999");
        std::env::set_var("LOG_LEVEL", "DEBUG");

        let cfg = Config::from_env();
        assert_eq!(cfg.port, 9999);
        assert_eq!(cfg.log_level, "DEBUG");

        std::env::remove_var("PROXY_PORT");
        std::env::remove_var("LOG_LEVEL");
    }
}
