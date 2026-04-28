//! ScareRegistryGate – entry point.
//!
//! Starts an Axum server that implements the OCI Distribution Spec v2:
//!   - Basic Auth on every endpoint.
//!   - Blob uploads buffered in RAM, then uploaded to Cloudflare R2.
//!   - Manifest pushes stored in R2 and notified to CentralHub.
//!   - Blob/manifest pulls redirected (307) to the public R2 URL.
//!   - Redis heartbeat registered by `heartbeat.py` before this binary starts.
//!   - SIGTERM/SIGINT handled for graceful shutdown.

mod config;
mod hub;
mod oci;
mod r2;

use std::sync::Arc;

use axum::{
    body::Body,
    http::{Response, StatusCode},
    routing::any,
};
use dashmap::DashMap;
use tokio::net::TcpListener;
use tracing::{error, info};

/// Shared application state injected into every Axum handler.
#[derive(Clone)]
pub struct AppState {
    /// Runtime configuration loaded from environment variables.
    pub config: config::Config,
    /// Cloudflare R2 client.
    pub r2: Arc<r2::R2Client>,
    /// CentralHub notification client.
    pub hub: Arc<hub::HubClient>,
    /// Redis URL string (informational; connection managed via `redis` field).
    pub redis_url: String,
    /// Shared Redis connection manager (cheaply cloned per handler).
    pub redis: redis::aio::ConnectionManager,
    /// In-memory byte buffers for in-progress blob uploads, keyed by UUID.
    pub session_buffers: Arc<DashMap<String, Vec<u8>>>,
}

#[tokio::main]
async fn main() {
    let cfg = config::Config::from_env();

    // Initialise structured logging.
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new(&cfg.log_level)),
        )
        .with_target(false)
        .init();

    info!(
        "[ScareRegistryGate] Starting on port {} | bucket={} | hub={}",
        cfg.port, cfg.r2_bucket, cfg.centralhub_url
    );

    // Sanity-check critical env vars: log first/last char and byte length to
    // detect invisible characters (BOM, NBSP, etc.) that trim() may leave behind.
    cfg.log_sanity_check();

    // Warn if running with an empty registry password (insecure)
    if cfg.registry_password.is_empty() {
        tracing::warn!(
            "[ScareRegistryGate] REGISTRY_PASSWORD is not set – \
             any client can push images. Set REGISTRY_PASSWORD for production use."
        );
    }

    // Build Cloudflare R2 client.
    let r2_client = r2::R2Client::new(
        &cfg.r2_account_id,
        &cfg.r2_access_key_id,
        &cfg.r2_secret_access_key,
        &cfg.r2_bucket,
        &cfg.r2_public_url,
    );

    // Build CentralHub client.
    let hub_client = hub::HubClient::new(&cfg.centralhub_url, &cfg.centralhub_api_key);

    // Connect to Redis.
    let redis_url = cfg.redis_url();
    let redis_client = match redis::Client::open(redis_url.as_str()) {
        Ok(c) => c,
        Err(e) => {
            error!("[ScareRegistryGate] Failed to create Redis client: {e}");
            std::process::exit(1);
        }
    };
    let redis_cm = match redis::aio::ConnectionManager::new(redis_client).await {
        Ok(cm) => cm,
        Err(e) => {
            error!("[ScareRegistryGate] Failed to connect to Redis: {e}");
            std::process::exit(1);
        }
    };

    let state = Arc::new(AppState {
        r2: Arc::new(r2_client),
        hub: Arc::new(hub_client),
        redis_url: redis_url.clone(),
        redis: redis_cm,
        session_buffers: Arc::new(DashMap::new()),
        config: cfg.clone(),
    });

    // Assemble router.
    let app = oci::oci_router()
        .route("/health", any(health_handler))
        .with_state(state);

    // Bind listener.
    let bind_addr = format!("0.0.0.0:{}", cfg.port);
    let listener = match TcpListener::bind(&bind_addr).await {
        Ok(l) => l,
        Err(e) => {
            error!("[ScareRegistryGate] Failed to bind {bind_addr}: {e}");
            std::process::exit(1);
        }
    };

    info!("[ScareRegistryGate] Listening on {bind_addr}");

    // Graceful shutdown on SIGTERM / SIGINT.
    let shutdown = async {
        #[cfg(unix)]
        {
            use tokio::signal::unix::{signal, SignalKind};
            let mut sigterm =
                signal(SignalKind::terminate()).expect("Failed to register SIGTERM handler");
            let mut sigint =
                signal(SignalKind::interrupt()).expect("Failed to register SIGINT handler");
            tokio::select! {
                _ = sigterm.recv() => info!("[ScareRegistryGate] Received SIGTERM, shutting down"),
                _ = sigint.recv()  => info!("[ScareRegistryGate] Received SIGINT, shutting down"),
            }
        }
        #[cfg(not(unix))]
        {
            tokio::signal::ctrl_c()
                .await
                .expect("Failed to install CTRL+C handler");
            info!("[ScareRegistryGate] Received CTRL+C, shutting down");
        }
    };

    if let Err(e) = axum::serve(listener, app)
        .with_graceful_shutdown(shutdown)
        .await
    {
        error!("[ScareRegistryGate] Server error: {e}");
        std::process::exit(1);
    }

    info!("[ScareRegistryGate] Shutdown complete");
}

/// `GET /health` – liveness probe used by docker-compose and load balancers.
async fn health_handler() -> Response<Body> {
    Response::builder()
        .status(StatusCode::OK)
        .header("Content-Type", "text/plain")
        .body(Body::from("OK"))
        .unwrap_or_else(|_| Response::new(Body::empty()))
}
