/**
 * @file cellTypeLoaderUtil.test.ts
 * @description `artifactStageSegment` — the single builder of the stage segment
 * used by both cell-artifact URL sites (BaseCell type.json, useCellViewProvider
 * dynamic import).
 *
 * The runtime case is the one that matters: the `user/{namespace}` segment is
 * what Auth Proxy resolves for RBAC. A silent fallback here means a URL that
 * 403s and a cell that degrades to GeneratedFormView with no server-visible
 * error — so a missing namespace must throw.
 */

import { describe, it, expect } from 'vitest'
import { artifactStageSegment } from '../cellTypeLoaderUtil'

describe('artifactStageSegment', () => {
  it('returns the stage alone for canonical (no namespace needed)', () => {
    expect(artifactStageSegment('canonical')).toBe('canonical')
    expect(artifactStageSegment('canonical', null)).toBe('canonical')
    expect(artifactStageSegment('canonical', 'ignored-owner')).toBe('canonical')
  })

  it('returns the stage alone for sandbox', () => {
    expect(artifactStageSegment('sandbox')).toBe('sandbox')
    expect(artifactStageSegment('sandbox', null)).toBe('sandbox')
  })

  it('adds the owner namespace for runtime', () => {
    expect(artifactStageSegment('runtime', '550e8400-e29b-41d4-a716-446655440000')).toBe(
      'runtime/user/550e8400-e29b-41d4-a716-446655440000',
    )
  })

  it('throws when runtime has no namespace', () => {
    expect(() => artifactStageSegment('runtime')).toThrow(/namespace/)
    expect(() => artifactStageSegment('runtime', null)).toThrow(/namespace/)
    expect(() => artifactStageSegment('runtime', '')).toThrow(/namespace/)
  })

  it('never returns a runtime segment without a namespace', () => {
    // Guard against a future "fix" that swaps the throw for a fallback: a bare
    // "runtime" segment addresses a tree that does not exist on disk.
    let segment: string | null = null
    try {
      segment = artifactStageSegment('runtime', undefined)
    } catch {
      segment = null
    }
    expect(segment).toBeNull()
  })
})
