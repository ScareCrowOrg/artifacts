/**
 * @file roomLabel.ts
 * @description Pure label helper for the party-cell active-sessions list (F4).
 *
 * Extracted from View.vue so the label logic is unit-testable (RULESET Rule
 * 3.1) without pulling in the whole usePartyCalls composable (WebRTC deps).
 */

/** Minimal room shape the label needs — a subset of usePartyCalls.AvailableRoom. */
export interface RoomLike {
  roomId: string
  sessions?: Array<{ displayName?: string }>
}

/**
 * Label for a discovered room in the active-sessions list.
 *
 * The label is ALWAYS the room name (``room.roomId``) — never the displayName
 * of the first participant.  The displayName resolves to the authenticated
 * user's name via calls_rooms.register_session (the frontend does not send a
 * displayName), so the old ``first?.displayName || room.roomId`` preference
 * showed the user's own name ("Flavio") where the list should show the room
 * ("Minha-Sala").  ``roomId`` is always present on a discovered room, so the
 * label is never empty.
 */
export function partyRoomLabel(room: RoomLike): string {
  return room.roomId
}
