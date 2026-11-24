import { useState } from 'react';
import { Archive, Pencil, Pin, Trash2 } from 'lucide-react';
import { api } from './api';
import { archiveRequest, canRename, deleteRequest, pinRequest, renameRequest } from './conversationActionRequests';
import type { ChatRequest } from './conversationActionRequests';

const errorText=(error:unknown)=>error instanceof Error?error.message:String(error);

/** Pin, archive/restore and delete for the selected conversation.
 *
 * Deletion is soft and recoverable on the backend, but the panel still asks for a second click: the
 * list loses the row, and a single misplaced click should not hide a conversation.
 */
export function ConversationActions({conversation,archived,onDone}:{
  conversation:{id:string;pinned:boolean;title:string};archived:boolean;onDone:(removedId?:string)=>void;
}){
  const [confirming,setConfirming]=useState(false);
  const [renaming,setRenaming]=useState(false);
  const [title,setTitle]=useState(conversation.title);
  const [error,setError]=useState('');
  async function run(request:ChatRequest){
    setError('');
    try{
      await api(request.path,request.method,request.body);
      setConfirming(false);
      onDone(request.method==='DELETE'?conversation.id:undefined);
    }catch(reason){setError(errorText(reason));}
  }
  async function saveTitle(){
    if(!canRename(title)){setError('A title needs visible text, up to 120 characters');return;}
    await run(renameRequest(conversation.id,title));
    setRenaming(false);
  }
  if(renaming) return <div className="chat-actions">
    <input aria-label="Conversation title" className="chat-rename" autoFocus value={title}
      onChange={event=>setTitle(event.target.value)}
      onKeyDown={event=>{
        if(event.key==='Enter'){event.preventDefault();void saveTitle();}
        if(event.key==='Escape'){event.preventDefault();setTitle(conversation.title);setRenaming(false);}
      }}
      onBlur={()=>{setTitle(conversation.title);setRenaming(false);}}/>
    {error&&<span className="message-error">{error}</span>}
  </div>;
  return <div className="chat-actions">
    <button title={conversation.pinned?'Unpin conversation':'Pin conversation'} aria-label="Pin conversation"
      onClick={()=>run(pinRequest(conversation))}><Pin size={12}/></button>
    <button title="Rename conversation" aria-label="Rename conversation"
      onClick={()=>{setTitle(conversation.title);setRenaming(true);}}><Pencil size={12}/></button>
    <button title={archived?'Restore to active conversations':'Archive conversation'} aria-label="Archive conversation"
      onClick={()=>run(archiveRequest(conversation.id,!archived))}><Archive size={12}/></button>
    <button title={confirming?'Click again to delete':'Delete conversation'} aria-label="Delete conversation"
      className={confirming?'danger':''} onClick={()=>confirming?run(deleteRequest(conversation.id)):setConfirming(true)}
      onBlur={()=>setConfirming(false)}><Trash2 size={12}/></button>
    {error&&<span className="message-error">{error}</span>}
  </div>;
}
