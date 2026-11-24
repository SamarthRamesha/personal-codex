import { useEffect, useState } from 'react';
import { api } from './api';
import { summarizeReport } from './taskReport';
import type { TaskReport } from './taskReport';

const errorText=(error:unknown)=>error instanceof Error?error.message:String(error);

/** The recorded facts of a task: rounds, test outcomes, changed files and remaining budget.
 *
 * This reads the backend's objective report. It is not the model's own account of its work, and a
 * task that ran no test is shown that way.
 */
export function TaskReportPanel({taskId}:{taskId:string}){
  const [report,setReport]=useState<TaskReport|null>(null);
  const [error,setError]=useState('');
  useEffect(()=>{
    setReport(null);setError('');
    if(!taskId)return;
    let stale=false;
    api<TaskReport>(`/api/tasks/${taskId}/agent/report`)
      .then(value=>{if(!stale)setReport(value);})
      .catch(reason=>{if(!stale)setError(errorText(reason));});
    return()=>{stale=true;};
  },[taskId]);
  if(!taskId)return null;
  const summary=summarizeReport(report);
  return <section className="task-report">
    <h3>Objective report<span className="pill">{report?.status||'loading'}</span></h3>
    <p className="muted small">{error||summary.headline}</p>
    {summary.remaining&&<p className="muted small">{summary.remaining}</p>}
    {summary.exhausted&&<p className="message-error">{summary.exhausted}</p>}
    {summary.rows.map(row=><p className={`report-test ${row.tone}`} key={row.key}>{row.label}</p>)}
    {summary.changed.length>0&&<p className="muted small">Changed: {summary.changed.join(', ')}</p>}
    {report?.diff_summary&&<details><summary>Diff stat</summary><pre>{report.diff_summary}</pre></details>}
  </section>;
}
