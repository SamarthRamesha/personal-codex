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
  $('#request-agent-plan').disabled=!providers.length; $('#build-agent-plan').disabled=!providers.length;
  $('#request-agent-round').disabled=!providers.length; $('#plan-agent-round').disabled=!providers.length;
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
  const [workspace,events,executions,invocations,proposal,rounds,report]=await Promise.all([api(`/api/tasks/${task.id}/workspace`),api(`/api/tasks/${task.id}/events`),api(`/api/tasks/${task.id}/executions`),api(`/api/tasks/${task.id}/invocations`),api(`/api/tasks/${task.id}/agent`),api(`/api/tasks/${task.id}/agent/rounds`),api(`/api/tasks/${task.id}/agent/report`)]);
  renderProposal(proposal);
  renderRounds(rounds,report);
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
let busy=false;
async function action(path,body,success){if(busy)return;busy=true;try{const d=await api(path,{method:'POST',body:JSON.stringify(body||{})});msg($('#action-result'),success(d));await refresh()}catch(e){msg($('#action-result'),e.message,true)}finally{busy=false}}
$('#add-project').onclick=async()=>{try{let d=await api('/api/projects',{method:'POST',body:JSON.stringify({name:$('#project-name').value,path:$('#project-path').value})});msg($('#project-result'),`Added ${d.name}.`);await refresh()}catch(e){msg($('#project-result'),e.message,true)}};
$('#create-task').onclick=async()=>{try{if(!$('#project').value)throw Error('Add a project first.');let d=await api('/api/tasks',{method:'POST',body:JSON.stringify({project_id:$('#project').value,prompt:$('#prompt').value})});selectedId=d.id;msg($('#task-result'),`Plan created with ${d.plan.length} coordinated stages.`);$('#prompt').value='';await refresh()}catch(e){msg($('#task-result'),e.message,true)}};
$('#request-workspace').onclick=()=>action(`/api/tasks/${selectedId}/workspace-request`,{},()=> 'Workspace request queued for approval.');
$('#create-workspace').onclick=()=>action(`/api/tasks/${selectedId}/workspace`,{},d=>`Workspace ready on ${d.branch}.`);
$('#request-command').onclick=()=>action(`/api/tasks/${selectedId}/execution-request`,{command:$('#command').value},()=> 'Exact command approval queued.');
$('#run-command').onclick=()=>action(`/api/tasks/${selectedId}/execute`,{command:$('#command').value},d=>`Command finished with exit code ${d.exit_code}.`);
function renderProposal(p){
 if(!p||p.status==='absent'){ $('#agent-proposal').innerHTML='<div class=empty>No agent proposal for this task.</div>'; $('#execute-agent-plan').disabled=true; return }
 const ops=(p.operations||[]).map((op,i)=>`<div class=item><span class=tag>${esc(op.tool)}</span><strong>${esc(op.path||op.command||'')}</strong>${op.tool==='apply_patch'?`<div class=output>- ${esc((op.old_text||'').slice(0,300))}\n+ ${esc((op.new_text||'').slice(0,300))}</div>`:''}${op.tool==='run_tests'?`<small class=muted>timeout ${op.timeout}s</small>`:''}</div>`).join('');
 const results=(p.results||[]).map(r=>`<div class=item><span class=tag>${esc(r.status)}</span><strong>${esc(r.tool)}</strong>${r.error?`<small class=muted>${esc(r.error)}</small>`:''}</div>`).join('');
 $('#agent-proposal').innerHTML=`<div class=item><span class=tag>${esc(p.status)}</span><strong>${esc(p.summary||'Proposed operations')}</strong><small class=muted>digest ${esc((p.digest||'').slice(0,16))} · ${esc(p.workspace_branch)}</small></div>${ops}${results?'<h3>Execution results</h3>'+results:''}`;
 $('#execute-agent-plan').disabled=p.status!=='pending';
}
function renderRounds(d,report){
 const rounds=(d&&d.rounds)||[];
 const header=d&&d.limits?`<div class=item><span class=tag>${esc(d.status)}</span><strong>Round ${d.limits.rounds_used} of ${d.limits.max_rounds}</strong><small class=muted>${d.limits.remaining} remaining · ${d.limits.elapsed_seconds}s elapsed</small></div>`:'';
 const items=rounds.map(r=>{const t=r.test_result||{};return `<div class=item><span class=tag>${esc(r.status)}</span><strong>Round ${r.round_number}</strong><small class=muted>${esc(r.summary||'')}</small>${t.tests_ran?`<div class=output>${esc(t.test_command)} → exit ${esc(t.test_exit_code)}${t.failed_tests&&t.failed_tests.length?'\n'+esc(t.failed_tests.join('\n')):''}</div>`:''}${r.error?`<small class=muted>${esc(r.error)}</small>`:''}</div>`}).join('');
 $('#agent-rounds').innerHTML=header+(items||'<div class=empty>No rounds yet.</div>');
 const b=d&&d.budget;
 const usage=b?`<div class=item><span class=tag>budget</span><strong>prompt ${b.used.prompt_bytes}/${b.limits.prompt_bytes} B · responses ${b.used.response_bytes}/${b.limits.response_bytes} B</strong><small class=muted>invocations ${b.used.invocations}/${b.limits.invocations} · tests ${b.used.test_output_bytes}/${b.limits.test_output_bytes} B · context ${b.used.context_bytes}/${b.limits.context_bytes} B${b.exhausted?' · EXHAUSTED '+esc(b.exhausted):''}</small></div>`+(d.cancellation?`<div class=item><span class=tag>cancelled</span><strong>Cancellation recorded</strong><small class=muted>${esc(d.cancellation.reason||'')}</small></div>`:''):'';
 $('#agent-usage').innerHTML=usage||'<div class=empty>No budget data yet.</div>';
 const latest=rounds.length?rounds[rounds.length-1]:null;
 const ledger=(latest&&latest.ledger)||[];
 $('#agent-operations').innerHTML=ledger.length?ledger.map(o=>`<div class=item><span class=tag>${esc(o.status)}</span><strong>#${o.op_index+1} ${esc(o.tool)}</strong><small class=muted>${o.applied?'applied · ':''}${esc(o.error||o.summary||'')}</small></div>`).join(''):'<div class=empty>No operations recorded yet.</div>';
 const ctx=(latest&&latest.context)||null;
 $('#agent-context').innerHTML=ctx?`<div class=item><span class=tag>context</span><strong>${(ctx.files||[]).length} file(s) · ${esc(ctx.bytes)} bytes</strong><small class=muted>digest ${esc((ctx.digest||'').slice(0,16))}</small></div>`+(ctx.files||[]).map(f=>`<div class=item><strong>${esc(f.path)}</strong><small class=muted>${esc(f.reason||'')} · lines ${esc(f.lines||'')}</small></div>`).join(''):'<div class=empty>No context selected yet.</div>';
 $('#agent-report').innerHTML=report&&report.tests&&report.tests.length?`<h3>Final report</h3><div class=list><div class=item><span class=tag>${esc(report.status)}</span><strong>${report.changed_files.length} file(s) · ${report.tests.length} test run(s)</strong><small class=muted>${esc((report.changed_files||[]).join(', '))}</small></div>${report.diff_summary?`<div class=item><span class=tag>diff</span><div class=output>${esc(report.diff_summary)}</div></div>`:''}</div>`:'';
}
$('#request-agent-round').onclick=()=>action(`/api/tasks/${selectedId}/agent/round/request`,{provider_id:$('#provider-select').value,prompt:$('#agent-extra').value},d=>`Round ${d.round} approval queued (${d.kind}).`);
$('#plan-agent-round').onclick=()=>action(`/api/tasks/${selectedId}/agent/round/plan`,{provider_id:$('#provider-select').value,prompt:$('#agent-extra').value},d=>`Round ${d.round}: ${d.status}.`);
$('#execute-agent-round').onclick=()=>action(`/api/tasks/${selectedId}/agent/round/execute`,{},d=>`Round ${d.round} ${d.status}.`);
$('#cancel-agent-round').onclick=()=>action(`/api/tasks/${selectedId}/agent/round/cancel`,{},d=>`Round ${d.round} ${d.status}.`);
$('#cancel-task').onclick=()=>action(`/api/tasks/${selectedId}/cancel`,{reason:'cancelled from dashboard'},()=> 'Cancellation recorded; no new operation will start.');
$('#reset-budget').onclick=()=>action(`/api/tasks/${selectedId}/agent/budget/reset`,{confirm:true},d=>`Budget reset explicitly; ${d.budget.used.invocations} invocation(s) used.`);
$('#request-agent-plan').onclick=()=>action(`/api/tasks/${selectedId}/agent/request`,{provider_id:$('#provider-select').value,prompt:$('#agent-extra').value},d=>`Agent plan approval queued (${d.kind}).`);
$('#build-agent-plan').onclick=()=>action(`/api/tasks/${selectedId}/agent/plan`,{provider_id:$('#provider-select').value,prompt:$('#agent-extra').value},d=>`Proposal ready: ${d.operations.length} operation(s); approve it in the queue.`);
$('#execute-agent-plan').onclick=()=>action(`/api/tasks/${selectedId}/agent/execute`,{},d=>`Agent run ${d.status}.`);
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
