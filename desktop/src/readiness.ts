/** One project's declared environment, rendered for review.
 *
 * The backend report is read-only: it never installs, starts or downloads anything. This module
 * only decides how that report reads, so the panel cannot present "unknown" as "ready" or an
 * unrun install command as done.
 */
export type InstallStep = {manager:string;command:string};
export type ReadinessServer = {script:string;declared:string;command:string;port:number|null};
export type ReadinessEcosystem = {
  kind:string; manifest:string|null; lockfile:string|null;
  dependencies:'installed'|'missing'|'unknown';
  evidence:string; install_steps:InstallStep[]; dev_servers:ReadinessServer[];
  notes:string[]; manifest_problem?:string;
};
export type Readiness = {
  path:string; executed:boolean; summary:string;
  ecosystems:ReadinessEcosystem[]; advisories:string[]; inspected:string[];
};

export type ReadinessRow = {
  key:string; kind:string; state:ReadinessEcosystem['dependencies'];
  label:string; detail:string; commands:string[]; devServers:ReadinessServer[];
  notes:string[];
};

const LABELS:Record<ReadinessEcosystem['dependencies'],string> = {
  missing:'Dependencies missing',
  installed:'Dependencies installed',
  unknown:'Dependency state unverified',
};

export function readinessRows(report:Readiness|null|undefined):ReadinessRow[] {
  return (report?.ecosystems||[]).map(entry=>({
    key:entry.kind,
    kind:entry.kind,
    state:entry.dependencies,
    label:LABELS[entry.dependencies]||LABELS.unknown,
    detail:entry.evidence,
    commands:entry.install_steps.map(step=>step.command),
    devServers:entry.dev_servers,
    notes:entry.notes,
  }));
}

/** A dev server is only described as bound to a port when its own script declared one. */
export function serverLabel(server:ReadinessServer): string {
  const base = `${server.command} · declared as “${server.declared}”`;
  return server.port === null ? `${base} · port not declared` : `${base} · port ${server.port}`;
}

export function readinessEmptyText(report:Readiness|null|undefined): string {
  if (!report) return 'Reading this project’s declared environment…';
  if (!report.ecosystems.length) return report.summary;
  return '';
}
