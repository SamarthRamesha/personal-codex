import { useState } from 'react';
import { api } from './api';

type Entry = {id:string;kind:string;content:string;verification:string};
type Proposal = {id:string;kind:string;content:string;status:string;evidence:string|null};
type Evidence = {round:number;tests:string;exit_code:number};
type Memory = {kinds:string[];memory:Entry[]};

const provenance:Record<string,string> = {
  'passing-round':'Verified by a passing round',
  manual:'Owner note',
  stale:'Evidence no longer current',
};
function readEvidence(raw:string|null):Evidence|null {
  if(!raw)return null;
  try {
    const evidence=JSON.parse(raw) as Partial<Evidence>|null;
    if(typeof evidence?.tests==='string'&&typeof evidence.round==='number'&&typeof evidence.exit_code==='number')
      return {tests:evidence.tests,round:evidence.round,exit_code:evidence.exit_code};
  } catch {
    return null;
  }
  return null;
}

export function ProjectMemory({projectId}:{projectId:string}) {
  const [memory,setMemory]=useState<Memory|null>(null);
  const [proposals,setProposals]=useState<Proposal[]>([]);
  const [kind,setKind]=useState('convention'),[content,setContent]=useState('');
  const [busy,setBusy]=useState(false),[error,setError]=useState('');
  const path=`/api/projects/${projectId}/memory`;

  async function update(mutation?:()=>Promise<unknown>){
    setBusy(true);setError('');
    try {
      await mutation?.();
      const [saved,reviews]=await Promise.all([
        api<Memory>(path),
        api<{proposals:Proposal[]}>(`${path}/proposals`),
      ]);
      setMemory(saved);
      setProposals(reviews.proposals.filter(proposal=>proposal.status==='pending'));
    } catch(reason) {
      setError(reason instanceof Error?reason.message:String(reason));
    } finally {
      setBusy(false);
    }
  }

  return <details className="project-memory" onToggle={event=>{if(event.currentTarget.open&&!busy)void update();}}>
    <summary>Project memory</summary>
    {error&&<p className="message-error" role="alert">{error}</p>}
    {!memory&&busy&&<p role="status">Loading project memory…</p>}
    {memory&&<>
      <p className="muted small">Saved notes can be included in project conversations and coding plans.</p>
      {memory.memory.length===0&&<p>No saved notes.</p>}
      {memory.memory.map(entry=><article key={entry.id}>
        <strong>{entry.kind}</strong> <small>{provenance[entry.verification]||entry.verification}</small>
        <p>{entry.content}</p>
      </article>)}
      {proposals.length>0&&<h3>Notes awaiting review</h3>}
      {proposals.map(proposal=>{
        const evidence=readEvidence(proposal.evidence);
        return <article key={proposal.id}>
        <strong>{proposal.kind}</strong>
        <p>{proposal.content}</p>
        {evidence&&<p className="muted small">Round {evidence.round} · {evidence.tests} · exit {evidence.exit_code}</p>}
        <div className="button-row">
          <button disabled={busy} onClick={()=>void update(()=>api(`/api/memory-proposals/${proposal.id}/decide`,'POST',{status:'approved'}))}>Save reviewed note</button>
          <button disabled={busy} onClick={()=>void update(()=>api(`/api/memory-proposals/${proposal.id}/decide`,'POST',{status:'rejected'}))}>Dismiss note</button>
        </div>
      </article>;
      })}
      <form onSubmit={event=>{
        event.preventDefault();
        if(!content.trim()||busy)return;
        void update(async()=>{
          await api(path,'POST',{kind,content:content.trim()});
          setContent('');
        });
      }}>
        <label>Note type<select value={kind} disabled={busy} onChange={event=>setKind(event.target.value)}>
          {memory.kinds.map(value=><option key={value}>{value}</option>)}
        </select></label>
        <label>Write a project note<textarea maxLength={2000} disabled={busy} value={content} onChange={event=>setContent(event.target.value)}/></label>
        <button type="submit" disabled={busy||!content.trim()}>Save project note</button>
      </form>
    </>}
  </details>;
}
