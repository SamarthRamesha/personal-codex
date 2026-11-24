/** The task's objective report, in the terms the panel can show without embellishment.
 *
 * The backend builds this from recorded rounds, never from model prose. The panel did not show it
 * at all, so the only visible completion claim was the model's own summary. This module keeps the
 * report factual: how many rounds executed, which test commands passed or failed, what files
 * changed and how much of the task's budget is left. It never upgrades a task to "complete".
 */
export type ReportTest = {round:number; command?:string|null; exit_code?:number|null; failed?:string[]};
export type ReportLimits = {max_rounds:number; rounds_used:number; next_round:number; remaining:number;
  max_task_seconds:number; elapsed_seconds:number};
export type ReportBudget = {limits:Record<string,number>; used:Record<string,number>;
  remaining:Record<string,number>; exhausted?:string|null};
export type TaskReport = {task_id:string; status:string; rounds:number; summary?:string|null;
  changed_files?:string[]; tests?:ReportTest[]; diff_summary?:string; limits?:ReportLimits;
  budget?:ReportBudget};

export type ReportRow = {key:string; label:string; tone:'pass'|'fail'|'none'};
export type ReportSummary = {
  headline:string; rounds:string; rows:ReportRow[]; changed:string[];
  remaining:string; exhausted:string;
};

function count(n:number, word:string):string {
  return `${n} ${word}${n===1?'':'s'}`;
}

export function summarizeReport(report:TaskReport|null|undefined):ReportSummary {
  if(!report) return {headline:'No report has been recorded yet.', rounds:'', rows:[], changed:[],
    remaining:'', exhausted:''};
  const tests=report.tests||[];
  const passing=tests.filter(test=>test.exit_code===0);
  const failing=tests.filter(test=>test.exit_code!==0);
  const rows=tests.map((test,index)=>({
    key:`${test.round}-${index}`,
    label:`Round ${test.round} · ${test.command||'unnamed command'} · ${test.exit_code===0?'exit 0':test.exit_code==null?'exit not reported':`exit ${test.exit_code}`}`,
    tone:(test.exit_code===0?'pass':'fail') as 'pass'|'fail',
  }));
  const headline=report.rounds===0
    ? 'No executed round has been recorded, so this task has no verified result.'
    : `${count(report.rounds,'executed round')} · ${count(passing.length,'passing test run')} · ${count(failing.length,'failing test run')} · ${count((report.changed_files||[]).length,'changed file')}`;
  const limits=report.limits;
  const rounds=limits?`Round ${limits.next_round} next · ${limits.remaining} of ${limits.max_rounds} remaining`:'';
  const remaining=rounds;
  const exhausted=report.budget?.exhausted?`Budget exhausted: ${report.budget.exhausted}.`:'';
  return {headline, rounds, rows, changed:report.changed_files||[], remaining, exhausted};
}
