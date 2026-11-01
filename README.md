# Personal Codex

Private, local-first development control plane for autonomous coding work. This first vertical slice is intentionally dependency-free: a Python standard-library service, SQLite task ledger, and browser UI.

## Run

```sh
cd /Users/macbramesha/Documents/Codex/2026-11-01/files-pasted-by-the-user-personal/outputs/personal-codex
python3 app/server.py
# then open http://127.0.0.1:8787
```

The service binds loopback only unless `PERSONAL_CODEX_HOST` is deliberately changed. Do not expose it to a LAN or the public internet without adding mutual authentication and TLS.

## Verify

```sh
python3 -m unittest discover -s tests -v
python3 -m py_compile app/server.py
```

To run the full disposable HTTP lifecycle test in an environment that permits loopback listeners:

```sh
PERSONAL_CODEX_HTTP_TESTS=1 python3 -m unittest discover -s tests -v
```

## Current capabilities

- Register an existing local repository by path.
- Locally inspect a bounded, non-secret file inventory and generate a Planner → Developer → Testing → Reviewer task plan.
- Persist projects, plans, agent events, approvals, and provider metadata to local SQLite.
- Record provider settings without accepting or storing secret values; `secret_ref` is an environment-variable name only.
- Keep execution and external operations represented as approvals rather than silently running them.

This is a working foundation, not yet the complete desktop/distributed product. See `PROJECT_STATUS.md` and `TASKS.md`.
