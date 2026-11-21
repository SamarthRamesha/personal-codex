import {describe,it,expect} from 'vitest';
import {summarizeSelfCheck} from './automationReport';

const check=(name:string,passed:boolean,detail?:string)=>({name,passed,...(detail?{detail}:{})});

describe('native self-check summary',()=>{
  it('reports a full pass with the number of checks that actually ran',()=>{
    const summary=summarizeSelfCheck({status:'passed',actual_ui_exercised:true,
      checks:[check('prepare_is_read_only',true),check('native_text_and_press_result',true),check('native_scrollbar_result',true)]});
    expect(summary.headline).toBe('All 3 checks passed.');
    expect(summary).toMatchObject({status:'passed',total:3,passed:3,failed:0,failures:[]});
  });
  it('names the failing check instead of leaving the reader to scan JSON',()=>{
    const summary=summarizeSelfCheck({status:'needs_review',checks:[
      check('native_text_and_press_result',true),
      check('native_scrollbar_result',false,'no editable scrollbar with a value was observed')]});
    expect(summary.headline).toContain('native_scrollbar_result');
    expect(summary.failed).toBe(1);
    expect(summary.failures[0]).toEqual({name:'native_scrollbar_result',detail:'no editable scrollbar with a value was observed'});
  });
  it('shows where a stopped check ended',()=>{
    const summary=summarizeSelfCheck({status:'failed',stage:'native_scrollbar',error:'AutomationError.targetChanged',checks:[check('prepare_is_read_only',true)]});
    expect(summary.headline).toContain('native_scrollbar');
    expect(summary.headline).toContain('AutomationError.targetChanged');
    expect(summary.stage).toBe('native_scrollbar');
  });
  it('distinguishes a missing permission from a failed check',()=>{
    const summary=summarizeSelfCheck({status:'permission_required',actual_ui_exercised:false});
    expect(summary.headline).toContain('Accessibility');
    expect(summary.total).toBe(0);
  });
  it('does not treat an empty pass as verification',()=>{
    expect(summarizeSelfCheck({status:'passed',checks:[]}).headline).toContain('no checks');
  });
  it('survives a report it cannot read',()=>{
    for(const value of [null,undefined,'blocked',42,[]]){
      const summary=summarizeSelfCheck(value);
      expect(summary.status).toBe('unreadable');
      expect(summary.headline).toContain('Nothing is verified');
    }
  });
  it('ignores any unexpected field in a check entry',()=>{
    const summary=summarizeSelfCheck({status:'needs_review',
      checks:[{name:'selected_window_isolation',passed:false,value:'SECRET-WINDOW-TEXT',detail:'windows differ'}]});
    expect(JSON.stringify(summary)).not.toContain('SECRET-WINDOW-TEXT');
    expect(summary.failures[0]).toEqual({name:'selected_window_isolation',detail:'windows differ'});
  });
});
