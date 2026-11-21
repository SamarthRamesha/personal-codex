import {describe,it,expect} from 'vitest';
import {windowStillMatches,windowMismatchReason,type WindowEntry} from './automationWindow';

const listed: WindowEntry={index:0,title:'Synthetic fixture'};
const other: WindowEntry={index:1,title:'Personal Codex Protected Fixture'};

describe('window identity for a new scope',()=>{
  it('accepts the same window at the same position',()=>{
    expect(windowStillMatches(listed,[{...listed}],0)).toBe(true);
    expect(windowStillMatches({index:0,title:'  Padded  '},[{index:0,title:'Padded'}],0)).toBe(true);
  });
  it('refuses a different window that took the same position',()=>{
    expect(windowStillMatches(listed,[other],0)).toBe(false);
    expect(windowMismatchReason(listed,[other],0)).toContain('moved, closed or changed');
  });
  it('refuses a window that closed or a position that no longer exists',()=>{
    expect(windowStillMatches(listed,[],0)).toBe(false);
    expect(windowStillMatches({index:2,title:'Third'},[listed,other],2)).toBe(false);
    expect(windowMismatchReason(listed,[],0)).toContain('closed since it was listed');
  });
  it('refuses reordered windows even when the title is still present',()=>{
    // The chosen title now lives at another index; controlling this index would be a different window.
    expect(windowStillMatches(listed,[other,{...listed}],0)).toBe(false);
    expect(windowStillMatches({index:1,title:'Second'},[{index:0,title:'First'},{index:1,title:'Second'}],1)).toBe(true);
  });
  it('refuses an untitled window instead of trusting its position',()=>{
    expect(windowStillMatches({index:0,title:''},[{index:0,title:''}],0)).toBe(false);
    expect(windowStillMatches({index:0,title:'Named'},[{index:0,title:'   '}],0)).toBe(false);
    expect(windowMismatchReason({index:0,title:''},[{index:0,title:''}],0)).toContain('no title');
  });
  it('asks for a window when nothing was chosen',()=>{
    expect(windowStillMatches(undefined,[listed],0)).toBe(false);
    expect(windowMismatchReason(undefined,[listed],0)).toBe('Choose a window to control.');
  });
  it('does not leak other window titles in its refusal',()=>{
    const reasons=[windowMismatchReason(listed,[],0),windowMismatchReason(listed,[other],0),
      windowMismatchReason({index:0,title:''},[{index:0,title:''}],0),windowMismatchReason(undefined,[],0)];
    for(const reason of reasons){
      expect(reason).not.toContain('Synthetic fixture');
      expect(reason).not.toContain('Personal Codex Protected Fixture');
    }
  });
});
