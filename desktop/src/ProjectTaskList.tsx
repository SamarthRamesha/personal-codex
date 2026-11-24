import { useState } from 'react';
import { taskBoardSummary, orderedTaskRows, projectTaskRows, taskHistoryHidden, taskTime, shortPrompt } from './projectTaskSummary';
import type { TaskLike } from './projectTaskSummary';

/** Read-only list of the selected project's coding tasks.
 *
 * It is a view over `GET /api/tasks`; selecting a row opens that task in the workspace, where every
 * action still goes through its own approval. Nothing here starts, resumes or cancels anything.
 */
export function ProjectTaskList({tasks,projectId,selectedId,onSelect,limit=20}:{
  tasks:TaskLike[]; projectId:string; selectedId:string; onSelect:(id:string)=>void; limit?:number;
}){
  const [older,setOlder]=useState(0);
  if(!projectId) return null;
  const shown=limit+older;
  const rows = orderedTaskRows(projectTaskRows(tasks,projectId,shown));
  const hidden = taskHistoryHidden(tasks,projectId,shown);
  return <section className="project-tasks">
    <h3>Project tasks<span className="pill">{rows.length}{hidden>0?`+${hidden}`:''}</span></h3>
    <p className="muted small">{taskBoardSummary(rows,hidden)}</p>
    {!rows.length&&<p className="muted small">No saved tasks in this project.</p>}
    {rows.length>0&&<ul className="task-list">{rows.map(row=><li key={row.id}>
      <button className={row.id===selectedId?'chosen':''} aria-pressed={row.id===selectedId} onClick={()=>onSelect(row.id)}>
        <span className="task-title">{shortPrompt(row.prompt)}</span>
        <span className={`pill ${row.phase}`}>{row.label}</span>
        <span className="task-time">{taskTime(row.updated_at)}</span>
      </button>
      {row.attention&&<p className="muted small">{row.detail}</p>}
    </li>)}</ul>}
    {hidden>0&&<button onClick={()=>setOlder(count=>count+limit)}>Show older tasks</button>}
  </section>;
}
