import { beforeEach, describe, expect, it, vi } from 'vitest';
const bridge=vi.hoisted(()=>({calls:[] as {command:string;args:Record<string,unknown>}[],finish:null as null|(()=>void),channel:null as null|{onmessage:(value:{text:string})=>void}}));
vi.mock('@tauri-apps/api/core',()=>({
  isTauri:()=>true,
  Channel:class {onmessage=(_value:{text:string})=>{};constructor(){bridge.channel=this;}},
  invoke:vi.fn((command:string,args:Record<string,unknown>={})=>{
    bridge.calls.push({command,args});
    if(command==='backend_stream')return new Promise<void>(resolve=>{bridge.finish=resolve;});
    if(command==='cancel_stream'){bridge.finish?.();return Promise.resolve();}
    return Promise.resolve({status:200,body:JSON.stringify({ok:true,authenticated:true,execution_mode:'disabled',capabilities:{repository_execution:false,mac_worker:true}})});
  })
}));
import { api, connect, stream } from './api';
beforeEach(()=>{bridge.calls=[];bridge.finish=null;bridge.channel=null;});
describe('native bridge contract',()=>{
  it('passes credentials only into the native connection and preserves execution policy',async()=>{
    const report=await connect('https://backend.example.ts.net','synthetic-token');
    expect(report.capabilities?.repository_execution).toBe(false);
    await api('/api/conversations','POST',{title:'fixture'});
    expect(bridge.calls[0]).toEqual({command:'connect_backend',args:{baseUrl:'https://backend.example.ts.net',token:'synthetic-token'}});
    expect(bridge.calls[1]).toEqual({command:'backend_request',args:{path:'/api/conversations',method:'POST',body:{title:'fixture'}}});
  });
  it('cancels the exact stream id when its viewer aborts',async()=>{
    const controller=new AbortController();const events:unknown[]=[];
    const pending=stream('/api/conversations/c/messages/m/stream',event=>events.push(event),controller.signal);
    const id=bridge.calls[0].args.streamId;
    bridge.channel!.onmessage({text:'id: 3\nevent: token\ndata: {"text":"hello"}\n\n'});
    controller.abort();await pending;
    expect(events).toHaveLength(1);
    expect(bridge.calls[1]).toEqual({command:'cancel_stream',args:{streamId:id}});
  });
  it('closes and reports a malformed stream instead of silently rendering partial data',async()=>{
    const controller=new AbortController();
    const pending=stream('/api/conversations/c/messages/m/stream',()=>{},controller.signal);
    const rejection=expect(pending).rejects.toThrow();
    bridge.channel!.onmessage({text:'event: token\ndata: invalid-json\n\n'});
    await rejection;expect(bridge.calls[1].command).toBe('cancel_stream');
  });
});
