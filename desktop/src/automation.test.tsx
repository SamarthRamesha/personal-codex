import {describe,it,expect} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import rust from '../src-tauri/src/automation.rs?raw';
import swift from '../automation/Sources/Main.swift?raw';
import driver from '../automation/Sources/NativeDriver.swift?raw';
import fixture from '../automation/Fixtures/Fixture.swift?raw';
import acceptance from '../automation/Sources/Acceptance.swift?raw';
import browser from '../automation/Sources/Browser.swift?raw';
import ui from './MacAutomation.tsx?raw';
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
    expect(rust).toContain('confirmed: bool');expect(ui).toContain('confirmed:modelConsent');
    expect(swift).toContain('request["window_index"]');expect(ui).toContain('window_index:windowIndex');
    expect(rust).toContain('if result.is_err() { guard.take();');
    expect(ui).toContain('window_title:listed!.title');expect(ui).toContain('window_number:listed!.number');
    expect(swift).toContain('expectedNumber: request["window_number"]');expect(driver).toContain('AXWindowNumber');expect(swift).toContain('expectedTitle: request["window_title"]');
    expect(ui).toContain('windowStillMatches(listed');expect(ui).toContain('windowMismatchReason(');
  });
  it('reads scrollers through the relationships the accessibility tree exposes',()=>{
    // Overlay scrollers are hidden until scrolling, so the child walk alone can never see one.
    expect(driver).toContain('AXVerticalScrollBar');expect(driver).toContain('AXHorizontalScrollBar');
    expect(driver).toContain('if role == "AXScrollArea"');
    expect(fixture).toContain('scrollerStyle = .legacy');
    // A scroll area can expose both bars; the check must pick the vertical one deterministically.
    expect(acceptance).toContain('hasSuffix(".scrollV")');
    expect(acceptance).toContain('no editable scrollbar with a value was observed');
    // The self-check must exercise the identity guard, not only the happy path.
    expect(acceptance).toContain('window_identity_refused');expect(acceptance).toContain('expectedNumber: axInt(windows[primary], "AXWindowNumber")');
  });
  it('does not let an unrelated error prove the one-use refusal',()=>{
    // Catching every error would report one-use enforcement as proven even when execution failed for
    // an unrelated reason, so the check must name the refusal it expects.
    expect(acceptance).toContain('catch AutomationError.actionNotConfirmed { record("approval_is_one_use", true) }');
    // The stronger identity must be exercised natively, not only read in review.
    expect(acceptance).toContain('window_number_identity_refused');
  });
  it('binds a created browser window by identity, not by position alone',()=>{
    // Creating a window reorders the accessibility list, so binding the index alone could control a
    // different window than the one just created and focused.
    expect(browser).toContain('expectedTitle: observedTitle.isEmpty ? nil : observedTitle');
    expect(browser).toContain('expectedNumber: axInt(window, "AXWindowNumber")');
  });
});
