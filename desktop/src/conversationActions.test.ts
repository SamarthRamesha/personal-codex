import {describe,expect,it} from 'vitest';
import {archiveRequest,deleteRequest,listPath,pinRequest,selectionAfterDelete} from './conversationActions';

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

  it('clears the open conversation only when that conversation was deleted',()=>{
    expect(selectionAfterDelete('c1','c1')).toBe('');
    expect(selectionAfterDelete('c2','c1')).toBe('c1');
  });
});
