# Using Personal Codex without a paid AI service

Personal Codex is local-first. A normal offline launch uses only the Mac, the
Personal Codex backend on `127.0.0.1:8787`, and Ollama on `127.0.0.1:11434`.
No ChatGPT Plus subscription, Codex token, Freebuff session, hosted API key or
cloud account is needed to launch, chat, plan, edit, test, review or deliver a
coding task.

This page covers exactly that path: what runs, how to start it, how to choose a
model, how to back up and recover, and what remains limited.

## What works with no paid service

| Capability | Offline behaviour |
|---|---|
| Launch and connect | Native app plus the loopback backend and Ollama started by `scripts/offline_workstation.py` |
| Chat | Streaming answers from an installed local model; stop, regenerate, continue |
| Conversations | Persisted history, pin, rename, archive/restore, search |
| Projects | Register or open a local Git repository; project memory and documents stay in the profile |
| Coding tasks | Request → plan → exact approval → isolated worktree edit → tests → repair → review → Git delivery |
| Dependencies and previews | Reviewed locked npm installs and owned plain-Node previews, when the project declares them |
| Recovery | SQLite snapshots, backend restart recovery, explicit resume of interrupted tasks |
| Mac automation | Reviewed actions and capture/OCR through the native helper, subject to macOS permissions |

The backend starts with `PERSONAL_CODEX_INFERENCE_POLICY=offline`. In that mode
every provider record must be the local Ollama endpoint with a configured local
model, no secret reference and no cloud consent. There is no telemetry and no
automatic cloud fallback. Optional gateway/cloud adapters stay disabled unless
someone deliberately enables and registers them.

## Requirements

- macOS 14 or later on the M3.
- Python 3.11 or newer.
- Git (Xcode command line tools).
- Ollama, already installed, with at least one model in its local cache.
- A matching source checkout (the release artifact includes `Personal-Codex-source.zip`).

Personal Codex never downloads models or replaces an existing Ollama setup.

## Start it

1. Extract the `Personal-Codex-macOS-ARM64-<commit>` artifact into a new folder
   and verify `Personal-Codex-macOS.sha256` if present. Extract the inner
   `Personal-Codex-macOS.zip` there. Keep any existing permission-approved
   automation bundle where it is.
2. Check readiness before launching. Run this from the matching source checkout;
   add the same flags you intend to launch with:

   ```sh
   python3 scripts/offline_workstation.py --doctor \
     --app "/absolute/path/Personal Codex.app" \
     --data-dir "$PWD/data/release-candidate"
   ```

   The report lists each check as `OK`, `WARN` or `FAIL` with a remedy and exits
   non-zero when something blocks a launch. `--json` prints a machine-readable
   report. The doctor starts nothing and changes no permission.

3. Launch with an isolated profile:

   ```sh
   python3 scripts/offline_workstation.py \
     --data-dir "$PWD/data/release-candidate" \
     --app "/absolute/path/Personal Codex.app"
   ```

   In the app, choose **Connect backend**. The launcher owns Ollama and the
   backend and stops both when it exits. If Ollama is already running under your
   own control, add `--reuse-ollama`; Personal Codex will not start, stop or
   reconfigure it.

If ports 11434 or 8787 are busy, the launcher refuses to start rather than
attaching to an unknown process. Quit the other listener, or use
`--reuse-ollama` for an existing Ollama only.

## Choosing a model

The vetted coding models are `qwen3.5:9b` and `qwen2.5-coder:14b`. By default the
launcher uses the first of those that is installed. A different installed model
can be selected explicitly:

```sh
python3 scripts/offline_workstation.py --model llama3.2:3b ...
```

The tag must exist in `ollama list`; the launcher verifies that before starting
the backend and prints a warning when the model is not on the vetted list.
Structured coding proposals are tuned for the vetted Qwen models, so a smaller or
unrelated model may produce unusable JSON. Chat still works, and every proposal
is reviewed before anything is written. To make more than one extra model
available in the app's selector, list them in `PERSONAL_CODEX_OFFLINE_MODELS`
(comma-separated) when starting the backend. Nothing is downloaded.

## Data, backup and recovery

Everything for a profile lives in the `--data-dir` you choose (mode `0700`):

- `personal_codex.db` — conversations, tasks, approvals, memory, documents and ledger.
- `owner.token` — the local authentication token for the loopback backend.
- `projects/` — the project root offered to the app when `--project-root` is not given.
- `backups/snapshot-*.sqlite3` — verified snapshots.
- `session-*/` — the launcher's own Ollama and backend logs.

**Snapshot.** With the app connected, open **Connection & settings** and choose
**Create verified database snapshot**. Each snapshot is integrity-checked and
kept under `backups/`; up to seven are retained and none are deleted automatically.

**Back up by hand.** Quit the launcher first, then copy the whole profile folder
to a private location. The database is only consistent while the backend is
stopped.

**Restore.** Restore a snapshot to a **new** path; nothing is ever overwritten:

```sh
python3 scripts/restore_database.py data/release-candidate/backups/snapshot-*.sqlite3 \
  /path/to/new-profile/personal_codex.db
```

Review the restored copy, then start a backend against that new profile. The
encrypted `scripts/recovery_bundle.py checkpoint|restore` path covers whole
profiles up to 64 MiB; see [recovery](RECOVERY.md).

**Interrupted work.** Restart the launcher and reconnect. Conversations keep
their saved messages, and an interrupted coding task shows its last recorded
round; request a fresh round, or explicitly resume a stopped full-task run within
its original scope. Approvals are one-use and expire, so a resumed step asks
again rather than replaying authority.

## Keeping it maintainable without paid AI

The repository, backend, tests, launcher and docs need only Python, Node for the
desktop frontend build, and Git. Nothing in the build or test path calls a paid
API. To work on Personal Codex itself:

```sh
python3 -m unittest discover -s tests          # backend
cd desktop && npm test && npm run build        # frontend
```

Hosted CI is a convenience, not a dependency: the same commands run locally.

## Limits to keep in mind

- The release candidate is ad-hoc signed, not notarized.
- Interactive Mac click/type/scroll, capture/OCR and the product browser helper
  still need owner acceptance with the synthetic fixtures and approved permissions.
- Dependency installation and previews support only the documented narrow subset.
- There is no cross-device synchronization and no JARVIS requirement.
- A successful build or test run is not a claim of universal model quality.
