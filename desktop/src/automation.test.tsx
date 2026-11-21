import {describe,it,expect} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import {readFileSync} from 'node:fs';
import {AutomationReview,MacAutomation} from './MacAutomation';

describe('scoped Mac automation',()=>{
  it('has no pre-authorized scope and keeps stop reachable',()=>{
    const html=renderToStaticMarkup(<MacAutomation close={()=>{}}/>);
    expect(html).toContain('Stop automation');expect(html).toContain('not granted');
    expect(html).not.toContain('Approve and run these steps');
    expect(html).toContain('Existing tabs are not used');
  });
  it('shows literal steps and a specific result instead of treating a proposal as completion',()=>{
    const plan={plan_id:'synthetic',observation_digest:'hash',effect:'Focus selected window',proposal:{summary:'Synthetic preview',steps:[{operation:'set_text',target:'field',text:'<script>untrusted</script>'}],expected:{target:'result',attribute:'value',equals:'Preview: hello'}}};
    const snapshot={scopeID:'scope',window:'Fixture',controls:[{id:'field',role:'AXTextField',label:'Message',value:'',enabled:true,editable:true,pressable:false,sensitive:false},{id:'result',role:'AXStaticText',label:'Result',value:'Ready',enabled:true,editable:false,pressable:false,sensitive:false}],truncated:false,browser:false,digest:'hash'};
    const html=renderToStaticMarkup(<AutomationReview plan={plan} snapshot={snapshot} busy={false} approve={()=>{throw new Error('must not act during render');}}/>);
    expect(html).toContain('&lt;script&gt;');expect(html).not.toContain('<script>');
    expect(html).toContain('Preview: hello');expect(html).toContain('Approve and run these steps');
    expect(html).toContain('used once');
  });
  it('keeps native/helper argument contracts aligned',()=>{
    const rust=readFileSync(new URL('../src-tauri/src/automation.rs',import.meta.url),'utf8');
    const swift=readFileSync(new URL('../automation/Sources/Main.swift',import.meta.url),'utf8');
    const ui=readFileSync(new URL('./MacAutomation.tsx',import.meta.url),'utf8');
    expect(rust).toContain('confirmed: bool');expect(ui).toContain('confirmed:modelConsent');
    expect(swift).toContain('request["window_index"]');expect(ui).toContain('window_index:windowIndex');
    expect(rust).toContain('if result.is_err() { guard.take();');
  });
});
