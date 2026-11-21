import {useEffect,useRef,useState} from 'react';
import {invoke} from '@tauri-apps/api/core';
import {X,Square,RefreshCw} from 'lucide-react';
import {windowStillMatches,windowMismatchReason} from './automationWindow';

type Application={pid:number;name:string;bundle_id:string;allowed:boolean};
export type Control={id:string;role:string;label:string;value?:string;enabled:boolean;editable:boolean;pressable:boolean;sensitive:boolean;clipped?:boolean};
export type Snapshot={scopeID:string;window:string;digest:string;controls:Control[];truncated:boolean;browser:boolean;origin?:string};
export type Proposal={summary:string;steps:{operation:string;target:string;text?:string}[];expected:{target:string;attribute:string;equals:string}};
type Plan={plan_id:string;proposal:Proposal;observation_digest:string;effect:string};
type Scope={scope_id:string;snapshot:Snapshot;app:string;bundle_id:string;pid:number};
type Permission={accessibility:boolean;screen_capture:boolean;key_events:boolean};
type Capture={image_base64:string;ocr:string;window:string};
type Response={snapshot?:Snapshot;scope_id?:string;app?:string;bundle_id?:string;windows?:{index:number;title:string;number?:number}[];status?:string;actions?:number};
const rpc=<T,>(request:Record<string,unknown>)=>invoke<T>('automation_ipc',{request});

export function AutomationReview({plan,snapshot,busy,approve}:{plan:Plan;snapshot:Snapshot;busy:boolean;approve:()=>void}){
  return <section className="mac-action-review" aria-label="Review automation plan"><h3>{plan.proposal.summary}</h3>
    <p className="muted small">{plan.effect} Approval expires after two minutes and can be used once.</p>
    <ol>{plan.proposal.steps.map((step,index)=><li key={index}><strong>{step.operation}</strong> · {snapshot.controls.find(c=>c.id===step.target)?.label||step.target}
      {step.text!==undefined&&<pre>{step.text}</pre>}</li>)}</ol>
    <p>Verify <strong>{snapshot.controls.find(c=>c.id===plan.proposal.expected.target)?.label||plan.proposal.expected.target}</strong> · {plan.proposal.expected.attribute}:</p>
    <pre>{plan.proposal.expected.equals}</pre><button className="primary" disabled={busy} onClick={approve}>Approve and run these steps</button>
  </section>;
}

