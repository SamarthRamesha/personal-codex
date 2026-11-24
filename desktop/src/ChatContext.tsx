import { useEffect, useState } from 'react';
import { api } from './api';
import { contextSummary } from './chatContext';
import type { ChatContextReport } from './chatContext';

const errorText=(error:unknown)=>error instanceof Error?error.message:String(error);

/** What the next turn can draw on. Read-only; it never triggers a model call or a file read. */
export function ChatContext({conversationId}:{conversationId:string}){
  const [report,setReport]=useState<ChatContextReport|null>(null);
  const [error,setError]=useState('');
  useEffect(()=>{
    setReport(null);setError('');
    if(!conversationId)return;
    let stale=false;
    api<ChatContextReport>(`/api/conversations/${conversationId}/context`)
      .then(value=>{if(!stale)setReport(value);})
      .catch(reason=>{if(!stale)setError(errorText(reason));});
    return()=>{stale=true;};
  },[conversationId]);
  if(!conversationId)return null;
  const summary=contextSummary(report);
  return <details className="chat-context">
    <summary>Context</summary>
    <p className="muted small">{error||summary.headline}</p>
    {summary.items.map(item=><p className="muted small" key={item.key}>{item.label}</p>)}
    {report?.notes.map(note=><p className="muted small" key={note}>{note}</p>)}
  </details>;
}
