# Project environment readiness

`GET /api/projects/{id}/environment` answers one question the coding panel could not: *does this
project declare dependencies and dev commands, and are they installed yet?* It reports; it never
installs, starts or downloads anything.

## What it reads

A fixed, short list of well-known names under the registered project root:

| Ecosystem | Manifest | Lockfile used for the command | Local marker |
|---|---|---|---|
| node | `package.json` | `pnpm-lock.yaml`, `yarn.lock`, `bun.lockb`, `package-lock.json` | `node_modules/` |
| python | `requirements.txt`, `pyproject.toml` or `Pipfile` | `uv.lock`, `poetry.lock`, `Pipfile.lock` | `.venv/` or `venv/` |
| rust | `Cargo.toml` | `Cargo.lock` | none (reported as unknown) |
| go | `go.mod` | `go.sum` | none (reported as unknown) |

One bounded `package.json` (≤ 200 000 bytes) is parsed for its declared `dev`, `serve`, `start`
and `preview` scripts. Nothing else is opened: no lockfile, source file, `.env` or credential is
read, and no symlinked manifest is followed.

## What the report claims

- `dependencies` is `installed`, `missing` or `unknown`, always with the `evidence` that produced
  it. A state without a local marker is `unknown` — Rust and Go are never reported as installed.
- `install_steps` lists single commands, in order. They are never chained with shell operators,
  so each one can be handed to the approved command runner unchanged.
- `dev_servers` lists only scripts the project actually declares, with the port taken from that
  script (`--port 1420`, `PORT=3000`). No port is invented; an undeclared one is `null` and said
  so.
- `checks` lists the check scripts the project itself declares (`test`, `lint`, `typecheck`,
  `type-check`, `check`, `build` for Node; Cargo's and Go's own toolchain commands elsewhere), each
  with the exact command to copy. A project with no declared check reports an empty list and says
  so — the report never invents a test command and never treats "not declared" as "passing".
- `tools` names the executables the install and check commands need, whether each is on `PATH`
  (`shutil.which`, a lookup that starts nothing), and what to install when one is missing.
- `executed: false` and `network: false` are part of the reply, `limits.runs_no_tool` records that
  no tool was started, and `advisories` repeats the boundary for the reader.

The report is a statement about declared files, not proof that a project builds or runs. A
dependency tree can exist and still be wrong; a dev script can be declared and still fail.

## Verification

`python3 -m unittest tests.test_environment -v` — 16 tests, 14 unit and 2 HTTP-gated:

- a locked Node project reports `npm ci`, an installed tree and the declared dev port;
- a project with no lockfile reports `npm install` and an undeclared port as `null`;
- `pnpm-lock.yaml` selects pnpm; `uv.lock` selects `uv sync --frozen`;
- Python reports `python3 -m venv .venv` and the pip step as two commands;
- Rust and Go report `unknown` rather than guessing;
- an empty project, an invalid manifest, an oversized manifest and a symlinked manifest are all
  reported honestly instead of failing or being half-parsed;
- `.env` is never read and its value never appears in the reply;
- a missing project directory is refused;
- the HTTP route returns the report without creating an execution row or a `node_modules`
  directory, and an unknown project is a `404`.

## Not covered

- No dependency installation or dev-server process is started by this feature; that lifecycle is
  handled by separate [reviewed installation](DEPENDENCY_INSTALLATION.md) and [managed preview](MANAGED_PREVIEWS.md) controls for supported task worktrees. Other tools remain operator-managed.
- Only the four ecosystems above are detected. A project with another manifest reports that no
  recognised manifest was found.
- The report is a snapshot taken when it is requested; nothing watches the directory afterwards.
