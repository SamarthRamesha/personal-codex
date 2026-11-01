const $=s=>document.querySelector(s);
const api=(url,opt={})=>fetch(url,{headers:{'Content-Type':'application/json'},...opt}).then(async r=>{const d=await r.json();if(!r.ok)throw Error(d.error||'Request failed');return d});
const esc=v=>{const d=document.createElement('div');d.textContent=v??'';return d.innerHTML};
const msg=(el,text,fail=false)=>{el.textContent=text;el.style.color=fail?'#ff9e9e':'#74e0ba'};
let tasks=[], selectedId=null, providerCache=[], invoking=false;
function updateProviderHint(){
 const p=providerCache.find(x=>x.id===$('#provider-select').value);
 $('#provider-hint').textContent=p?`${p.kind} · ${p.model} · ${p.endpoint} · ${p.cloud_allowed?'cloud transmission needs a separate network approval':'loopback only — no network approval needed'}`:'No provider selected; register one below before requesting an invocation.';
}

async function refresh(){
 try{
  const [projects,nextTasks,approvals,providers]=await Promise.all(['/api/projects','/api/tasks','/api/approvals','/api/providers'].map(api));
  tasks=nextTasks;
  $('#project').innerHTML=projects.length?projects.map(p=>`<option value="${p.id}">${esc(p.name)} — ${esc(p.path)}</option>`).join(''):'<option value="">Add a project first</option>';
  $('#tasks').innerHTML=tasks.length?tasks.map(t=>`<div class="item clickable" data-task="${t.id}"><span class=tag>${esc(t.status)}</span><strong>${esc(t.prompt)}</strong><small>${new Date(t.updated_at*1000).toLocaleString()}</small></div>`).join(''):'<div class=empty>No planned tasks yet.</div>';
  document.querySelectorAll('[data-task]').forEach(el=>el.onclick=()=>selectTask(el.dataset.task));
  $('#approvals').innerHTML=approvals.length?approvals.map(a=>`<div class=item><span class=tag>${esc(a.kind)}</span><strong>${esc(a.detail)}</strong><div class=approval-buttons><button class=approve data-approval="${a.id}" data-status="approved">Approve</button><button class=reject data-approval="${a.id}" data-status="rejected">Reject</button></div></div>`).join(''):'<div class=empty>No pending approvals.</div>';
  document.querySelectorAll('[data-approval]').forEach(el=>el.onclick=()=>decide(el.dataset.approval,el.dataset.status));
  $('#providers').innerHTML=providers.length?providers.map(p=>`<div class=item><strong>${esc(p.model)}</strong><small>${esc(p.kind)} · ${p.cloud_allowed?'cloud allowed':'local-only'}</small></div>`).join(''):'<div class=empty>No model providers configured.</div>';
  providerCache=providers;
  $('#provider-select').innerHTML=providers.length?providers.map(p=>`<option value="${p.id}">${esc(p.model)} — ${esc(p.kind)}${p.cloud_allowed?' · cloud':''}</option>`).join(''):'<option value="">No providers configured</option>';
  $('#request-provider-invoke').disabled=!providers.length; $('#invoke-provider').disabled=!providers.length;
  $('#provider-select').onchange=updateProviderHint; updateProviderHint();
  $('#approval-count').textContent=approvals.length;
  if(selectedId) await renderSelected();
 }catch(e){console.error(e)}
}
async function decide(id,status){try{await api(`/api/approvals/${id}`,{method:'PATCH',body:JSON.stringify({status})});await refresh()}catch(e){alert(e.message)}}
async function selectTask(id){selectedId=id;await renderSelected()}
async function renderSelected(){
 const task=tasks.find(t=>t.id===selectedId); if(!task){selectedId=null;return}
 $('#selected-title').textContent=task.prompt; $('#task-actions').hidden=false;
 const plan=JSON.parse(task.plan); $('#task-plan').className='plan'; $('#task-plan').innerHTML=plan.map((s,i)=>`<div class=plan-step><strong>${i+1}. ${esc(s.agent)} — ${esc(s.action)}</strong><br><span class=muted>${esc(s.detail)}</span></div>`).join('');
 try{
  const [workspace,events,executions,invocations]=await Promise.all([api(`/api/tasks/${task.id}/workspace`),api(`/api/tasks/${task.id}/events`),api(`/api/tasks/${task.id}/executions`),api(`/api/tasks/${task.id}/invocations`)]);
  const ready=workspace.status==='ready'; $('#workspace-state').textContent=ready?workspace.branch:workspace.status;
  const released=workspace.status==='released', merged=workspace.status==='merged';
  $('#create-workspace').disabled=ready; $('#request-workspace').disabled=ready;
  $('#run-command').disabled=!ready; $('#request-command').disabled=!ready;
  $('#request-release').disabled=!ready; $('#release-workspace').disabled=!ready;
  $('#preview-merge').disabled=!released; $('#request-merge').disabled=!released; $('#merge-branch').disabled=!released;
  $('#request-branch-delete').disabled=!merged; $('#delete-branch').disabled=!merged;
  const log=[...events.map(e=>`<div class=item><strong>${esc(e.agent)} · ${esc(e.level)}</strong><small>${esc(e.message)}</small></div>`),...executions.map(x=>`<div class=item><span class=tag>exit ${x.exit_code}</span><strong>${esc(x.argv)}</strong><div class=output>${esc(x.output)}</div></div>` )];
  $('#task-events').innerHTML=log.length?log.join(''):'<div class=empty>No activity yet.</div>';
  const responses=invocations.map(x=>`<div class=item><span class=tag>sha ${esc(x.prompt_sha256.slice(0,12))}</span><strong>${esc(x.provider_id)}</strong><div class=output>${esc(x.response)}</div></div>`);
  $('#task-invocations').innerHTML=responses.length?responses.join(''):'<div class=empty>No provider responses yet.</div>';
 }catch(e){msg($('#action-result'),e.message,true)}
}
async function action(path,body,success){try{const d=await api(path,{method:'POST',body:JSON.stringify(body||{})});msg($('#action-result'),success(d));await refresh()}catch(e){msg($('#action-result'),e.message,true)}}
$('#add-project').onclick=async()=>{try{let d=await api('/api/projects',{method:'POST',body:JSON.stringify({name:$('#project-name').value,path:$('#project-path').value})});msg($('#project-result'),`Added ${d.name}.`);await refresh()}catch(e){msg($('#project-result'),e.message,true)}};
$('#create-task').onclick=async()=>{try{if(!$('#project').value)throw Error('Add a project first.');let d=await api('/api/tasks',{method:'POST',body:JSON.stringify({project_id:$('#project').value,prompt:$('#prompt').value})});selectedId=d.id;msg($('#task-result'),`Plan created with ${d.plan.length} coordinated stages.`);$('#prompt').value='';await refresh()}catch(e){msg($('#task-result'),e.message,true)}};
$('#request-workspace').onclick=()=>action(`/api/tasks/${selectedId}/workspace-request`,{},()=> 'Workspace request queued for approval.');
$('#create-workspace').onclick=()=>action(`/api/tasks/${selectedId}/workspace`,{},d=>`Workspace ready on ${d.branch}.`);
$('#request-command').onclick=()=>action(`/api/tasks/${selectedId}/execution-request`,{command:$('#command').value},()=> 'Exact command approval queued.');
$('#run-command').onclick=()=>action(`/api/tasks/${selectedId}/execute`,{command:$('#command').value},d=>`Command finished with exit code ${d.exit_code}.`);
$('#request-provider-invoke').onclick=()=>action(`/api/tasks/${selectedId}/provider-request`,{provider_id:$('#provider-select').value,prompt:$('#provider-prompt').value},d=>`${d.kind} approval queued for ${d.detail.refs.model}.`);
$('#invoke-provider').onclick=async()=>{
 if(invoking)return; invoking=true; $('#invoke-provider').disabled=true;
 try{await action(`/api/tasks/${selectedId}/invoke`,{provider_id:$('#provider-select').value,prompt:$('#provider-prompt').value},d=>`${d.model} responded (${d.text.length} characters)${d.cloud_allowed?' via cloud network approval':' over loopback'}.`)}
 finally{invoking=false; $('#invoke-provider').disabled=!providerCache.length}
};
$('#request-release').onclick=()=>action(`/api/tasks/${selectedId}/workspace-release-request`,{},()=> 'Critical workspace-release request queued for approval.');
$('#release-workspace').onclick=()=>action(`/api/tasks/${selectedId}/workspace-release`,{},d=>`Workspace released; ${d.branch} remains for recovery.`);
$('#preview-merge').onclick=async()=>{try{const d=await api(`/api/tasks/${selectedId}/merge-preview`);msg($('#action-result'),d.can_merge?`Conflict-free merge into ${d.target}.`:`Merge cannot proceed: ${d.detail}`,!d.can_merge)}catch(e){msg($('#action-result'),e.message,true)}};
$('#request-merge').onclick=()=>action(`/api/tasks/${selectedId}/merge-request`,{},d=>`Critical merge request queued for ${d.target}.`);
$('#merge-branch').onclick=()=>action(`/api/tasks/${selectedId}/merge`,{},d=>`Merged into ${d.target}; recovery branch retained.`);
$('#request-branch-delete').onclick=()=>action(`/api/tasks/${selectedId}/branch-delete-request`,{},()=> 'Critical branch-deletion request queued.');
$('#delete-branch').onclick=()=>action(`/api/tasks/${selectedId}/branch-delete`,{},()=> 'Merged recovery branch deleted.');
$('#refresh').onclick=refresh;refresh();
