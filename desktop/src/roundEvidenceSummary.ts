/** What one executed round actually proved, in the words the panel can show.
 *
 * The backend records the evidence (`test_command`, `test_exit_code`, `tests_ran`,
 * `failed_tests`, `changed_files`, `errors`). The panel used to print that object as raw JSON, so a
 * round that ran no test looked like a round that passed. This module keeps the distinction:
 * a round without a passing test command is never shown as a pass.
 */
export type TestResult = {
  test_command?:string|null; test_exit_code?:number|null; tests_ran?:boolean;
  changed_files?:string[]; failed_tests?:string[]; errors?:string[]; test_output?:string; ok?:boolean;
};
export type RoundEvidence = {
  tone:'pass'|'fail'|'none';
  tests:string;
  failed:string[];
  changed:string[];
  errors:string[];
  output:string;
};

function label(command:string|null|undefined):string {
  const text=(command||'').trim();
  return text ? `\`${text}\`` : 'an unnamed test command';
}

export function roundEvidence(result:TestResult|null|undefined):RoundEvidence {
  const empty=roundEvidenceShape();
  if(!result) return {...empty, tests:'No test evidence was recorded for this round.'};
  const failed=(result.failed_tests||[]).filter(Boolean);
  const changed=(result.changed_files||[]).filter(Boolean);
  const errors=(result.errors||[]).filter(Boolean);
  const output=result.test_output||'';
  if(!result.tests_ran) {
    return {tone:'none', tests:'No test command ran in this round, so it cannot be counted as passing.',
      failed, changed, errors, output};
  }
  if(result.test_exit_code===0 && failed.length===0) {
    return {tone:'pass', tests:`Tests passed: ${label(result.test_command)} exited 0.`, failed, changed, errors, output};
  }
  const exit=result.test_exit_code===null||result.test_exit_code===undefined
    ? 'reported no exit code' : `exited ${result.test_exit_code}`;
  return {tone:'fail', tests:`Tests failed: ${label(result.test_command)} ${exit}.`, failed, changed, errors, output};
}

function roundEvidenceShape():RoundEvidence {
  return {tone:'none', tests:'', failed:[], changed:[], errors:[], output:''};
}
