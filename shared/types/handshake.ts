/**
 * handshake.ts
 *
 * Shared message interfaces for the Cockpit ↔ Runner MFE handshake protocol.
 * Migrated from useWorkspaceHandshake.ts into shared types so all viewers
 * and cell types can use them without depending on dynamic-workspace internals.
 */

import type { ThemeMode } from '@/stores/workspaceStore'

// ── Cockpit → Runner ─────────────────────────────────────────────────────────

export interface InitWorkspaceMessage {
  type: 'INIT_WORKSPACE'
  payload: {
    workspaceId: string
    sessionToken: string
    cockpitOrigin: string
    userId: string
  }
  timestamp: number
}

export interface SwitchThemeMessage {
  type: 'SWITCH_THEME'
  payload: {
    theme: ThemeMode
  }
  timestamp: number
}

export interface SwitchLocaleMessage {
  type: 'SWITCH_LOCALE'
  payload: {
    locale: string
  }
  timestamp: number
}

export interface SyncConfigMessage {
  type: 'SYNC_CONFIG'
  payload: {
    theme: ThemeMode
    locale: string
  }
  timestamp: number
}

export interface ValidationResultMessage {
  type: 'VALIDATION_RESULT'
  payload: {
    workspaceId: string
    success: boolean
    userId?: string
    error?: string
  }
  timestamp: number
}

// ── Runner → Cockpit ─────────────────────────────────────────────────────────

export interface WorkspaceReadyMessage {
  type: 'RUNNER_READY'
  payload: {
    workspaceId: string
    runnerOrigin: string
    version: string
    capabilities: string[]
    status: 'ready'
  }
  timestamp: number
}

export interface WorkspaceErrorMessage {
  type: 'RUNNER_ERROR'
  payload: {
    workspaceId: string
    errorCode: string
    message: string
  }
  timestamp: number
}

export interface ValidateSessionRequestMessage {
  type: 'VALIDATE_SESSION_REQUEST'
  payload: {
    workspaceId: string
    sessionToken: string
  }
  timestamp: number
}

// ── Handshake message type union ─────────────────────────────────────────────

export type HandshakeMessage =
  | InitWorkspaceMessage
  | SwitchThemeMessage
  | SwitchLocaleMessage
  | SyncConfigMessage
  | ValidationResultMessage
  | WorkspaceReadyMessage
  | WorkspaceErrorMessage
  | ValidateSessionRequestMessage