export function MacAutomation({close}:{close:()=>void}){
  const [permission,setPermission]=useState<Permission|null>(null),[apps,setApps]=useState<Application[]>([]);
  const [pid,setPid]=useState(''),[windows,setWindows]=useState<{index:number;title:string;number?:number}[]>([]),[windowIndex,setWindowIndex]=useState(0);
  const [readConsent,setReadConsent]=useState(false),[modelConsent,setModelConsent]=useState(false),[captureConsent,setCaptureConsent]=useState(false);
  const [scope,setScope]=useState<Scope|null>(null),[plan,setPlan]=useState<Plan|null>(null),[capture,setCapture]=useState<Capture|null>(null);
  const [goal,setGoal]=useState(''),[model,setModel]=useState('qwen3.5:9b'),[busy,setBusy]=useState(''),[error,setError]=useState(''),[receipt,setReceipt]=useState('');
  const [controlId,setControlId]=useState(''),[operation,setOperation]=useState('set_text'),[text,setText]=useState('');
  const [expectedId,setExpectedId]=useState(''),[attribute,setAttribute]=useState('value'),[expectedText,setExpectedText]=useState('');
  const [events,setEvents]=useState<{stage:string;index:number;operation:string}[]>([]);
  const [browser,setBrowser]=useState('com.apple.Safari'),[browserURL,setBrowserURL]=useState('https://example.com'),[browserConsent,setBrowserConsent]=useState(false);
  const [checkConsent,setCheckConsent]=useState(false),[checkCapture,setCheckCapture]=useState(false),[checkReport,setCheckReport]=useState('');
  const epoch=useRef(0);
  function discardScope(){epoch.current++;setBusy('');setScope(null);setPlan(null);setCapture(null);void invoke('stop_mac_automation').catch(()=>{});}
  function updatePermission(value:Permission){setPermission(previous=>({...previous,...value}));}
  useEffect(()=>{
    let stale=false;
    void rpc<Permission>({op:'status'}).then(value=>{if(!stale)setPermission(value);}).catch(reason=>{if(!stale)setError(String(reason));});
    void rpc<{applications:Application[]}>({op:'applications'}).then(value=>{if(!stale)setApps(value.applications);}).catch(()=>{});
    return()=>{stale=true;epoch.current++;void invoke('stop_mac_automation').catch(()=>{});};
  },[]);
  useEffect(()=>{
    if(busy!=='Running approved steps…')return;
    const timer=setInterval(()=>{void invoke<{events:typeof events}>('automation_activity').then(r=>setEvents(r.events)).catch(()=>{});},200);
    return()=>clearInterval(timer);
  },[busy]);
  async function action<T>(label:string,work:()=>Promise<T>,apply:(result:T)=>void){
    const ticket=++epoch.current;setBusy(label);setError('');setReceipt('');
    try{const result=await work();if(epoch.current===ticket)apply(result);}
    catch(reason){if(epoch.current===ticket){setError(String(reason));setScope(null);setPlan(null);setCapture(null);}}
    finally{if(epoch.current===ticket)setBusy('');}
  }
  async function stop(){
    epoch.current++;setBusy('');setPlan(null);setScope(null);setCapture(null);
    await invoke('stop_mac_automation').catch(()=>{});
    setReceipt('Automation stopped. An in-flight action may have completed; inspect the app before starting a new scope.');
  }
  function updateSnapshot(snapshot:Snapshot){setScope(old=>old?{...old,snapshot}:null);setPlan(null);setCapture(null);}
  const controls=scope?.snapshot.controls||[];
  return <div className="modal-backdrop"><section className="settings-modal mac-automation" role="dialog" aria-modal="true" aria-label="Mac automation">
    <div className="modal-title"><div><p className="eyebrow">LOCAL · WINDOW-SCOPED</p><h2>Mac automation</h2></div>
      <div className="button-row"><button onClick={()=>void stop()}><Square size={15}/>Stop automation</button><button title="Close Mac automation" onClick={()=>{void stop();close();}}><X size={18}/></button></div></div>
    <p>Choose a window, inspect its controls, and review a click/type plan. This requires macOS 14 or later. Permissions are granted by you in macOS.</p>
    <div className="automation-permissions"><span>Accessibility: {permission?.accessibility?'available':'not granted'}</span><span>Screen capture: {permission?.screen_capture?'available':'not granted'}</span><span>Keyboard events: {permission?.key_events?'available':'not granted'}</span>
      <button disabled={!!busy} onClick={()=>void action('Checking permissions…',()=>rpc<Permission>({op:'status'}),setPermission)}><RefreshCw size={13}/>Check permissions</button>
      <button disabled={!!busy} onClick={()=>void action('Requesting Accessibility permission…',()=>rpc<Permission>({op:'request_accessibility',confirmed:true}),updatePermission)}>Request Accessibility permission</button>
      <button disabled={!!busy} onClick={()=>void action('Requesting capture permission…',()=>rpc<Permission>({op:'request_capture',confirmed:true}),updatePermission)}>Request screen capture permission</button></div>
    <p className="muted small">Only the selected app window is read. Secure and recognized credential controls are omitted. Known security, password-manager and shell apps, plus recognized consequential controls, are refused. Review each plan; this is not a sandbox for hostile apps or websites. Permission prompts must be completed by you.</p>
    <details><summary>Check automation with a disposable test app</summary>
      <p>The check opens and focuses synthetic windows, types a test message, presses Preview, checks scrolling and secure-field omission, then closes its own test app. It does not use your personal windows. Your current automation scope will end.</p>
      <label className="automation-consent"><input type="checkbox" checked={checkConsent} disabled={!!busy} onChange={e=>setCheckConsent(e.target.checked)}/>Run these synthetic checks through the native automation driver.</label>
      <label className="automation-consent"><input type="checkbox" checked={checkCapture} disabled={!!busy} onChange={e=>setCheckCapture(e.target.checked)}/>Also check capture and OCR of the synthetic window. Requires screen capture permission.</label>
      <button disabled={!!busy||!checkConsent||!permission?.accessibility||(checkCapture&&!permission?.screen_capture)} onClick={()=>{setScope(null);setPlan(null);setCapture(null);setCheckReport('');void action('Checking the disposable test app…',()=>rpc<Record<string,unknown>>({op:'self_check',confirmed:checkConsent,capture:checkCapture}),r=>setCheckReport(JSON.stringify(r,null,2)));}}>Run synthetic Mac check</button>
      {checkReport&&<pre role="status">{checkReport}</pre>}
    </details>
    <details><summary>Start a fresh browser window</summary><label>Browser<select value={browser} disabled={!!busy} onChange={e=>setBrowser(e.target.value)}>
      <option value="com.apple.Safari">Safari</option><option value="com.google.Chrome">Chrome</option><option value="org.mozilla.firefox">Firefox</option><option value="app.zen-browser.zen">Zen</option><option value="com.microsoft.edgemac">Edge</option></select></label>
      <label>Address<input value={browserURL} maxLength={2048} disabled={!!busy} onChange={e=>setBrowserURL(e.target.value)}/></label>
      <label className="automation-consent"><input type="checkbox" checked={browserConsent} disabled={!!busy} onChange={e=>setBrowserConsent(e.target.checked)}/>Create and focus a new window at this address, and allow local reading of that window. Existing tabs are not used.</label>
      <button disabled={!!busy||!browserConsent||!permission?.accessibility||!permission?.key_events} onClick={()=>void action('Opening a verified new browser window…',()=>rpc<Scope>({op:'new_browser',browser,url:browserURL,confirmed:browserConsent}),r=>{
        setScope(r);setPlan(null);setCapture(null);setWindows([]);setReadConsent(true);setModelConsent(false);setCaptureConsent(false);setPid(String(r.pid));
        setApps(previous=>previous.some(a=>a.pid===r.pid)?previous:[...previous,{pid:r.pid,name:r.app,bundle_id:r.bundle_id,allowed:true}]);
      })}>Open and scope new browser window</button><p className="muted small">Requires Accessibility and keyboard-event permission. HTTPS or loopback HTTP only. Later actions stay on the selected origin; cross-origin transitions require a new scope.</p></details>
    <label>Running application<select value={pid} disabled={!!busy} onChange={event=>{discardScope();setPid(event.target.value);setWindows([]);setReadConsent(false);setModelConsent(false);}}>
      <option value="">Choose an application</option>{apps.map(app=><option key={app.pid} value={app.pid} disabled={!app.allowed}>{app.name}{!app.allowed?' · unavailable for automation':''}</option>)}</select></label>
    <label className="automation-consent"><input type="checkbox" checked={readConsent} disabled={!!busy} onChange={event=>{setReadConsent(event.target.checked);if(!event.target.checked)discardScope();}}/>Allow local reading of this app's selected window for up to ten minutes.</label>
    <div className="button-row"><button disabled={!!busy||!pid||!readConsent||!permission?.accessibility} onClick={()=>void action('Reading window list…',()=>rpc<Response>({op:'windows',pid:Number(pid),confirmed:true}),r=>{setWindows(r.windows||[]);setWindowIndex(0);})}>List this app's windows</button>
      {windows.length>0&&<><select aria-label="Window to control" value={windowIndex} disabled={!!busy} onChange={e=>{discardScope();setWindowIndex(Number(e.target.value));}}>{windows.map(w=><option key={w.index} value={w.index}>{w.title||`Window ${w.index+1}`}</option>)}</select>
        <button disabled={!!busy||!readConsent} onClick={()=>void action('Starting selected-window scope…',async()=>{
          const listed=windows[windowIndex];
          const fresh=(await rpc<Response>({op:'windows',pid:Number(pid),confirmed:true})).windows||[];
          if(!windowStillMatches(listed,fresh,windowIndex))throw new Error(windowMismatchReason(listed,fresh,windowIndex));
          return rpc<Scope>({op:'begin',pid:Number(pid),window_index:windowIndex,window_title:listed!.title,
            ...(listed!.number!==undefined?{window_number:listed!.number}:{}),confirmed:true});
        },r=>{setScope(r);setPlan(null);setCapture(null);setModelConsent(false);setCaptureConsent(false);setEvents([]);})}>Start window scope</button></>}</div>
    {scope&&<><div className="automation-scope"><strong>{scope.app} · {scope.snapshot.window}</strong>{scope.snapshot.origin&&<code>{scope.snapshot.origin}</code>}<small>Scope {scope.scope_id.slice(0,8)} · expires after ten minutes or 32 actions</small></div>
      <button disabled={!!busy} onClick={()=>void action('Refreshing selected window…',()=>rpc<Response>({op:'observe',scope_id:scope.scope_id}),r=>{if(r.snapshot)updateSnapshot(r.snapshot);})}>Refresh window controls</button>
      {scope.snapshot.truncated&&<p className="notice">The control list is bounded and was clipped. Plans can use only the controls shown; screenshot capture is refused for an incomplete safety view.</p>}
      <details><summary>Inspect selected-window controls · {controls.length}</summary><div className="automation-controls">{controls.map(c=><div key={c.id}><code>{c.id}</code><span>{c.role} · {c.label||'Unnamed'}</span>{c.sensitive?<strong>Protected; omitted</strong>:<pre>{c.value||''}</pre>}</div>)}</div></details>
      <label>What should this window do?<textarea value={goal} maxLength={3000} disabled={!!busy} onChange={e=>setGoal(e.target.value)} placeholder={'For example: enter "hello" in Message, click Preview, and verify "Preview: hello" in the result.'}/></label>
      <select aria-label="Local automation model" value={model} disabled={!!busy} onChange={e=>setModel(e.target.value)}><option>qwen3.5:9b</option><option>qwen2.5-coder:14b</option></select>
      <label className="automation-consent"><input type="checkbox" checked={modelConsent} disabled={!!busy} onChange={e=>setModelConsent(e.target.checked)}/>Send this selected-window text and request to my existing local Ollama model. No cloud fallback or model download.</label>
      <button disabled={!!busy||!modelConsent||!goal.trim()} onClick={()=>void action('Planning locally…',()=>invoke<Plan>('plan_mac_automation',{goal:goal.trim(),model,scopeId:scope.scope_id,confirmed:modelConsent}),setPlan)}>Suggest a local plan</button>
      <details><summary>Prepare one manual step · no model needed</summary><label>Control<select value={controlId} disabled={!!busy} onChange={e=>setControlId(e.target.value)}><option value="">Choose a control</option>{controls.filter(c=>c.enabled&&!c.sensitive&&(c.editable||c.pressable)).map(c=><option key={c.id} value={c.id}>{c.id} · {c.label||c.role}</option>)}</select></label>
        <label>Action<select value={operation} disabled={!!busy} onChange={e=>setOperation(e.target.value)}><option value="set_text">Set text</option><option value="press">Press control</option><option value="key">Key: enter, tab or escape</option><option value="scroll">Scroll: increment, decrement, start or end</option></select></label>
        {operation!=='press'&&<label>Text or key<input value={text} maxLength={2000} disabled={!!busy} onChange={e=>setText(e.target.value)}/></label>}
        <label>Control to verify<select value={expectedId} disabled={!!busy} onChange={e=>setExpectedId(e.target.value)}><option value="">Choose result control</option>{controls.filter(c=>!c.sensitive&&!c.pressable).map(c=><option key={c.id} value={c.id}>{c.id} · {c.label||c.role}</option>)}</select></label>
        <label>Verify attribute<select value={attribute} onChange={e=>setAttribute(e.target.value)}><option value="value">Value</option><option value="label">Label</option></select></label>
        <label>Expected text<input value={expectedText} maxLength={2000} disabled={!!busy} onChange={e=>setExpectedText(e.target.value)}/></label>
        <button disabled={!!busy||!controlId||!expectedId||!expectedText} onClick={()=>void action('Preparing manual step…',()=>rpc<Plan>({op:'prepare',scope_id:scope.scope_id,observation_digest:scope.snapshot.digest,proposal:JSON.stringify({summary:'One reviewed manual step',steps:[{operation,target:controlId,...(operation==='press'?{}:{text})}],expected:{target:expectedId,attribute,equals:expectedText}})}),setPlan)}>Review manual step</button></details>
      {plan&&<AutomationReview plan={plan} snapshot={scope.snapshot} busy={!!busy} approve={()=>{const chosen=plan;setPlan(null);void action('Running approved steps…',()=>rpc<Response>({op:'execute',scope_id:scope.scope_id,plan_id:chosen.plan_id,confirmed:true}),r=>{if(r.snapshot)updateSnapshot(r.snapshot);setReceipt(r.status==='verified'?`${r.actions} approved action(s) ran and the expected control matched.`:'Actions ran, but the expected control did not match. Inspect the result; no automatic retry.');});}}/>}
      <details><summary>Optional selected-window screenshot and local OCR</summary><label className="automation-consent"><input type="checkbox" checked={captureConsent} disabled={!!busy} onChange={e=>{setCaptureConsent(e.target.checked);if(!e.target.checked)setCapture(null);}}/>Capture this selected window once. Preview/OCR stay in this panel; nothing is sent to a model or saved automatically.</label>
        <button disabled={!!busy||!captureConsent||!permission?.screen_capture} onClick={()=>void action('Capturing selected window…',()=>rpc<Capture>({op:'capture',scope_id:scope.scope_id,confirmed:true}),setCapture)}>Capture selected window</button>
        {capture&&<><img className="automation-capture" src={`data:image/jpeg;base64,${capture.image_base64}`} alt={`Selected window: ${capture.window}`}/><pre>{capture.ocr}</pre></>}</details>
    </>}
    {busy&&<p role="status">{busy}</p>}{receipt&&<p className="notice" role="status">{receipt}</p>}{error&&<p className="message-error" role="alert">{error}</p>}
    {events.length>0&&<details><summary>Recent action outcomes · no typed content logged</summary>{events.slice(-16).map((event,index)=><p className="muted small" key={index}>Step {event.index+1} · {event.operation} · {event.stage}</p>)}</details>}
  </section></div>;
}
