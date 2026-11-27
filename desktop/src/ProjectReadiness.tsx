import { useEffect, useState } from 'react';
import { Check, Copy } from 'lucide-react';
import { api } from './api';
import { checkNote, readinessEmptyText, readinessRows, serverLabel, toolLine } from './readiness';
import type { Readiness } from './readiness';

const errorText=(error:unknown)=>error instanceof Error?error.message:String(error);

/** Read-only project readiness: manifests, dependency state and the exact commands to run.
 *
 * Every command here is shown for the owner to run deliberately. Nothing on this panel installs a
 * dependency or starts a server, and it never labels an unverified state as ready.
 */
export function ProjectReadiness({projectId, taskId}:{projectId:string;taskId?:string}){
  const [report,setReport]=useState<Readiness|null>(null);
  const [error,setError]=useState('');
  const [copied,setCopied]=useState('');
  const [revision,setRevision]=useState(0);
  useEffect(()=>{
    setReport(null);setError('');setCopied('');
    if(!projectId)return;
    let stale=false;
    api<Readiness>(taskId?`/api/tasks/${taskId}/environment`:`/api/projects/${projectId}/environment`)
      .then(value=>{if(!stale)setReport(value);})
      .catch(reason=>{if(!stale)setError(errorText(reason));});
    return()=>{stale=true;};
  },[projectId,taskId,revision]);
  if(!projectId)return null;
  const rows=readinessRows(report);
  async function copy(command:string){
    try{await navigator.clipboard.writeText(command);setCopied(command);}
    catch(reason){setError(errorText(reason));}
  }
  return <section className="readiness">
    <h3>{taskId?'Task worktree readiness':'Project readiness'}<span className="pill">read-only</span></h3>
    <p className="muted small">{error||readinessEmptyText(report)||report?.summary}</p>
    {report&&<p><code>{report.path}</code></p>}
    <div className="button-row">
      {report&&<button onClick={()=>copy(report.path)}>Copy directory</button>}
      <button onClick={()=>setRevision(value=>value+1)}>Refresh readiness</button>
    </div>
    {rows.map(row=><details key={row.key} open={row.state==='missing'}>
      <summary><strong>{row.kind}</strong> · {row.label}</summary>
      <p className="muted small">{row.detail}</p>
      {row.commands.length>0&&<div className="button-row">
        {row.commands.map(command=><button key={command} title={`Copy: ${command}`} onClick={()=>copy(command)}>
          {copied===command?<Check size={13}/>:<Copy size={13}/>}<code>{command}</code>
        </button>)}
      </div>}
      {row.tools.length>0&&<p className="muted small">{toolLine(row.tools)}</p>}
      {row.checks.length>0&&<div className="button-row">
        {row.checks.map(check=><button key={check.script} title={`Copy: ${check.command}`} onClick={()=>copy(check.command)}>
          {copied===check.command?<Check size={13}/>:<Copy size={13}/>}<code>{check.command}</code>
        </button>)}
      </div>}
      {row.checks.length===0&&<p className="muted small">{checkNote(row)}</p>}
      {row.devServers.length>0&&<ul className="muted small">
        {row.devServers.map(server=><li key={server.script}>{serverLabel(server)}{' '}
          <button onClick={()=>copy(server.command)}>{copied===server.command?'Copied':'Copy start command'}</button>
        </li>)}
      </ul>}
      {row.devServers.length>0&&<p className="muted small">Review the declared script and its bind address, then run it from the displayed directory in a dedicated terminal. Press Ctrl+C there to stop it.</p>}
      {row.notes.map(note=><p className="muted small" key={note}>{note}</p>)}
    </details>)}
    {report&&<p className="muted small">{report.advisories.join(' ')}</p>}
  </section>;
}
