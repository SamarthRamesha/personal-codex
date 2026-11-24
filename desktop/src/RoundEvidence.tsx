import { roundEvidence } from './roundEvidenceSummary';
import type { TestResult } from './roundEvidenceSummary';

/** A round's evidence: what ran, whether it passed, what changed, and the bounded output. */
export function RoundEvidenceView({result}:{result:TestResult|null|undefined}){
  if(!result) return null;
  const evidence=roundEvidence(result);
  return <div className={`round-evidence ${evidence.tone}`}>
    <p>{evidence.tests}</p>
    {evidence.failed.length>0&&<ul>{evidence.failed.map(name=><li key={name}>{name}</li>)}</ul>}
    <p className="muted small">
      {evidence.changed.length>0?`Changed: ${evidence.changed.join(', ')}`:'No file was changed in this round.'}
    </p>
    {evidence.errors.map(error=><p className="message-error" key={error}>{error}</p>)}
    {evidence.output&&<details><summary>Test output</summary><pre>{evidence.output}</pre></details>}
  </div>;
}
