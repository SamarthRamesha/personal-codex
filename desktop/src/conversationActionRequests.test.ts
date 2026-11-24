import { nextChatId } from './conversationActionRequests';
import {describe,expect,it} from 'vitest';
import {archiveRequest,canRename,deleteRequest,filterChats,listPath,pinRequest,renameRequest,selectionAfterDelete} from './conversationActionRequests';

describe('conversation actions',()=>{
  it('pins and unpins by flipping the stored flag',()=>{
    expect(pinRequest({id:'c1',pinned:false})).toEqual({method:'PATCH',path:'/api/conversations/c1',body:{pinned:true}});
    expect(pinRequest({id:'c1',pinned:true}).body).toEqual({pinned:false});
  });

  it('archives and restores, and deletes with the soft-delete route',()=>{
    expect(archiveRequest('c2')).toEqual({method:'PATCH',path:'/api/conversations/c2',body:{archived:true}});
    expect(archiveRequest('c2',false).body).toEqual({archived:false});
    expect(deleteRequest('c2')).toEqual({method:'DELETE',path:'/api/conversations/c2'});
  });

  it('asks for the archived list explicitly and only sends a real query',()=>{
    expect(listPath(false,'')).toBe('/api/conversations?archived=0&limit=100');
    expect(listPath(true,'  spec  ')).toBe('/api/conversations?archived=1&limit=100&q=spec');
  });

  it('normalises a rename and refuses an empty or oversized title before the round trip',()=>{
    expect(renameRequest('c3','  Spec   review  ')).toEqual({method:'PATCH',path:'/api/conversations/c3',body:{title:'Spec review'}});
    expect(canRename('   ')).toBe(false);
    expect(canRename('x'.repeat(120))).toBe(true);
    expect(canRename('x'.repeat(121))).toBe(false);
    expect(()=>renameRequest('c3','   ')).toThrow('visible text');
  });

  it('filters the sidebar by project only when a project is chosen',()=>{
    const chats=[{id:'a',project_id:'p1'},{id:'b',project_id:null},{id:'c',project_id:'p2'}];
    expect(filterChats(chats,'')).toHaveLength(3);
    expect(filterChats(chats,'p1').map(chat=>chat.id)).toEqual(['a']);
    expect(filterChats(chats,'p2').map(chat=>chat.id)).toEqual(['c']);
  });

  it('clears the open conversation only when that conversation was deleted',()=>{
    expect(selectionAfterDelete('c1','c1')).toBe('');
    expect(selectionAfterDelete('c2','c1')).toBe('c1');
  });
});

describe('keyboard movement through the conversation list', () => {
  const chats=[{id:'a'},{id:'b'},{id:'c'}];

  it('enters the list from the search box and stops at the end', () => {
    expect(nextChatId(chats,'','down')).toBe('a');
    expect(nextChatId(chats,'c','down')).toBe('c');
    expect(nextChatId([],'', 'down')).toBe('');
  });

  it('moves up without wrapping past the first conversation', () => {
    expect(nextChatId(chats,'b','up')).toBe('a');
    expect(nextChatId(chats,'a','up')).toBe('a');
    expect(nextChatId(chats,'','up')).toBe('');
  });
});
