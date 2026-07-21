# Party Cell

Real-time voice, video, and screen sharing cell powered by Cloudflare Calls (WebRTC SFU).

## Overview

The Party Cell enables users to have voice/video calls and share their screen or 3D canvas
within the ScareVerse ecosystem. It uses **Cloudflare Calls** as the SFU (Selective Forwarding Unit)
for media routing — no backend media processing. Room presence is synchronised via Redis Pub/Sub
and WebSocket (`useDistributedState`).

## Architecture

```
Browser → POST /api/calls/session → calls_router.py → Cloudflare Calls API
                                                      → sessionId + SDP answer
Browser → RTCPeerConnection → Cloudflare SFU Anycast (media, direct)
Browser → /wss/events + Redis → room presence (useDistributedState)
```

## States

The cell handles 4 states:
1. **Error** — connection failed, credential missing, permission denied
2. **Disconnected** — no call active, "Start Party" button shown
3. **Connected** — call active with video grid and controls
4. **Waiting** — connected but no remote participants yet

## Integration

### Adding to a viewer
```typescript
import { usePartyCalls } from '@artifacts/shared/composables/usePartyCalls'
const { isConnected, startCall, hangUp } = usePartyCalls()
```

### Required environment
- Cloudflare Calls credentials in vault (`cloudflare-app-id`, `cloudflare-app-secret`)
- WebRTC-compatible browser (Chrome, Firefox, Edge, Safari)
- HTTPS or localhost (required by `getUserMedia` and `getDisplayMedia`)

## Translations

- `en.json` — English
- `pt-BR.json` — Portuguese (Brazil)
