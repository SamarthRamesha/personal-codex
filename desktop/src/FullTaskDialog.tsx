import {useState} from 'react';
import {Folder,Paperclip,X} from 'lucide-react';
import {api,chooseFullAttachments,chooseProjectFolder,createSelectedProject,importFullAttachments} from './api';
import type {Attachment,Project} from './api';

export function FullTaskDialog({initialPrompt,project,initialMode,provider,close,started}:{
  initialPrompt:string;project?:Project;initialMode:'new'|'existing'|'registered';provider:string;
  close:()=>void;started:(selected:Project,taskId:string)=>Promise<void>;
}){
  const [mode,setMode]=useState(initialMode),[name,setName]=useState('');
  const [prompt,setPrompt]=useState(initialPrompt),[destination,setDestination]=useState('');
  const [registered,setRegistered]=useState<Project|undefined>(undefined);
  const [pending,setPending]=useState<string[]>([]),[imported,setImported]=useState<Attachment[]>([]);
  const [rounds,setRounds]=useState(8),[minutes,setMinutes]=useState(9),[busy,setBusy]=useState(''),[error,setError]=useState('');
  const chosen=registered??(mode==='registered'?project:undefined);
  const path=chosen?.path||destination;
  const selectedIds=imported.map(item=>item.id);

  async function action(label:string,run:()=>Promise<void>){
    setBusy(label);setError('');
    try{await run();}
    catch(reason){setError(reason instanceof Error?reason.message:String(reason));}
    finally{setBusy('');}
  }
  async function start(){
    await action('Authorizing and preparing task…',async()=>{
      const target=chosen??await createSelectedProject(destination);
      setRegistered(target);
      let ids=selectedIds;
      if(pending.length){
        const selected=pending;
        setPending([]);
        const results=await importFullAttachments(target.id,selected);
        const failures=results.flatMap(item=>item.error?[item.error]:[]);
        const success=results.flatMap(item=>item.attachment?[item.attachment]:[]);
        setImported(previous=>[...success,...previous]);
        ids=[...new Set([...ids,...success.map(item=>item.id)])];
        if(failures.length)throw new Error(failures.join('\n'));
      }
      const result=await api<{task_id:string}>('/api/full-tasks','POST',{
        project_id:target.id,prompt:prompt.trim(),attachments:ids,provider_id:provider,rounds,seconds:minutes*60,confirm:true,
      });
      await started(target,result.task_id);
    });
  }

  return <div className="modal-backdrop"><section className="settings-modal project-dialog full-task-dialog" role="dialog" aria-label="Full task execution">
    <div className="modal-title"><h2>Full task execution</h2><button title="Close full task" disabled={!!busy} onClick={close}><X size={18}/></button></div>
    <label>Project request<textarea autoFocus maxLength={8000} value={prompt} disabled={!!busy}
      onChange={e=>setPrompt(e.target.value)} placeholder="Describe what to build, expected behavior, and how to verify it."/></label>
    {!registered&&<label>Workspace<select value={mode} disabled={!!busy} onChange={e=>{
      setMode(e.target.value as typeof mode);setDestination('');setImported([]);
    }}><option value="new">Create a new project</option><option value="existing">Open a Git project from Finder</option>
    {project&&<option value="registered">Use {project.name}</option>}</select></label>}
    {!chosen&&<>{mode==='new'&&<label>Project name<input value={name} maxLength={60} disabled={!!busy}
      onChange={e=>{setName(e.target.value);setDestination('');}}/></label>}
      <button disabled={!!busy||(mode==='new'&&!name.trim())} onClick={()=>action('Choosing folder…',async()=>{
        setDestination(await chooseProjectFolder(mode==='new'?name.trim():'',mode==='existing')??'');
      })}><Folder size={15}/>{mode==='new'?'Choose destination in Finder':'Choose Git project in Finder'}</button>
    </>}
    {path&&<div className="project-destination"><small>Destination</small><p><code>{path}</code></p></div>}
    <div className="full-attachments">
      <button disabled={!!busy} onClick={()=>action('Choosing attachments…',async()=>{
        setPending([]);setPending(await chooseFullAttachments());
      })}><Paperclip size={14}/>Choose attachments in Finder</button>
      {pending.length>0&&<ul>{pending.map((file,index)=><li key={index}>{file}</li>)}</ul>}
      {imported.length>0&&<div><small>Attachments included in this run</small>{imported.map(item=><div key={item.id}>
        {item.name} <button disabled={!!busy} onClick={()=>setImported(previous=>previous.filter(old=>old.id!==item.id))}>Remove</button>
      </div>)}</div>}
    </div>
    <div className="full-budgets"><label>Maximum implementation rounds<input type="number" min={2} max={12} value={rounds} disabled={!!busy}
      onChange={e=>setRounds(Number(e.target.value))}/></label>
    <label>Time budget in minutes<input type="number" min={2} max={15} value={minutes} disabled={!!busy}
      onChange={e=>setMinutes(Number(e.target.value))}/></label></div>
    <p className="muted small">Authorize one local run. The agent may inspect and edit scoped files, run contained Python or Node validations, and deliver verified changes. Delivery checks the selected Git revision and preserves conflicting files.</p>
    {error&&<p className="message-error" role="alert">{error}</p>}
    <button className="primary" disabled={!!busy||!provider||!path||!prompt.trim()||rounds<2||rounds>12||minutes<2||minutes>15||selectedIds.length+pending.length>8}
      onClick={start}>{busy||'Authorize and run full task'}</button>
  </section></div>;
}
