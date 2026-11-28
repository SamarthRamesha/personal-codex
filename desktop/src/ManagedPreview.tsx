import {useEffect,useState} from 'react';
import {api,openDevelopmentPreview} from './api';
import {previewActive,previewRequest} from './previewReview';
import type {PreviewJob} from './previewReview';
export function ManagedPreview({taskId}:{taskId:string}){
  const [job,setJob]=useState<PreviewJob|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  const [script,setScript]=useState('dev'),[port,setPort]=useState('4300'),[confirmed,setConfirmed]=useState(false);
  const path=`/api/tasks/${taskId}/preview`;
  useEffect(()=>{let stale=false;api<PreviewJob|null>(path).then(value=>{if(!stale)setJob(value);}).catch(reason=>{if(!stale)setError(String(reason));});return()=>{stale=true;};},[path]);
  useEffect(()=>{setConfirmed(false);},[job?.id]);
  const active=previewActive(job);
  useEffect(()=>{
    if(!active)return;
    let stale=false;
    const timer=setInterval(()=>{api<PreviewJob>(path).then(value=>{if(!stale)setJob(value);}).catch(reason=>{if(!stale)setError(String(reason));});},1000);
    return()=>{stale=true;clearInterval(timer);};
  },[active,path]);
  async function action(operation:string,body:unknown){
    setBusy(true);setError('');
    try{await api(`${path}/${operation}`,'POST',body);setJob(await api<PreviewJob>(path));}
    catch(reason){setError(reason instanceof Error?reason.message:String(reason));}finally{setBusy(false);}
  }
  function start(){try{void action('execute',previewRequest(job!,confirmed));}catch(reason){setError(String(reason));}}
  return <section className="readiness" aria-label="Managed development preview">
    <h3>Managed development preview</h3>
    <p className="muted small">Declared Node entry points only, such as node server.js. Your server gets one loopback listener and read access to this task worktree. Outbound connections and project writes are denied. Previews expire after 15 minutes.</p>
    {error&&<p role="alert" className="message-error">{error}</p>}
    <label>Declared script<select disabled={busy||active} value={script} onChange={event=>setScript(event.target.value)}>{['dev','start','serve','preview'].map(value=><option key={value}>{value}</option>)}</select></label>
    <label>Loopback port<input type="number" min="1024" max="65535" disabled={busy||active} value={port} onChange={event=>setPort(event.target.value)}/></label>
    <button disabled={busy||active} onClick={()=>void action('propose',{script,port:Number(port)})}>Review preview start</button>
    {job&&<>
      <p role="status">{job.status} · {job.output}</p>
      {job.status==='proposed'&&<>
        <p><code>{job.proposal.command.join(' ')}</code> in <code>{job.proposal.root}</code></p>
        <p>{job.proposal.network}. {job.proposal.files}.</p>
        <p>Address: <code>{job.proposal.url}</code></p>
        <label className="confirm-line"><input type="checkbox" checked={confirmed} onChange={event=>setConfirmed(event.target.checked)}/> Start this exact reviewed preview and loopback listener.</label>
        <button disabled={busy||!confirmed} onClick={start}>Start reviewed preview</button>
      </>}
      {active&&<button disabled={busy} onClick={()=>void action('stop',{})}>Stop owned preview</button>}
      {job.status==='running'&&<>
        <p><code>{job.proposal.url}</code> · process {job.process_id}</p>
        <button onClick={()=>{void navigator.clipboard.writeText(job.proposal.url).catch(reason=>setError(String(reason)));}}>Copy preview address</button>
        <button onClick={()=>{void openDevelopmentPreview(taskId,job.id,job.proposal.url).catch(reason=>setError(String(reason)));}}>Open preview in browser</button>
      </>}
      {job.logs&&<details><summary>Preview logs</summary><pre>{job.logs}</pre></details>}
      {['interrupted','expired','failed','exited','stopped'].includes(job.status)&&<p className="muted small">Review a new start to run again. No automatic restart or stored-process-ID cleanup occurs.</p>}
    </>}
  </section>;
}
