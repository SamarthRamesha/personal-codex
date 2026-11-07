import { Channel, invoke, isTauri } from '@tauri-apps/api/core';
export type Reply = {status:number;body:string};
export type Conversation = {id:string;title:string;project_id:string|null;provider_id:string|null;model:string;pinned:boolean;updated_at:number;last_message?:{preview:string}|null};
export type Message = {id:string;role:string;content:string;status:string;model?:string;error?:string|null;latency_ms?:number;last_seq?:number};
export type Provider = {id:string;kind:string;endpoint:string;model:string;cloud_allowed:boolean;enabled:boolean;health?:{status:string}};
export type Project = {id:string;name:string;path:string};
export type Task = {id:string;project_id:string;prompt:string;status:string;updated_at:number};
export type Approval = {id:string;project_id:string;kind:string;detail:string;status:string};
export type Diff = {digest:string;digest_valid:boolean;stale:boolean;files?:{path:string;diff:string[];stale:boolean}[];patches?:{path:string;diff:string[];stale:boolean}[]};
export type SSE = {id:number;event:string;data:Record<string,unknown>};

/** Framing survives arbitrary chunk boundaries, CRLF, comments and multibyte text. */
export class SSEParser {
  private buffer=''; private frame:string[]=[];
  constructor(private deliver:(event:SSE)=>void){}
  push(text:string){
    this.buffer+=text;
    if(this.buffer.length>1_000_000) throw new Error('Event exceeds limit');
    let end:number;
    while((end=this.buffer.indexOf('\n'))>=0){
      const line=this.buffer.slice(0,end).replace(/\r$/,''); this.buffer=this.buffer.slice(end+1);
      if(line==='') {this.dispatch();this.frame=[];} else {this.frame.push(line);}
    }
  }
  private dispatch(){
    const data=this.frame.filter(x=>x.startsWith('data:')).map(x=>x.slice(5).trimStart()).join('\n');
    if(!data) return;
    const event=this.frame.find(x=>x.startsWith('event:'))?.slice(6).trim()||'message';
    const id=Number(this.frame.find(x=>x.startsWith('id:'))?.slice(3).trim()||0);
    this.deliver({event,id:Number.isFinite(id)?id:0,data:JSON.parse(data)});
  }
}
function unpack<T>(reply:Reply):T {
  let result:Record<string,unknown>;
  try{result=JSON.parse(reply.body);}catch{throw new Error('Backend returned an invalid response');}
  if(reply.status<200||reply.status>=300) throw new Error(String(result.error||`HTTP ${reply.status}`));
  return result as T;
}
export const native=isTauri();
export async function connect(baseUrl:string,token:string){
  if(!native) return unpack<{authenticated:boolean;server_name:string}>(await browserRequest('GET','/api/connection'));
  return unpack<{authenticated:boolean;server_name:string}>(await invoke<Reply>('connect_backend',{baseUrl,token}));
}
export async function disconnect(){if(native) await invoke('disconnect_backend');}
async function browserRequest(method:string,path:string,body?:unknown):Promise<Reply>{
  // Development only: Vite proxies loopback API; no credential or configurable remote URL in browser.
  const result=await fetch(path,{method,headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined});
  return {status:result.status,body:await result.text()};
}
export async function api<T>(path:string,method='GET',body?:unknown):Promise<T>{
  return unpack<T>(native?await invoke<Reply>('backend_request',{method,path,body:body??null}):await browserRequest(method,path,body));
}
export async function stream(path:string,onEvent:(event:SSE)=>void,signal:AbortSignal){
  const parser=new SSEParser(event=>{if(!signal.aborted)onEvent(event);});
  if(native){
    const onChunk=new Channel<{text:string}>(); onChunk.onmessage=chunk=>{if(!signal.aborted)parser.push(chunk.text);};
    await invoke('backend_stream',{path,onChunk});
  }else{
    const response=await fetch(path,{signal});
    if(!response.ok||!response.body) throw new Error('Event stream unavailable');
    const reader=response.body.getReader(); const decoder=new TextDecoder();
    while(!signal.aborted){const {done,value}=await reader.read();if(done)break;parser.push(decoder.decode(value,{stream:true}));}
    if(signal.aborted) await reader.cancel();
  }
}
