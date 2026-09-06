/**
 * promotion.ts — Pure helpers for artifact promotion (sandbox → runtime).
 *
 * Kept dependency-free so it can be imported and unit-tested in isolation
 * (the ArtifactsManagerCell module has heavy #canonical/ imports that the
 * vitest resolver cannot load — see artifacts/tests/stubs). Mirrors the
 * backend `_type_to_dir()` and the /bundle · /promote status mapping.
 */

/** Maps an artifact record type (hyphenated) to the /bundle directory name. */
export function artifactTypeToDirName(type: string): string | null {
  switch (type) {
    case 'cell-type':
      return 'cell_types'
    case 'book':
      return 'book_types'
    case 'service':
      return 'services'
    case 'worker':
    case 'job-type':
      return 'workers'
    default:
      return null
  }
}

/** Promotion error codes mapped to i18n keys by the View. */
export type PromoteErrorCode =
  | 'promoteForbidden'
  | 'promoteConflict'
  | 'promoteInvalid'
  | 'promoteUnsupportedType'
  | 'promoteFailed'

/** Structured promotion error carrying a code the View can translate to i18n. */
export class PromoteError extends Error {
  readonly code: PromoteErrorCode

  constructor(code: PromoteErrorCode, message: string) {
    super(message)
    this.name = 'PromoteError'
    this.code = code
  }
}

/** A transitive dependency resolved by the /bundle contract. */
export interface DependencyPreview {
  artifact_type: string
  slug: string
  version?: string
  stage?: string
}

/** Result of a successful promotion (sandbox → runtime/user/{owner}). */
export interface PromotionSummary {
  bundleId: string
  promotedCount: number
  entries: Array<{ artifact_type: string; slug: string; target_path: string }>
}

/**
 * Map an HTTP status from the artifacts API to a structured {@link PromoteError}:
 * 403 → forbidden (non-owner), 409 → conflict (slug/namespace), 422 → invalid
 * (validation / missing dependency), anything else → generic failure.
 */
export function classifyPromoteError(status: number, detail: string): PromoteError {
  const message = detail ? `HTTP ${status}: ${detail.slice(0, 300)}` : `HTTP ${status}`
  switch (status) {
    case 403:
      return new PromoteError('promoteForbidden', message)
    case 409:
      return new PromoteError('promoteConflict', message)
    case 422:
      return new PromoteError('promoteInvalid', message)
    default:
      return new PromoteError('promoteFailed', message)
  }
}
