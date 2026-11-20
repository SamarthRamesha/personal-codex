# Contributing

## Work from evidence

Read the current README, implementation matrix and architecture before changing behavior. Keep existing API routes functional. Reproduce an actual failure or specify a meaningful acceptance case; do not weaken a test to manufacture a pass. A build or injected-provider test is not a live-model, native UI or remote-server acceptance result.

## Local checks

```sh
PERSONAL_CODEX_DATA=/absolute/path/to/a/new/disposable-directory PERSONAL_CODEX_HTTP_TESTS=1 python3 -m unittest discover -s tests -v
cd desktop
npm ci
npm test
npm run build
cargo test --locked --manifest-path src-tauri/Cargo.toml -j 2
```

Use separate empty test directories. Do not point tests at a personal profile. Native builds require macOS toolchains; optional gateway and recovery dependencies stay optional. Deterministic full-task checks are documented in the getting-started/progress guides; live-model checks require an explicitly chosen already-installed model.

## Boundaries

- Never commit credentials, tokens, private server/device inventory, model caches, personal attachments or runtime databases. The diagnostic file is not a test fixture.
- Preserve user changes, prior bundles, profiles, worktrees and Git history. Do not clean/reset or silently retry ambiguous operations.
- Keep approvals bound to exact scope/state; imports and model outputs remain untrusted.
- No silent cloud routing, unrequested model/dependency installation, host Docker authority in the API or automatic server/network changes.
- Keep local Mac actions behind native selection and one-use review. Do not add a backend route that can launch Mac apps.
- Document limitations and skipped/failed checks honestly. Run checks appropriate to the changed behavior.

## Pull requests

Explain the concrete trigger and changed behavior, validation and remaining limits. Use the template. CI uses pinned first-party actions with read-only repository permissions; no private server credentials or models are required.
