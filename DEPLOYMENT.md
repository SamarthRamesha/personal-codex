# Deployment

## Mac local development

Run `python3 app/server.py` from the repository root. The database will be created at `data/personal_codex.db`, which is ignored by Git.

The service passed an approved loopback smoke test: `/api/health` returned its expected JSON response and the dashboard was served. On the owner's Mac, run `curl http://127.0.0.1:8787/api/health` and open the URL in a browser.

The dashboard supports a release → preview → critical-approved merge → separately critical-approved recovery-branch deletion flow. Resolve conflicts manually in a dedicated workspace; the service only reports them and will not leave the main worktree in a conflicted merge state.

Provider registration is safe to use during local setup because it validates metadata only. It does not probe an Ollama instance, contact a cloud endpoint, or retrieve an environment-variable secret.

Provider invocation now reaches a real adapter per invocation. To probe a local install, start `ollama serve`, pull a model (for example `ollama pull qwen2.5-coder`), register the provider with endpoint `http://127.0.0.1:11434` and that model name, request the invocation approval, approve it, and invoke. The request goes to `/api/chat` and the bounded reply is stored in the ledger. No model is required for the automated tests, which use a stub loopback server.

For an OpenAI-compatible local server (llama.cpp, LM Studio, vLLM), register endpoint `http://127.0.0.1:<port>/v1` and, if the server needs a key, a `secret_ref` naming the environment variable that holds it. The key is read only at call time and is never stored. A cloud endpoint additionally requires `cloud_allowed: true` at registration and a separate `network` approval before each distinct invocation, and its `secret_ref` is mandatory.

The agent workflow adds no new deployment step: create a task, approve its workspace, request an
agent plan approval, approve it, build the plan, approve the proposal digest, then execute. The
dashboard shows the operation list and results. Releasing, previewing, merging, and deleting the
recovery branch keep their existing separate approvals.

If no transport should be available at all, set `server.PROVIDER_TRANSPORT = unavailable_provider_transport`; every invocation then fails closed with a clear message.

## ZimaOS

Do not deploy anything to ZimaOS yet. First collect an authorized, read-only inventory (OS, Docker availability, storage, services, open ports, and CPU/RAM) and choose a non-conflicting port. The eventual worker must be private-network only, authenticated, encrypted, and separately backed up.
