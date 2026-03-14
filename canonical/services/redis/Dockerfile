FROM redis:7-alpine

# redis:7-alpine já inclui redis-cli

# BUILD_ID invalidates cache when artifacts change (passed at build time)
ARG BUILD_ID=latest
RUN echo "Build ID: ${BUILD_ID}"

# Ensure we're running as root for COPY and chmod operations
USER root

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 6380

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

# HEALTHCHECK verifies Redis is responding
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
  CMD redis-cli -p 6380 ping || exit 1
