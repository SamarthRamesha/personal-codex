# Next-session continuation prompt

You are taking over an existing software project from another AI coding agent. You have no access to previous conversation, account, chat history, or hidden context. Your authoritative sources are this repository, its Git state, its documentation, and this prompt.

Project objective: build Personal Codex, a secure local-first autonomous coding environment for a Mac interactive client and an eventual ZimaOS private worker. Current source is `/Users/macbramesha/Documents/Codex/2026-11-01/files-pasted-by-the-user-personal/outputs/personal-codex`.

First inspect the repository and verify this prompt against actual files. Do not restart or recreate completed features. Resolve discrepancies in favour of the actual repository. Preserve security requirements and update checkpoints continuously.

Current architecture: Python 3.13 standard-library loopback service (`app/server.py`), SQLite at `data/personal_codex.db`, and static browser dashboard under `web/`. Implemented: local repository registration, bounded non-secret repository summaries, persisted tasks/events/approvals/provider metadata, and four-stage plans. Provider secrets are not stored—only environment variable references. Tasks do not execute commands. Tests: `python3 -m unittest discover -s tests -v` (4 passed on 2026-11-01) and `python3 -m py_compile app/server.py` (passed). Launch: `python3 app/server.py`; this sandbox blocked listener binding with `PermissionError`, so verify launch on the owner's Mac.

Mac findings: Apple Silicon Darwin 25.6.0, Python 3.13.9, Node 24.22.1, Git 2.50.1, SQLite and SSH available; Cargo and Docker not on PATH; ~76 GiB free workspace storage. ZimaOS is uninspected: no endpoint or credentials were supplied. Do not deploy or probe it without authorized access.

Git branch is `main`; inspect `git status` for exact current state. No dependencies were installed. Highest-priority next task: implement a capability-gated command runner using task-owned Git worktrees, strict authorized root, command allowlist, timeout/resource limits, output redaction, and approval lookup; cover it with tests. Then implement agent-provider adapter(s) and real task execution. Do not allow public network binding, remote pushes, cloud context transmission, destructive actions, or secrets access without explicit approval.

Continue recursively: maintain PROJECT_STATUS.md, ARCHITECTURE.md, TASKS.md, HANDOFF.md, NEXT_SESSION_PROMPT.md, CHANGELOG.md, DEVELOPMENT_LOG.md, SECURITY.md, and DEPLOYMENT.md. If near model/account limits, stop starting large work, verify files and Git state, update those documents, regenerate this prompt from actual state, and include it directly in your final response.
