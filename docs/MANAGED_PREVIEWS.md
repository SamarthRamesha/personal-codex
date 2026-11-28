# Managed development previews

An authenticated offline Mac task can review a declared package.json script of the form `node relative-entry.js` (also .mjs/.cjs). Choose dev/start/serve/preview and a port ≥1024. Review the exact command, entry/manifest hashes, task directory, loopback address, read/write/network scope and 15-minute lifetime. Confirm once within ten minutes. A changed file/directory, used approval, occupied port or existing owned preview refuses the start.

The application binds one IPv4 loopback socket and passes it to the confined Node process. A trusted preload directs the server's listen call to that socket. New IP binds and outbound connections stay denied; the process can read the selected worktree and write only private scratch/logs. A specific inbound exception permits requests on the owned listener, with explicit new-bind denial retained. Initial testing found that a localhost bind exception could allow wildcard binding; that implementation was rejected before publication. Actual tests cover wildcard requests staying on loopback, raw child bind/connect denial, project-write denial and HTTP readiness.

Readiness requires the actual owned process-group listener and a successful HTTP response. The UI exposes status, actual process id, bounded logs, address copy and a deliberate browser-open action. Native opening rechecks the selected current local backend, exact running preview id and root loopback URL. Opening is owner-initiated and may focus the default browser; it is not autonomous browser control. Use a separate browser window when working elsewhere.

Stop addresses only the live owned process/supervisor. The supervisor also observes backend death and stops its child group. On restart, starting/running rows become interrupted; no stored PID is killed and no process auto-restarts. Stop after expiry/failure by reviewing a new proposal. Logs/staging remain private and retained. This is a trusted-local development boundary, not accepted hostile-project or production server isolation.

Limits: one owned preview per task, Node entry points only, 15 minutes, 512 MiB Node heap setting and bounded logs. General npm/Vite/framework adapters, hot-reload/cache write scopes, multiple cooperating services, WebSocket acceptance and production deployment remain unfinished. JARVIS profiles reject this feature.

Run the synthetic lifecycle checks on the Mac:

```sh
PERSONAL_CODEX_HTTP_TESTS=1 python3 -m unittest tests.test_dependencies tests.test_previews -v
```

For an explicit real-model web implementation from supplied manifest/independent-test baseline, followed by registry installation and independent preview checks:

```sh
python3 scripts/web_project_acceptance.py --live --registry --output /absolute/new/disposable-web-profile
```

This downloads public is-number@7.0.0 metadata/tarball and invokes an already installed supported model. It neither uses personal projects nor accesses JARVIS. Earlier calculator acceptance is a separate, narrower fixture.
