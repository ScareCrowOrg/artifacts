# ─── Stage 1: Build ───────────────────────────────────────────────────────────
FROM rust:1.88-slim AS builder

WORKDIR /app

# Install system dependencies required by some crates (openssl, etc.)
RUN apt-get update && apt-get install -y \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy manifest files first for layer caching (deps only change when Cargo.toml changes)
COPY Cargo.toml ./

# Create a dummy main.rs so we can pre-compile dependencies
RUN mkdir src && echo 'fn main() {}' > src/main.rs
RUN cargo build --release 2>&1
RUN rm -rf src

# Copy actual source files
COPY src ./src

# Touch main.rs to force rebuild of the binary (not deps)
RUN touch src/main.rs && cargo build --release 2>&1

# ─── Stage 2: Runtime ─────────────────────────────────────────────────────────
FROM debian:bookworm-slim AS runtime

WORKDIR /app

# Install Python 3 + pip (for heartbeat.py), ca-certificates (for HTTPS)
RUN apt-get update && apt-get install -y \
    ca-certificates \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps for BaseService heartbeat and canonical.shared imports
RUN pip install --no-cache-dir --break-system-packages redis httpx

# Copy compiled binary from builder
COPY --from=builder /app/target/release/auth-proxy /app/auth-proxy

# Copy entrypoint script and heartbeat registration
COPY entrypoint.sh /app/entrypoint.sh
COPY heartbeat.py /app/heartbeat.py

RUN chmod +x /app/auth-proxy /app/entrypoint.sh /app/heartbeat.py

# Expose default proxy port
EXPOSE 5055

CMD ["/app/entrypoint.sh"]
