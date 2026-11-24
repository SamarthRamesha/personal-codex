/** Message-text search results, grouped so the sidebar shows where each match lives.
 *
 * The backend has returned attributed message hits since the conversation milestone, but the panel
 * only re-listed conversations, so a match inside a long chat had no visible reason for appearing.
 * These helpers keep one representative hit per conversation and label who said it.
 */
export type ConversationHit = {
  message_id:string; conversation_id:string; role:string;
  snippet:string; created_at:number; title:string;
};
export type HitGroup = {
  conversation_id:string; title:string; role:string; snippet:string; created_at:number;
};

export function hitSpeaker(role:string):string {
  if (role === 'user') return 'You';
  if (role === 'assistant') return 'Personal Codex';
  return 'System';
}

/** One row per conversation, newest match first, bounded so a broad query cannot flood the list. */
export function groupHits(hits:ConversationHit[], max = 8):HitGroup[] {
  const seen = new Set<string>();
  const groups:HitGroup[] = [];
  for (const hit of hits) {
    if (seen.has(hit.conversation_id)) continue;
    seen.add(hit.conversation_id);
    groups.push({conversation_id:hit.conversation_id, title:hit.title, role:hit.role,
      snippet:hit.snippet, created_at:hit.created_at});
    if (groups.length >= max) break;
  }
  return groups;
}
