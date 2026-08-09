/**
 * @file roomLabel.spec.ts
 * @description Unit tests for roomLabel.ts — the active-sessions label (F4).
 *
 * Caso A (party-cell-usability-ux): the list must show the ROOM NAME
 * (roomId), never the displayName of the first participant (which resolves to
 * the authenticated user's name, not the room name).
 */

import { describe, it, expect } from 'vitest'
import { partyRoomLabel, type RoomLike } from '../roomLabel'

function makeRoom(overrides: Partial<RoomLike> = {}): RoomLike {
  return {
    roomId: 'minha-sala',
    sessions: [],
    ...overrides,
  }
}

describe('partyRoomLabel (Caso A — room name in the session list)', () => {
  it('returns the roomId when the first participant has a displayName', () => {
    const room = makeRoom({
      sessions: [{ displayName: 'Flavio' }],
    })
    expect(partyRoomLabel(room)).toBe('minha-sala')
  })

  it('returns the roomId when the session has NO participants', () => {
    const room = makeRoom({ sessions: [] })
    expect(partyRoomLabel(room)).toBe('minha-sala')
  })

  it('returns the roomId when sessions is absent', () => {
    expect(partyRoomLabel(makeRoom({ sessions: undefined }))).toBe('minha-sala')
  })

  it('ignores a displayName even when the first participant provides one', () => {
    const room = makeRoom({
      roomId: 'sala-2',
      sessions: [{ displayName: 'Qualquer-Usuario' }],
    })
    expect(partyRoomLabel(room)).toBe('sala-2')
  })

  it('keeps the label non-empty for a room without displayName (fallback to roomId)', () => {
    const room = makeRoom({
      sessions: [{ displayName: undefined }],
    })
    expect(partyRoomLabel(room)).toBe('minha-sala')
  })
})
