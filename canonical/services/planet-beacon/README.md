# planet-beacon

Lightweight ScareVerse service that announces a planet's presence and available viewers to the CentralHub every 60 seconds.

## Overview

`planet-beacon` implements a **dual heartbeat** strategy:

| Layer | Mechanism | Redis Key | TTL |
|-------|-----------|-----------|-----|
| L1 | BaseService → Redis L1 | `state:service:planet-beacon:available` | 180s (3× interval) |
| L2 | POST → CentralHub → Redis L2 | `planet:presence:{planet_id}` | 90s |

The L1 heartbeat enables local GateKeeper service discovery.
The L2 presence heartbeat enables the Cockpit to display a live list of online planets via `GET /api/v1/planets/online`.

## Viewer Discovery (PnP)

On each beacon cycle, `planet-beacon` scans `artifacts/canonical/viewers/` for subdirectories that contain an `index.html`. Any qualifying directory is reported as an available viewer.

**Adding a new viewer is as simple as creating the folder — no database registration needed.**
Within 60 seconds the viewer appears in the Cockpit for all users.

## Configuration

All settings are environment variables (injected by Launcher via `manifest.json`):

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PLANET_ID` | ✅ | — | Unique planet UUID |
| `PLANET_NAME` | ✅ | — | Human-readable planet name |
| `TUNNEL_FQDN` | ✅ | — | Planet FQDN (e.g. `planet.scareverse.net`) |
| `CENTRALHUB_SERVICE_TOKEN` | ✅ | — | Bearer token for CentralHub auth |
| `CENTRALHUB_URL` | ❌ | `https://hub.scareverse.net` | CentralHub base URL |
| `BEACON_INTERVAL` | ❌ | `60` | Seconds between presence heartbeats |
| `PRESENCE_TTL` | ❌ | `90` | Redis TTL for presence key (seconds) |
| `VIEWERS_BASE_DIR` | ❌ | `/app/artifacts/canonical/viewers` | Path to scan for viewers |
| `REDIS_L1_HOST` | ❌ | `redis-local` | Redis L1 host |
| `REDIS_L1_PORT` | ❌ | `6380` | Redis L1 port |
| `REDIS_L1_PASSWORD` | ❌ | `scarerunner` | Redis L1 password |

## Running Locally

```bash
# Build
docker build -t planet-beacon .

# Run (example)
docker run --rm \
  -e PLANET_ID=my-planet-uuid \
  -e PLANET_NAME=andromeda \
  -e TUNNEL_FQDN=andromeda.scareverse.net \
  -e CENTRALHUB_SERVICE_TOKEN=<token> \
  -v $(pwd)/../../../../artifacts:/app/artifacts:ro \
  planet-beacon
```

Or with docker-compose (from the planet's compose stack):

```bash
docker-compose -f docker-compose.yml up
```

## How It Works

1. **Startup**: BaseService L1 heartbeat task starts (`state:service:planet-beacon:available`).
2. **Loop** (every `BEACON_INTERVAL` seconds):
   a. Scans `VIEWERS_BASE_DIR` for viewer directories with `index.html`.
   b. POSTs `{ planet_id, name, fqdn, status: "online", viewers }` to `CENTRALHUB_URL/api/v1/planets/presence`.
   c. CentralHub stores `planet:presence:{planet_id}` in Redis L2 with `PRESENCE_TTL` TTL.
3. **Expiry**: If the beacon stops, the presence key expires after `PRESENCE_TTL` seconds (default 90s). The planet disappears from the Cockpit on the next poll cycle.

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Planet not appearing in Cockpit | `PLANET_ID` or `CENTRALHUB_SERVICE_TOKEN` not set | Check env vars |
| `401 Unauthorized` in logs | Invalid service token | Rotate `CENTRALHUB_SERVICE_TOKEN` in vault |
| No viewers listed for planet | No `index.html` in viewer subdirectories | Verify viewer directory structure |
| L1 heartbeat disabled | `redis-py` not installed or Redis L1 unreachable | Check `REDIS_L1_HOST` and `REDIS_L1_PORT` |
