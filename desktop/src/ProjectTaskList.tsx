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
  if(!projectId) return null;
  const rows = orderedTaskRows(projectTaskRows(tasks,projectId,limit));
  const hidden = taskHistoryHidden(tasks,projectId,limit);
  return <section className="project-tasks">
    <h3>Project tasks<span className="pill">{rows.length}{hidden>0?`+${hidden}`:''}</span></h3>
    <p className="muted small">{taskBoardSummary(rows,hidden)}</p>
    {!rows.length&&<p className="muted small">Create a coding task from a conversation to start its review trail.</p>}
    {rows.length>0&&<ul className="task-list">{rows.map(row=><li key={row.id}>
      <button className={row.id===selectedId?'chosen':''} aria-pressed={row.id===selectedId} onClick={()=>onSelect(row.id)}>
        <span className="task-title">{shortPrompt(row.prompt)}</span>
        <span className={`pill ${row.phase}`}>{row.label}</span>
        <span className="task-time">{taskTime(row.updated_at)}</span>
      </button>
      {row.attention&&<p className="muted small">{row.detail}</p>}
    </li>)}</ul>}
  </section>;
}
