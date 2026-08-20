/**
 * @file micState.ts
 * @description Pure helper for the party-cell mute toggle state transition
 * (Caso B — media opt-in).  Extracted from View.vue's handleMuteToggle so the
 * opt-in/mute transition is unit-testable (RULESET Rule 3.1).
 */

/**
 * Resolve the UI `isMuted` state after a mic-button click.
 *
 * - First click (mic was NOT enabled yet) ENABLES the mic → the resulting
 *   state is UNMUTED (false).
 * - Later clicks (mic already enabled) flip the current mute state.
 */
export function resolveMicMutedAfterToggle(
  wasEnabled: boolean,
  wasMuted: boolean,
): boolean {
  return wasEnabled ? !wasMuted : false
}
