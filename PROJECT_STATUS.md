# Project status

Updated 20 November 2026. **The project is partially complete; JARVIS is not deployed.**

## Ready locally

Native chat/history/streaming, existing local models, reviewed coding tasks, isolated worktrees, repair/checks/delivery, explicit resume, memory integrity, attributed document search and bounded exact proposal-cycle detection.

## Implemented, acceptance still limited

Mac actions can request installed-app/document opening and Finder reveal through exact one-use native review. Native tests/build passed; visual opening acceptance is blocked. General cross-app automation is not implemented.

The outbound Mac inference worker and restricted backend profile are implemented and locally tested. The exact backend source passed 17 disposable-Linux container checks, not target deployment acceptance.

## Verification

| Check | Result |
|---|---|
| Local backend | 372 passed / 5 skipped / 377 discovered |
| Frontend | 14 passed, TypeScript/Vite build passed |
| Native | 7 Rust tests passed, optimized app built, strict ad-hoc signature verified |
| Current API container | 17 checks passed; clean stop/restart persistence |
| New Mac actions UI | Blocked by UI connector; no visual success claim |
| JARVIS | Dashboard TCP reachable; HTTPS443 and backend8787 refuse; remote acceptance incomplete |

See [implementation matrix](docs/IMPLEMENTATION_MATRIX.md), [remaining work](TASKS.md), [getting started](docs/GETTING_STARTED.md) and [continuation](NEXT_SESSION_PROMPT.md). Both GitHub branches were fast-forwarded to f2ea8e7. All three hosted jobs passed on that source: Linux backend (363 passed / 14 optional or platform skips), frontend and macOS native. [Verified run](https://github.com/SamarthRamesha/personal-codex/actions/runs/44749454322). The original failed readiness fixture and its test-only correction are recorded in the development log. Recheck current remote state on continuation.
