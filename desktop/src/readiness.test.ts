import { describe, expect, it } from 'vitest';
import { checkCommands, checkNote, readinessEmptyText, readinessRows, serverLabel, toolLine } from './readiness';
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

describe('project checks and toolchain state', () => {
  const withChecks:Readiness = {...report,ecosystems:[{...report.ecosystems[0],
    checks:[{script:'test',declared:'vitest run',command:'npm run test'},
            {script:'lint',declared:'eslint .',command:'npm run lint'}],
    tools:[{name:'node',present:true,install:'install Node.js'},
           {name:'npm',present:false,install:'install npm'}]}]};

  it('lists the declared check commands and copies them unchanged', () => {
    const [row]=readinessRows(withChecks);
    expect(checkCommands(row)).toEqual(['npm run test','npm run lint']);
    expect(row.checks[0].declared).toBe('vitest run');
  });

  it('reports a missing tool with the action that fixes it', () => {
    const [row]=readinessRows(withChecks);
    expect(toolLine(row.tools)).toContain('on PATH: node');
    expect(toolLine(row.tools)).toContain('missing: npm (install npm)');
    expect(toolLine([])).toBe('');
  });

  it('never leaves an undeclared check looking like a pass', () => {
    const [row]=readinessRows(report);
    expect(row.checks).toEqual([]);
    expect(row.tools).toEqual([]);
    expect(checkNote(row)).toContain('No check command is declared');
    const [broken]=readinessRows({...report,ecosystems:[{...report.ecosystems[0],manifest_problem:'invalid JSON'}]});
    expect(checkNote(broken)).toContain('invalid JSON');
    expect(checkNote(readinessRows(withChecks)[0])).toBe('');
  });
});
