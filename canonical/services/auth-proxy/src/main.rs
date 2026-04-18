//! Auth Proxy – entry point.
//!
//! Starts an Axum web server that:
//!   - Validates SessionID via Backend for every `/artifacts/*` request.
//!   - Proxies validated requests to Vite (transparent streaming).
//!   - Registers a Redis heartbeat so Traefik can detect readiness before routing traffic.
//!   - Handles SIGTERM/SIGINT for graceful shutdown (30-second grace period).

mod config;
mod proxy;
mod ws_proxy;

use axum::{extract::Request, routing::any, Router};
use reqwest::ClientBuilder;
use std::sync::Arc;
use std::time::Duration;
use tokio::net::TcpListener;
use tracing::{error, info};

/// Shared application state injected into every Axum handler.
#[derive(Clone)]
pub struct AppState {
    /// Pooled HTTP client for Backend session-check and Vite proxy calls.
    pub http_client: reqwest::Client,
    /// Vite upstream base URL (e.g. `http://vite:5052`).
    pub vite_upstream: String,
    /// Backend session-check URL (e.g. `http://backend:5050/api/v1/auth/session-check`).
    pub backend_auth_url: String,
    /// Backend upstream base URL (e.g. `http://backend:5050`).
    pub backend_upstream: String,
}

#[tokio::main]
async fn main() {
    let cfg = config::Config::from_env();

    // Initialise tracing / logging.
    let log_filter = cfg.log_level.clone();
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new(&log_filter)),
        )
        .with_target(false)
        .init();

    info!(
        "[AuthProxy] Starting on port {} | Vite: {} | Backend auth: {} | Backend upstream: {}",
        cfg.port, cfg.vite_upstream, cfg.backend_auth_url, cfg.backend_upstream
    );

    // Build a shared HTTP client with connection pooling.
    let http_client = ClientBuilder::new()
        .pool_max_idle_per_host(20)
        .timeout(Duration::from_secs(30))
        .build()
        .expect("Failed to build HTTP client");

    let state = Arc::new(AppState {
        http_client,
        vite_upstream: cfg.vite_upstream.clone(),
        backend_auth_url: cfg.backend_auth_url.clone(),
        backend_upstream: cfg.backend_upstream.clone(),
    });

    // Note: Redis heartbeat registration is now handled by heartbeat.py
    // (called via entrypoint.sh before this binary starts).
    // See: artifacts/canonical/services/auth-proxy/heartbeat.py

    // Build Axum router.
    let state_root = Arc::clone(&state);
    let state_wildcard = Arc::clone(&state);
    let app = Router::new()
        // Health endpoint – used by docker-compose healthcheck and Traefik
        .route("/health", any(proxy::health_handler))
        // Universal proxy – all methods, all paths (except /health)
        .route(
            "/",
            any(move |req: Request| {
                let s = Arc::clone(&state_root);
                async move { proxy::request_handler(axum::extract::State((*s).clone()), req).await }
            }),
        )
        .route(
            "/*path",
            any(move |req: Request| {
                let s = Arc::clone(&state_wildcard);
                async move { proxy::request_handler(axum::extract::State((*s).clone()), req).await }
            }),
        );

    // Bind listener.
    let bind_addr = format!("0.0.0.0:{}", cfg.port);
    let listener = TcpListener::bind(&bind_addr)
        .await
        .unwrap_or_else(|e| panic!("Failed to bind to {bind_addr}: {e}"));

    info!("[AuthProxy] Listening on {}", bind_addr);

    // Graceful shutdown: wait for SIGTERM or SIGINT.
    let shutdown = async {
        #[cfg(unix)]
        {
            use tokio::signal::unix::{signal, SignalKind};
            let mut sigterm =
                signal(SignalKind::terminate()).expect("Failed to register SIGTERM handler");
            let mut sigint =
                signal(SignalKind::interrupt()).expect("Failed to register SIGINT handler");
            tokio::select! {
                _ = sigterm.recv() => info!("[AuthProxy] Received SIGTERM, shutting down"),
                _ = sigint.recv() => info!("[AuthProxy] Received SIGINT, shutting down"),
            }
        }
        #[cfg(not(unix))]
        {
            tokio::signal::ctrl_c()
                .await
                .expect("Failed to install CTRL+C handler");
            info!("[AuthProxy] Received CTRL+C, shutting down");
        }
    };

    if let Err(e) = axum::serve(listener, app)
        .with_graceful_shutdown(shutdown)
        .await
    {
        error!("[AuthProxy] Server error: {}", e);
        std::process::exit(1);
    }

    info!("[AuthProxy] Shutdown complete");
}
