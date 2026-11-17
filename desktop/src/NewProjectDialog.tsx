import { useState } from 'react';
import { Folder, X } from 'lucide-react';
import { chooseProjectFolder, createSelectedProject, type Project } from './api';

export function NewProjectDialog({ initialPrompt, existing, close, created }: {
  initialPrompt: string;
  existing: boolean;
  close: () => void;
  created: (project: Project, prompt: string) => Promise<void>;
}) {
  const [name, setName] = useState('');
  const [prompt, setPrompt] = useState(initialPrompt);
  const [destination, setDestination] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function attempt(action: () => Promise<void>) {
    setBusy(true);
    setError('');
    try {
      await action();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
      setDestination('');
    } finally {
      setBusy(false);
    }
  }

  return <div className="modal-backdrop"><section className="settings-modal project-dialog" role="dialog" aria-label={existing?'Open project':'New project'}>
    <div className="modal-title"><h2>{existing?'Open an existing Git project':'New project'}</h2><button title="Close new project" disabled={busy} onClick={close}><X size={18}/></button></div>
    {!existing&&<label>Project name<input autoFocus value={name} maxLength={60} disabled={busy}
      onChange={event => { setName(event.target.value); setDestination(''); }}/></label>}
    <label>What should Personal Codex build?<textarea aria-label="Project request" value={prompt} maxLength={2400}
      disabled={busy} onChange={event => setPrompt(event.target.value)}/></label>
    <div className="button-row">
      <button disabled={busy || (!existing&&!name.trim())} onClick={() => attempt(async () => {
        setDestination(await chooseProjectFolder(existing?'':name.trim(),existing) ?? '');
      })}><Folder size={15}/>{existing?'Choose Git project in Finder':'Choose location in Finder'}</button>
    </div>
    {destination && <div className="project-destination"><p>Project destination</p><code>{destination}</code>
      <p className="muted small">{existing?'Opening this project authorizes access to this repository.':'Creating this project authorizes access to this new repository.'}</p>
      <button className="primary" disabled={busy} onClick={() => attempt(async () => {
        const project = await createSelectedProject(destination);
        await created(project, prompt.trim());
      })}>{busy?'Opening…':existing?'Authorize and open project':'Create project here'}</button></div>}
    {error && <p role="alert" className="message-error">{error}</p>}
  </section></div>;
}
