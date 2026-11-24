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

/** Deleting the open conversation must clear the view, not leave a dead id selected. */
export function selectionAfterDelete(removedId:string, currentId:string):string {
  return removedId===currentId?'':currentId;
}
