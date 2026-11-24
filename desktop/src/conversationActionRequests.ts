/** Requests the panel can make about a conversation, built as data so they can be tested.
 *
 * The backend has supported pinning, archiving, soft delete and archived listing since the
 * conversation milestone, with its own tests; the panel offered none of them, so an old chat could
 * not be renamed, pinned, hidden or removed from the client at all. These helpers keep the exact
 * route, method and body in one place.
 */
export type ChatRequest = {method:'PATCH'|'DELETE';path:string;body?:Record<string,unknown>};

export function listPath(archived:boolean, query:string):string {
  const params=new URLSearchParams({archived:archived?'1':'0',limit:'100'});
  const text=query.trim();
  if(text) params.set('q',text);
  return `/api/conversations?${params.toString()}`;
}

export function pinRequest(conversation:{id:string;pinned:boolean}):ChatRequest {
  return {method:'PATCH',path:`/api/conversations/${conversation.id}`,body:{pinned:!conversation.pinned}};
}

export function archiveRequest(id:string, archived=true):ChatRequest {
  return {method:'PATCH',path:`/api/conversations/${id}`,body:{archived}};
}

export function deleteRequest(id:string):ChatRequest {
  return {method:'DELETE',path:`/api/conversations/${id}`};
}

/** The backend refuses an empty title (`title must contain visible characters`), so the client can
 * say so before a round trip. 120 characters is the stored limit. */
export function canRename(title:string):boolean {
  const text=title.replace(/\s+/g,' ').trim();
  return text.length>0&&text.length<=120;
}

export function renameRequest(id:string,title:string):ChatRequest {
  const text=title.replace(/\s+/g,' ').trim();
  if(!canRename(text)) throw new Error('A conversation title needs visible text, up to 120 characters');
  return {method:'PATCH',path:`/api/conversations/${id}`,body:{title:text}};
}

/** Client-side project filter: the sidebar lists what the operator asked for, nothing else. */
export function filterChats<T extends {project_id:string|null}>(chats:T[], projectId:string):T[] {
  if(!projectId) return chats;
  return chats.filter(chat=>chat.project_id===projectId);
}

/** Deleting the open conversation must clear the view, not leave a dead id selected. */
export function selectionAfterDelete(removedId:string, currentId:string):string {
  return removedId===currentId?'':currentId;
}

/** Arrow-key movement through the visible list: from the search box into the results, then down or
 * back up. It stops at both ends instead of wrapping, so a held key cannot jump across the list. */
export function nextChatId<T extends {id:string}>(chats:T[], currentId:string, direction:'down'|'up'):string {
  if(!chats.length) return '';
  const index=chats.findIndex(chat=>chat.id===currentId);
  if(index<0) return direction==='down'?chats[0].id:'';
  const next=direction==='down'?index+1:index-1;
  if(next<0||next>=chats.length) return chats[index].id;
  return chats[next].id;
}
