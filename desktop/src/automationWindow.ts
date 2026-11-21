export type WindowEntry = {index: number; title: string; number?: number};

/**
 * A window list is positional, so an index is only valid for the list it came from.
 *
 * Before a scope starts, the panel lists the app's windows again and checks that the same
 * position still holds the window the user chose. A stale index would otherwise silently
 * scope the helper to a different window, which is exactly what the native driver's own
 * identity check refuses as well.
 *
 * The window number, when the app exposes one, is the stronger identity: it survives title
 * edits and list reordering. Both are sent to the helper, and either mismatch refuses.
 */
export function windowStillMatches(listed: WindowEntry | undefined, fresh: WindowEntry[], index: number): boolean {
  const current = fresh[index];
  if (!listed || !current) return false;
  const chosen = listed.title.trim();
  const observed = current.title.trim();
  // An empty title cannot identify a window; position alone is not identity.
  if (!chosen || !observed || chosen !== observed) return false;
  // Without a number on both sides there is nothing more to compare, and the driver repeats
  // the same check before it binds the window.
  if (listed.number === undefined || current.number === undefined) return true;
  return listed.number === current.number;
}

/** Explain a refusal without leaking unrelated window titles into the message. */
export function windowMismatchReason(listed: WindowEntry | undefined, fresh: WindowEntry[], index: number): string {
  if (!listed) return 'Choose a window to control.';
  if (!fresh[index]) return 'That window closed since it was listed. List this app\'s windows again before starting a scope.';
  if (!listed.title.trim() || !fresh[index].title.trim()) {
    return 'That window has no title, so it cannot be identified reliably. List this app\'s windows again and choose a titled one.';
  }
  if (listed.title.trim() === fresh[index].title.trim()
      && listed.number !== undefined && fresh[index].number !== undefined && listed.number !== fresh[index].number) {
    return 'That window was replaced by a different window with the same title. List this app\'s windows again before starting a scope.';
  }
  return 'That window moved, closed or changed since it was listed. List this app\'s windows again before starting a scope.';
}
