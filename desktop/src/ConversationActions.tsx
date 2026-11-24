import { useState } from 'react';
import { Archive, Pin, Trash2 } from 'lucide-react';
import { api } from './api';
import { archiveRequest, deleteRequest, pinRequest } from './conversationActionRequests';
import type { ChatRequest } from './conversationActionRequests';

const errorText=(error:unknown)=>error instanceof Error?error.message:String(error);

/** Pin, archive/restore and delete for the selected conversation.
 *
 * Deletion is soft and recoverable on the backend, but the panel still asks for a second click: the
 * list loses the row, and a single misplaced click should not hide a conversation.
 */
export function ConversationActions({conversation,archived,onDone}:{
  conversation:{id:string;pinned:boolean};archived:boolean;onDone:(removedId?:string)=>void;
}){
  const [confirming,setConfirming]=useState(false);
  const [error,setError]=useState('');
  async function run(request:ChatRequest){
    setError('');
    try{
      await api(request.path,request.method,request.body);
      setConfirming(false);
      onDone(request.method==='DELETE'?conversation.id:undefined);
    }catch(reason){setError(errorText(reason));}
  }
  return <div className="chat-actions">
    <button title={conversation.pinned?'Unpin conversation':'Pin conversation'} aria-label="Pin conversation"
      onClick={()=>run(pinRequest(conversation))}><Pin size={12}/></button>
    <button title={archived?'Restore to active conversations':'Archive conversation'} aria-label="Archive conversation"
      onClick={()=>run(archiveRequest(conversation.id,!archived))}><Archive size={12}/></button>
    <button title={confirming?'Click again to delete':'Delete conversation'} aria-label="Delete conversation"
      className={confirming?'danger':''} onClick={()=>confirming?run(deleteRequest(conversation.id)):setConfirming(true)}
      onBlur={()=>setConfirming(false)}><Trash2 size={12}/></button>
    {error&&<span className="message-error">{error}</span>}
  </div>;
}
