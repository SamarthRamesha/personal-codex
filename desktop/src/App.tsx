import { useCallback, useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { ArrowUp, ChevronDown, ChevronRight, Circle, Code2, Copy, FileCode2, Folder, GitBranch, LayoutPanelLeft, MessageSquare, Plus, RefreshCw, Search, Settings2, ShieldCheck, Square, Terminal, Unplug, X } from 'lucide-react';
import { api, connect, disconnect, native, stream } from './api';
import type { Approval, Conversation, Diff, Message, Project, Provider, Task } from './api';

type Detail={conversation:Conversation&{messages:Message[];tasks:Task[]};active_messages:string[]};
type RoundReport={rounds:{id:string;round_number:number;status:string;summary?:string;error?:string;test_result?:{tests?:unknown[];changed_files?:string[]}}[];budget?:unknown;status:string};
type FileView={path:string;text:string;sha256:string;truncated:boolean};
const errorText=(error:unknown)=>error instanceof Error?error.message:String(error);
const relative=(time:number)=>new Date(time*1000).toLocaleDateString(undefined,{month:'short',day:'numeric'});

export default function App(){
  const [diagnostics,setDiagnostics]=useState<{storage:{free_bytes:number;managed_bytes:number;budget_bytes:number;reserve_bytes:number;warnings:string[];scope:string};cpu:{count:number;load_average:number[]};backups:{count:number}}|null>(null);
  const [connected,setConnected]=useState(false),[health,setHealth]=useState('Disconnected');
  const [settings,setSettings]=useState(true),[url,setUrl]=useState(localStorage.getItem('pc.backend')||'http://127.0.0.1:8787');
  const [token,setToken]=useState(''),[busy,setBusy]=useState(''),[error,setError]=useState('');
  const [chats,setChats]=useState<Conversation[]>([]),[projects,setProjects]=useState<Project[]>([]),[providers,setProviders]=useState<Provider[]>([]);
  const [chatId,setChatId]=useState(''),[detail,setDetail]=useState<Detail|null>(null),[search,setSearch]=useState('');
  const [providerId,setProviderId]=useState(''),[model,setModel]=useState(''),[models,setModels]=useState<string[]>([]),[projectId,setProjectId]=useState('');
  const [draft,setDraft]=useState(''),[pane,setPane]=useState<'chat'|'work'>('chat'),[tasks,setTasks]=useState<Task[]>([]),[taskId,setTaskId]=useState('');
  const [proposal,setProposal]=useState<{operations:Record<string,unknown>[];summary?:string;status:string}|null>(null);
  const [approvals,setApprovals]=useState<Approval[]>([]),[rounds,setRounds]=useState<RoundReport|null>(null),[diff,setDiff]=useState<Diff|null>(null);
  const [files,setFiles]=useState<string[]>([]),[file,setFile]=useState<FileView|null>(null),[activity,setActivity]=useState<{agent:string;level:string;message:string}[]>([]);
  const [command,setCommand]=useState('python3 -m unittest discover -s tests -v'),[executions,setExecutions]=useState<{exit_code:number;output:string}[]>([]);
  const [projectPath,setProjectPath]=useState(''),[newProject,setNewProject]=useState(false),[providerEndpoint,setProviderEndpoint]=useState('http://127.0.0.1:11434'),[providerModel,setProviderModel]=useState('');
  const sendPending=useRef(false);
  const streamEpoch=useRef(0),bottom=useRef<HTMLDivElement>(null),chatRef=useRef(chatId),lastSeq=useRef<Record<string,number>>({});
  chatRef.current=chatId;
  const provider=providers.find(x=>x.id===providerId), selectedProject=projects.find(x=>x.id===projectId),active=detail?.active_messages||[];
  const selectedTask=tasks.find(x=>x.id===taskId);
  const act=useCallback(async(name:string,fn:()=>Promise<void>)=>{setBusy(name);setError('');try{await fn();}catch(e){setError(errorText(e));}finally{setBusy('');}},[]);
  const refresh=useCallback(async()=>{
    const [c,p,m,t,a]=await Promise.all([api<{conversations:Conversation[]}>('/api/conversations'),api<Project[]>('/api/projects'),api<Provider[]>('/api/providers'),api<Task[]>('/api/tasks'),api<Approval[]>('/api/approvals')]);
    setChats(c.conversations);setProjects(p);setProviders(m);setTasks(t);setApprovals(a);
    return {chats:c.conversations,providers:m};
  },[]);
  const loadChat=useCallback(async(id:string)=>{
    const data=await api<Detail>(`/api/conversations/${id}`);if(chatRef.current!==id)return;
    for(const message of data.conversation.messages)lastSeq.current[message.id]=message.last_seq||0;
    setDetail(data);setProjectId(data.conversation.project_id||'');setProviderId(data.conversation.provider_id||'');setModel(data.conversation.model||'');
  },[]);
  const loadTask=useCallback(async(id:string)=>{
    const [r,a,e,ex]=await Promise.all([api<RoundReport>(`/api/tasks/${id}/agent/rounds`),api<Approval[]>('/api/approvals'),api<{agent:string;level:string;message:string}[]>(`/api/tasks/${id}/events`),api<{exit_code:number;output:string}[]>(`/api/tasks/${id}/executions`)]);
    setRounds(r);setApprovals(a);setActivity(e);setExecutions(ex);
    setProposal(await api(`/api/tasks/${id}/agent`));
    try{setDiff(await api<Diff>(`/api/tasks/${id}/agent/diff`));}catch{setDiff(null);}
  },[]);
  useEffect(()=>{
    if(!connected)return;
    const timer=setTimeout(()=>{api<{conversations:Conversation[]}>(`/api/conversations?q=${encodeURIComponent(search)}`).then(r=>setChats(r.conversations)).catch(e=>setError(errorText(e)));},220);
    return()=>clearTimeout(timer);
  },[search,connected]);
  useEffect(()=>{if(!chatId||!connected)return;setDetail(null);act('Loading',()=>loadChat(chatId));},[chatId,connected,loadChat,act]);
  useEffect(()=>{
    if(!providerId||!connected){setModels([]);return;}
    let cancelled=false;api<{models:string[]}>(`/api/providers/${providerId}/models`).then(r=>{if(!cancelled)setModels(r.models);}).catch(e=>{if(!cancelled){setModels([]);setError(errorText(e));}});
    return()=>{cancelled=true;};
  },[providerId,connected]);
  useEffect(()=>{if(connected&&taskId)act('Loading task',()=>loadTask(taskId));},[connected,taskId,act,loadTask]);
  useEffect(()=>{
    setFile(null);if(!connected||!projectId){setFiles([]);return;}
    let cancelled=false;api<{files:string[]}>(`/api/projects/${projectId}/files`).then(r=>{if(!cancelled)setFiles(r.files);}).catch(e=>{if(!cancelled)setError(errorText(e));});return()=>{cancelled=true;};
  },[projectId,connected]);
  useEffect(()=>{if(settings&&connected)api<typeof diagnostics>('/api/diagnostics').then(setDiagnostics).catch(e=>setError(errorText(e)));},[settings,connected]);
  const activeKey=active.join(',');
  useEffect(()=>{
    if(!connected||!chatId||!activeKey)return;
    const controller=new AbortController(),epoch=++streamEpoch.current,mid=activeKey.split(',')[0];
    let done=false;
    const follow=async()=>{
      for(let attempt=0;attempt<4&&!done&&!controller.signal.aborted;attempt++){
        try{
          await stream(`/api/conversations/${chatId}/messages/${mid}/stream?after=${lastSeq.current[mid]||0}`,event=>{
            if(epoch!==streamEpoch.current)return;
            if(event.event==='token'&&event.id>(lastSeq.current[mid]||0)){
              lastSeq.current[mid]=event.id;
              // Read authoritative persisted text after completion. Streaming deltas are display-only.
              setDetail(previous=>previous?{...previous,conversation:{...previous.conversation,messages:previous.conversation.messages.map(m=>m.id===mid?{...m,content:m.content+String(event.data.text||''),status:'streaming'}:m)}}:previous);
            }
            if(event.event==='done')done=true;
          },controller.signal);
          if(done&&!controller.signal.aborted){await loadChat(chatId);await refresh();return;}
        }catch(e){if(controller.signal.aborted)return;if(attempt===3){setError(errorText(e));return;}}
        await new Promise(resolve=>setTimeout(resolve,Math.min(500*2**attempt,4000)));
      }
      if(!done&&!controller.signal.aborted)setError('Stream interrupted. Reconnect to load the saved answer.');
    };
    follow();return()=>{controller.abort();streamEpoch.current++;};
  },[activeKey,chatId,connected,loadChat,refresh]);
  useEffect(()=>{bottom.current?.scrollIntoView({behavior:'smooth'});},[detail?.conversation.messages.map(x=>x.content.length).join(',')]);
  useEffect(()=>{
    const handler=(event:KeyboardEvent)=>{if((event.metaKey||event.ctrlKey)&&event.key==='n'){event.preventDefault();setChatId('');setDetail(null);setDraft('');setPane('chat');}if((event.metaKey||event.ctrlKey)&&event.key==='k'){event.preventDefault();document.querySelector<HTMLInputElement>('[aria-label="Search conversations"]')?.focus();}if((event.metaKey||event.ctrlKey)&&event.key===','){event.preventDefault();setSettings(true);}};
    window.addEventListener('keydown',handler);return()=>window.removeEventListener('keydown',handler);
  },[]);
  function clearSession(){
    streamEpoch.current++;chatRef.current='';lastSeq.current={};
    setConnected(false);setHealth('Disconnected');setChatId('');setTaskId('');setProjectId('');setProviderId('');setModel('');
    setDetail(null);setChats([]);setProjects([]);setProviders([]);setTasks([]);setFiles([]);setRounds(null);setApprovals([]);setDiff(null);setFile(null);setExecutions([]);setActivity([]);setDiagnostics(null);setProposal(null);
  }
  async function doConnect(){await act('Connecting',async()=>{
    await disconnect();clearSession();
    const report=await connect(url,token);setToken('');localStorage.setItem('pc.backend',url);setHealth(report.authenticated?'Owner authenticated':'Local development');setConnected(true);
    const data=await refresh();if(data.providers.length){const first=data.providers.find(p=>!p.cloud_allowed&&p.kind!=='respan-gateway');if(first){setProviderId(first.id);setModel(first.model);}}
    setSettings(false);
  });}
  async function send(){if(!draft.trim()||active.length||sendPending.current)return;sendPending.current=true;try{await act('Sending',async()=>{
    let cid=chatId;
    if(!cid){const row=await api<Conversation>('/api/conversations','POST',{project_id:projectId||null,provider_id:providerId,model});cid=row.id;chatRef.current=cid;setChatId(cid);}
    await api(`/api/conversations/${cid}`,'PATCH',{project_id:projectId||null,provider_id:providerId,model});
    const result=await api<{assistant_message_id:string}>(`/api/conversations/${cid}/messages`,'POST',{content:draft,provider_id:providerId});
    lastSeq.current[result.assistant_message_id]=0;setDraft('');
    // Loading persisted chunks and then resuming after their last sequence prevents replay duplication.
    await loadChat(cid);await refresh();
  });}finally{sendPending.current=false;}}
  async function taskAction(suffix:string,body:unknown={}){await act('Working',async()=>{await api(`/api/tasks/${taskId}/${suffix}`,'POST',body);await loadTask(taskId);await refresh();});}
  function resetChat(){setChatId('');chatRef.current='';setDetail(null);setDraft('');setPane('chat');}
  const visibleApprovals=approvals.filter(a=>a.project_id===(selectedTask?.project_id||projectId));

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="traffic-space" data-tauri-drag-region/><div className="brand"><div className="brand-mark"><Code2 size={19}/></div><span>Personal Codex<small>YOUR PRIVATE WORKSPACE</small></span></div>
      <button className="new-chat" onClick={resetChat}><Plus size={17}/>New conversation<span>⌘ N</span></button>
      <label className="search"><Search size={15}/><input aria-label="Search conversations" placeholder="Search conversations" value={search} onChange={e=>setSearch(e.target.value)}/><kbd>⌘ K</kbd></label>
      <div className="section-label">PROJECTS<button title="Register project" onClick={()=>{setNewProject(true);setSettings(true);}}><Plus size={14}/></button></div>
      <div className="projects">{projects.map(p=><button className={projectId===p.id?'chosen':''} key={p.id} onClick={()=>{setProjectId(p.id);setTaskId('');setRounds(null);setProposal(null);setDiff(null);setPane('work');}}><Folder size={15}/><span>{p.name}</span><ChevronRight size={13}/></button>)}{!projects.length&&<p className="muted small">Register a repository to start coding.</p>}</div>
      <div className="section-label">CONVERSATIONS<span>{chats.length}</span></div>
      <nav className="chat-list">{chats.map(c=><button className={chatId===c.id?'chosen':''} key={c.id} onClick={()=>{setChatId(c.id);setPane('chat');}}><MessageSquare size={15}/><span>{c.title}<small>{c.last_message?.preview||relative(c.updated_at)}</small></span></button>)}{!chats.length&&<p className="muted small empty-list">Your conversations stay on your backend.</p>}</nav>
      <div className="sidebar-bottom"><div className="privacy"><ShieldCheck size={14}/><span>Local first. Yours to control.</span></div><button onClick={()=>setSettings(true)}><Settings2 size={16}/>Settings & connection<span className={`status-dot ${connected?'online':''}`}/></button></div>
    </aside>
    <main>
      <header className="topbar" data-tauri-drag-region><div className="breadcrumbs"><LayoutPanelLeft size={16}/><span>{selectedProject?.name||'Personal workspace'}</span><ChevronRight size={13}/><strong>{pane==='chat'?'Conversation':'Coding workspace'}</strong></div><div className="top-actions"><span className={`connection ${connected?'online':''}`}><Circle size={6} fill="currentColor"/>{health}</span><button title="Refresh saved state" disabled={!connected||!!busy} onClick={()=>act('Refreshing',async()=>{await refresh();if(chatId)await loadChat(chatId);if(taskId)await loadTask(taskId);})}><RefreshCw size={15}/></button></div></header>
      <div className="view-tabs"><button className={pane==='chat'?'active':''} onClick={()=>setPane('chat')}><MessageSquare size={14}/>Conversation</button><button className={pane==='work'?'active':''} onClick={()=>setPane('work')}><Code2 size={15}/>Workspace{visibleApprovals.length>0&&<span className="count">{visibleApprovals.length}</span>}</button><div className="tab-spacer"/><span className="private-label"><ShieldCheck size={12}/>Private by default</span></div>
      {error&&<div className="error" role="alert"><span>{error}</span><button title="Dismiss error" onClick={()=>setError('')}><X size={14}/></button></div>}
      {pane==='chat'?<>
        <div className="conversation-scroll">
          {!detail?.conversation.messages.length?<div className="welcome"><div className="welcome-icon"><Code2 size={28}/></div><p className="eyebrow">A QUIET PLACE TO BUILD</p><h1>What would you like to work on?</h1><p>Think through a problem, explore your code,<br/>or turn an idea into a reviewed change.</p><div className="suggestions">{['Help me understand this project','Plan a small, testable improvement','Review an approach before I build'].map((text,i)=><button key={text} onClick={()=>setDraft(text)}>{i===0?<Folder size={17}/>:i===1?<Code2 size={17}/>:<ShieldCheck size={17}/>}<span>{text}</span><ChevronRight size={15}/></button>)}</div></div>:<div className="messages">{detail.conversation.messages.map(m=><article className={`message ${m.role}`} key={m.id}><div className="message-avatar">{m.role==='assistant'?<Code2 size={17}/>:<span>Y</span>}</div><div className="message-body"><div className="message-meta"><strong>{m.role==='assistant'?'Personal Codex':'You'}</strong>{m.role==='assistant'&&<span>{m.model||'Local model'}{m.status==='streaming'?' · responding':m.latency_ms?` · ${(m.latency_ms/1000).toFixed(1)}s`:''}</span>}</div><div className="markdown"><ReactMarkdown components={{a:({children})=><span>{children}</span>,img:()=>null,pre:({children})=><div className="code-block"><div className="code-label">Code<button title="Copy code" onClick={e=>{const pre=e.currentTarget.closest('.code-block')?.querySelector('pre');if(pre)navigator.clipboard.writeText(pre.textContent||'');}}><Copy size={13}/>Copy</button></div><pre>{children}</pre></div>}}>{m.content||' '}</ReactMarkdown>{m.status==='streaming'&&<span className="typing"/>}</div>{m.error&&<p className="message-error">{m.error}</p>}<div className="message-tools"><button onClick={()=>navigator.clipboard.writeText(m.content)} title="Copy message"><Copy size={13}/></button>{m.status==='error'&&<button disabled={!!busy} onClick={()=>act('Retrying',async()=>{await api(`/api/conversations/${chatId}/regenerate`,'POST');await loadChat(chatId);})}><RefreshCw size={13}/>Retry</button>}</div></div></article>)}</div>}
          <div ref={bottom}/>
        </div>
        <div className="composer-wrap"><div className="context-row"><select aria-label="Conversation project" value={projectId} onChange={e=>setProjectId(e.target.value)}><option value="">Personal workspace</option>{projects.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select>{chatId&&projectId&&<button disabled={!!busy} onClick={()=>act('Creating task',async()=>{const task=await api<{id:string}>(`/api/conversations/${chatId}/task`,'POST',{project_id:projectId,prompt:draft.trim()||undefined});setTaskId(task.id);setPane('work');await refresh();})}><GitBranch size={13}/>Create coding task</button>}</div><div className="composer"><textarea aria-label="Message" placeholder={connected?'Ask, plan, or build something…':'Connect your backend to begin…'} value={draft} disabled={!connected} onChange={e=>setDraft(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.nativeEvent.isComposing){e.preventDefault();send();}}}/><div className="composer-toolbar"><div className="model-selector"><span className="model-dot"/><select aria-label="Provider" value={providerId} onChange={e=>{const p=providers.find(p=>p.id===e.target.value);setProviderId(e.target.value);setModel(p?.model||'');}}><option value="">Select provider</option>{providers.filter(p=>p.enabled&&!p.cloud_allowed&&p.kind!=='respan-gateway').map(p=><option key={p.id} value={p.id}>{p.kind} · {p.model}</option>)}</select>{models.length>0&&<><ChevronDown size={11}/><select aria-label="Installed model" value={model||provider?.model||''} onChange={e=>setModel(e.target.value)}>{models.map(m=><option key={m}>{m}</option>)}</select></>}<span className="local-badge">LOCAL</span></div>{active.length?<button className="send stop" title="Stop generation" onClick={()=>act('Stopping',async()=>{await api(`/api/conversations/${chatId}/messages/${active[0]}/stop`,'POST');})}><Square size={14} fill="currentColor"/></button>:<button className="send" title="Send message" disabled={!draft.trim()||!connected||!providerId||!!busy} onClick={send}><ArrowUp size={18}/></button>}</div></div><p className="composer-note">{busy||'Changes to your code always go through review and approval.'}<span>↵ Send · ⇧ ↵ New line</span></p></div>
      </>:<div className="workspace">
        <aside className="file-tree"><div className="section-label">PROJECT FILES<Folder size={13}/></div>{!projectId&&<p className="muted small">Choose a project in the sidebar.</p>}{files.map(path=><button key={path} className={file?.path===path?'chosen':''} onClick={()=>act('Reading file',async()=>setFile(await api<FileView>(`/api/projects/${projectId}/file?path=${encodeURIComponent(path)}`)))}><FileCode2 size={13}/><span>{path}</span></button>)}</aside>
        <div className="work-content"><div className="work-header"><select aria-label="Coding task" value={taskId} onChange={e=>setTaskId(e.target.value)}><option value="">Choose a coding task</option>{tasks.filter(t=>!projectId||t.project_id===projectId).map(t=><option value={t.id} key={t.id}>{t.prompt.slice(0,80)} · {t.status}</option>)}</select>{taskId&&<button onClick={()=>{api(`/api/tasks/${taskId}/cancel`,'POST',{reason:'Stopped from desktop'}).then(()=>loadTask(taskId)).catch(e=>setError(errorText(e)));}} disabled={!connected}><Square size={12}/>Cancel task</button>}</div>
          {file&&<section className="file-preview"><div><FileCode2 size={14}/><strong>{file.path}</strong><span>Read only · {file.sha256.slice(0,12)}</span><button title="Close file" onClick={()=>setFile(null)}><X size={14}/></button></div><pre>{file.text}</pre>{file.truncated&&<p className="muted">Preview truncated.</p>}</section>}
          {!taskId&&!file&&<div className="work-empty"><GitBranch size={30}/><h2>Every change has a review trail.</h2><p>Create a coding task from a conversation, then approve its workspace and review each proposed round.</p></div>}
          {taskId&&<><section className="task-controls"><div><p className="eyebrow">CODING TASK</p><h2>{selectedTask?.prompt}</h2><span className="pill">{rounds?.status||selectedTask?.status}</span></div><div className="button-row"><button disabled={!!busy} onClick={()=>taskAction('workspace-request')}>Request workspace</button><button disabled={!!busy} onClick={()=>taskAction('workspace')}>Create approved workspace</button><button disabled={!!busy||!providerId} onClick={()=>taskAction('agent/round/request',{provider_id:providerId})}>Request round</button><button disabled={!!busy||!providerId} onClick={()=>taskAction('agent/round/plan',{provider_id:providerId})}>Generate proposal</button></div></section>
            {proposal?.status==='pending'&&<section><h3>Proposal operations</h3><p className="muted small">{proposal.summary}</p><pre>{JSON.stringify(proposal.operations,null,2)}</pre></section>}
            {visibleApprovals.length>0&&<section className="approvals"><h3><ShieldCheck size={15}/>Waiting for your approval</h3>{visibleApprovals.map(a=><div className="approval" key={a.id}><span className="pill">{a.kind}</span><pre>{a.detail}</pre><div className="button-row"><button disabled={!!busy} className="primary" onClick={()=>act('Approving',async()=>{await api(`/api/approvals/${a.id}`,'PATCH',{status:'approved'});await loadTask(taskId);})}>Approve exact request</button><button disabled={!!busy} onClick={()=>act('Rejecting',async()=>{await api(`/api/approvals/${a.id}`,'PATCH',{status:'rejected'});await loadTask(taskId);})}>Reject</button></div></div>)}</section>}
            {diff&&<section className="diff-review"><h3>Proposed changes<span className="pill">{diff.stale?'STALE':'Ready for review'}</span></h3><code>{diff.digest}</code>{(diff.files||diff.patches||[]).map((p,i)=><div key={i}><h4>{p.path}</h4><pre>{p.diff.join("\n")}</pre></div>)}<button disabled={!!busy||diff.stale||!diff.digest_valid} onClick={()=>taskAction('agent/round/execute')}>Execute approved proposal</button></section>}
            {rounds?.rounds.map(r=><section className="round" key={r.id}><h3>Round {r.round_number}<span className="pill">{r.status}</span></h3><p>{r.summary}</p>{r.error&&<p className="message-error">{r.error}</p>}{r.test_result&&<pre>{JSON.stringify(r.test_result,null,2)}</pre>}</section>)}
            <section className="terminal-panel"><h3><Terminal size={15}/>Approved command runner</h3><p className="muted small">Runs an exact approved command in this task’s isolated worktree.</p><input aria-label="Test command" value={command} onChange={e=>setCommand(e.target.value)}/><div className="button-row"><button disabled={!!busy} onClick={()=>taskAction('execution-request',{command})}>Request command approval</button><button disabled={!!busy} onClick={()=>taskAction('execute',{command,timeout:120})}>Run approved command</button></div>{executions.map((e,i)=><div key={i}><span className="pill">Exit {e.exit_code}</span><pre>{e.output}</pre></div>)}</section>
            <section className="activity"><h3>Activity</h3>{activity.slice(-30).map((e,i)=><p key={i}><span>{e.agent}</span>{e.message}</p>)}</section>
          </>}
        </div>
      </div>}
    </main>
    {settings&&<div className="modal-backdrop"><section className="settings-modal"><div className="modal-title"><div><p className="eyebrow">PERSONAL CODEX</p><h2>Connection & settings</h2></div>{connected&&<button title="Close settings" onClick={()=>setSettings(false)}><X size={18}/></button>}</div><p className="muted">Connect to your own backend. Remote connections require verified HTTPS on your Tailscale hostname and an owner token.</p><label>Backend URL<input value={url} onChange={e=>setUrl(e.target.value)} placeholder="https://jarvis.your-tailnet.ts.net:8787" autoComplete="off"/></label>{native&&<label>Owner token<input type="password" value={token} onChange={e=>setToken(e.target.value)} placeholder="Required for authenticated backends" autoComplete="off"/><small>Held in native process memory for this connection. Never saved in browser storage.</small></label>}{!native&&<p className="notice">Browser development preview connects only through the local Vite proxy. Use the native app for remote authentication.</p>}<div className="button-row"><button className="primary" disabled={!!busy} onClick={doConnect}>{busy==='Connecting'?'Connecting…':connected?'Reconnect':'Connect backend'}</button>{connected&&<button onClick={()=>act('Disconnecting',async()=>{await disconnect();clearSession();})}><Unplug size={14}/>Disconnect</button>}</div>{error&&<p className="message-error" role="alert">{error}</p>}{connected&&<><hr/><h3>Resources & recovery</h3>{diagnostics&&<div className="diagnostics"><div><span>Free storage</span><strong>{(diagnostics.storage.free_bytes/1e9).toFixed(1)} GB</strong></div><div><span>Safety reserve</span><strong>{(diagnostics.storage.reserve_bytes/1e9).toFixed(0)} GB</strong></div><div><span>Managed data / budget</span><strong>{(diagnostics.storage.managed_bytes/1e6).toFixed(1)} MB / {(diagnostics.storage.budget_bytes/1e9).toFixed(0)} GB</strong></div><div><span>Verified snapshots retained</span><strong>{diagnostics.backups.count} / 7</strong></div><p className="muted small">{diagnostics.storage.scope}</p>{diagnostics.storage.warnings.map(w=><p className="message-error" key={w}>{w}</p>)}</div>}<button disabled={!!busy} onClick={()=>act('Creating verified snapshot',async()=>{await api('/api/maintenance/backup','POST',{});setDiagnostics(await api('/api/diagnostics'));})}>Create verified database snapshot</button><hr/><h3>Local inference</h3><p className="muted small">Register an existing loopback Ollama service. No models are downloaded.</p><label>Ollama endpoint<input value={providerEndpoint} onChange={e=>setProviderEndpoint(e.target.value)}/></label><label>Exact installed model name<input value={providerModel} onChange={e=>setProviderModel(e.target.value)} placeholder="Use a name from ollama list"/></label><button disabled={!!busy||!providerModel} onClick={()=>act('Registering provider',async()=>{const p=await api<{id:string}>('/api/providers','POST',{kind:'ollama',endpoint:providerEndpoint,model:providerModel});await refresh();setProviderId(p.id);setModel(providerModel);setProviderModel('');})}>Register local provider</button><hr/><h3>{newProject?'Register a project':'Projects'}</h3><label>Repository path on the backend<input value={projectPath} onChange={e=>setProjectPath(e.target.value)} placeholder="/path/to/your/repository"/></label><button disabled={!!busy||!projectPath} onClick={()=>act('Registering project',async()=>{const p=await api<Project>('/api/projects','POST',{path:projectPath});await refresh();setProjectId(p.id);setProjectPath('');setNewProject(false);})}>Register repository</button></>}<footer><ShieldCheck size={14}/>No telemetry. No automatic cloud fallback.</footer></section></div>}
  </div>;
}
