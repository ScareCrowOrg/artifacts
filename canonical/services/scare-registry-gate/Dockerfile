# ─── Stage 1: Build (Static with MUSL) ────────────────────────────────────────
FROM rust:1.93-alpine AS builder

WORKDIR /app

# Static compilation dependencies
RUN apk add --no-cache musl-dev pkgconfig openssl-dev openssl-libs-static g++ make

# Add MUSL target for static linking
RUN rustup target add x86_64-unknown-linux-musl

# Copy manifest files first for layer caching
COPY Cargo.toml Cargo.lock ./

# Pre-compile dependencies with a dummy binary (static)
RUN mkdir src && echo 'fn main() {}' > src/main.rs
RUN RUSTFLAGS="-C target-feature=+crt-static" cargo build --release --target x86_64-unknown-linux-musl 2>&1
RUN rm -rf src

# Copy actual source files
COPY src ./src

# Build static binary (no dynamic libc dependency)
RUN touch src/main.rs && \
    RUSTFLAGS="-C target-feature=+crt-static" cargo build --release --target x86_64-unknown-linux-musl 2>&1

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

# Copy static binary from MUSL build (no GLIBC dependency)
COPY --from=builder /app/target/x86_64-unknown-linux-musl/release/scare-registry-gate /app/scare-registry-gate

# Copy entrypoint and heartbeat scripts
COPY entrypoint.sh /app/entrypoint.sh
COPY heartbeat.py /app/heartbeat.py

RUN chmod +x /app/scare-registry-gate /app/entrypoint.sh /app/heartbeat.py

# Default OCI gateway port
EXPOSE 5678

CMD ["/app/entrypoint.sh"]
