# `party-calls/` — Módulos do composable `usePartyCalls`

> Refactor (issue `party-calls-modularization`): o monolítico
> `usePartyCalls.ts` (2626 linhas, blocker RULESET 1.1) virou um **facade +
> shell** reativo em `../usePartyCalls.ts` (~400 linhas) + esta subpasta irmã
> com os 5 domínios isolados. **Movimentação verbatim** — nenhuma mudança de
> comportamento, nenhum caller alterado.

## Por que este diretório se chama `party-calls/`?

Windows é case-insensitive: uma pasta `usePartyCalls/` colidiria com o arquivo
`usePartyCalls.ts` no mesmo diretório. `party-calls/` evita a colisão.

## Mapa dos módulos

| Módulo | Domínio | Funções exportadas |
|--------|---------|--------------------|
| `types.ts` | Contratos públicos | `ConnectionPhase`, `AvailableRoom`, `UsePartyCallsReturn`, `RemoteSession`, `SfuTrackResult` |
| `state.ts` | Estado singleton + invariantes + log | TODO estado module-level (`_pc`, `_localStream`, `_transceiverMeta`, `_pendingSubscribeMids`, `_remoteStreamAddedAt`, …), coleção `_pendingSubscribeTimers` (F4), helpers `_dropTransceiverMeta`/`_markMidsPending`/`_unmarkMidPending`/`_ownerHasPendingMids`/`_anchorTransceiverMetaFromMidMap`/`_clearPendingSubscribeTimers` (F4), `log` (`'composable:usePartyCalls'`), constantes |
| `http.ts` | Transporte | `_apiFetchJson`, `_pollProvisionTask` (F8: retry transiente com backoff), `_executePartyAction` |
| `sfuSignaling.ts` | Primitivas WebRTC/SFU | `_waitForIceConnected`, `_registerLocalTracksOnSfu`, `_teardownRemoteMedia`, `_answerSfuRenegotiationOffer`, `_closeLocalRenegotiation` (F9: fechamento único de renegociação + rollback em regResult null — G2), `_removeTrackFromSfu`, `_createAndSetOffer` |
| `subscription.ts` | Assinatura remota | `_subscribeToRemoteTracks` (+ `_logSfuStatsDump` interno) |
| `discovery.ts` | Descoberta/registry/heartbeat | `_refreshDiscovery`, `_registerAndDiscoverSessions`, `_updateRegistryTracks`, `_startHeartbeat`, `_stopHeartbeat` |
| `remoteMedia.ts` | Classificação ontrack + merge | `_handleRemoteTrack` (param `remoteStreams`) (+ `_cleanupEndedRemoteTrack` interno) |
| `localMedia.ts` | Mídia local + publish | `createLocalMediaActions(ctx)` → `{ shareStream, muteAudio, toggleCamera, toggleScreenShare, stopSharing }`, `_stopStream`, `LocalMediaContext` |

> ℹ️ O CHANGE_PLAN previa `localMedia.ts` + `publish.ts` separados; foram
> **fundidos em `localMedia.ts`** (~500 linhas, < 650) porque
> `_updatePublishedTracks` é compartilhado pelos dois e uma separação criaria
> ciclo de import.

## Grafo de dependências (sem ciclos)

```
usePartyCalls.ts (facade)
  ├─→ types / state / http
  ├─→ sfuSignaling ─→ http ─→ state
  ├─→ subscription ─→ http ─→ state
  ├─→ discovery ─→ subscription / sfuSignaling / http / state
  ├─→ remoteMedia ─→ state / sfuSignaling
  ├─→ localMedia ─→ discovery / sfuSignaling / http / state
```

## Regras de dependência (NÃO violar)

- 🚫 **`subscription.ts` NUNCA importa `discovery.ts`** — se precisar sinalizar
  re-descoberta, retorna o sinal ao chamador.
- 🚫 **Nenhum módulo de domínio importa `usePartyCalls.ts`** (facade) — o fluxo
  de dependência é sempre facade → módulos, nunca o inverso.
- ⚠️ Estado é lido/escrito **diretamente** via `./state` (semântica singleton ESM
  preservada do estado module-level original) — é onde os bugs de race vivem,
  leia `state.ts` primeiro ao debugar.

## Logging

Todos os módulos importam `log` de `state.ts` com label
`'composable:usePartyCalls'` **preservado** — filtros de telemetria e greps de
debug dependem dele. 

> 🧹 **Bug-hardening (2026-08-17)**: as strings `[DIAG]` temporárias dos ciclos
> de debug foram **removidas** (F14). Mantidos os logs operacionais/PERMANENTES —
> ex: `[pending] marked/protect/cleared`, `[cleanup] origin/blocked/removed`,
> `[bind-skip]`, `[subscribe] mid_map populated` / `transceiver_meta anchored`,
> `[publish] local tracks registered`, `[stats] inbound_rtp`, `[teardown]`. O
> teste `__tests__/usePartyCalls.test.ts` + `usePartyCalls.bugHardening.test.ts`
> assertam esses logs limpos (sem prefixo `[DIAG]`).
