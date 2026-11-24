import { useCallback, useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { listen } from '@tauri-apps/api/event';
import { NewProjectDialog } from './NewProjectDialog';
import { FullTaskDialog } from './FullTaskDialog';
import { ArrowUp, Archive, ChevronDown, ChevronRight, Circle, Code2, Copy, FileCode2, Folder, GitBranch, LayoutPanelLeft, MessageSquare, Plus, Paperclip, RefreshCw, Search, Settings2, ShieldCheck, Square, Terminal, Unplug, X } from 'lucide-react';
import { api, attachProjectFile, openFullDestination, connect, disconnect, native, offlineSession, OFFLINE_BACKEND, stream } from './api';
import { messageMeta, messageState, regenerateLabel } from './messageState';
import type { Approval, Attachment, Conversation, Diff, InferenceMetrics, Message, ModelDescriptor, Project, Provider, Task } from './api';
import { ModelDetails } from './ModelDetails';
import { InferenceStats } from './InferenceStats';
import { ProjectDocuments } from './ProjectDocuments';
import { ProjectReadiness } from './ProjectReadiness';
import { ProjectTaskList } from './ProjectTaskList';
import { activityNote, activityRows } from './activityFeed';
import type { ActivityEvent } from './activityFeed';
import { canCancelTask, needsOwnerAttention, taskDetail } from './projectTaskSummary';
import { providerForModel } from './providerChoice';
import { RoundEvidenceView } from './RoundEvidence';
import { TaskReportPanel } from './TaskReport';
import type { TaskReport } from './taskReportSummary';
import { TaskDelivery } from './TaskDelivery';
import { ConversationHits } from './ConversationHits';
import { ChatContext } from './ChatContext';
import { ConversationActions } from './ConversationActions';
import { filterChats, listPath, nextChatId, selectionAfterDelete } from './conversationActionRequests';
import type { TestResult } from './roundEvidenceSummary';
import { MacActions } from './MacActions';
import { MacAutomation } from './MacAutomation';

type Detail={conversation:Conversation&{messages:Message[];tasks:Task[]};active_messages:string[]};
type RoundReport={rounds:{id:string;round_number:number;status:string;summary?:string;error?:string;test_result?:TestResult}[];budget?:unknown;status:string};
type AgentChanges={digest:string;can_apply:boolean;files:{path:string;diff:string[];truncated:boolean}[]};
type Delivery={status:string;path:string;workspace:string;files:string[];markdown:string;commands:string};
type AgentRun = {status:string;full_task?:boolean;delivery?:Delivery|null;attempt?:number;max_rounds?:number;summary?:string;workspace?:string;files?:string[];
  command?:string;provider_id?:string;evidence:{attempt:number;type:string;exit_code?:number;changed?:string[];feedback?:string;metrics?:InferenceMetrics}[]};
type FileView={path:string;text:string;sha256:string;truncated:boolean};
type TaskView={
  id:string;
  rounds:RoundReport;
  approvals:Approval[];
  activity:ActivityEvent[];
  executions:{exit_code:number;output:string}[];
  proposal:{operations:Record<string,unknown>[];summary?:string;status:string}|null;
  diff:Diff|null;
  report:TaskReport|null;
  workspace:{status:string;path?:string;branch?:string};
};
const errorText=(error:unknown)=>error instanceof Error?error.message:String(error);
const relative=(time:number)=>new Date(time*1000).toLocaleDateString(undefined,{month:'short',day:'numeric'});

export default function App(){
  const [executionEnabled,setExecutionEnabled]=useState(true),[providerKind,setProviderKind]=useState('ollama');
  const [diagnostics,setDiagnostics]=useState<{storage:{free_bytes:number;managed_bytes:number;budget_bytes:number;reserve_bytes:number;warnings:string[];scope:string};cpu:{count:number;load_average:number[]};backups:{count:number};conversation_rows:{messages:number;chunks:number;chunk_text_bytes:number;active_messages:number;prunable_chunks:number}}|null>(null);
  const [connected,setConnected]=useState(false),[health,setHealth]=useState('Disconnected');
  const [offlineLaunch,setOfflineLaunch]=useState<boolean|null>(null),[offline,setOffline]=useState(false);
  const [offlineAddress,setOfflineAddress]=useState(OFFLINE_BACKEND);
  const [settings,setSettings]=useState(true),[url,setUrl]=useState(localStorage.getItem('pc.backend')||'http://127.0.0.1:8787');
  const [token,setToken]=useState(''),[busy,setBusy]=useState(''),[error,setError]=useState('');
  const [chats,setChats]=useState<Conversation[]>([]),[projects,setProjects]=useState<Project[]>([]),[providers,setProviders]=useState<Provider[]>([]);
  const [archivedView,setArchivedView]=useState(false),[chatFilter,setChatFilter]=useState('');
  const [chatId,setChatId]=useState(''),[detail,setDetail]=useState<Detail|null>(null),[search,setSearch]=useState('');
  const [providerId,setProviderId]=useState(''),[model,setModel]=useState(''),[models,setModels]=useState<string[]>([]),[projectId,setProjectId]=useState('');
  const [modelCatalog,setModelCatalog]=useState<ModelDescriptor[]>([]),[configuredContext,setConfiguredContext]=useState<number|null>(null);
  const [draft,setDraft]=useState(''),[pane,setPane]=useState<'chat'|'work'>('chat'),[tasks,setTasks]=useState<Task[]>([]),[taskId,setTaskSelection]=useState('');
  const [taskView,setTaskView]=useState<TaskView|null>(null);
  const [taskPrompt,setTaskPrompt]=useState('');
  const [files,setFiles]=useState<string[]>([]),[file,setFile]=useState<FileView|null>(null);
  const [command,setCommand]=useState('python3 -m unittest discover -s tests -v');
  const [projectPath,setProjectPath]=useState(''),[newProject,setNewProject]=useState(false),[providerEndpoint,setProviderEndpoint]=useState('http://127.0.0.1:11434'),[providerModel,setProviderModel]=useState('');
  const [fullDialog,setFullDialog]=useState<{prompt:string;mode:'new'|'existing'|'registered'}|null>(null);
  const [copiedCommands,setCopiedCommands]=useState(false);
  const [macActions,setMacActions]=useState(false),[macAutomation,setMacAutomation]=useState(false);
  const [projectPrompt,setProjectPrompt]=useState<string|null>(null),[existingProject,setExistingProject]=useState(false);
  const [attachments,setAttachments]=useState<Attachment[]>([]),[dropReady,setDropReady]=useState(false);
  const [agentRun,setAgentRun]=useState<AgentRun|null>(null),[confirmRun,setConfirmRun]=useState(false);
  const [agentChanges,setAgentChanges]=useState<AgentChanges|null>(null),[appliedPath,setAppliedPath]=useState('');
  const sendPending=useRef(false);
  const taskRequest=useRef(0), taskRef=useRef(taskId);
  taskRef.current=taskId;
  const streamEpoch=useRef(0),bottom=useRef<HTMLDivElement>(null),chatRef=useRef(chatId),lastSeq=useRef<Record<string,number>>({});
  chatRef.current=chatId;
  const provider=providers.find(x=>x.id===providerId), selectedProject=projects.find(x=>x.id===projectId),active=detail?.active_messages||[];
  const selectedTask=tasks.find(x=>x.id===taskId);
  const currentTask=taskView?.id===taskId?taskView:null;
  const {rounds, proposal, diff}=currentTask||{};
  const agentActive=agentRun?.status==='running';
  function setTaskId(id:string){
    if(taskRef.current===id)return;
    taskRequest.current++;taskRef.current=id;
    setTaskSelection(id);setTaskView(null);
    setAgentRun(null);setConfirmRun(false);setAgentChanges(null);setAppliedPath('');setCopiedCommands(false);
  }
  function selectProvider(id:string){
    setProviderId(id);
    setModel(providers.find(item=>item.id===id)?.model||'');
  }
  useEffect(()=>{
    offlineSession().then(address=>{setOfflineLaunch(!!address);if(address)setOfflineAddress(address);}).catch(e=>setError(errorText(e)));
  },[]);
  const act=useCallback(async(name:string,fn:()=>Promise<void>)=>{setBusy(name);setError('');try{await fn();}catch(e){setError(errorText(e));}finally{setBusy('');}},[]);
  const refresh=useCallback(async()=>{
    const [c,p,m,t]=await Promise.all([api<{conversations:Conversation[]}>('/api/conversations'),api<Project[]>('/api/projects'),api<Provider[]>('/api/providers'),api<Task[]>('/api/tasks')]);
    setChats(c.conversations);setProjects(p);setProviders(m);setTasks(t);
    return {chats:c.conversations,providers:m};
  },[]);
  const loadChat=useCallback(async(id:string)=>{
    const data=await api<Detail>(`/api/conversations/${id}`);if(chatRef.current!==id)return;
    for(const message of data.conversation.messages)lastSeq.current[message.id]=message.last_seq||0;
    setDetail(data);setProjectId(data.conversation.project_id||'');setProviderId(data.conversation.provider_id||'');setModel(data.conversation.model||'');
  },[]);
  const loadTask=useCallback(async(id:string)=>{
    const request=++taskRequest.current;
    const base=`/api/tasks/${id}`;
    const [rounds,approvals,activity,executions,proposal,diff,workspace,report]=await Promise.all([
      api<RoundReport>(`${base}/agent/rounds`),
      api<Approval[]>(`/api/approvals?task_id=${encodeURIComponent(id)}`),
      api<ActivityEvent[]>(`${base}/events`),
      api<TaskView['executions']>(`${base}/executions`),
      api<TaskView['proposal']>(`${base}/agent`),
      api<Diff>(`${base}/agent/diff`).catch(()=>null),
      api<TaskView['workspace']>(`${base}/workspace`),
      api<TaskReport>(`${base}/agent/report`).catch(()=>null),
    ]);
    if(taskRef.current===id&&request===taskRequest.current)
      setTaskView({id,rounds,approvals:approvals.filter(approval=>approval.task_id===id),activity,executions,proposal,diff,workspace,report});
  },[]);
  useEffect(()=>{
    if(!connected)return;
    const timer=setTimeout(()=>{api<{conversations:Conversation[]}>(listPath(archivedView,search)).then(r=>setChats(r.conversations)).catch(e=>setError(errorText(e)));},220);
    return()=>clearTimeout(timer);
  },[search,connected,archivedView]);
  useEffect(()=>{
    if(!native||!offlineLaunch)return;
    const subscription=listen('personal-codex-attachment-drop',()=>setDropReady(true));
    return()=>{void subscription.then(unlisten=>unlisten());};
  },[offlineLaunch]);
  useEffect(()=>{
    setAttachments([]);
    if(!offline||!connected||!projectId)return;
    let stale=false;
    api<Attachment[]>(`/api/projects/${projectId}/attachments`).then(items=>{if(!stale)setAttachments(items);})
      .catch(e=>{if(!stale)setError(errorText(e));});
    return()=>{stale=true;};
  },[offline,connected,projectId]);
  useEffect(()=>{
    if(!offline||!connected||!taskId)return;
    let stale=false;
    async function poll(){
      try{
        const current=await api<AgentRun>(`/api/tasks/${taskId}/autonomous`);
        if(!stale)setAgentRun(current);
        if(current.full_task){
          const events=await api<ActivityEvent[]>(`/api/tasks/${taskId}/events`);
          if(!stale)setTaskView(previous=>previous?.id===taskId?{...previous,activity:events}:previous);
        }
      }catch(e){if(!stale)setError(errorText(e));}
    }
    void poll();
    const timer=setInterval(poll,1800);
    return()=>{stale=true;clearInterval(timer);};
  },[offline,connected,taskId]);
  useEffect(()=>{if(!chatId||!connected)return;setDetail(null);act('Loading',()=>loadChat(chatId));},[chatId,connected,loadChat,act]);
  useEffect(()=>{
    if(!providerId||!connected){setModels([]);setModelCatalog([]);setConfiguredContext(null);return;}
    setModels([]);setModelCatalog([]);setConfiguredContext(null);
    let cancelled=false;api<{models:string[];catalog?:ModelDescriptor[];configured_context_length?:number|null}>(`/api/providers/${providerId}/models`).then(r=>{if(!cancelled){setModels(r.models);setModelCatalog(r.catalog||[]);setConfiguredContext(r.configured_context_length??null);}}).catch(e=>{if(!cancelled){setModels([]);setModelCatalog([]);setError(errorText(e));}});
    return()=>{cancelled=true;};
  },[providerId,connected,offline]);
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
    setConnected(false);setOffline(false);setHealth('Disconnected');setExecutionEnabled(false);setChatId('');setTaskId('');setProjectId('');setProviderId('');setModel('');
    taskRequest.current++;taskRef.current='';
    setDetail(null);setChats([]);setProjects([]);setProviders([]);setTasks([]);setFiles([]);setTaskView(null);setFile(null);setDiagnostics(null);setTaskPrompt('');
  }
  async function doConnect(){await act('Connecting',async()=>{
    await disconnect();clearSession();
    const report=await connect(offlineLaunch?offlineAddress:url,offlineLaunch?'':token);
    const localOnly=report.inference_policy==='offline';
    setToken('');setOffline(localOnly);
    setExecutionEnabled(report.capabilities?.repository_execution??report.execution_mode!=='disabled');
    if(!offlineLaunch)localStorage.setItem('pc.backend',url);
    setHealth(localOnly?'Offline mode · owner authenticated':report.authenticated?'Owner authenticated':'Local development');
    setConnected(true);
    const data=await refresh();if(data.providers.length){const first=data.providers.find(p=>p.enabled&&!p.cloud_allowed&&p.kind!=='respan-gateway');if(first){setProviderId(first.id);setModel(first.model);}}
    setSettings(false);
  });}
  async function send(){if(!draft.trim()||active.length||sendPending.current)return;
    if(offlineLaunch&&offline&&!projectId&&/^(create|start|scaffold|set up|build|open|inspect)\b.{0,100}\b(project|repository|repo|application|app|dashboard|website)\b/i.test(draft.trim())){
      const mode=/^(open|inspect)\b/i.test(draft.trim())?'existing':'new';
      setFullDialog({prompt:draft.trim(),mode});return;
    }sendPending.current=true;try{await act('Sending',async()=>{
    let cid=chatId;
    if(!cid){const row=await api<Conversation>('/api/conversations','POST',{project_id:projectId||null,provider_id:providerId,model});cid=row.id;chatRef.current=cid;setChatId(cid);}
    await api(`/api/conversations/${cid}`,'PATCH',{project_id:projectId||null,provider_id:providerId,model});
    const result=await api<{assistant_message_id:string}>(`/api/conversations/${cid}/messages`,'POST',{content:draft,provider_id:providerId});
    lastSeq.current[result.assistant_message_id]=0;setDraft('');
    // Loading persisted chunks and then resuming after their last sequence prevents replay duplication.
    await loadChat(cid);await refresh();
  });}finally{sendPending.current=false;}}
  async function taskAction(suffix:string,body:unknown={}){await act('Working',async()=>{await api(`/api/tasks/${taskId}/${suffix}`,'POST',body);await loadTask(taskId);await refresh();});}
  function createProjectTask(){
    const prompt=taskPrompt.trim();
    if(!projectId||!prompt)return;
    void act('Creating task',async()=>{
      const task=await api<{id:string}>('/api/tasks','POST',{project_id:projectId,prompt});
      setTaskId(task.id);setTaskPrompt('');
      await refresh();
    });
  }
  async function attachFile(fromDrop:boolean){
    await act('Extracting local attachment',async()=>{
      const attachment=await attachProjectFile(projectId,fromDrop);
      if(attachment)setAttachments(previous=>[attachment,...previous]);
      if(fromDrop)setDropReady(false);
    });
  }
  async function projectCreated(project:Project,prompt:string){
    setProjectPrompt(null);setProjectId(project.id);setPane('work');setDraft('');
    await act('Loading project',async()=>{
      if(prompt){
        const task=await api<Task>('/api/tasks','POST',{project_id:project.id,prompt});
        setTaskId(task.id);
      }else setTaskId('');
      await refresh();
    });
  }
  async function fullStarted(project:Project,id:string){
    setFullDialog(null);setProjectId(project.id);setTaskId(id);setPane('work');setDraft('');
    await act('Loading full task',async()=>{await refresh();});
  }
  async function startAutonomous(){
    await act('Starting local run',async()=>{
      const current=await api<AgentRun>(`/api/tasks/${taskId}/autonomous/start`,'POST',{
        command:agentRun?.command||command,provider_id:agentRun?.provider_id||providerId,rounds:4,confirm:true,
      });
      setAgentRun(current);setConfirmRun(false);
    });
  }
  function resetChat(){setChatId('');chatRef.current='';setDetail(null);setDraft('');setPane('chat');}
  async function afterChatAction(removedId?:string){
    if(removedId){const next=selectionAfterDelete(removedId,chatRef.current);setChatId(next);chatRef.current=next;if(!next)setDetail(null);}
    await act('Updating conversations',async()=>{const result=await api<{conversations:Conversation[]}>(listPath(archivedView,search));setChats(result.conversations);});
  }
  const visibleApprovals=currentTask?.approvals||[];
  const activity=currentTask?.activity||[];
  const executions=currentTask?.executions||[];
  const workspaceReady=currentTask?.workspace.status==='ready';
  const activityView=activityRows(activity,30);
  const taskStatus=rounds?.status||selectedTask?.status||'';
  const visibleChats=filterChats(chats,chatFilter);

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="traffic-space" data-tauri-drag-region/><div className="brand"><div className="brand-mark"><Code2 size={19}/></div><span>Personal Codex<small>YOUR PRIVATE WORKSPACE</small></span></div>
      <button className="new-chat" onClick={resetChat}><Plus size={17}/>New conversation<span>⌘ N</span></button>
      {native&&<button className="full-task-button" onClick={()=>{setSettings(false);setMacActions(true);}}>Mac actions</button>}
      {native&&<button className="full-task-button" onClick={()=>{setSettings(false);setMacAutomation(true);}}>Mac automation</button>}
      {offline&&offlineLaunch&&executionEnabled&&<button className="full-task-button"
        onClick={()=>setFullDialog({prompt:draft,mode:selectedProject?'registered':'new'})}>Full task execution</button>}
      <label className="search"><Search size={15}/><input aria-label="Search conversations" placeholder="Search conversations" value={search} onChange={e=>setSearch(e.target.value)} onKeyDown={e=>{if(e.key!=='ArrowDown'&&e.key!=='ArrowUp')return;const target=nextChatId(visibleChats,chatId,e.key==='ArrowDown'?'down':'up');if(!target)return;e.preventDefault();setChatId(target);setPane('chat');(document.querySelector<HTMLButtonElement>(`[data-chat-id="${target}"]`))?.focus();}}/><kbd>⌘ K</kbd></label>
      <ConversationHits query={search} onOpen={id=>{setChatId(id);setPane('chat');}}/>
      <div className="section-label">PROJECTS<div className="project-actions">{offline&&offlineLaunch&&<button title="New project" onClick={()=>{setExistingProject(false);setProjectPrompt('');}}><Plus size={14}/></button>}<button title={offline&&offlineLaunch?'Open project':'Register project'} onClick={()=>{
        if(offline&&offlineLaunch){setExistingProject(true);setProjectPrompt('');}
        else{setNewProject(true);setSettings(true);}
      }}><Folder size={14}/></button></div></div>
      <div className="projects">{projects.map(p=><button className={projectId===p.id?'chosen':''} key={p.id} disabled={!!busy} onClick={()=>{setProjectId(p.id);setTaskId('');setTaskPrompt('');setPane('work');}}><Folder size={15}/><span>{p.name}</span><ChevronRight size={13}/></button>)}{!projects.length&&<p className="muted small">Register a repository to start coding.</p>}</div>
      <div className="section-label">{archivedView?'ARCHIVED':'CONVERSATIONS'}<div className="project-actions"><span>{visibleChats.length}</span><button title={archivedView?'Show active conversations':'Show archived conversations'} aria-label="Toggle archived conversations" onClick={()=>setArchivedView(value=>!value)}><Archive size={13}/></button></div></div>
      <label className="chat-filter"><select aria-label="Filter conversations by project" value={chatFilter} onChange={e=>setChatFilter(e.target.value)}><option value="">All projects</option>{projects.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
      <nav className="chat-list">{visibleChats.map(c=><div className={chatId===c.id?'chat-row chosen':'chat-row'} key={c.id}><button data-chat-id={c.id} onClick={()=>{setChatId(c.id);setPane('chat');}}><MessageSquare size={15}/><span>{c.title}<small>{c.last_message?.preview||relative(c.updated_at)}</small></span></button>{chatId===c.id&&<ConversationActions conversation={c} archived={archivedView} onDone={afterChatAction}/>}</div>)}{!visibleChats.length&&<p className="muted small empty-list">{chats.length?(chatFilter?'No conversations in this project.':'No archived conversations.'):'Your conversations stay on your backend.'}</p>}</nav>
      <div className="sidebar-bottom"><div className="privacy"><ShieldCheck size={14}/><span>Local first. Yours to control.</span></div><button onClick={()=>setSettings(true)}><Settings2 size={16}/>Settings & connection<span className={`status-dot ${connected?'online':''}`}/></button></div>
    </aside>
    <main>
      <header className="topbar" data-tauri-drag-region><div className="breadcrumbs"><LayoutPanelLeft size={16}/><span>{selectedProject?.name||'Personal workspace'}</span><ChevronRight size={13}/><strong>{pane==='chat'?'Conversation':'Coding workspace'}</strong></div><div className="top-actions"><span className={`connection ${connected?'online':''}`}><Circle size={6} fill="currentColor"/>{health}</span><button title="Refresh saved state" disabled={!connected||!!busy} onClick={()=>act('Refreshing',async()=>{await refresh();if(chatId)await loadChat(chatId);if(taskId)await loadTask(taskId);})}><RefreshCw size={15}/></button></div></header>
      <div className="view-tabs"><button className={pane==='chat'?'active':''} onClick={()=>setPane('chat')}><MessageSquare size={14}/>Conversation</button><button className={pane==='work'?'active':''} onClick={()=>setPane('work')}><Code2 size={15}/>Workspace{visibleApprovals.length>0&&<span className="count">{visibleApprovals.length}</span>}</button><div className="tab-spacer"/><span className="private-label"><ShieldCheck size={12}/>Private by default</span></div>
      {error&&<div className="error" role="alert"><span>{error}</span><button title="Dismiss error" onClick={()=>setError('')}><X size={14}/></button></div>}
      {pane==='chat'?<>
        <div className="conversation-scroll">
          {!detail?.conversation.messages.length?<div className="welcome"><div className="welcome-icon"><Code2 size={28}/></div><p className="eyebrow">A QUIET PLACE TO BUILD</p><h1>What would you like to work on?</h1><p>Think through a problem, explore your code,<br/>or turn an idea into a reviewed change.</p><div className="suggestions">{['Help me understand this project','Plan a small, testable improvement','Review an approach before I build'].map((text,i)=><button key={text} onClick={()=>setDraft(text)}>{i===0?<Folder size={17}/>:i===1?<Code2 size={17}/>:<ShieldCheck size={17}/>}<span>{text}</span><ChevronRight size={15}/></button>)}</div></div>:<div className="messages">{detail.conversation.messages.map(m=><article className={`message ${m.role}`} key={m.id}><div className="message-avatar">{m.role==='assistant'?<Code2 size={17}/>:<span>Y</span>}</div><div className="message-body"><div className="message-meta"><strong>{m.role==='assistant'?'Personal Codex':'You'}</strong>{m.role==='assistant'&&<span>{m.model||'Local model'}{messageMeta(m.status,m.latency_ms)}</span>}</div><div className="markdown"><ReactMarkdown components={{a:({children})=><span>{children}</span>,img:()=>null,pre:({children})=><div className="code-block"><div className="code-label">Code<button title="Copy code" onClick={e=>{const pre=e.currentTarget.closest('.code-block')?.querySelector('pre');if(pre)navigator.clipboard.writeText(pre.textContent||'');}}><Copy size={13}/>Copy</button></div><pre>{children}</pre></div>}}>{m.content||' '}</ReactMarkdown>{m.status==='streaming'&&<span className="typing"/>}</div>{m.error&&<p className="message-error">{m.error}</p>}<div className="message-tools"><button onClick={()=>navigator.clipboard.writeText(m.content)} title="Copy message"><Copy size={13}/></button>{messageState(m.status).canRegenerate&&<button disabled={!!busy} onClick={()=>act('Regenerating',async()=>{await api(`/api/conversations/${chatId}/regenerate`,'POST');await loadChat(chatId);})}><RefreshCw size={13}/>{regenerateLabel(m.status)}</button>}</div></div></article>)}</div>}
          <div ref={bottom}/>
        </div>
        <div className="composer-wrap">
        {offline&&offlineLaunch&&projectId&&<div className="attachment-tools">
          <button disabled={!!busy} onClick={()=>attachFile(false)}><Paperclip size={14}/>Attach file</button>
          {dropReady&&<button disabled={!!busy} onClick={()=>attachFile(true)}>Attach dropped file</button>}
          {attachments.map(item=><details key={item.id}><summary>{item.name} · {item.mechanism}</summary><pre>{item.excerpt}</pre></details>)}
        </div>}
        <div className="context-row"><select aria-label="Conversation project" value={projectId} onChange={e=>setProjectId(e.target.value)}><option value="">Personal workspace</option>{projects.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select>{chatId&&<ChatContext key={chatId} conversationId={chatId}/>}{chatId&&projectId&&<button disabled={!!busy} onClick={()=>act('Creating task',async()=>{const task=await api<{id:string}>(`/api/conversations/${chatId}/task`,'POST',{project_id:projectId,prompt:draft.trim()||undefined});setTaskId(task.id);setPane('work');await refresh();})}><GitBranch size={13}/>Create coding task</button>}</div><div className="composer"><textarea aria-label="Message" placeholder={connected?'Ask, plan, or build something…':'Connect your backend to begin…'} value={draft} disabled={!connected} onChange={e=>setDraft(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.nativeEvent.isComposing){e.preventDefault();send();}}}/><div className="composer-toolbar"><div className="model-selector"><span className="model-dot"/><select aria-label="Provider" value={providerId} onChange={e=>selectProvider(e.target.value)}><option value="">Select provider</option>{providers.filter(p=>p.enabled&&!p.cloud_allowed&&p.kind!=='respan-gateway').map(p=><option key={p.id} value={p.id}>{p.kind} · {p.model}</option>)}</select>{models.length>0&&<><ChevronDown size={11}/><select aria-label="Installed model" value={model||provider?.model||''} onChange={e=>{const chosen=e.target.value;const owner=providerForModel(providers,chosen);setModel(chosen);if(owner)setProviderId(owner.id);}}>{models.map(m=><option key={m}>{m}</option>)}</select></>}<span className="local-badge">{offline?'LOCAL OLLAMA':provider?.kind==='mac-worker'?'MAC':'BACKEND'}</span></div>{active.length?<button className="send stop" title="Stop generation" onClick={()=>act('Stopping',async()=>{await api(`/api/conversations/${chatId}/messages/${active[0]}/stop`,'POST');})}><Square size={14} fill="currentColor"/></button>:<button className="send" title="Send message" disabled={!draft.trim()||!connected||!providerId||!!busy} onClick={send}><ArrowUp size={18}/></button>}</div></div><p className="composer-note">{busy||'Changes to your code always go through review and approval.'}<span>↵ Send · ⇧ ↵ New line</span></p></div>
      </>:<div className="workspace">
        <aside className="file-tree"><div className="section-label">PROJECT FILES<Folder size={13}/></div>{!projectId&&<p className="muted small">Choose a project in the sidebar.</p>} {(agentRun?.files?.length?agentRun.files:files).map(path=><button key={path} className={file?.path===path?'chosen':''} onClick={()=>act('Reading file',async()=>setFile(await api<FileView>(agentRun?.files?.length?`/api/tasks/${taskId}/autonomous/file?path=${encodeURIComponent(path)}`:`/api/projects/${projectId}/file?path=${encodeURIComponent(path)}`)))}><FileCode2 size={13}/><span>{path}</span></button>)}</aside>
        <div className="work-content"><div className="work-header"><select aria-label="Coding task" value={taskId} onChange={e=>{
          const chosen=tasks.find(task=>task.id===e.target.value);
          if(chosen)setProjectId(chosen.project_id);
          setTaskId(e.target.value);
        }}><option value="">Choose a coding task</option>{tasks.filter(t=>!projectId||t.project_id===projectId).map(t=><option value={t.id} key={t.id}>{t.prompt.slice(0,80)} · {t.id===taskId&&agentRun?.full_task?agentRun.status:t.status}</option>)}</select>{taskId&&canCancelTask(taskStatus||selectedTask?.status||'')&&<button onClick={()=>{api(`/api/tasks/${taskId}/cancel`,'POST',{reason:'Stopped from desktop'}).then(()=>loadTask(taskId)).then(()=>refresh()).catch(e=>setError(errorText(e)));}} disabled={!connected}><Square size={12}/>Cancel task</button>}</div>
          {connected&&projectId&&!taskId&&<form className="task-controls" onSubmit={event=>{event.preventDefault();createProjectTask();}}>
            <label>Requested change<textarea value={taskPrompt} onChange={event=>setTaskPrompt(event.target.value)}/></label>
            <button className="primary" type="submit" disabled={!!busy||!taskPrompt.trim()}>Create coding task</button>
          </form>}
          <ProjectTaskList tasks={tasks} projectId={projectId} selectedId={taskId} onSelect={id=>setTaskId(id)}/>
          {offline&&connected&&projectId&&<ProjectDocuments key={projectId} projectId={projectId} attachments={attachments} onImport={()=>attachFile(false)}/>}
          {connected&&projectId&&<ProjectReadiness key={projectId} projectId={projectId}/>}
          {file&&<section className="file-preview"><div><FileCode2 size={14}/><strong>{file.path}</strong><span>Read only · {file.sha256.slice(0,12)}</span><button title="Close file" onClick={()=>setFile(null)}><X size={14}/></button></div><pre>{file.text}</pre>{file.truncated&&<p className="muted">Preview truncated.</p>}</section>}
          {!taskId&&!file&&!projectId&&<div className="work-empty"><GitBranch size={30}/><h2>Choose a project or open a saved task.</h2></div>}
          {taskId&&<>{offline&&executionEnabled&&<section className="local-agent">
            <h3>{agentRun?.full_task?'Full task execution':'Local coding agent'}</h3>
            <p className="muted small">The agent edits a task worktree and reruns your approved validation command.</p>
            {agentRun?.workspace&&<p className="muted small"><code>{agentRun.workspace}</code></p>}
            {agentRun?.summary&&<p>{agentRun.summary}</p>}
            {agentRun?.full_task&&agentRun.delivery&&<div className="full-task-report">
              <div className="button-row">
                <button onClick={()=>act('Opening project',()=>openFullDestination(taskId))}>Open project in Finder</button>
                <button onClick={()=>act('Copying commands',async()=>{
                  await navigator.clipboard.writeText(agentRun.delivery?.commands||'');setCopiedCommands(true);
                })}>{copiedCommands?'Commands copied':'Copy exact commands'}</button>
                {agentRun.status!=='complete'&&<button onClick={()=>act('Resuming full task',async()=>{
                  const run=await api<AgentRun>(`/api/tasks/${taskId}/full-resume`,'POST',{confirm:true});setAgentRun(run);
                })}>Resume within original scope</button>}
              </div>
              <ReactMarkdown components={{a:({children})=><span>{children}</span>,img:()=>null}}>{agentRun.delivery.markdown}</ReactMarkdown>
            </div>}
            {agentActive?<button onClick={()=>act('Stopping local run',async()=>{await api(`/api/tasks/${taskId}/autonomous/stop`,'POST',{});})}><Square size={14}/>Stop local run</button>:
              !agentRun?.full_task&&agentRun?.status!=='complete'&&<button disabled={!!busy||!providerId} onClick={()=>setConfirmRun(true)}>{agentRun?.command?'Resume local run':'Run local agent'}</button>}
            {confirmRun&&<div className="local-agent-scope">
              <p>Authorize up to four rounds of file creation and edits in the task worktree.</p>
              <label>Exact validation command<input aria-label="Agent validation command" value={agentRun?.command||command} readOnly={!!agentRun?.command} onChange={e=>setCommand(e.target.value)}/></label>
              <button className="primary" disabled={!!busy} onClick={startAutonomous}>Authorize and run</button>
              <button onClick={()=>setConfirmRun(false)}>Cancel</button>
            </div>}
             {!agentRun?.full_task&&agentRun?.status==='complete'&&<button disabled={!!busy} onClick={()=>act('Reviewing task changes',async()=>{
              setAgentChanges(await api<AgentChanges>(`/api/tasks/${taskId}/autonomous/changes`));
            })}>Review changes</button>}
            {agentChanges&&<div className="local-agent-scope">
              {agentChanges.files.map(item=><details key={item.path}><summary>{item.path}</summary><pre>{item.diff.join('\n')}</pre>{item.truncated&&<p>Diff preview clipped. Open the task file to inspect it.</p>}</details>)}
              {agentChanges.can_apply&&!appliedPath&&<button className="primary" disabled={!!busy} onClick={()=>act('Applying reviewed files',async()=>{
                const result=await api<{path:string}>(`/api/tasks/${taskId}/autonomous/apply`,'POST',{digest:agentChanges.digest,confirm:true});
                setAppliedPath(result.path);
              })}>Apply reviewed files to project</button>}
              {appliedPath&&<p>Files applied to {appliedPath}</p>}
            </div>}
            {agentRun?.evidence.slice(-10).map((item,index)=><details key={index}><summary>Round {item.attempt} · {item.type}{item.exit_code!=null?` · exit ${item.exit_code}`:''}</summary><InferenceStats metrics={item.metrics}/>{item.feedback&&<pre>{item.feedback}</pre>}</details>)}
          </section>}{!agentRun?.full_task&&<>{!executionEnabled&&<p className="notice">Repository execution is disabled on this backend. Chat, planning and review remain available.</p>}{taskStatus&&needsOwnerAttention(taskStatus)&&<p className="notice" role="status">{taskDetail(taskStatus)}</p>}
            {workspaceReady&&taskStatus!=='completed'&&<label className="task-provider">Planning model
              <select value={providerId} disabled={!!busy||agentActive} onChange={event=>selectProvider(event.target.value)}>
                <option value="">Choose a local provider</option>
                {providers.filter(item=>item.enabled&&!item.cloud_allowed&&item.kind!=='respan-gateway').map(item=>
                  <option key={item.id} value={item.id}>{item.kind} · {item.model}</option>)}
              </select>
            </label>}
            <section className="task-controls"><div><p className="eyebrow">CODING TASK</p><h2>{selectedTask?.prompt}</h2><span className="pill">{rounds?.status||selectedTask?.status}</span></div><div className="button-row">{!workspaceReady&&<><button disabled={!!busy||!currentTask||!executionEnabled||agentActive} onClick={()=>taskAction('workspace-request')}>Request workspace</button><button disabled={!!busy||!currentTask||!executionEnabled||agentActive} onClick={()=>taskAction('workspace')}>Create approved workspace</button></>}{workspaceReady&&<><button disabled={!!busy||!providerId||!executionEnabled||agentActive||!!diff} onClick={()=>taskAction('agent/round/request',{provider_id:providerId})}>{taskStatus==='interrupted'?'Request fresh round':'Request round'}</button><button disabled={!!busy||!providerId||!executionEnabled||agentActive||!!diff} onClick={()=>taskAction('agent/round/plan',{provider_id:providerId})}>Generate proposal</button></>}</div></section>
            {proposal?.status==='pending'&&<section><h3>Proposal operations</h3><p className="muted small">{proposal.summary}</p><pre>{JSON.stringify(proposal.operations,null,2)}</pre></section>}
            {visibleApprovals.length>0&&<section className="approvals"><h3><ShieldCheck size={15}/>Waiting for your approval</h3><p className="muted small">Each approval authorizes exactly one action and lapses ten minutes after you approve it.</p>{visibleApprovals.map(a=><div className="approval" key={a.id}><span className="pill">{a.kind}</span><pre>{a.detail}</pre><div className="button-row"><button disabled={!!busy} className="primary" onClick={()=>act('Approving',async()=>{await api(`/api/approvals/${a.id}`,'PATCH',{status:'approved'});await loadTask(taskId);})}>Approve exact request</button><button disabled={!!busy} onClick={()=>act('Rejecting',async()=>{await api(`/api/approvals/${a.id}`,'PATCH',{status:'rejected'});await loadTask(taskId);})}>Reject</button></div></div>)}</section>}
            {diff&&<section className="diff-review"><h3>Proposed changes<span className="pill">{diff.stale?'STALE':'Ready for review'}</span></h3><code>{diff.digest}</code>{(diff.files||diff.patches||[]).map((p,i)=><div key={i}><h4>{p.path}</h4><pre>{p.diff.join("\n")}</pre></div>)}<button disabled={!!busy||!executionEnabled||diff.stale||!diff.digest_valid} onClick={()=>taskAction('agent/round/execute')}>Execute approved proposal</button></section>}
            {rounds?.rounds.map(r=><section className="round" key={r.id}><h3>Round {r.round_number}<span className="pill">{r.status}</span></h3><p>{r.summary}</p>{r.error&&<p className="message-error">{r.error}</p>}{r.test_result&&<RoundEvidenceView result={r.test_result}/>}</section>)}
            {currentTask&&taskStatus==='completed'&&<TaskDelivery workspace={currentTask.workspace}
              disabled={!!busy||!executionEnabled||agentActive} act={taskAction}/>}
            <section className="terminal-panel"><h3><Terminal size={15}/>Approved command runner</h3><p className="muted small">Runs an exact approved command in this task’s isolated worktree.</p><input aria-label="Test command" value={command} onChange={e=>setCommand(e.target.value)}/><div className="button-row"><button disabled={!!busy||!workspaceReady||!executionEnabled||agentActive} onClick={()=>taskAction('execution-request',{command})}>Request command approval</button><button disabled={!!busy||!workspaceReady||!executionEnabled||agentActive} onClick={()=>taskAction('execute',{command,timeout:120})}>Run approved command</button></div>{executions.map((e,i)=><div key={i}><span className="pill">Exit {e.exit_code}</span><pre>{e.output}</pre></div>)}</section>
            </>}
            {currentTask?.report&&<TaskReportPanel report={currentTask.report}/>}
            <section className="activity"><h3>Activity</h3>{activityView.hidden>0&&<p className="muted small">{activityNote(activityView.hidden,activity.length)}</p>}{activityView.rows.map((e,i)=><p key={i}><span>{e.agent}<small>{e.at}</small></span>{e.message}</p>)}</section>
          </>}
        </div>
      </div>}
    </main>
    {fullDialog&&<FullTaskDialog initialPrompt={fullDialog.prompt} initialMode={fullDialog.mode} project={selectedProject}
      provider={providerId} close={()=>setFullDialog(null)} started={fullStarted}/>}
    {projectPrompt!==null&&<NewProjectDialog initialPrompt={projectPrompt} existing={existingProject} close={()=>setProjectPrompt(null)} created={projectCreated}/>}
    {macActions&&<MacActions close={()=>{setMacActions(false);if(!connected)setSettings(true);}}/>}
    {macAutomation&&<MacAutomation close={()=>{setMacAutomation(false);if(!connected)setSettings(true);}}/>}
    {settings&&!macActions&&!macAutomation&&<div className="modal-backdrop"><section className="settings-modal"><div className="modal-title"><div><p className="eyebrow">PERSONAL CODEX</p><h2>Connection & settings</h2></div><button title="Close settings" onClick={()=>setSettings(false)}><X size={18}/></button></div>{offlineLaunch?<p className="muted">Connect to the offline backend at {offlineAddress}. Your local owner file authenticates this session.</p>:<><p className="muted">Connect to your own backend. Remote connections require verified HTTPS on your Tailscale hostname and an owner token.</p><label>Backend URL<input value={url} onChange={e=>setUrl(e.target.value)} placeholder="https://jarvis.your-tailnet.ts.net:8787" autoComplete="off"/></label></>}{native&&!offlineLaunch&&<label>Owner token<input type="password" value={token} onChange={e=>setToken(e.target.value)} placeholder="Required for authenticated backends" autoComplete="off"/><small>Held in native process memory for this connection. Never saved in browser storage.</small></label>}{!native&&<p className="notice">Browser development preview connects only through the local Vite proxy. Use the native app for remote authentication.</p>}<div className="button-row"><button className="primary" disabled={!!busy||offlineLaunch===null} onClick={doConnect}>{busy==='Connecting'?'Connecting…':connected?'Reconnect':'Connect backend'}</button>{connected&&<button onClick={()=>act('Disconnecting',async()=>{await disconnect();clearSession();})}><Unplug size={14}/>Disconnect</button>}</div>{error&&<p className="message-error" role="alert">{error}</p>}{connected&&<><hr/><h3>Resources & recovery</h3>{diagnostics&&<div className="diagnostics"><div><span>Free storage</span><strong>{(diagnostics.storage.free_bytes/1e9).toFixed(1)} GB</strong></div><div><span>Safety reserve</span><strong>{(diagnostics.storage.reserve_bytes/1e9).toFixed(0)} GB</strong></div><div><span>Managed data / budget</span><strong>{(diagnostics.storage.managed_bytes/1e6).toFixed(1)} MB / {(diagnostics.storage.budget_bytes/1e9).toFixed(0)} GB</strong></div><div><span>Verified snapshots retained</span><strong>{diagnostics.backups.count} / 7</strong></div><div><span>Conversation rows</span><strong>{diagnostics.conversation_rows.messages} messages · {diagnostics.conversation_rows.chunks} stream chunks</strong></div><p className="muted small">{diagnostics.storage.scope}</p>{diagnostics.storage.warnings.map(w=><p className="message-error" key={w}>{w}</p>)}</div>}<button disabled={!!busy} onClick={()=>act('Creating verified snapshot',async()=>{await api('/api/maintenance/backup','POST',{});setDiagnostics(await api('/api/diagnostics'));})}>Create verified database snapshot</button><button disabled={!!busy||!diagnostics?.conversation_rows.prunable_chunks} onClick={()=>act('Compacting finished answers',async()=>{await api('/api/maintenance/compact','POST',{});setDiagnostics(await api('/api/diagnostics'));})}>Compact finished answers{diagnostics?.conversation_rows.prunable_chunks?` (${diagnostics.conversation_rows.prunable_chunks} chunks)`:''}</button><hr/><h3>Local inference</h3><ModelDetails model={modelCatalog.find(entry=>entry.name===(model||provider?.model))} context={configuredContext}/>{offline?<p className="muted small">The provider selector switches between the configured local Ollama models.</p>:<><p className="muted small">Register backend loopback Ollama or an outbound Mac worker. No models are downloaded.</p><label>Inference location<select value={providerKind} onChange={e=>setProviderKind(e.target.value)}><option value="ollama">Backend loopback Ollama</option><option value="mac-worker">Mac worker (outbound only)</option></select></label><label>{providerKind==='ollama'?'Ollama endpoint':'Mac worker uses its fixed loopback Ollama endpoint'}<input disabled={providerKind!=='ollama'} value={providerKind==='ollama'?providerEndpoint:'No inbound Mac listener'} onChange={e=>setProviderEndpoint(e.target.value)}/></label><label>Exact installed model name<input value={providerModel} onChange={e=>setProviderModel(e.target.value)} placeholder="Use a name from ollama list"/></label><button disabled={!!busy||!providerModel} onClick={()=>act('Registering provider',async()=>{const p=await api<{id:string}>('/api/providers','POST',{kind:providerKind,endpoint:providerKind==='ollama'?providerEndpoint:'',model:providerModel});await refresh();setProviderId(p.id);setModel(providerModel);setProviderModel('');})}>Register local provider</button></>}{provider?.health?.issues?.map(issue=><p className="muted small" key={issue}>{issue}</p>)}<hr/><h3>{newProject?'Register a project':'Projects'}</h3><label>Repository path on the backend<input value={projectPath} onChange={e=>setProjectPath(e.target.value)} placeholder="/path/to/your/repository"/></label><button disabled={!!busy||!projectPath} onClick={()=>act('Registering project',async()=>{const p=await api<Project>('/api/projects','POST',{path:projectPath});await refresh();setProjectId(p.id);setProjectPath('');setNewProject(false);})}>Register repository</button></>}<footer><ShieldCheck size={14}/>No telemetry. No automatic cloud fallback.</footer></section></div>}
  </div>;
}
