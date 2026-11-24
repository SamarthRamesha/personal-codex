/** How one project's coding tasks read in the workspace list.
 *
 * The backend stores a task's status as the single source of truth. This module only groups those
 * statuses for review: it never upgrades a task to "done", never hides an interrupted one and never
 * claims a task is running when the backend has not said so. Statuses it does not recognise are
 * shown verbatim in an `open` phase rather than guessed at.
 */
export type TaskLike = {id:string;project_id:string;prompt:string;status:string;updated_at:number};

export type TaskPhase = 'running'|'needs-action'|'complete'|'closed'|'failed'|'open';

export type TaskRow = {
  id:string; prompt:string; status:string; phase:TaskPhase;
  label:string; detail:string; attention:boolean; updated_at:number;
};

const STATUS:Record<string,{phase:TaskPhase;label:string;detail:string}> = {
  planned:{phase:'open',label:'Planned',detail:'A plan exists; no workspace or round has run yet.'},
  running:{phase:'running',label:'Running',detail:'A round is executing now. Stop it before starting another.'},
  iterating:{phase:'running',label:'Iterating',detail:'A round is executing now. Stop it before starting another.'},
  'needs-another-round':{phase:'needs-action',label:'Needs another round',detail:'The last round did not finish the task. Its evidence is kept; request a fresh round.'},
  'ready-to-complete':{phase:'needs-action',label:'Checks passed',detail:'Review the passing results and request the completion round.'},
  interrupted:{phase:'needs-action',label:'Interrupted',detail:'The backend restarted mid-task. Completed work is saved; the interrupted step is not replayed and needs a new review.'},
  'budget-exhausted':{phase:'needs-action',label:'Budget exhausted',detail:'The round budget ran out before completion. Reset the budget deliberately or split the task.'},
  complete:{phase:'complete',label:'Delivered',detail:'The reviewed work was applied. The delivery report and evidence remain available.'},
  completed:{phase:'complete',label:'Completed',detail:'The task completed. Its report and evidence remain available.'},
  cancelled:{phase:'closed',label:'Cancelled',detail:'You stopped this task. Continuing reviewed work requires a fresh round and new approvals.'},
  failed:{phase:'failed',label:'Failed',detail:'The last attempt failed. The error and evidence are recorded for review.'},
  error:{phase:'failed',label:'Failed',detail:'The last attempt failed. The error and evidence are recorded for review.'},
};

/** Unknown statuses stay visible as open work instead of being folded into a guessed bucket. */
export function taskPhase(status:string):TaskPhase {
  return STATUS[status]?.phase ?? 'open';
}

export function taskLabel(status:string):string {
  return STATUS[status]?.label ?? status.replace(/[-_]/g,' ');
}

export function taskDetail(status:string):string {
  return STATUS[status]?.detail ?? 'This backend reported a status the desktop does not recognise. Inspect the task before acting on it.';
}

/** True when the status means a person has to decide something before the task can progress. */
export function needsOwnerAttention(status:string):boolean {
  const phase = taskPhase(status);
  return phase==='needs-action' || phase==='failed';
}

/** A delivered or already-stopped task has nothing to cancel; the backend refuses both with 409. */
export function canCancelTask(status:string):boolean {
  const phase = taskPhase(status);
  return phase!=='complete' && phase!=='closed';
}

/** Newest first, bounded so a long history stays readable; the selected task is always kept. */
export function projectTaskRows(tasks:TaskLike[], projectId:string, limit=12):TaskRow[] {
  if(!projectId) return [];
  const rows = tasks
    .filter(task=>task.project_id===projectId)
    .sort((left,right)=>right.updated_at-left.updated_at)
    .slice(0,limit)
    .map(task=>({
      id:task.id, prompt:task.prompt, status:task.status, phase:taskPhase(task.status),
      label:taskLabel(task.status), detail:taskDetail(task.status),
      attention:taskPhase(task.status)==='needs-action', updated_at:task.updated_at,
    }));
  return rows;
}

export function taskHistoryHidden(tasks:TaskLike[], projectId:string, limit=12):number {
  if(!projectId) return 0;
  return Math.max(0, tasks.filter(task=>task.project_id===projectId).length-limit);
}

export type TaskCounts = {total:number;running:number;attention:number;done:number;failed:number};

export function taskCounts(rows:TaskRow[]):TaskCounts {
  return {
    total:rows.length,
    running:rows.filter(row=>row.phase==='running').length,
    attention:rows.filter(row=>row.phase==='needs-action').length,
    done:rows.filter(row=>row.phase==='complete').length,
    failed:rows.filter(row=>row.phase==='failed').length,
  };
}

/** One line, in the order the owner needs it: what is running, what needs them, what finished. */
export function taskBoardSummary(rows:TaskRow[], hidden=0):string {
  if(!rows.length) return 'No coding tasks in this project yet.';
  const counts = taskCounts(rows);
  const parts:string[] = [];
  if(counts.running) parts.push(`${counts.running} running`);
  if(counts.attention) parts.push(`${counts.attention} needs action`);
  if(counts.failed) parts.push(`${counts.failed} failed`);
  if(counts.done) parts.push(`${counts.done} delivered`);
  const listed = hidden>0 ? `newest ${rows.length} of ${rows.length+hidden}` : `${rows.length}`;
  const head = `${listed} task${rows.length+hidden===1?'':'s'}`;
  return parts.length ? `${head} · ${parts.join(' · ')}` : `${head} · none running`;
}

/** Attention first so an interrupted or unfinished task is not buried under finished ones. */
export function orderedTaskRows(rows:TaskRow[]):TaskRow[] {
  const rank:Record<TaskPhase,number> = {'needs-action':0,failed:1,running:2,open:3,complete:4,closed:5};
  return [...rows].sort((left,right)=>rank[left.phase]-rank[right.phase] || right.updated_at-left.updated_at);
}

export function shortPrompt(prompt:string, limit=72):string {
  const text = prompt.trim().replace(/\s+/g,' ');
  return text.length<=limit ? text : `${text.slice(0,limit-1)}…`;
}

export function taskTime(updatedAt:number):string {
  if(!Number.isFinite(updatedAt)||updatedAt<=0) return 'time unknown';
  return new Date(updatedAt*1000).toLocaleDateString(undefined,{month:'short',day:'numeric'});
}
