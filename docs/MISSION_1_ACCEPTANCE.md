# Mission 1 acceptance evidence — 2026-11-07 (Asia/Kolkata)

Overall: **PARTIAL**. A real Mac client and local-model coding workflow now work. The ZimaOS half has not been deployed or measured.

| Criterion | Status | Actual evidence / limitation |
| --- | --- | --- |
| Native Mac application launches | PASS | Tauri app compiled, bundled and opened; actual native UI inspected. |
| Backend runs on ZimaOS | BLOCKED | SSH reached `<ssh-user>@<server-tailscale-ip>` but existing noninteractive login was rejected (`publickey,password`). No server changes were made. |
| Secure connection through Tailscale | PARTIAL | Mac Tailscale running; confirmed JARVIS peer online/active, hostname `<server>.<tailnet>.ts.net`, IP `<server-tailscale-ip>`. Native owner-token authentication and TLS rejection were verified on isolated loopback fixtures. Live JARVIS HTTPS and off-Wi-Fi tests remain blocked. |
| Local model responds | PARTIAL | Installed Mac Ollama models discovered; real 3B chat/streaming and Qwen 14B workflow passed. Server model suitability is unknown. |
| Conversation persists | PASS | Real provider chat saved in SQLite; reload and restart verified. |
| Coding task can be created | PASS | Synthetic chat converted to a task through the real HTTP API. |
| Agent inspects an approved project | PASS | Real Qwen model read the disposable calculator fixture in an approved Git worktree. No private repository was used. |
| Proposed changes can be reviewed | PASS | Digest/file-hash bound API review plus native operation and diff UI. Unmatched patches now explicitly appear stale. |
| Approved tests can run | PASS | Real approved patch executed, `python3 -m unittest discover -v` exited 0; original fixture repository stayed unchanged. |
| Results and task history persist | PASS | Real model declared completion; recorded evidence accepted it; task and chat survived Store restart. |
| Existing tests continue passing | PASS | HTTP-enabled: 177 discovered, 173 executed, 4 skipped. Default: 177 discovered, 143 executed, 34 skipped. No test was removed or weakened. |
| Documentation reflects implementation | PASS | Current status, deployment, security, architecture, changelog, development log, task list and regenerated handoff updated; historical material preserved. |

## Live model evidence

`python3 scripts/live_coding_check.py --model qwen2.5-coder:14b --output <new-directory>` contacts only installed Mac Ollama and creates a synthetic Git repository, database and worktree. It checks owner authentication, model discovery, persisted chat, separate workspace/provider/proposal approvals, fixture-only operation review, a current diff, the actual patch, test execution, original-source preservation, evidence-checked completion and restart persistence.

Observed Qwen result: every check passed; 110,671 ms total; 65,546 ms for the proposal invocation. The model was already installed (reported disk size 9.0 GB); no weights were downloaded. This is one tiny fixture, not a coding-quality benchmark or a server resource certification. Tokens per second, peak memory and concurrent inference performance have not been measured.

The installed `llama3.2:3b` model (2.0 GB) passed the real JSON/stream probe and produced a working patch with passing tests. It then repeated the patch instead of reporting completion. Its end-to-end result is PARTIAL. The first fixture run also rejected harmless read-only inspection steps because the harness allowlist was too narrow; the harness was corrected while retaining exact patch/command restrictions. Failed attempts were retained separately.

## Native UI evidence

Actual app checks: launch; loopback connection; persisted history; a real response reading “Native local streaming works”; stop reflected as stopped; project file preview; saved rounds and passing test output; proposal digest/diff display; verified snapshot count advancing from 0 to 1; disconnect/reconnect; authenticated fixture reporting “Owner authenticated”; missing token returning HTTP 401; self-signed TLS fixture rejected with no fallback and prior data cleared. Test backends were stopped afterward; the app was left disconnected.

Synthetic fixture review approvals were issued by a constrained diagnostic harness after checking the exact allowable fixture operations. This is not a claim that a human manually approved a ZimaOS workflow in the native app.

## Remaining acceptance work

1. Establish authorized SSH login without sending passwords or private keys into chat.
2. Run `scripts/inspect_host.sh` through SSH. It reads machine metadata, runtime availability, listeners and local model names; it never traverses `/DATA` or backup directories.
3. Measure the actual storage volume, CPU, RAM, accelerator support and existing services. Preserve at least 200 GB free and start with a 75 GB total owned-storage budget; count externally managed model storage before selecting or downloading anything.
4. Prepare a reviewed, dedicated server data directory and least-privilege execution design. Request explicit approval before installation, certificates/tailnet changes, service configuration, credentials or deployment writes.
5. Configure a trusted hostname certificate and application token without public exposure. Test identity, authentication, cancellation, connection interruption and recovery against JARVIS at home and off Wi-Fi.
6. Repeat the full native-to-JARVIS local-model workflow and record performance. Do not mark Mission 1 complete before this passes.
