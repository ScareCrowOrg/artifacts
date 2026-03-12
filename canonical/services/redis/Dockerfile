FROM redis:7-alpine

# Custom configuration or healthcheck can go here
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
  CMD redis-cli ping || exit 1
