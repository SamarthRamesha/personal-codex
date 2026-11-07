import { describe, expect, it } from 'vitest';
import { SSEParser } from './api';
import type { SSE } from './api';
describe('persisted event framing',()=>{
  it('handles every character boundary, unicode, CRLF and heartbeat comments',()=>{
    const events:SSE[]=[];const parser=new SSEParser(event=>events.push(event));
    const frame=': keepalive\r\n\r\nid: 42\r\nevent: token\r\ndata: {"text":"hello 世界"}\r\n\r\nevent: done\ndata: {"status":"complete"}\n\n';
    for(const char of frame)parser.push(char);
    expect(events).toEqual([{id:42,event:'token',data:{text:'hello 世界'}},{id:0,event:'done',data:{status:'complete'}}]);
  });
  it('never dispatches a partial or malformed event as valid text',()=>{
    const events:SSE[]=[];const parser=new SSEParser(e=>events.push(e));
    parser.push('event: token\ndata: {"text":');expect(events).toEqual([]);
    expect(()=>parser.push('invalid}\n\n')).toThrow();expect(events).toEqual([]);
  });
});

describe('untrusted stream bounds',()=>{
  it('bounds a frame spread over thousands of individually small lines',()=>{
    const parser=new SSEParser(()=>{});
    expect(()=>{for(let n=0;n<10000;n++)parser.push('data: abcdefghijklmnop\n');}).toThrow('Event exceeds limit');
  });
  it('discards heartbeats without constructing an unbounded frame',()=>{
    const events:SSE[]=[];const parser=new SSEParser(e=>events.push(e));
    for(let n=0;n<10000;n++)parser.push(': ping\n');
    parser.push('\nevent: done\ndata: {}\n\n');expect(events).toEqual([{event:'done',id:0,data:{}}]);
  });
});
