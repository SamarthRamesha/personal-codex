type Workspace = {status:string;path?:string;branch?:string};

export function TaskDelivery({workspace, disabled, act}:{
  workspace:Workspace;
  disabled:boolean;
  act:(action:string)=>void;
}) {
  if (workspace.status==='merged' || workspace.status==='complete') {
    return <section className="task-delivery"><h3>Deliver changes</h3><p>Changes merged into the project.</p></section>;
  }
  if (workspace.status==='ready') {
    return <section className="task-delivery">
      <h3>Deliver changes</h3>
      <p>Review and commit the intended files in the task worktree using Git. Then request release of the clean worktree. Your committed changes stay on <code>{workspace.branch}</code>.</p>
      <p><code>{workspace.path}</code></p>
      <div className="button-row">
        <button disabled={disabled} onClick={()=>act('workspace-release-request')}>Request worktree release</button>
        <button disabled={disabled} onClick={()=>act('workspace-release')}>Release approved worktree</button>
      </div>
    </section>;
  }
  if (workspace.status==='released') {
    return <section className="task-delivery">
      <h3>Deliver changes</h3>
      <p>Review the recovery branch and destination revision in the merge approval. The backend checks for conflicts and requires a new approval if either revision changes.</p>
      <div className="button-row">
        <button disabled={disabled} onClick={()=>act('merge-request')}>Request merge into project</button>
        <button disabled={disabled} onClick={()=>act('merge')}>Merge approved revisions</button>
      </div>
    </section>;
  }
  return null;
}
