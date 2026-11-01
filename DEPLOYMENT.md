# Deployment

## Mac local development

Run `python3 app/server.py` from the repository root. The database will be created at `data/personal_codex.db`, which is ignored by Git.

The current execution environment disallows listener binding, so deployment was not launched here. On the owner's Mac, verify with `curl http://127.0.0.1:8787/api/health` and open the URL in a browser.

## ZimaOS

Do not deploy anything to ZimaOS yet. First collect an authorized, read-only inventory (OS, Docker availability, storage, services, open ports, and CPU/RAM) and choose a non-conflicting port. The eventual worker must be private-network only, authenticated, encrypted, and separately backed up.
