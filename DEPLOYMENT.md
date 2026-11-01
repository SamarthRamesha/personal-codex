# Deployment

## Mac local development

Run `python3 app/server.py` from the repository root. The database will be created at `data/personal_codex.db`, which is ignored by Git.

The service passed an approved loopback smoke test: `/api/health` returned its expected JSON response and the dashboard was served. On the owner's Mac, run `curl http://127.0.0.1:8787/api/health` and open the URL in a browser.

The dashboard supports a release → preview → critical-approved merge → separately critical-approved recovery-branch deletion flow. Resolve conflicts manually in a dedicated workspace; the service only reports them and will not leave the main worktree in a conflicted merge state.

Provider registration is safe to use during local setup because it validates metadata only. It does not probe an Ollama instance, contact a cloud endpoint, or retrieve an environment-variable secret. Provider invocation remains unimplemented.

## ZimaOS

Do not deploy anything to ZimaOS yet. First collect an authorized, read-only inventory (OS, Docker availability, storage, services, open ports, and CPU/RAM) and choose a non-conflicting port. The eventual worker must be private-network only, authenticated, encrypted, and separately backed up.
