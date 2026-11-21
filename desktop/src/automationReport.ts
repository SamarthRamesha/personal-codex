export type SelfCheckEntry = {name?: unknown; passed?: unknown; detail?: unknown};

export type SelfCheckSummary = {
  status: string;
  total: number;
  passed: number;
  failed: number;
  failures: {name: string; detail?: string}[];
  headline: string;
  stage?: string;
  error?: string;
};

/**
 * The native self-check prints a JSON report of synthetic checks. Reading that raw JSON to find
 * the one failed check is error-prone during acceptance, so the panel names the failure directly.
 *
 * Only check names, pass flags, the stage and the error are used: the report carries no typed
 * values or window content, and this deliberately does not invent any.
 */
export function summarizeSelfCheck(report: unknown): SelfCheckSummary {
  if (!report || typeof report !== 'object' || Array.isArray(report)) {
    return {status: 'unreadable', total: 0, passed: 0, failed: 0, failures: [],
      headline: 'The native check returned no readable report. Nothing is verified by this result.'};
  }
  const source = report as Record<string, unknown>;
  const status = typeof source.status === 'string' ? source.status : 'unknown';
  const stage = typeof source.stage === 'string' ? source.stage : undefined;
  const error = typeof source.error === 'string' ? source.error : undefined;
  const entries = Array.isArray(source.checks) ? source.checks as SelfCheckEntry[] : [];
  const named = entries.filter(entry => entry && typeof entry === 'object' && typeof entry.name === 'string');
  const failures = named.filter(entry => entry.passed !== true)
    .map(entry => ({name: entry.name as string, ...(typeof entry.detail === 'string' ? {detail: entry.detail} : {})}));
  const passed = named.length - failures.length;
  const total = named.length;
  let headline: string;
  if (status === 'permission_required') {
    headline = 'macOS has not granted Accessibility to the automation helper, so no check ran.';
  } else if (status === 'failed') {
    headline = `The check stopped${stage ? ` at ${stage}` : ''} before finishing${error ? `: ${error}` : '.'}`;
  } else if (failures.length > 0) {
    headline = `${failures.length} of ${total} checks need review: ${failures.map(failure => failure.name).join(', ')}.`;
  } else if (total === 0) {
    headline = status === 'passed'
      ? 'The report says passed but lists no checks, so nothing here is verified.'
      : 'The native check returned no individual results.';
  } else {
    headline = `All ${total} checks passed.`;
  }
  return {status, total, passed, failed: failures.length, failures, headline,
    ...(stage ? {stage} : {}), ...(error ? {error} : {})};
}
