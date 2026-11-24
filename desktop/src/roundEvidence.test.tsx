import {renderToStaticMarkup} from 'react-dom/server';
import {describe,expect,it} from 'vitest';
import {RoundEvidenceView} from './RoundEvidence';
import {roundEvidence} from './roundEvidence';

describe('round evidence',()=>{
  it('calls a clean exit a pass and shows what changed',()=>{
    const evidence=roundEvidence({tests_ran:true,test_command:'python3 -m unittest',test_exit_code:0,changed_files:['app/a.py']});
    expect(evidence.tone).toBe('pass');
    expect(evidence.tests).toContain('exited 0');
    const html=renderToStaticMarkup(<RoundEvidenceView result={{tests_ran:true,test_command:'python3 -m unittest',test_exit_code:0,changed_files:['app/a.py']}}/>);
    expect(html).toContain('round-evidence pass');
    expect(html).toContain('Changed: app/a.py');
  });

  it('names the failing test lines instead of dumping JSON',()=>{
    const result={tests_ran:true,test_command:'npm test',test_exit_code:1,
      failed_tests:['FAIL: test_one'],test_output:'FAIL: test_one\n'};
    const evidence=roundEvidence(result);
    expect(evidence.tone).toBe('fail');
    const html=renderToStaticMarkup(<RoundEvidenceView result={result}/>);
    expect(html).toContain('FAIL: test_one');
    expect(html).toContain('exited 1');
  });

  it('does not let a round without tests read as a pass',()=>{
    const evidence=roundEvidence({tests_ran:false,changed_files:['a.ts']});
    expect(evidence.tone).toBe('none');
    expect(evidence.tests).toContain('No test command ran');
    expect(renderToStaticMarkup(<RoundEvidenceView result={{tests_ran:false}}/>)).toContain('No test command ran');
    expect(roundEvidence(null).tone).toBe('none');
    expect(renderToStaticMarkup(<RoundEvidenceView result={null}/>)).toBe('');
  });

  it('treats an unreported exit code as unproven rather than passing',()=>{
    const evidence=roundEvidence({tests_ran:true,test_command:'make check'});
    expect(evidence.tone).toBe('fail');
    expect(evidence.tests).toContain('no exit code');
  });
});
