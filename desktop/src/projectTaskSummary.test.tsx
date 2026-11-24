import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import {
  canCancelTask, needsOwnerAttention, orderedTaskRows, projectTaskRows, shortPrompt, taskBoardSummary, taskCounts, taskDetail,
  taskHistoryHidden, taskLabel, taskPhase, taskTime,
} from './projectTaskSummary';
import { ProjectTaskList } from './ProjectTaskList';
import type { TaskLike } from './projectTaskSummary';

const tasks:TaskLike[] = [
  {id:'a',project_id:'p1',prompt:'Add the parser',status:'needs-another-round',updated_at:300},
  {id:'b',project_id:'p1',prompt:'Fix the build',status:'running',updated_at:200},
  {id:'c',project_id:'p1',prompt:'Deliver the report',status:'completed',updated_at:100},
  {id:'d',project_id:'p2',prompt:'Other project',status:'planned',updated_at:400},
];

describe('project task summary',()=>{
  it('groups the statuses the backend records without upgrading any of them',()=>{
    expect(taskPhase('running')).toBe('running');
    expect(taskPhase('iterating')).toBe('running');
    expect(taskPhase('interrupted')).toBe('needs-action');
    expect(taskPhase('needs-another-round')).toBe('needs-action');
    expect(taskPhase('ready-to-complete')).toBe('needs-action');
    expect(taskPhase('budget-exhausted')).toBe('needs-action');
    expect(taskPhase('completed')).toBe('complete');
    expect(taskPhase('cancelled')).toBe('closed');
    expect(taskPhase('failed')).toBe('failed');
  });

  it('says which statuses need the owner before work can continue',()=>{
    expect(needsOwnerAttention('interrupted')).toBe(true);
    expect(needsOwnerAttention('needs-another-round')).toBe(true);
    expect(needsOwnerAttention('failed')).toBe(true);
    expect(needsOwnerAttention('running')).toBe(false);
    expect(needsOwnerAttention('completed')).toBe(false);
    expect(needsOwnerAttention('quarantined')).toBe(false);
  });

  it('offers cancellation only while a task can still be stopped',()=>{
    expect(canCancelTask('planned')).toBe(true);
    expect(canCancelTask('running')).toBe(true);
    expect(canCancelTask('needs-another-round')).toBe(true);
    expect(canCancelTask('interrupted')).toBe(true);
    expect(canCancelTask('completed')).toBe(false);
    expect(canCancelTask('complete')).toBe(false);
    expect(canCancelTask('cancelled')).toBe(false);
  });

  it('keeps an unrecognised status visible instead of guessing a bucket',()=>{
    expect(taskPhase('quarantined')).toBe('open');
    expect(taskLabel('quarantined')).toBe('quarantined');
    expect(taskDetail('quarantined')).toContain('does not recognise');
  });

  it('lists only the selected project, newest first, and never another project',()=>{
    const rows = projectTaskRows(tasks,'p1');
    expect(rows.map(row=>row.id)).toEqual(['a','b','c']);
    expect(projectTaskRows(tasks,'p2').map(row=>row.id)).toEqual(['d']);
    expect(projectTaskRows(tasks,'')).toEqual([]);
  });

  it('bounds the list and reports how much history is hidden',()=>{
    expect(projectTaskRows(tasks,'p1',2).map(row=>row.id)).toEqual(['a','b']);
    expect(taskHistoryHidden(tasks,'p1',2)).toBe(1);
    expect(taskHistoryHidden(tasks,'p1',10)).toBe(0);
  });

  it('orders work needing the owner above finished work',()=>{
    const rows = orderedTaskRows(projectTaskRows(tasks,'p1'));
    expect(rows.map(row=>row.id)).toEqual(['a','b','c']);
    expect(rows.filter(row=>row.attention).map(row=>row.id)).toEqual(['a']);
  });

  it('summarises what needs attention before what finished',()=>{
    const rows = projectTaskRows(tasks,'p1');
    expect(taskCounts(rows)).toEqual({total:3,running:1,attention:1,done:1,failed:0});
    expect(taskBoardSummary(rows)).toBe('3 tasks · 1 running · 1 needs action · 1 delivered');
    expect(taskBoardSummary(rows,4)).toContain('newest 3 of 7');
    expect(taskBoardSummary([])).toBe('No coding tasks in this project yet.');
  });

  it('trims long prompts and tolerates a missing timestamp',()=>{
    expect(shortPrompt('  a   b  ')).toBe('a b');
    expect(shortPrompt('x'.repeat(100),10)).toHaveLength(10);
    expect(shortPrompt('x'.repeat(100),10).endsWith('…')).toBe(true);
    expect(taskTime(0)).toBe('time unknown');
    expect(taskTime(Number.NaN)).toBe('time unknown');
  });
});

describe('project task list rendering',()=>{
  it('renders only the selected project with its status text and selected state',()=>{
    const html = renderToStaticMarkup(<ProjectTaskList tasks={tasks} projectId="p1" selectedId="b" onSelect={()=>{}}/>);
    expect(html).toContain('Add the parser');
    expect(html).toContain('Fix the build');
    expect(html).toContain('Needs another round');
    expect(html).toContain('aria-pressed="true"');
    expect(html).not.toContain('Other project');
    expect(html).toContain('1 needs action');
  });

  it('offers no action control of its own',()=>{
    const html = renderToStaticMarkup(<ProjectTaskList tasks={tasks} projectId="p1" selectedId="" onSelect={()=>{}}/>);
    expect(html).not.toContain('Resume');
    expect(html).not.toContain('Cancel');
  });

  it('renders nothing before a project is chosen',()=>{
    expect(renderToStaticMarkup(<ProjectTaskList tasks={tasks} projectId="" selectedId="" onSelect={()=>{}}/>)).toBe('');
  });
});
