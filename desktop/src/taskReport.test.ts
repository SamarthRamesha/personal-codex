import {describe,expect,it} from 'vitest';
import {summarizeReport} from './taskReport';
import type {TaskReport} from './taskReport';

const base:TaskReport={task_id:'t',status:'needs-another-round',rounds:2,changed_files:['a.py'],
  limits:{max_rounds:3,rounds_used:2,next_round:3,remaining:1,max_task_seconds:1800,elapsed_seconds:60},
  budget:{limits:{},used:{},remaining:{},exhausted:null},
  tests:[{round:1,command:'npm test',exit_code:1,failed:['FAIL: a']},{round:2,command:'npm test',exit_code:0}]};

describe('task report summary',()=>{
  it('counts passing and failing rounds separately and never claims completion',()=>{
    const summary=summarizeReport(base);
    expect(summary.headline).toContain('2 executed rounds');
    expect(summary.headline).toContain('1 passing test run');
    expect(summary.headline).toContain('1 failing test run');
    expect(summary.headline).toContain('1 changed file');
    expect(summary.headline.toLowerCase()).not.toContain('complete');
  });

  it('shows each test command with its exit code',()=>{
    const summary=summarizeReport(base);
    expect(summary.rows.map(row=>row.tone)).toEqual(['fail','pass']);
    expect(summary.rows[0].label).toContain('exit 1');
    expect(summary.rows[1].label).toContain('exit 0');
  });

  it('reports an unreported exit code as such, not as a pass',()=>{
    const summary=summarizeReport({...base,tests:[{round:1,command:'make check'}]});
    expect(summary.rows[0].tone).toBe('fail');
    expect(summary.rows[0].label).toContain('exit not reported');
  });

  it('says a task has no verified result when no round was recorded',()=>{
    expect(summarizeReport({...base,rounds:0,tests:[]}).headline).toContain('no verified result');
    expect(summarizeReport(null).headline).toContain('No report');
  });

  it('passes on the remaining round budget and an exhausted budget',()=>{
    expect(summarizeReport(base).remaining).toBe('Round 3 next · 1 of 3 remaining');
    const exhausted=summarizeReport({...base,budget:{limits:{},used:{},remaining:{},exhausted:'invocations'}});
    expect(exhausted.exhausted).toContain('invocations');
  });
});
