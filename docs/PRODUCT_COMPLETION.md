# Product completion inventory

Updated 28 November 2026 from the resumed integration worktree on the owner's ARM64 Mac. Integration CI [#128](https://github.com/SamarthRamesha/personal-codex/actions/runs/46146932344) and [#129](https://github.com/SamarthRamesha/personal-codex/actions/runs/46147661571) passed backend, frontend and native jobs. These are integration candidates; stable main has not been merged, reset or repaired by this session.

| Capability | Classification | Evidence and next gate |
|---|---|---|
| Offline launcher and release packaging | Implemented and integration-tested | Actual isolated desktop startup/authentication worked. Existing Ollama can be reused explicitly without managing its lifecycle. Hosted ARM64 artifacts include the app, checksums and matching source. Ad-hoc signing remains a distribution limit. |
| AI providers and chat | Implemented and exercised with an installed model | Actual native 9B chat, regeneration, pin, rename and archive/restore worked in a synthetic profile. Restart/search acceptance is recorded separately below. External inference remains explicit; no automatic cloud fallback. |
| History, memory and documents | Partially accepted | Persisted history/search, project memory corrections and selected-document indexing have regression coverage. Broader real desktop memory/document workflows and retrieval evaluation remain open. |
| Supervised coding and orchestration | Implemented for bounded workflows | Real 9B existing-project repair and a web calculator from supplied manifest/independent tests passed. Exact requested root paths are preserved; declared HTTP servers are excluded from finite CLI smoke. Broader complex blank-project generation and framework support remain open. |
| Reviewed dependencies | Implemented for a narrow supported subset | Actual desktop locked npm installation passed with verified TLS. Review binds exact package URLs, SHA512, file hashes and destination. npm runs offline with lifecycle scripts disabled. Existing node_modules, other managers, workspaces and native-addon setup remain unsupported. |
| Managed previews | Implemented for declared plain Node entries | Actual desktop review/start/readiness and browser page checks passed; lifecycle regressions cover stop, expiry, restart and backend-crash cleanup. One inherited loopback listener; no new IP bind/outbound/project write. General Vite/framework/hot-reload adapters remain open. |
| Native Mac controls, capture and OCR | Implemented; owner acceptance pending | Helper/Rust policy and synthetic tests pass. Candidate reports no Accessibility/key-event grants. No settings were changed. Actual selected-window click/type/scroll, capture/OCR and natural-language action acceptance still require the owner's approved grants and synthetic fixture checks. |
| Mac opening panel | Visually inspected; opening action pending | Catalogue search and exact Calculator proposal/cancel worked in the candidate. No personal application was opened by that test. Actual reviewed destination opening and Finder selection remain owner checks. |
| Browser automation helper | Owner acceptance pending | The generated page was tested in an independent background browser. This does not prove the product's own browser helper, isolation or multi-page workflows. |
| Interruption and recovery | Implemented and integration-tested | SQLite restart drills, explicit full-task resume, bounded recovery and conflict preservation are covered. Large encrypted restore, hard storage quotas and cross-device sync remain open. |
| JARVIS | Not deployed or inspected in this session | Private HTTPS profile, outbound worker and deployment/rollback design exist. Target identity/storage/isolation, family access and exact deployment approvals remain gates. |
| Production distribution | Partially implemented | ARM64 ad-hoc builds, checksums and matching source exist. Developer ID notarization, trusted updates and broader acceptance remain open. |

## Real-model evidence and its limits

[Web acceptance receipt](acceptance/2026-11-28-web.json): qwen3.5:9b completed the supplied Node baseline in 180.81 seconds. Independent test bytes stayed unchanged; reviewed public is-number@7.0.0 installation and owned preview passed. Independent HTTP checks verified the page and addition API. A separate browser check entered 2 and 3 and observed 5, then -2 and 3 and observed 1.

Earlier attempts are retained locally: first the 768-token JSON limit, then a long-lived server selected as a CLI check, then incorrect src/ relocation. Those failures drove regression fixes. Structured offline output is now bounded at 2048 tokens, length termination is reported explicitly and nonstream rounds retain JSON mode. Ordinary chat remains bounded at 768 tokens. One successful fixture is not a general coding guarantee.

## Verification and owner gates

Current full local Mac backend: **510 discovered, 505 passed, five optional/platform skips**. Frontend: **101 passed**, plus TypeScript/Vite production build. Rust: **14 passed, one optional installed-model test ignored**. Helper: **42 in-memory checks**; these are not actual cross-app acceptance. Hosted jobs additionally run scripted coding, cancellation/resume, contained npm and preview lifecycle checks.

Owner-only checks: grant or confirm permissions only for the intended candidate identity, run the native synthetic click/type/scroll and protected capture/OCR fixture, test the product's own fresh-browser helper and natural-language action review, and confirm the approved preview still behaves as expected. No permission transfer between bundles is assumed. [Owner guide](FINAL_TESTING_GUIDE.md), [Mac acceptance runbook](MAC_ACCEPTANCE_RUNBOOK.md).

## Optional server data

Each backend profile remains the authority for its own data. Offline sessions stay on the Mac; a future JARVIS profile stores sessions created there. Reconnecting selects a profile; there is no automatic cross-profile synchronization. Migration requires a verified backup, an isolated restore and Git review of conflicts while keeping the old profile available for rollback. [Deployment gates](../DEPLOYMENT.md)
