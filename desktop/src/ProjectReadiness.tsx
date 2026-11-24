import { useEffect, useState } from 'react';
import { Check, Copy } from 'lucide-react';
import { api } from './api';
import { readinessEmptyText, readinessRows, serverLabel } from './readiness';
import type { Readiness } from './readiness';

const errorText=(error:unknown)=>error instanceof Error?error.message:String(error);

/** Read-only project readiness: manifests, dependency state and the exact commands to run.
 *
 * Every command here is shown for the owner to run deliberately. Nothing on this panel installs a
 * dependency or starts a server, and it never labels an unverified state as ready.
 */
export function ProjectReadiness({projectId}:{projectId:string}){
  const [report,setReport]=useState<Readiness|null>(null);
  const [error,setError]=useState('');
  const [copied,setCopied]=useState('');
  useEffect(()=>{
    setReport(null);setError('');setCopied('');
    if(!projectId)return;
    let stale=false;
    api<Readiness>(`/api/projects/${projectId}/environment`)
      .then(value=>{if(!stale)setReport(value);})
      .catch(reason=>{if(!stale)setError(errorText(reason));});
    return()=>{stale=true;};
  },[projectId]);
  if(!projectId)return null;
  const rows=readinessRows(report);
  async function copy(command:string){
    try{await navigator.clipboard.writeText(command);setCopied(command);}
    catch(reason){setError(errorText(reason));}
  }
  return <section className="readiness">
    <h3>Project readiness<span className="pill">read-only</span></h3>
    <p className="muted small">{error||readinessEmptyText(report)||report?.summary}</p>
    {rows.map(row=><details key={row.key} open={row.state==='missing'}>
      <summary><strong>{row.kind}</strong> · {row.label}</summary>
      <p className="muted small">{row.detail}</p>
      {row.commands.length>0&&<div className="button-row">
        {row.commands.map(command=><button key={command} title={`Copy: ${command}`} onClick={()=>copy(command)}>
          {copied===command?<Check size={13}/>:<Copy size={13}/>}<code>{command}</code>
        </button>)}
      </div>}
      {row.devServers.length>0&&<ul className="muted small">
        {row.devServers.map(server=><li key={server.script}>{serverLabel(server)}</li>)}
      </ul>}
      {row.notes.map(note=><p className="muted small" key={note}>{note}</p>)}
    </details>)}
    {report&&<p className="muted small">{report.advisories.join(' ')}</p>}
  </section>;
}
