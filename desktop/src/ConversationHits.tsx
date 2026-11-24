import { useEffect, useState } from 'react';
import { api } from './api';
import { groupHits, hitSpeaker } from './searchHits';
import type { ConversationHit } from './searchHits';

const errorText=(error:unknown)=>error instanceof Error?error.message:String(error);
const MIN_QUERY = 2;

/** Where the search text matched: one row per conversation, with the speaker and the snippet. */
export function ConversationHits({query,onOpen}:{query:string;onOpen:(id:string)=>void}){
  const [hits,setHits]=useState<ConversationHit[]>([]);
  const [searched,setSearched]=useState('');
  const [error,setError]=useState('');
  useEffect(()=>{
    const text=query.trim();
    setError('');
    if(text.length<MIN_QUERY){setHits([]);setSearched('');return;}
    let stale=false;
    const timer=setTimeout(()=>{
      api<{results:ConversationHit[]}>(`/api/conversations/search?q=${encodeURIComponent(text)}&limit=20`)
        .then(value=>{if(!stale){setHits(value.results||[]);setSearched(text);}})
        .catch(reason=>{if(!stale){setHits([]);setSearched(text);setError(errorText(reason));}});
    },220);
    return()=>{stale=true;clearTimeout(timer);};
  },[query]);
  if(query.trim().length<MIN_QUERY) return null;
  const groups=groupHits(hits);
  return <div className="hit-list" aria-label="Message matches">
    {error&&<p className="muted small">{error}</p>}
    {!error&&groups.length===0&&searched===query.trim()&&
      <p className="muted small">No message text matches this search.</p>}
    {groups.map(hit=><button key={hit.conversation_id} title={`Open ${hit.title}`} onClick={()=>onOpen(hit.conversation_id)}>
      <span className="hit-title">{hit.title}</span>
      <small>{hitSpeaker(hit.role)} · {hit.snippet}</small>
    </button>)}
  </div>;
}
