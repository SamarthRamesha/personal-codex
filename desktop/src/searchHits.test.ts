import {describe,expect,it} from 'vitest';
import {groupHits,hitSpeaker} from './searchHits';
import type {ConversationHit} from './searchHits';

const hit=(id:string,conversation:string,created_at:number,role='user'):ConversationHit=>
  ({message_id:id,conversation_id:conversation,role,snippet:`snippet ${id}`,created_at,title:`chat ${conversation}`});

describe('search hits',()=>{
  it('keeps the newest match per conversation in the backend order',()=>{
    const groups=groupHits([hit('m3','b',30),hit('m2','a',20),hit('m1','a',10)]);
    expect(groups.map(group=>group.conversation_id)).toEqual(['b','a']);
    expect(groups[1].snippet).toBe('snippet m2');
  });

  it('is bounded so a broad query cannot flood the sidebar',()=>{
    const many=Array.from({length:20},(_,index)=>hit(`m${index}`,`c${index}`,index));
    expect(groupHits(many,3)).toHaveLength(3);
  });

  it('labels the speaker instead of showing a raw role',()=>{
    expect(hitSpeaker('user')).toBe('You');
    expect(hitSpeaker('assistant')).toBe('Personal Codex');
    expect(hitSpeaker('system')).toBe('System');
  });
});
