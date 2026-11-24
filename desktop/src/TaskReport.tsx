import { summarizeReport } from './taskReportSummary';
import type { TaskReport } from './taskReportSummary';

export function TaskReportPanel({report}:{report:TaskReport}){
  const summary=summarizeReport(report);
  return <section className="task-report">
    <h3>Objective report<span className="pill">{report.status}</span></h3>
    <p className="muted small">{summary.headline}</p>
    {summary.remaining&&<p className="muted small">{summary.remaining}</p>}
    {summary.exhausted&&<p className="message-error">{summary.exhausted}</p>}
    {summary.rows.map(row=><p className={`report-test ${row.tone}`} key={row.key}>{row.label}</p>)}
    {summary.changed.length>0&&<p className="muted small">Changed: {summary.changed.join(', ')}</p>}
    {report.diff_summary&&<details><summary>Diff stat</summary><pre>{report.diff_summary}</pre></details>}
  </section>;
}
