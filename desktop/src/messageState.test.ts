import {describe, expect, it} from 'vitest';
import {messageMeta, messageState, regenerateLabel} from './messageState';

describe('assistant message state', () => {
  it('offers regeneration for an answer the operator stopped', () => {
    // The regression: only `error` showed a retry, so a cancelled answer was a dead end.
    expect(messageState('stopped')).toEqual({label: 'Stopped', canRegenerate: true});
    expect(regenerateLabel('stopped')).toBe('Regenerate');
  });

  it('keeps failure retryable and names it a failure', () => {
    expect(messageState('error')).toEqual({label: 'Failed', canRegenerate: true});
    expect(regenerateLabel('error')).toBe('Retry');
  });

  it('never offers regeneration for an answer that is already in flight', () => {
    for (const status of ['queued', 'streaming']) {
      expect(messageState(status).canRegenerate).toBe(false);
    }
    expect(messageState('queued').label).toBe('Queued');
    expect(messageState('streaming').label).toBe('Responding');
  });

  it('reports settled work by its latency instead of a state word', () => {
    expect(messageState('complete')).toEqual({label: '', canRegenerate: false});
    expect(messageMeta('complete', 1500)).toBe(' · 1.5s');
    expect(messageMeta('complete', null)).toBe('');
    expect(messageMeta('streaming', 900)).toBe(' · responding');
    expect(messageMeta('stopped', 900)).toBe(' · stopped');
  });
});
