import { describe, expect, it } from 'vitest';
import { readinessEmptyText, readinessRows, serverLabel } from './readiness';
import type { Readiness } from './readiness';

const report: Readiness = {
  path:'/tmp/fixture', executed:false, inspected:['package.json'],
  summary:'node: dependencies are missing — run `npm ci` first.',
  advisories:['This report is read-only: nothing was installed, started or downloaded.'],
  ecosystems:[{
    kind:'node', manifest:'package.json', lockfile:'package-lock.json', dependencies:'missing',
    evidence:'no node_modules directory', install_steps:[{manager:'npm',command:'npm ci'}],
    dev_servers:[{script:'dev',declared:'vite',command:'npm run dev',port:null}], notes:[],
  }],
};

describe('readiness display', () => {
  it('names the missing state and offers the exact install command', () => {
    const [row]=readinessRows(report);
    expect(row.label).toBe('Dependencies missing');
    expect(row.commands).toEqual(['npm ci']);
    expect(row.state).toBe('missing');
  });

  it('never presents an unverified dependency state as ready', () => {
    const [row]=readinessRows({...report,ecosystems:[{...report.ecosystems[0],dependencies:'unknown'}]});
    expect(row.label).toBe('Dependency state unverified');
  });

  it('says a port is undeclared instead of inventing one', () => {
    expect(serverLabel(report.ecosystems[0].dev_servers[0])).toContain('port not declared');
    expect(serverLabel({...report.ecosystems[0].dev_servers[0],port:5173})).toContain('port 5173');
  });

  it('uses the backend summary when nothing was detected, and nothing before a report', () => {
    expect(readinessEmptyText({...report,ecosystems:[],summary:'No recognised project manifest was found.'}))
      .toBe('No recognised project manifest was found.');
    expect(readinessEmptyText(null)).toContain('Reading');
    expect(readinessRows(null)).toEqual([]);
  });
});
