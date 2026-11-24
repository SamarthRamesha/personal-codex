import {describe,expect,it} from 'vitest';
import {contextSummary} from './chatContext';
import type {ChatContextReport} from './chatContext';

const report:ChatContextReport={
  conversation_id:'c1',executed:false,
  history:{stored:6,prompt_input:4,excluded:2,prompt_chars:1200,limits:{messages:20,chars:24000}},
  project:{id:'p1',name:'Fixture'},
  memory:{stored:5,included:3,included_bytes:900,limits:{entries:6,bytes:1200}},
  attachments:{stored:2,included:1,names:['spec.md'],limits:{entries:4,bytes:2200}},
  documents:{indexed_sources:1,search_available:true,limits:{reference_bytes:1600}},
  notes:['Only complete turns are prompt input; a stopped or failed partial answer is display-only.'],
};

describe('chat context summary',()=>{
  it('reports the prompt bound and what was excluded',()=>{
    const summary=contextSummary(report);
    expect(summary.headline).toBe('4 of 6 stored messages in the next prompt · 1,200 of 24,000 characters');
    expect(summary.items.find(item=>item.key==='excluded')?.label).toContain('2 turns excluded');
  });

  it('shows included against stored for memory and attachments without claiming use',()=>{
    const summary=contextSummary(report);
    expect(summary.items.find(item=>item.key==='memory')?.label).toContain('3 of 5 stored memory entries');
    expect(summary.items.find(item=>item.key==='attachments')?.label).toContain('spec.md');
    expect(summary.headline.toLowerCase()).not.toContain('used');
  });

  it('says a conversation has no project, and handles a missing report',()=>{
    const summary=contextSummary({...report,project:null,memory:null,attachments:null,documents:null});
    expect(summary.items.find(item=>item.key==='project')?.label).toContain('No project selected');
    expect(contextSummary(null).headline).toContain('No context report');
  });

  it('flags an unavailable document search instead of hiding it',()=>{
    const summary=contextSummary({...report,documents:{...report.documents!,search_available:false}});
    expect(summary.items.find(item=>item.key==='documents')?.label).toContain('unavailable');
  });
});
