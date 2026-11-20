import { useEffect, useState } from 'react';
import { api } from './api';
import type { Attachment } from './api';

export type DocumentHit={attachment_id:string;name:string;mechanism:string;source_hash:string;chunk:number;start_char:number;end_char:number;excerpt:string;trust:string};
type Document={attachment_id:string;name:string;source_hash:string;chunks:number;stale:boolean};
type Catalog={available:boolean;documents:Document[];limits:{documents:number}};

export function DocumentResults({hits}:{hits:DocumentHit[]}){
  return <div className="document-results">{hits.map(hit=><article key={`${hit.attachment_id}-${hit.chunk}`}>
    <strong>{hit.name}</strong><small>Excerpt {hit.chunk+1} · characters {hit.start_char}–{hit.end_char} · source fingerprint <code title={hit.source_hash}>{hit.source_hash.slice(0,12)}</code></small>
    <pre>{hit.excerpt}</pre><small>Untrusted reference · {hit.mechanism}</small>
  </article>)}</div>;
}

export function ProjectDocuments({projectId,attachments,onImport}:{projectId:string;attachments:Attachment[];onImport:()=>Promise<void>}){
  const [catalog,setCatalog]=useState<Catalog|null>(null),[selected,setSelected]=useState(''),[query,setQuery]=useState('');
  const [hits,setHits]=useState<DocumentHit[]>([]),[searched,setSearched]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const root=`/api/projects/${projectId}/documents`;
  useEffect(()=>{let stale=false;api<Catalog>(root).then(value=>{if(!stale)setCatalog(value);})
    .catch(()=>{if(!stale)setError('Document search is unavailable on this backend.');});return()=>{stale=true;};},[root]);
  async function change(operation:'index'|'remove',id:string){
    setBusy(true);setError('');try{
      await api(`${root}/${operation}`,'POST',{attachment_id:id,confirm:true});
      setHits([]);setSearched(false);setCatalog(await api<Catalog>(root));
    }catch(reason){setError(reason instanceof Error?reason.message:String(reason));}finally{setBusy(false);}
  }
  async function search(){
    setBusy(true);setError('');try{const result=await api<{hits:DocumentHit[]}>(`${root}/search?q=${encodeURIComponent(query)}`);setHits(result.hits);setSearched(true);}
    catch(reason){setError(reason instanceof Error?reason.message:String(reason));}finally{setBusy(false);}
  }
  return <details className="project-documents"><summary>Project document search{catalog&&` · ${catalog.documents.length} saved`}</summary>
    <p className="muted small">Add an imported document to search its saved excerpt and use relevant passages in this project's conversations and coding tasks. Reference text can be outdated; verify it against your project.</p>
    <p className="muted small">Removing a search entry keeps the imported document.</p>
    {error&&<p className="error" role="alert">{error}</p>}
    {catalog&&!catalog.available&&<p>Document search is unavailable in this installation.</p>}
    <div className="document-actions"><button disabled={busy} onClick={()=>void onImport()}>Import document</button>
      <select aria-label="Document to add to project search" value={selected} onChange={event=>setSelected(event.target.value)} disabled={busy||!catalog?.available}>
        <option value="">Choose an imported document</option>{attachments.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}
      </select><button disabled={busy||!selected||!catalog?.available} onClick={()=>void change('index',selected)}>Add to search</button></div>
    {catalog?.documents.map(item=><div className="saved-document" key={item.attachment_id}><span>{item.name}{item.stale?' · source changed':''}</span>
      <button disabled={busy||!catalog.available} onClick={()=>void change('index',item.attachment_id)}>Update saved excerpt</button>
      <button disabled={busy} onClick={()=>void change('remove',item.attachment_id)}>Remove from search</button></div>)}
    <form className="document-actions" onSubmit={event=>{event.preventDefault();void search();}}><input aria-label="Search saved project documents" value={query} maxLength={200} onChange={event=>setQuery(event.target.value)} placeholder="Search saved project documents" disabled={busy||!catalog?.available}/>
      <button disabled={busy||!query.trim()||!catalog?.available}>{busy?'Working…':'Search documents'}</button></form>
    {searched&&!hits.length&&<p>No matching saved excerpts.</p>}<DocumentResults hits={hits}/>
  </details>;
}
