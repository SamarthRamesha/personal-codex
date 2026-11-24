import { describe, expect, it } from 'vitest';
import { activityNote, activityRows, clockLabel } from './activityFeed';
import type { ActivityEvent } from './activityFeed';

const events:ActivityEvent[] = Array.from({length:35},(_,index)=>({
  agent:index%2?'tool':'orchestrator', level:'info', message:`step ${index}`,
  created_at:1_700_000_000+index,
}));

describe('task activity trail',()=>{
  it('keeps the newest events in recorded order and counts what is hidden',()=>{
    const {rows,hidden}=activityRows(events,30);
    expect(rows).toHaveLength(30);
    expect(hidden).toBe(5);
    expect(rows[0].message).toBe('step 5');
    expect(rows[29].message).toBe('step 34');
  });

  it('shows every event when the trail is short',()=>{
    const {rows,hidden}=activityRows(events.slice(0,3),30);
    expect(rows.map(row=>row.message)).toEqual(['step 0','step 1','step 2']);
    expect(hidden).toBe(0);
  });

  it('says the time is unknown instead of inventing one',()=>{
    expect(clockLabel(undefined)).toBe('time unknown');
    expect(clockLabel(null)).toBe('time unknown');
    expect(clockLabel(0)).toBe('time unknown');
    expect(clockLabel(1_700_000_000)).toMatch(/\d/);
    const {rows}=activityRows([{agent:'planner',level:'info',message:'planned'}]);
    expect(rows[0].at).toBe('time unknown');
    expect(rows[0].time).toBeNull();
  });

  it('only mentions a limit when events were actually hidden',()=>{
    expect(activityNote(0,3)).toBe('');
    expect(activityNote(5,35)).toBe('Showing the newest 30 of 35 recorded events (limit 30).');
  });

  it('never returns more than the limit, even with a nonsense one',()=>{
    expect(activityRows(events,0).rows).toEqual([]);
    expect(activityRows(events,-4).rows).toEqual([]);
    expect(activityRows(events,2.7).rows).toHaveLength(2);
  });
});
