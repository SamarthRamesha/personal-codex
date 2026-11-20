import {useEffect,useState} from 'react';
import {invoke} from '@tauri-apps/api/core';
import {X} from 'lucide-react';

export type MacActionPreview={id:string;kind:string;label:string;target:string;expires_in_seconds:number};
type MacApp={name:string;path:string};
const description=(kind:string)=>kind==='open_app'?'Launch application':kind==='open_document'?'Open document in its default app':'Reveal item in Finder';

export function MacActionReview({preview,busy,confirm,cancel}:{preview:MacActionPreview;busy:boolean;confirm:()=>void;cancel:()=>void}){
  return <section className="mac-action-review" aria-label="Review Mac action">
    <p className="eyebrow">REVIEW BEFORE OPENING</p><h3>{description(preview.kind)}</h3>
    <p>{preview.label}</p><code>{preview.target}</code>
    <p className="muted small">This approval is used once and expires after two minutes. macOS may ask which app to use or request permission.</p>
    <div className="button-row"><button className="primary" disabled={busy} onClick={confirm}>Confirm and open</button>
      <button disabled={busy} onClick={cancel}>Cancel action</button></div>
  </section>;
}

export function MacActions({close}:{close:()=>void}){
  const [query,setQuery]=useState(''),[apps,setApps]=useState<MacApp[]>([]),[preview,setPreview]=useState<MacActionPreview|null>(null);
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[receipt,setReceipt]=useState('');
  useEffect(()=>{
    let stale=false;const timer=setTimeout(()=>{invoke<MacApp[]>('mac_applications',{query}).then(items=>{if(!stale)setApps(items);})
      .catch(reason=>{if(!stale)setError(String(reason));});},180);
    return()=>{stale=true;clearTimeout(timer);};
  },[query]);
  useEffect(()=>()=>{void invoke('cancel_mac_action').catch(()=>{});},[]);
  async function action(run:()=>Promise<void>){
    setBusy(true);setError('');setReceipt('');
    try{await run();}catch(reason){setError(String(reason));}finally{setBusy(false);}
  }
  async function choose(kind:'open_document'|'reveal_item',folder=false){
    setPreview(null);
    await action(async()=>setPreview(await invoke<MacActionPreview|null>('choose_mac_item',{kind,folder})));
  }
  return <div className="modal-backdrop" onKeyDown={event=>{if(event.key==='Escape'&&!busy)close();}}><section className="settings-modal mac-actions" role="dialog" aria-modal="true" aria-label="Mac actions">
    <div className="modal-title"><div><p className="eyebrow">ON THIS MAC</p><h2>Mac actions</h2></div>
      <button title="Close Mac actions" disabled={busy} onClick={close}><X size={18}/></button></div>
    <p>Open an installed application, choose a document, or find an item in Finder. Review the exact destination before anything opens.</p>
    <p className="muted small">These actions stay on your Mac and work without a backend connection. File contents and application names are not sent to JARVIS or a model.</p>
    <div className="button-row"><button disabled={busy} onClick={()=>void choose('open_document')}>Choose document to open</button>
      <button disabled={busy} onClick={()=>void choose('reveal_item')}>Find file in Finder</button>
      <button disabled={busy} onClick={()=>void choose('reveal_item',true)}>Find folder in Finder</button></div>
    <label>Search installed applications<input autoFocus aria-label="Search installed applications" value={query} maxLength={100}
      disabled={busy} onChange={event=>setQuery(event.target.value)} placeholder="Calculator, Notes, TextEdit…"/></label>
    <div className="mac-app-list">{apps.map(app=><button disabled={busy} key={app.path} title={app.path} onClick={()=>{
      setPreview(null);void action(async()=>setPreview(await invoke<MacActionPreview>('prepare_mac_app',{path:app.path})));
    }}>{app.name}</button>)}{!apps.length&&<p className="muted small">No matching applications.</p>}</div>
    {preview&&<MacActionReview preview={preview} busy={busy} confirm={()=>{
      const selected=preview;setPreview(null);
      void action(async()=>setReceipt(await invoke<string>('execute_mac_action',{id:selected.id,confirmed:true})));
    }} cancel={()=>{setPreview(null);void action(async()=>{await invoke('cancel_mac_action');});}}/>}
    {busy&&<p role="status">Working…</p>}{receipt&&<p role="status" className="notice">{receipt}</p>}
    {error&&<p role="alert" className="message-error">{error}</p>}
    <p className="muted small">Opening is available now. Cross-app clicking, typing, screen reading and arbitrary system commands are not enabled. Coding continues through approved project tasks.</p>
  </section></div>;
}
