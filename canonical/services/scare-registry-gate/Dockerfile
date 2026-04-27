# ─── Stage 1: Build ───────────────────────────────────────────────────────────
FROM rust:1.93-slim AS builder

WORKDIR /app

# System dependencies required by some crates (openssl, pkg-config)
RUN apt-get update && apt-get install -y \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy manifest files first for layer caching
COPY Cargo.toml ./

# Pre-compile dependencies with a dummy binary
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

# Python 3 + pip (for heartbeat.py), ca-certificates (for HTTPS to R2/CentralHub)
RUN apt-get update && apt-get install -y \
    ca-certificates \
    curl \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Python deps for BaseService heartbeat
RUN pip install --no-cache-dir --break-system-packages redis httpx

# Copy compiled binary from builder
COPY --from=builder /app/target/release/scare-registry-gate /app/scare-registry-gate

# Copy entrypoint and heartbeat scripts
COPY entrypoint.sh /app/entrypoint.sh
COPY heartbeat.py /app/heartbeat.py

RUN chmod +x /app/scare-registry-gate /app/entrypoint.sh /app/heartbeat.py

# Default OCI gateway port
EXPOSE 5678

CMD ["/app/entrypoint.sh"]
