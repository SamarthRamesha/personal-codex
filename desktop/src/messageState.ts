/** What an assistant message's status means to the reader, and whether it can be asked again.
 *
 * A stopped answer is neither a result nor a failure: the operator cancelled it, and the only way
 * to get that same turn answered was to retype the request. Regenerating reuses the stored user
 * turn, so the same button covers both. A queued or streaming answer is already in flight and must
 * not offer it.
 */
export type MessageState = { label: string; canRegenerate: boolean };

export function messageState(status: string): MessageState {
  if (status === 'error') return {label: 'Failed', canRegenerate: true};
  if (status === 'stopped') return {label: 'Stopped', canRegenerate: true};
  if (status === 'complete') return {label: '', canRegenerate: true};
  if (status === 'queued') return {label: 'Queued', canRegenerate: false};
  if (status === 'streaming') return {label: 'Responding', canRegenerate: false};
  return {label: '', canRegenerate: false};
}

/** Meta suffix for a message: its state while it is not settled, otherwise how long it took. */
export function messageMeta(status: string, latencyMs?: number | null): string {
  const state = messageState(status);
  if (state.label) return ` · ${state.label.toLowerCase()}`;
  return latencyMs ? ` · ${(latencyMs / 1000).toFixed(1)}s` : '';
}

/** Use Retry for a failed answer. */
export function regenerateLabel(status: string): string {
  return status === 'error' ? 'Retry' : 'Regenerate';
}
