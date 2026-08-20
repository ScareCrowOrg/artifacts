/**
 * @file micState.spec.ts
 * @description Unit tests for micState.ts — the mute toggle state transition
 * (Caso B — media opt-in).
 */

import { describe, it, expect } from 'vitest'
import { resolveMicMutedAfterToggle } from '../micState'

describe('resolveMicMutedAfterToggle (Caso B — mic opt-in)', () => {
  it('first click (mic was NOT enabled) → enables the mic UNMUTED', () => {
    expect(resolveMicMutedAfterToggle(false, false)).toBe(false)
  })

  it('first click while local mute flag was set → still ends UNMUTED (enable wins)', () => {
    expect(resolveMicMutedAfterToggle(false, true)).toBe(false)
  })

  it('mic already enabled and unmuted → next click MUTES', () => {
    expect(resolveMicMutedAfterToggle(true, false)).toBe(true)
  })

  it('mic already enabled and muted → next click UNMUTES', () => {
    expect(resolveMicMutedAfterToggle(true, true)).toBe(false)
  })
})
