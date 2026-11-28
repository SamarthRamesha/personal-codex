import {useEffect,useState} from 'react';
import {api} from './api';
import {canInstall,installationRequest} from './dependencyReview';
import type {DependencyJob} from './dependencyReview';
export function DependencyInstall({taskId,onInstalled}:{taskId:string;onInstalled:()=>void}){
  const [job,setJob]=useState<DependencyJob|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  const [confirmed,setConfirmed]=useState(false),[networkConfirmed,setNetworkConfirmed]=useState(false);
  const path=`/api/tasks/${taskId}/dependencies`;
  useEffect(()=>{let stale=false;api<DependencyJob|null>(path).then(value=>{if(!stale)setJob(value);}).catch(reason=>{if(!stale)setError(String(reason));});return()=>{stale=true;};},[path]);
  useEffect(()=>{setConfirmed(false);setNetworkConfirmed(false);},[job?.id]);
  useEffect(()=>{
    if(job?.status!=='running')return;
    let stale=false;
    const timer=setInterval(()=>{api<DependencyJob>(path).then(value=>{if(stale)return;setJob(value);if(value.status==='complete')onInstalled();}).catch(reason=>{if(!stale)setError(String(reason));});},1000);
    return()=>{stale=true;clearInterval(timer);};
  },[path,job?.status,onInstalled]);
  async function action(suffix:string,body:unknown){
    setBusy(true);setError('');
    try{await api(`${path}/${suffix}`,'POST',body);setJob(await api<DependencyJob>(path));}
    catch(reason){setError(reason instanceof Error?reason.message:String(reason));}finally{setBusy(false);}
  }
  return <section className="readiness" aria-label="Reviewed dependency installation">
    <h3>Reviewed dependency installation</h3>
    <p className="muted small">Locked npm packages only. Downloads require confirmation. Package scripts stay disabled. Existing dependencies are preserved.</p>
    {error&&<p role="alert" className="message-error">{error}</p>}
    <button disabled={busy||job?.status==='running'} onClick={()=>void action('propose',{})}>Review locked npm install</button>
    {job&&<><p role="status">{job.status} {job.output}</p>
      {job.status==='proposed'&&<>
        <p>Destination: <code>{job.proposal.root}/node_modules</code></p>
        <p>{job.proposal.packages.length} locked packages from {job.proposal.network.origin}. Download limit: {job.proposal.network.max_download_bytes/1024/1024} MiB.</p>
        <p><code>{job.proposal.command.join(' ')}</code></p><p>{job.proposal.scripts}</p>
        <details><summary>Exact packages, downloads and file versions</summary><pre>{JSON.stringify({packages:job.proposal.packages,files:job.proposal.hashes,writes:job.proposal.writes},null,2)}</pre></details>
        <label className="confirm-line"><input type="checkbox" checked={confirmed} onChange={event=>setConfirmed(event.target.checked)}/> Install this reviewed lockfile into the selected task worktree.</label>
        <label className="confirm-line"><input type="checkbox" checked={networkConfirmed} onChange={event=>setNetworkConfirmed(event.target.checked)}/> Allow only the listed HTTPS npm-registry downloads, without credentials or redirects.</label>
        <button disabled={busy||!canInstall(job,confirmed,networkConfirmed)} onClick={()=>void action('execute',installationRequest(job,confirmed,networkConfirmed))}>Download and install reviewed packages</button>
      </>}
      {job.status==='running'&&<button disabled={busy} onClick={()=>void action('cancel',{})}>Cancel installation</button>}
      {['failed','cancelled','interrupted'].includes(job.status)&&<p className="muted small">No automatic retry. Review a new proposal after inspecting the result. Private staging is retained.</p>}
    </>}
  </section>;
}
